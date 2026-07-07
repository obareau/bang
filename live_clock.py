"""LiveClock — moteur MIDI temps réel pour l'app Qt6 native.

Portage direct de web.py's `_midi_srv_clock_loop()` (web.py:1749-1889) vers
un `BangSession` (bang_session.py) au lieu du dict global `_state`. Même
logique de timing/modulation, seule la source de données change.

Aucun import Qt ici — c'est un threading.Thread pur, la couche Qt (signaux,
QTimer de poll du playhead) est branchée séparément par l'app.
"""
from __future__ import annotations

import random
import threading
import time

import mido

from bang_engine import compile_dna
from bang_session import BangSession, _lfo_val
import pattern_lib as pl


class LiveClock:
    """Horloge MIDI temps réel pilotée par un BangSession.

    Avance step par step au BPM du pattern courant (session.last_p), calcule
    les triggers avec modulation density/LFO/drop/swing, envoie de vrais
    note on/off via mido avec gate duration et note-off différé — même
    algorithme que _midi_srv_clock_loop dans web.py.
    """

    def __init__(self, session: BangSession, port_name: str, drum_channel: int = 9):
        self.session = session
        self.port_name = port_name
        self.drum_channel = drum_channel  # 0-based (9 = MIDI ch10, drums GM)
        self._port: mido.ports.BaseOutput | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

        # Position courante — lecture thread-safe pour un playhead Qt
        self._step_lock = threading.Lock()
        self._current_step = 0
        self._n_steps = 1

    # ------------------------------------------------------------------
    # État exposé (poll-able depuis un QTimer, pas de signal Qt ici)
    # ------------------------------------------------------------------

    @property
    def current_step(self) -> int:
        with self._step_lock:
            return self._current_step

    @property
    def total_steps(self) -> int:
        with self._step_lock:
            return self._n_steps

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def _set_step(self, step: int, n_steps: int) -> None:
        with self._step_lock:
            self._current_step = step
            self._n_steps = n_steps

    # ------------------------------------------------------------------
    # Contrôle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running.is_set():
            return
        self._port = mido.open_output(self.port_name)
        self._running.set()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._running.is_set():
            return
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        if self._port is not None:
            self._port.close()
            self._port = None

    # ------------------------------------------------------------------
    # Boucle temps réel (mirror _midi_srv_clock_loop, web.py:1749-1889)
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        port = self._port
        assert port is not None

        step = 0
        cycle_count = 0
        dropped_voices: set[str] = set()
        markov_notes: dict[str, list[int]] = {}
        pending_off: list[tuple[float, int, int]] = []  # (time, channel, note)

        while self._running.is_set():
            p = self.session.last_p
            voices = self.session.voices

            if not p or not voices:
                time.sleep(0.05)
                continue

            bpm      = p["bpm"]
            n_steps  = p["steps"]
            step_dur = 60.0 / (bpm * 4)
            gate_dur = step_dur * 0.75
            ch_drums   = self.drum_channel
            ch_melodic = 0 if ch_drums != 0 else 1
            voice_ch_map = self.session.voice_midi_ch
            voice_sw_map = self.session.voice_swing

            self._set_step(step, n_steps)

            t0 = time.perf_counter()

            # Note-off en attente
            still = []
            for off_t, ch, n in pending_off:
                if t0 >= off_t:
                    try:
                        port.send(mido.Message('note_off', note=n, channel=ch))
                    except Exception:
                        pass
                else:
                    still.append((off_t, ch, n))
            pending_off = still

            # Régénération Markov + décision drop au début du cycle
            if step == 0:
                cycle_count += 1
                markov_notes = {}
                engine = self.session.engine
                if engine:
                    mk_idx = 0
                    for note, dna, vtype in voices:
                        if vtype == "cc":
                            continue
                        if (vtype in ("markov", "bl") or vtype.startswith("ksp")) and mk_idx < len(engine.voices):
                            ev = engine.voices[mk_idx]
                            if ev.get("type") == "markov":
                                name = pl.voice_label(note, vtype)
                                markov_notes[name] = ev["chain"].generate(n_steps)
                        mk_idx += 1

                voice_lfo_map  = self.session.voice_lfo
                voice_drop_map = self.session.voice_drop
                dropped_voices = set()
                for _n, _d, _vt in voices:
                    if _vt in ("cc", "babka"):
                        continue
                    _nm   = pl.voice_label(_n, _vt)
                    _drop = voice_drop_map.get(_nm, 1.0)
                    _lfo  = voice_lfo_map.get(_nm)
                    if _lfo and _lfo.get("target") == "drop":
                        _ph = (cycle_count * _lfo["freq"]) % 1.0
                        _lv = _lfo_val(_lfo["shape"], _ph)
                        _drop = max(0.0, min(1.0, _drop * (1 - _lfo["depth"] + _lv * _lfo["depth"])))
                    if _drop < 1.0 and random.random() > _drop:
                        dropped_voices.add(_nm)

            # Collecte des triggers de ce step
            voice_lfo_map = self.session.voice_lfo
            events: list[tuple[float, int, int, int]] = []  # (trigger_t, ch, note, vel)
            for note, dna, vtype in voices:
                if vtype in ("cc", "babka") or (note == 0 and not vtype.startswith("ksp")):
                    continue
                name = pl.voice_label(note, vtype)
                if name in dropped_voices:
                    continue
                density = self.session.voice_density.get(name, 1.0)
                _lfo = voice_lfo_map.get(name)
                if _lfo and _lfo.get("target") == "density":
                    _ph = ((step / n_steps) * _lfo["freq"]) % 1.0
                    _lv = _lfo_val(_lfo["shape"], _ph)
                    density = max(0.0, min(1.0, density * (1 - _lfo["depth"] + _lv * _lfo["depth"])))

                if not dna:
                    continue
                compiled = compile_dna(dna)
                row = compiled[step % len(compiled)]
                trig, vel, prob, ratch, jit = row

                if trig and random.random() < prob * density:
                    is_melodic = vtype in ("markov", "bl") or vtype.startswith(("ksp", "vd", "vfm", "mf"))
                    ch = voice_ch_map.get(name, ch_melodic if is_melodic else ch_drums)
                    midi_note = markov_notes.get(name, [note] * n_steps)[step] if is_melodic else note
                    sw = voice_sw_map.get(name, 0.0)
                    swing_delay = (sw * step_dur * 0.33) if (step % 2 == 1 and sw > 0) else 0.0
                    events.append((t0 + swing_delay, ch, int(midi_note) & 0x7F, int(vel) & 0x7F))

            # Envoi chronologique
            events.sort(key=lambda e: e[0])
            for trigger_t, ch, midi_note, vel in events:
                delay = trigger_t - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                try:
                    port.send(mido.Message('note_on', note=midi_note, velocity=vel, channel=ch))
                    pending_off.append((time.perf_counter() + gate_dur, ch, midi_note))
                except Exception:
                    pass

            step = (step + 1) % n_steps

            elapsed = time.perf_counter() - t0
            remaining = step_dur - elapsed
            if remaining > 0:
                time.sleep(remaining)

        # Note-off sur tout ce qui reste actif à l'arrêt
        for _, ch, n in pending_off:
            try:
                port.send(mido.Message('note_off', note=n, channel=ch))
            except Exception:
                pass


if __name__ == "__main__":
    session = BangSession()
    session.generate(mode="morph", chaos=0.3, bpm=140, steps=16)

    ports = mido.get_output_names()
    print(f"Available MIDI ports: {ports}")

    if not ports:
        print("No MIDI output port available in this environment — skipping live test.")
    else:
        clock = LiveClock(session, port_name=ports[0])
        try:
            print(f"Starting clock on '{ports[0]}' for 2s...")
            clock.start()
            time.sleep(2.0)
            print(f"Playhead at step {clock.current_step}/{clock.total_steps}")
        finally:
            clock.stop()
            print("Stopped cleanly.")

    print("\n✓ live_clock.py smoke test OK")
