"""BangSession — état de session framework-agnostic pour l'app Qt6.

Mirror de web.py's `_state` dict (voir web.py:656-706), mais en vraie classe
avec attributs typés au lieu d'un dict global mutable. Toute la logique de
génération/transformation vient de pattern_lib.py — cette classe ne fait que
l'orchestration (undo, locks, dicts de modifiers par voix) exactement comme
le fait web.py, pour que le comportement Qt6 soit identique au webapp.

Aucun import Qt ici — cette classe est testable et utilisable en dehors de
toute UI.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field

import random

import pattern_lib as pl
from bang_engine import BangEngine, mutate_dna, _seed_to_int


@dataclass
class BangSession:
    """Note: generate()/mutation methods hold `_lock` while reassigning
    voices/last_p/engine, so LiveClock (running on its own thread) can read
    a consistent snapshot instead of racing a half-updated session while the
    user hits Generate/Vary/Undo during playback."""

    weather: dict | None = None

    # État courant
    voices: list[tuple[int, str, str]] = field(default_factory=list)
    engine: BangEngine | None = None
    last_p: dict | None = None

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
    plocks: list = field(default_factory=list)
    last_seed: str | None = None

    # Undo (ring buffer de 5, mirror _state["history"])
    history: deque = field(default_factory=lambda: deque(maxlen=5))

    # Modifiers par nom de voix (mirror _state["voice_*"])
    note_remap: dict[str, int] = field(default_factory=dict)
    voice_thin: dict[str, int] = field(default_factory=dict)
    voice_density: dict[str, float] = field(default_factory=dict)
    voice_chords: dict[str, str] = field(default_factory=dict)
    voice_steps: dict[str, int] = field(default_factory=dict)
    voice_offset: dict[str, int] = field(default_factory=dict)
    voice_drop: dict[str, float] = field(default_factory=dict)
    voice_vel_lane: dict[str, list[int]] = field(default_factory=dict)
    voice_prob_lane: dict[str, list[int]] = field(default_factory=dict)
    voice_lfo: dict[str, dict] = field(default_factory=dict)
    voice_midi_ch: dict[str, int] = field(default_factory=dict)
    voice_swing: dict[str, float] = field(default_factory=dict)

    locked_voices: set[int] = field(default_factory=set)

    # Preset tracking (mirror _state["current_preset"]/["current_ksp_preset"])
    current_preset: str = ""
    current_ksp_preset: str = ""
    max_poly: int = 0

    # Sequencer slots (mirror _state["seq_*"], web.py:685-692) — 8 slots, chacun
    # None ou un snapshot tuple (voices, plocks, last_p) comme l'undo history.
    seq_slots: list = field(default_factory=lambda: [None] * 8)
    seq_current: int = 0
    seq_cycles: int = 2
    seq_weights: list[int] = field(default_factory=lambda: [1] * 8)

    # A/B compare (mirror _state["slot_a"]/["slot_b"]) — snapshot tuple ou None.
    slot_a: tuple | None = None
    slot_b: tuple | None = None

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------

    def generate(
        self,
        mode: str = "morph",
        chaos: float = 0.30,
        bpm: int = 110,
        steps: int = 64,
        gravity: float = 0.70,
        cc_depth: float = 0.50,
        root: str = "A",
        scale: str = "penta_min",
        seed: str = "",
        swing: float = 0.0,
        vel_floor: int = 0,
        vel_ceiling: int = 127,
        vel_curve: float = 1.0,
        vel_humanize: int = 0,
        microtiming: float = 1.0,
        markov_channel: int = 9,
        temporal: bool = False,
        out: str = "bang_out.mid",
    ) -> list[tuple[int, str, str]]:
        """Génère un nouveau pattern (mirror web.py `/generate`, web.py:1960-1999)."""
        p = pl.read_form(
            mode=mode, chaos=chaos, bpm=bpm, steps=steps, gravity=gravity,
            cc_depth=cc_depth, out=out, temporal=temporal,
            vel_floor=vel_floor, vel_ceiling=vel_ceiling, vel_curve=vel_curve,
            root=root, scale=scale, seed=seed, swing=swing,
            markov_channel=markov_channel, vel_humanize=vel_humanize,
            microtiming=microtiming,
        )

        with self._lock:
            # Snapshot avant génération (pour undo) — mirror web.py:1985-1986
            if self.voices and self.last_p:
                self._push_history()

            # Fix seed: reproductibilité quand un seed est fourni (mirror web.py:980-981)
            if p.get("seed"):
                random.seed(_seed_to_int(p["seed"]))
            voices = pl.build_voices(p, weather=self.weather)
            voices = pl.apply_locks(voices, self.voices, self.locked_voices)
            voices = pl.apply_note_remap(voices, self.note_remap)
            voices = pl.apply_voice_steps(voices, self.voice_steps)

            engine = pl.assemble_engine(p, voices, weather=self.weather)
            plocks = (
                pl.generate_plocks(voices, p)
                if p["mode"] in ("volca_drum", "volca_kick", "volca_fm", "microfreak")
                else []
            )

            # Bascule atomique : last_p/voices/engine/plocks changent ensemble,
            # jamais vus à moitié mis à jour par le thread du LiveClock.
            self.last_p = p
            self.voices = voices
            self.engine = engine
            self.plocks = plocks

        return voices

    def export_midi(self, filename: str | None = None, dest_dir: str | None = None,
                     midi_type: int = 1) -> str:
        """Exporte le pattern courant en fichier MIDI (mirror web.py `/export`, web.py:2002-2093)."""
        if self.engine is None:
            if not self.last_p:
                raise RuntimeError("No pattern generated yet — call generate() first")
            self.voices = pl.apply_note_remap(pl.build_voices(self.last_p, weather=self.weather), self.note_remap)
            self.engine = pl.assemble_engine(self.last_p, self.voices, weather=self.weather)

        p = self.last_p
        assert p is not None
        from pathlib import Path
        target_dir = Path(dest_dir).expanduser() if dest_dir else Path(__file__).parent / "exports"
        target_dir.mkdir(parents=True, exist_ok=True)
        out_name = filename or p.get("out", "bang_out.mid")
        export_path = str(target_dir / out_name)

        voice_names = [pl.voice_label(n, t) for n, _d, t in self.voices]
        densities = [self.voice_density.get(name, 1.0) for name in voice_names]
        chord_types = [self.voice_chords.get(name, "mono") for name in voice_names]

        self.engine.export_midi(
            num_steps=p["steps"],
            filename=export_path,
            weather=self.weather,
            temporal_jitter=p["temporal"],
            seed=p["seed"] or None,
            swing=p["swing"],
            plocks=self.plocks or None,
            vel_humanize=p.get("vel_humanize", 0),
            densities=densities,
            voice_chords=chord_types,
            microtiming=p.get("microtiming", 1.0),
            midi_type=midi_type,
            voice_names=voice_names,
        )
        self.last_seed = self.engine.last_seed
        return export_path

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _push_history(self) -> None:
        self.history.append((list(self.voices), list(self.plocks), dict(self.last_p) if self.last_p else {}))

    def undo(self) -> bool:
        """Mirror web.py `/undo` (web.py:3351-3361). Retourne False si rien à annuler."""
        with self._lock:
            if not self.history:
                return False
            voices, plocks, last_p = self.history.pop()
            engine = pl.assemble_engine(last_p, voices, weather=self.weather)
            self.voices = voices
            self.plocks = plocks
            self.last_p = last_p
            self.engine = engine
            return True

    # ------------------------------------------------------------------
    # Locks
    # ------------------------------------------------------------------

    def set_lock(self, idx: int, locked: bool) -> None:
        if locked:
            self.locked_voices.add(idx)
        else:
            self.locked_voices.discard(idx)

    def toggle_lock(self, idx: int) -> bool:
        if idx in self.locked_voices:
            self.locked_voices.discard(idx)
            return False
        self.locked_voices.add(idx)
        return True

    # ------------------------------------------------------------------
    # Transforms par voix (mutent la DNA, re-assemblent l'engine)
    # ------------------------------------------------------------------

    def _reassemble(self) -> None:
        if self.last_p:
            self.engine = pl.assemble_engine(self.last_p, self.voices, weather=self.weather)

    def _mutate_voice(self, idx: int, transform) -> bool:
        """Applique `transform(dna) -> new_dna` sur la voix idx, avec undo + lock check."""
        with self._lock:
            if not self.voices or not (0 <= idx < len(self.voices)):
                return False
            if idx in self.locked_voices:
                return False
            note, dna, vtype = self.voices[idx]
            self._push_history()
            new_dna = transform(dna)
            voices = list(self.voices)
            voices[idx] = (note, new_dna, vtype)
            self.voices = voices
            self._reassemble()
            return True

    def invert_voice(self, idx: int) -> bool:
        return self._mutate_voice(idx, pl.voice_invert)

    def rotate_voice(self, idx: int, n: int = 1) -> bool:
        return self._mutate_voice(idx, lambda dna: pl.voice_rotate(dna, n))

    def reverse_voice(self, idx: int) -> bool:
        return self._mutate_voice(idx, pl.voice_reverse)

    def double_voice(self, idx: int) -> bool:
        return self._mutate_voice(idx, pl.voice_double)

    def halve_voice(self, idx: int) -> bool:
        return self._mutate_voice(idx, pl.voice_halve)

    def vary_voice(self, idx: int) -> bool:
        if not self.voices or not (0 <= idx < len(self.voices)):
            return False
        note, dna, vtype = self.voices[idx]
        if idx in self.locked_voices or vtype == "cc":
            return False
        return self._mutate_voice(idx, lambda d: pl.voice_vary(d, intensity=0.15))

    def euclidean_voice(self, idx: int, k: int) -> bool:
        if not self.voices or not (0 <= idx < len(self.voices)):
            return False
        note, dna, vtype = self.voices[idx]
        n = len(dna)
        if n == 0:
            return False
        return self._mutate_voice(idx, lambda d: pl.euclid_dna(n, k))

    def set_voice_pattern(self, idx: int, pattern: str) -> bool:
        """Écrase directement la DNA (mirror web.py `/voice/pattern`, web.py:3050-3064)."""
        pattern = pattern.strip()
        with self._lock:
            if not pattern or not (0 <= idx < len(self.voices)):
                return False
            note, _old, vtype = self.voices[idx]
            voices = list(self.voices)
            voices[idx] = (note, pattern, vtype)
            self.voices = voices
            self._reassemble()
            return True

    def regen_voice(self, idx: int) -> bool:
        """Régénère une seule voix (mirror web.py `/voice/regen`, web.py:2933-2955)."""
        with self._lock:
            if not self.voices or not self.last_p or not (0 <= idx < len(self.voices)):
                return False
            if idx in self.locked_voices:
                return False
            note, dna, vtype = self.voices[idx]
            self._push_history()
            fresh = pl.build_voices(self.last_p, weather=self.weather)
            if idx < len(fresh):
                _, new_dna, _ = fresh[idx]
            else:
                new_dna = mutate_dna(dna, intensity=0.9)
            voices = list(self.voices)
            voices[idx] = (note, new_dna, vtype)
            self.voices = voices
            self._reassemble()
            return True

    def vary_all(self) -> None:
        """Mutation légère de toutes les voix non verrouillées (mirror web.py `/vary`, web.py:3067-3083)."""
        with self._lock:
            if not self.voices or not self.last_p:
                return
            self._push_history()
            new_voices = []
            for idx, (note, dna, vtype) in enumerate(self.voices):
                if idx in self.locked_voices or vtype == "cc":
                    new_voices.append((note, dna, vtype))
                else:
                    new_voices.append((note, mutate_dna(dna, intensity=0.12), vtype))
            self.voices = new_voices
            self._reassemble()

    # ------------------------------------------------------------------
    # Modifiers par voix (dicts, pas de mutation DNA — appliqués à l'assemblage/rendu)
    # ------------------------------------------------------------------

    def set_voice_density(self, name: str, density: float) -> None:
        self.voice_density[name] = max(0.0, min(1.0, float(density)))

    def set_voice_chord(self, name: str, chord_type: str) -> None:
        if chord_type in pl.VALID_CHORDS:
            self.voice_chords[name] = chord_type

    def set_voice_offset(self, name: str, n: int) -> None:
        if n <= 0:
            self.voice_offset.pop(name, None)
        else:
            self.voice_offset[name] = n

    def set_voice_drop(self, name: str, pct: int) -> None:
        val = max(0, min(100, pct)) / 100.0
        if val >= 1.0:
            self.voice_drop.pop(name, None)
        else:
            self.voice_drop[name] = round(val, 2)

    def set_voice_swing(self, name: str, pct: int) -> None:
        val = max(0, min(100, int(pct)))
        if val == 0:
            self.voice_swing.pop(name, None)
        else:
            self.voice_swing[name] = round(val / 100, 2)

    def set_voice_midi_channel(self, name: str, ch: int) -> None:
        if ch < 0:
            self.voice_midi_ch.pop(name, None)
        else:
            self.voice_midi_ch[name] = max(0, min(15, ch))

    def set_voice_lfo(self, name: str, shape: str, target: str = "density",
                       freq: float = 1.0, depth: float = 0.5) -> None:
        if shape == "off":
            self.voice_lfo.pop(name, None)
        else:
            self.voice_lfo[name] = {"shape": shape, "target": target, "freq": freq, "depth": round(depth, 3)}

    def set_voice_thin(self, name: str, factor: int) -> None:
        self.voice_thin[name] = max(1, factor)

    # ------------------------------------------------------------------
    # Presets — drum machine / groove / KSP (mirror web.py preset routes)
    # ------------------------------------------------------------------

    def apply_drum_preset(self, preset_name: str) -> bool:
        """Apply a drum-machine note mapping (mirror web.py `/preset/apply`, web.py:3631).

        Looks up built-in DRUM_PRESETS first, then custom presets on disk. Sets
        note_remap, records current_preset, and reassembles the engine so the
        remap takes effect immediately. Returns False if the name is unknown.
        """
        import presets_lib as pr
        all_presets = {**pr.DRUM_PRESETS, **pr.load_custom_presets(self._presets_path())}
        if preset_name not in all_presets:
            return False
        with self._lock:
            self.note_remap = dict(all_presets[preset_name])
            self.current_preset = preset_name
            if self.last_p and self.voices:
                voices = pl.apply_note_remap(pl.build_voices(self.last_p, weather=self.weather), self.note_remap)
                voices = pl.apply_voice_steps(voices, self.voice_steps)
                self.voices = voices
                self.engine = pl.assemble_engine(self.last_p, voices, weather=self.weather)
            return True

    def apply_groove(self, groove_name: str) -> bool:
        """Overwrite the first 4 voices' DNA from a groove (mirror web.py `/groove/apply`, web.py:3115).

        Pushes undo history first, respects locked voices, skips CC voices, and
        reassembles the engine. Returns False if nothing is loaded or the groove
        name is unknown.
        """
        import presets_lib as pr
        if groove_name not in pr.GROOVE_PRESETS:
            return False
        with self._lock:
            if not self.voices or not self.last_p:
                return False
            self._push_history()
            preset = pr.GROOVE_PRESETS[groove_name]
            voices = list(self.voices)
            pi = 0
            for vi, (note, dna, vtype) in enumerate(voices):
                if vtype == "cc":
                    continue
                if vi not in self.locked_voices and pi < len(preset) and preset[pi]:
                    voices[vi] = (note, preset[pi], vtype)
                pi += 1
            self.voices = voices
            self.engine = pl.assemble_engine(self.last_p, voices, weather=self.weather)
            return True

    def apply_ksp_preset(self, preset_name: str) -> bool:
        """Apply a KSP scale preset (mirror web.py `/ksp/preset/load`, web.py:3701).

        Sets root/scale/gravity on last_p and per-track chords on voice_chords,
        records current_ksp_preset, and reassembles the engine. Looks up built-in
        presets then custom presets on disk. Returns False if the name is unknown.
        """
        import presets_lib as pr
        all_presets = {**pr.KSP_PRESETS_BUILTIN, **pr.load_ksp_presets(self._ksp_presets_path())}
        if preset_name not in all_presets:
            return False
        preset = all_presets[preset_name]
        with self._lock:
            for voice_name, chord in preset.get("chords", {}).items():
                if chord in pl.VALID_CHORDS:
                    self.voice_chords[voice_name] = chord
            if self.last_p:
                self.last_p["root"]    = preset["root"]
                self.last_p["scale"]   = preset["scale"]
                self.last_p["gravity"] = preset["gravity"]
                if self.voices:
                    self.engine = pl.assemble_engine(self.last_p, self.voices, weather=self.weather)
            self.current_ksp_preset = preset_name
            return True

    # ------------------------------------------------------------------
    # Note remap (mirror web.py `/notes`, web.py:2372)
    # ------------------------------------------------------------------

    def set_note_remap(self, voice_name: str, note: int) -> None:
        """Set/override the MIDI note a voice name maps to (clamped 0-127) and rebuild."""
        with self._lock:
            self.note_remap[voice_name] = max(0, min(127, int(note)))
            self._rebuild_after_remap()

    def clear_note_remap(self, voice_name: str) -> None:
        """Remove a single voice-name remap and rebuild."""
        with self._lock:
            self.note_remap.pop(voice_name, None)
            self._rebuild_after_remap()

    def _rebuild_after_remap(self) -> None:
        """Re-derive voices/engine from last_p with the current note_remap applied."""
        if not self.last_p or not self.voices:
            return
        voices = pl.apply_voice_steps(
            pl.apply_note_remap(pl.build_voices(self.last_p, weather=self.weather), self.note_remap),
            self.voice_steps,
        )
        self.voices = voices
        self.engine = pl.assemble_engine(self.last_p, voices, weather=self.weather)

    # ------------------------------------------------------------------
    # Session JSON export / import (mirror web.py `/session/*`, web.py:3565)
    # ------------------------------------------------------------------

    def _presets_path(self) -> str:
        from pathlib import Path
        return str(Path(__file__).parent / "bang_presets.json")

    def _ksp_presets_path(self) -> str:
        from pathlib import Path
        return str(Path(__file__).parent / "bang_ksp_presets.json")

    def export_session_json(self, path: str) -> str:
        """Write the full session state to a JSON file. Returns the path written."""
        import json
        import presets_lib as pr
        with self._lock:
            data = pr.session_to_dict(self)
        from pathlib import Path
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return path

    def import_session_json(self, path: str) -> None:
        """Restore the full session state from a JSON file (in place)."""
        import json
        import presets_lib as pr
        from pathlib import Path
        data = json.loads(Path(path).read_text())
        with self._lock:
            pr.session_from_dict(self, data)

    # ------------------------------------------------------------------
    # Météo + polyphonie (mirror web.py `/weather`)
    # ------------------------------------------------------------------

    def fetch_weather(self) -> dict | None:
        """Fetch current weather on demand and store it (mirror web.py `/weather`).

        Thin wrapper around bang_engine.fetch_weather(); the result feeds
        weather-driven DNA generation. Returns the dict (or None if offline).
        """
        import bang_engine
        w = bang_engine.fetch_weather()
        with self._lock:
            self.weather = w
        return w

    def set_max_poly(self, n: int) -> None:
        """Store the max polyphony limit (0 = unlimited) for the UI.

        NOTE: voice-stealing enforcement is NOT wired into LiveClock yet — this
        only persists the value. It's a genuine TODO, not a silent no-op.
        """
        self.max_poly = max(0, int(n))

    # ------------------------------------------------------------------
    # Sequencer slots (mirror web.py `/seq/*`, web.py:3185-3268)
    # ------------------------------------------------------------------

    def _snapshot(self) -> tuple:
        """Snapshot courant (voices, plocks, last_p) — même format que l'undo history."""
        return (list(self.voices), list(self.plocks),
                dict(self.last_p) if self.last_p else {})

    def _restore_snapshot(self, snap: tuple) -> None:
        """Restaure un snapshot (voices, plocks, last_p) et réassemble l'engine."""
        voices, plocks, last_p = snap
        self.voices = list(voices)
        self.plocks = list(plocks)
        self.last_p = dict(last_p)
        self.engine = pl.assemble_engine(self.last_p, self.voices, weather=self.weather)

    def seq_save(self, idx: int) -> bool:
        """Stocke le pattern courant dans le slot idx (mirror `/seq/save`, web.py:3185).

        Retourne False si idx hors bornes ou si aucun pattern n'est chargé.
        """
        with self._lock:
            if not (0 <= idx < 8) or not self.voices or not self.last_p:
                return False
            self.seq_slots[idx] = self._snapshot()
            return True

    def seq_load(self, idx: int) -> bool:
        """Restaure le slot idx dans l'état courant (mirror `/seq/load`, web.py:3198).

        Empile l'undo history, réassemble l'engine, met à jour seq_current.
        Retourne False si idx hors bornes ou slot vide.
        """
        with self._lock:
            if not (0 <= idx < 8) or self.seq_slots[idx] is None:
                return False
            if self.voices and self.last_p:
                self._push_history()
            self._restore_snapshot(self.seq_slots[idx])
            self.seq_current = idx
            return True

    def seq_clear(self, idx: int) -> bool:
        """Vide le slot idx (mirror `/seq/clear`, web.py:3220). False si hors bornes."""
        with self._lock:
            if not (0 <= idx < 8):
                return False
            self.seq_slots[idx] = None
            return True

    def seq_advance(self) -> int:
        """Sélectionne aléatoirement (pondéré) un slot occupé et le charge.

        Mirror `/seq/advance` (web.py:3230) : exclut le slot courant sauf s'il est
        le seul occupé, pondère par seq_weights. Retourne l'index chargé, ou -1
        si aucun slot n'est occupé.
        """
        with self._lock:
            occupied = [i for i in range(8) if self.seq_slots[i] is not None]
            if not occupied:
                return -1
            others = [i for i in occupied if i != self.seq_current]
            pool = others if others else occupied
            wts = [self.seq_weights[i] for i in pool]
            next_idx = random.choices(pool, weights=wts, k=1)[0]
            if self.voices and self.last_p:
                self._push_history()
            self._restore_snapshot(self.seq_slots[next_idx])
            self.seq_current = next_idx
            return next_idx

    def seq_set_weight(self, idx: int, weight: int) -> None:
        """Fixe le poids de sélection d'un slot (mirror `/seq/weight`, web.py:3263, clamp 1-9)."""
        with self._lock:
            if 0 <= idx < 8:
                self.seq_weights[idx] = max(1, min(9, int(weight)))

    def seq_set_cycles(self, n: int) -> None:
        """Fixe le nombre de cycles avant advance (mirror `/seq/config`, web.py:3257, clamp 1-64)."""
        with self._lock:
            self.seq_cycles = max(1, min(64, int(n)))

    # ------------------------------------------------------------------
    # A/B compare (mirror web.py `/ab/*`, web.py:3364-3390)
    # ------------------------------------------------------------------

    def ab_store(self, slot: str) -> bool:
        """Stocke le pattern courant dans le slot A ou B (mirror `/ab/store`, web.py:3364).

        Retourne False si aucun pattern n'est chargé.
        """
        with self._lock:
            if not self.voices or not self.last_p:
                return False
            snap = self._snapshot()
            if slot == "b":
                self.slot_b = snap
            else:
                self.slot_a = snap
            return True

    def ab_load(self, slot: str) -> bool:
        """Restaure le slot A ou B (mirror `/ab/load`, web.py:3376). False si vide."""
        with self._lock:
            snap = self.slot_b if slot == "b" else self.slot_a
            if snap is None:
                return False
            self._restore_snapshot(snap)
            return True

    # ------------------------------------------------------------------
    # Song mode — macro-arrangement (mirror web.py `_generate_song`, web.py:2118)
    # ------------------------------------------------------------------

    def generate_song(self, chaos: float, bpm: int, gravity: float,
                      cc_depth: float) -> tuple[BangEngine, int]:
        """Assemble une song complète (intro→…→fin) en UN seul BangEngine.

        Portage de web.py `_generate_song` (web.py:2118) : mêmes sections
        (`_SONG_STRUCTURE`), mêmes rampes de chaos et même logique de morph
        inter-variation. Là où web.py exporte 30 fichiers séparés, on concatène
        toutes les variations sur une timeline unique — chaque voix d'une section
        est ajoutée à l'engine maître avec une DNA préfixée/suffixée de silences
        pour tenir sa place temporelle. Retourne (engine, num_steps_total).

        Les modes de song (`ambient`/`noise`) ne produisent que des voix "drum"
        (aucune CC ni p-lock), donc l'assemblage se réduit à `add_voice`.
        """
        total_steps = sum(steps * count
                          for _g, _b, _m, _cs, _ce, steps, count, _br in SONG_STRUCTURE)
        engine = BangEngine(bpm=max(1, int(bpm)))
        chaos = max(0.0, min(1.0, float(chaos)))
        offset = 0

        for _grp, _basename, mode, cstart, cend, steps, count, is_break in SONG_STRUCTURE:
            prev_voices: list | None = None
            for i in range(count):
                cmult = cstart if count == 1 else cstart + (i / (count - 1)) * (cend - cstart)
                section_chaos = min(1.0, chaos * cmult)
                p = pl.read_form(mode=mode, chaos=section_chaos, bpm=bpm,
                                 steps=steps, gravity=gravity, cc_depth=cc_depth)
                if is_break or prev_voices is None:
                    voices = pl.apply_note_remap(
                        pl.build_voices(p, weather=self.weather), self.note_remap)
                else:
                    morph_intensity = 0.08 + section_chaos * 0.06
                    voices = [(n, mutate_dna(d, intensity=morph_intensity), t)
                              for n, d, t in prev_voices]
                prev_voices = voices

                trailing = total_steps - offset - steps
                for note, dna, vtype in voices:
                    if vtype == "cc" or not dna:
                        continue
                    body = pl.resize_dna(dna, steps)
                    padded = ("-" * offset) + body + ("-" * trailing)
                    engine.add_voice(note, padded)
                offset += steps

        return engine, total_steps

    def export_song_midi(self, filename: str, dest_dir: str | None,
                         chaos: float, bpm: int, gravity: float,
                         cc_depth: float) -> str:
        """Génère et exporte une song en un seul fichier MIDI (mirror `/export/song`, web.py:2191).

        Retourne le chemin absolu du fichier écrit.
        """
        from pathlib import Path
        engine, num_steps = self.generate_song(chaos, bpm, gravity, cc_depth)
        target_dir = Path(dest_dir).expanduser() if dest_dir else Path(__file__).parent / "exports"
        target_dir.mkdir(parents=True, exist_ok=True)
        out_name = filename or "bang_song.mid"
        if not out_name.endswith(".mid"):
            out_name += ".mid"
        export_path = str(target_dir / out_name)
        engine.export_midi(num_steps=num_steps, filename=export_path, weather=self.weather)
        self.last_seed = engine.last_seed
        return export_path


