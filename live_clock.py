"""LiveClock — moteur MIDI temps réel pour l'app Qt6 native.

Portage direct de web.py's `_midi_srv_clock_loop()` (web.py:1749-1889) vers
un `BangSession` (bang_session.py) au lieu du dict global `_state`. Même
logique de timing/modulation, seule la source de données change.

Aucun import Qt ici — c'est un threading.Thread pur, la couche Qt (signaux,
QTimer de poll du playhead) est branchée séparément par l'app.
"""
from __future__ import annotations

import collections
import random
import threading
import time

import mido

import babka as _babka
from bang_engine import compile_dna
from bang_session import BangSession, _lfo_val
import pattern_lib as pl

# GM percussion notes start at 35 (Acoustic Bass Drum). Notes below that
# (24 "Bass", 33 "A1") are used by several generation modes (morph/weather/
# noise/ambient) as genuine pitched bass hits with vtype="drum" — sending
# them to the drum-kit channel produces silence (no GM percussion sample
# maps that low). They need the same routing as a melodic/bass voice.
_MIN_GM_PERCUSSION_NOTE = 35

# Default MIDI channel per voice category, used only when the user hasn't
# set an explicit per-voice channel override (voice_ch_map). Spreads voices
# across distinct channels/instruments instead of piling everything melodic
# onto one channel — this is what makes the built-in preview synth (and any
# receiving multitimbral MIDI device) play drums AND bass AND leads
# together instead of one channel drowning out the rest.
_KSP_CHANNELS = {1: 2, 2: 3, 3: 4, 4: 5}  # ksp1..ksp4 -> channel 2..5


def default_channel(note: int, vtype: str, drum_channel: int) -> int:
    """Pick a default MIDI channel for a voice with no explicit override."""
    if vtype.startswith("ksp"):
        idx = int(vtype[3:])
        return _KSP_CHANNELS.get(idx, 2)
    if vtype == "vk":
        return 6
    if vtype.startswith("vfm"):
        return 7
    if vtype.startswith("mf"):
        return 8
    if vtype.startswith("vd"):
        return drum_channel
    if vtype == "bl":
        return 0
    if vtype == "markov":
        return 1
    if vtype in ("drum", "babka"):
        return drum_channel if note >= _MIN_GM_PERCUSSION_NOTE else 0
    return drum_channel


