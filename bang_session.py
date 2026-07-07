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

    def export_midi(self, filename: str | None = None, dest_dir: str | None = None) -> str:
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

        densities = [self.voice_density.get(pl.voice_label(n, t), 1.0) for n, _d, t in self.voices]
        chord_types = [self.voice_chords.get(pl.voice_label(n, t), "mono") for n, _d, t in self.voices]

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