# ---------------------------------------------------------------------------
# Structure de song macro-arrangement (portage de web.py `_SONG_STRUCTURE`,
# web.py:2100) — (group, basename, mode, chaos_start, chaos_end, steps, count, is_break)
# ---------------------------------------------------------------------------
SONG_STRUCTURE = [
    (1, "intro",      "ambient", 0.15, 0.35, 32, 4, False),
    (2, "transition", "noise",   0.55, 0.70, 16, 1, False),
    (3, "couplet",    "noise",   0.70, 1.00, 32, 8, False),
    (4, "break",      "ambient", 0.05, 0.12, 32, 1, True),
    (5, "couplet2",   "noise",   0.90, 1.15, 32, 4, False),
    (6, "climax",     "noise",   1.10, 1.40, 32, 4, False),
    (7, "break2",     "ambient", 0.05, 0.18, 32, 2, True),
    (8, "outro",      "ambient", 0.40, 0.12, 32, 2, False),
    (9, "fin",        "ambient", 0.08, 0.04, 32, 4, False),
]


def _lfo_val(shape: str, phase: float) -> float:
    """Valeur LFO normalisée [0..1] pour une phase [0..1] (mirror web.py:1597-1603)."""
    import math
    import random
    if shape == "sin":  return 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    if shape == "tri":  return 2 * phase if phase < 0.5 else 2 * (1 - phase)
    if shape == "ramp": return phase
    return random.random()


if __name__ == "__main__":
    session = BangSession()
    voices = session.generate(mode="morph", chaos=0.3, bpm=110, steps=64)
    print(f"Generated {len(voices)} voices:")
    for v in voices:
        print(f"  {v}")

    print("\nTransforms:")
    print("  invert(0):", session.invert_voice(0))
    print("  rotate(1, 2):", session.rotate_voice(1, 2))
    print("  regen(2):", session.regen_voice(2))
    print("  vary_voice(3):", session.vary_voice(3))
    print("  undo():", session.undo())

    session.set_voice_density("Kick", 0.8)
    session.set_voice_chord("Kick", "minor")  # invalid target but harmless
    print("\nvoice_density:", session.voice_density)

    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        path = session.export_midi(filename="smoke_test.mid", dest_dir=tmp)
        print(f"\nExported: {path} ({os.path.getsize(path)} bytes)")

    print("\n✓ bang_session.py smoke test OK")