class LiveClock:
    """Horloge MIDI temps réel pilotée par un BangSession.

    Avance step par step au BPM du pattern courant (session.last_p), calcule
    les triggers avec modulation density/LFO/drop/swing, envoie de vrais
    note on/off via mido avec gate duration et note-off différé — même
    algorithme que _midi_srv_clock_loop dans web.py.
    """

    def __init__(self, session: BangSession, port_name: str | None = None,
                 drum_channel: int = 9, use_preview_synth: bool = False):
        self.session = session
        self.port_name = port_name
        self.drum_channel = drum_channel  # 0-based (9 = MIDI ch10, drums GM)
        self.use_preview_synth = use_preview_synth
        self._port = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()

        # Position courante — lecture thread-safe pour un playhead Qt
        self._step_lock = threading.Lock()
        self._current_step = 0
        self._n_steps = 1

        # État interne de la boucle (persiste entre les ticks)
        self._step = 0
        self._cycle_count = 0
        self._dropped_voices: set[str] = set()
        self._markov_notes: dict[str, list[int]] = {}
        self._pending_off: list[tuple[float, int, int]] = []  # (time, channel, note)
        # Babka voices use fractional-duration steps (subdivisions, euclidean
        # inline, cycle alternation) instead of the uniform 1-step grid the
        # rest of the engine assumes — a plain per-integer-step scan can
        # never see them, which is why they were silently skipped before.
        # Schedule is recomputed once per cycle (step==0): a flat list of
        # (step_offset: float, velocity, ratchet) per voice, walked
        # continuously across as many internal babka cycles as needed to
        # fill the pattern's n_steps (mirrors bang_engine.py's file-export
        # babka branch, in step units instead of MIDI ticks).
        self._babka_schedule: dict[str, list[tuple[float, int, int]]] = {}

        # --- Moniteur d'activité MIDI (poll-able depuis un QTimer Qt) ---
        # Ring-buffer des derniers note-on envoyés + set des notes en cours de
        # résonance, protégés par un lock dédié (jamais bloqué par le timing).
        self._activity_lock = threading.Lock()
        # (timestamp, channel, note, velocity, voice_name)
        self._recent_events: collections.deque = collections.deque(maxlen=64)
        # (channel, note) -> voice_name  (note actuellement en train de sonner)
        self._active_notes: dict[tuple[int, int], str] = {}

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

    def recent_events(self) -> list[tuple[float, int, int, int, str]]:
        """Copie thread-safe du ring-buffer des derniers note-on envoyés.

        Chaque tuple : (timestamp, channel, note, velocity, voice_name).
        Destiné à être poll-é par un QTimer côté UI.
        """
        with self._activity_lock:
            return list(self._recent_events)

    def active_notes(self) -> dict[tuple[int, int], str]:
        """Copie thread-safe des notes en cours de résonance.

        Clé = (channel, note), valeur = nom de la voix. Vidée au fur et à
        mesure que les note-off partent (fin de gate).
        """
        with self._activity_lock:
            return dict(self._active_notes)

    # ------------------------------------------------------------------
    # Contrôle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running.is_set():
            return
        if self.use_preview_synth:
            from synth_preview import FluidSynthPort
            self._port = FluidSynthPort(drum_channel=self.drum_channel)
        else:
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

        while self._running.is_set():
            # Snapshot atomique — évite de lire un last_p/voices/engine
            # dépareillés si generate()/undo()/etc. tournent au même instant
            # sur le thread UI (Generate pendant Play/Preview).
            with self.session._lock:
                p = self.session.last_p
                voices = self.session.voices
                engine = self.session.engine
                voice_ch_map = dict(self.session.voice_midi_ch)
                voice_sw_map = dict(self.session.voice_swing)
                voice_lfo_map = dict(self.session.voice_lfo)
                voice_drop_map = dict(self.session.voice_drop)
                voice_density_map = dict(self.session.voice_density)
                audible_flags = [self.session.is_voice_audible(i) for i in range(len(voices))]

            if not p or not voices:
                time.sleep(0.05)
                continue

            try:
                self._tick(port, p, voices, engine, voice_ch_map, voice_sw_map,
                           voice_lfo_map, voice_drop_map, voice_density_map, audible_flags)
            except Exception:
                # Ne jamais laisser une régénération concurrente (pattern plus
                # court, voix retirée, changement de type, etc.) tuer le
                # thread silencieusement — on resynchronise et on continue.
                self._step = 0
                time.sleep(0.05)

        # Note-off sur tout ce qui reste actif à l'arrêt
        for _, ch, n in self._pending_off:
            try:
                port.send(mido.Message('note_off', note=n, channel=ch))
            except Exception:
                pass
        self._pending_off.clear()
        with self._activity_lock:
            self._active_notes.clear()

    @staticmethod
    def _compute_babka_schedule(pattern: str, n_steps: int) -> list[tuple[float, int, int]]:
        """Walk a babka pattern continuously (re-parsing per internal cycle,
        same as bang_engine.py's file-export branch) until `n_steps` worth of
        step-units is covered. Returns (step_offset, velocity, ratchet)."""
        events: list[tuple[float, int, int]] = []
        cursor = 0.0
        cyc = 0
        while cursor < n_steps:
            bsteps = _babka.parse(pattern, cycle=cyc)
            if not bsteps:
                break
            for s in bsteps:
                if cursor >= n_steps:
                    break
                if s.trigger and random.random() < s.prob:
                    events.append((cursor, int(s.velocity), max(1, int(s.ratchet))))
                cursor += s.duration
            cyc += 1
        return events

    def _tick(self, port, p, voices, engine, voice_ch_map, voice_sw_map,
              voice_lfo_map, voice_drop_map, voice_density_map, audible_flags) -> None:
        """Un pas de la boucle temps réel. Mute self._step/_cycle_count/etc."""
        bpm     = p["bpm"]
        n_steps = p["steps"]
        # Le pattern a pu être régénéré (steps différents) pendant la
        # lecture — reclamp avant toute indexation pour éviter un
        # IndexError sur markov_notes/[note]*n_steps.
        if self._step >= n_steps:
            self._step = 0
        step = self._step

        step_dur   = 60.0 / (bpm * 4)
        gate_dur   = step_dur * 0.75
        ch_drums   = self.drum_channel

        self._set_step(step, n_steps)

        t0 = time.perf_counter()

        # Note-off en attente
        still = []
        for off_t, ch, n in self._pending_off:
            if t0 >= off_t:
                try:
                    port.send(mido.Message('note_off', note=n, channel=ch))
                except Exception:
                    pass
                with self._activity_lock:
                    self._active_notes.pop((ch, n), None)
            else:
                still.append((off_t, ch, n))
        self._pending_off = still

        # Régénération Markov + décision drop au début du cycle
        if step == 0:
            self._cycle_count += 1
            self._markov_notes = {}
            if engine:
                mk_idx = 0
                for note, dna, vtype in voices:
                    if vtype == "cc":
                        continue
                    if (vtype in ("markov", "bl") or vtype.startswith("ksp")) and mk_idx < len(engine.voices):
                        ev = engine.voices[mk_idx]
                        if ev.get("type") == "markov":
                            name = pl.voice_label(note, vtype)
                            self._markov_notes[name] = ev["chain"].generate(n_steps)
                    mk_idx += 1

            dropped_voices = set()
            for _n, _d, _vt in voices:
                if _vt in ("cc", "babka"):
                    continue
                _nm   = pl.voice_label(_n, _vt)
                _drop = voice_drop_map.get(_nm, 1.0)
                _lfo  = voice_lfo_map.get(_nm)
                if _lfo and _lfo.get("target") == "drop":
                    _ph = (self._cycle_count * _lfo["freq"]) % 1.0
                    _lv = _lfo_val(_lfo["shape"], _ph)
                    _drop = max(0.0, min(1.0, _drop * (1 - _lfo["depth"] + _lv * _lfo["depth"])))
                if _drop < 1.0 and random.random() > _drop:
                    dropped_voices.add(_nm)
            self._dropped_voices = dropped_voices

            # Babka : planning fractionnaire recalculé une fois par cycle
            # (les positions ne tombent pas sur des steps entiers, donc un
            # scan step-par-step classique ne peut jamais les voir).
            self._babka_schedule = {}
            for note, dna, vtype in voices:
                if vtype != "babka" or not dna:
                    continue
                name = pl.voice_label(note, vtype)
                self._babka_schedule[name] = self._compute_babka_schedule(dna, n_steps)

        is_melodic_type = ("markov", "bl")

        # Collecte des triggers de ce step
        events: list[tuple[float, int, int, int, str]] = []  # (trigger_t, ch, note, vel, name)
        for vidx, (note, dna, vtype) in enumerate(voices):
            if vtype == "cc" or (note == 0 and not vtype.startswith("ksp")):
                continue
            if vidx < len(audible_flags) and not audible_flags[vidx]:
                continue
            name = pl.voice_label(note, vtype)
            if name in self._dropped_voices:
                continue
            density = voice_density_map.get(name, 1.0)
            _lfo = voice_lfo_map.get(name)
            if _lfo and _lfo.get("target") == "density":
                _ph = ((step / n_steps) * _lfo["freq"]) % 1.0
                _lv = _lfo_val(_lfo["shape"], _ph)
                density = max(0.0, min(1.0, density * (1 - _lfo["depth"] + _lv * _lfo["depth"])))

            ch = voice_ch_map.get(name, default_channel(note, vtype, ch_drums))
            is_melodic = vtype in is_melodic_type or vtype.startswith(("ksp", "vd", "vfm", "mf"))
            sw = voice_sw_map.get(name, 0.0)
            swing_delay = (sw * step_dur * 0.33) if (step % 2 == 1 and sw > 0) else 0.0

            if vtype == "babka":
                for offset, vel, _ratchet in self._babka_schedule.get(name, []):
                    if step <= offset < step + 1 and random.random() < density:
                        sub_delay = (offset - step) * step_dur
                        events.append((t0 + sub_delay, ch, int(note) & 0x7F, int(vel) & 0x7F, name))
                continue

            if not dna:
                continue
            compiled = compile_dna(dna)
            row = compiled[step % len(compiled)]
            trig, vel, prob, ratch, jit = row

            if trig and random.random() < prob * density:
                midi_note = self._markov_notes.get(name, [note] * n_steps)[step] if is_melodic else note
                events.append((t0 + swing_delay, ch, int(midi_note) & 0x7F, int(vel) & 0x7F, name))

        # Envoi chronologique
        events.sort(key=lambda e: e[0])
        for trigger_t, ch, midi_note, vel, name in events:
            delay = trigger_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            try:
                port.send(mido.Message('note_on', note=midi_note, velocity=vel, channel=ch))
                self._pending_off.append((time.perf_counter() + gate_dur, ch, midi_note))
                # Moniteur d'activité : log l'événement + marque la note active.
                with self._activity_lock:
                    self._recent_events.append((time.time(), ch, midi_note, vel, name))
                    self._active_notes[(ch, midi_note)] = name
            except Exception:
                pass

        self._step = (step + 1) % n_steps

        elapsed = time.perf_counter() - t0
        remaining = step_dur - elapsed
        if remaining > 0:
            time.sleep(remaining)


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
