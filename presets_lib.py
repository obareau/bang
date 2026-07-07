"""BANG! Presets Library — drum machines, grooves, KSP scale presets + session I/O.

Framework-agnostic (no Qt, no FastAPI), exactly like pattern_lib.py: the dicts
and helpers here are ported verbatim from web.py so the Qt6 app and the webapp
share identical preset behavior.

The session_to_dict / session_from_dict helpers duck-type a BangSession-like
object (see bang_session.py) — they never import BangSession, they just read /
write the documented attribute names via getattr/setattr. This keeps the import
graph one-directional (bang_session imports presets_lib, never the reverse) and
avoids any circular-import risk.

Expected session attributes (all present on bang_session.BangSession):
    voices, last_p, last_seed, engine, weather,
    voice_thin, voice_density, voice_chords, note_remap,
    locked_voices, and optionally max_poly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pattern_lib as pl

# ---------------------------------------------------------------------------
# Groove presets — 4 DNA strings (kick / snare / hh / perc), verbatim from web.py:67
# ---------------------------------------------------------------------------

GROOVE_PRESETS: dict[str, list[str]] = {
    "MPC Boom Bap":    ["x---x---x---x---", "----x-------x---", "x-x-x-x-x-x-x-x", "---x-----------x"],
    "Trap":            ["x-----------x---", "----x-----x-x---", "xxxxxxxxxxxxxxxx", "x-x-x-----------"],
    "Bossa Nova":      ["x--x--x-x--x--x-", "---x-----x------", "x-x-x-x-x-x-x-x", "x---x---x---x---"],
    "Reggae":          ["--------x-------", "x---x---x---x---", "x-x-x-x-x-x-x-x", "----x-------x---"],
    "Afrobeat":        ["x--x--x--x--x--x", "--x---x---x---x-", "x-x-x-x-x-x-x-x", "x--x-x--x--x-x--"],
    "Techno":          ["x---x---x---x---", "----x-------x---", "-x-x-x-x-x-x-x-", "x-----------x---"],
    "Drum'n'Bass":     ["x-----------x-x-", "----x-----------", "x-x-x-x-x-x-x-x", "x--x--x--x--x---"],
    "Hip-Hop Swing":   ["x---x--x----x---", "----x-------x---", "x--x--x-x--x--x-", "--x---x-------x-"],
    "Breakbeat":       ["x-x---x-x-x---x-", "---x-----x------", "x-x-x-x-x-x-x-x", "--x---x-------x-"],
    "Cumbia":          ["x--x-x--x--x-x--", "----x-------x---", "-x-x-x-x-x-x-x-", "x---x---x---x---"],
    "Soca":            ["x---x---x---x---", "--x---x---x---x-", "x-x-x-x-x-x-x-x", "x-x---x-x-x---x-"],
    "Clave 3-2":       ["x--x--x---------", "--------x--x-x--", "x-x-x-x-x-x-x-x", "x--x--x--x-x-x--"],
    "Waltz 3/4":       ["x-----x-----x---", "--x-----x-----x-", "x-x-x-x-x-x-x-x", "x---x---x---x---"],
    "Shuffle":         ["x---x---x---x---", "----x-------x---", "x--x--x--x--x--x", "--------x-------"],
    "Minimal Techno":  ["x-----------x---", "----x-----------", "-x-x-x-x-x-x-x-", "x---------------"],
    "Straight":        ["x---x---x---x---", "----x-------x---", "x---x---x---x---", ""],
}

# ---------------------------------------------------------------------------
# Drum machine presets (voice_name -> MIDI note), verbatim from web.py:90
# ---------------------------------------------------------------------------

DRUM_PRESETS: dict[str, dict[str, int]] = {
    "GM": {
        "Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48,
        "Bass": 24, "A1": 33, "E1": 40, "G1": 43,
    },
    "TR-808": {
        # Roland TR-8 / AudioRealism RD-808
        "Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 43,
        "Bass": 36, "A1": 46, "E1": 39, "G1": 45,
    },
    "TR-909": {
        # Roland TR-8 mode 909
        "Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 50,
        "Bass": 36, "A1": 49, "E1": 40, "G1": 47,
    },
    "MPC60": {
        # Akai MPC60 / MPC3000
        "Kick": 35, "Snare": 40, "HiHat": 42, "Tom": 47,
        "Bass": 36, "A1": 38, "E1": 39, "G1": 43,
    },
    "Battery 4": {
        # NI Battery 4 — mapping GM (kits standard)
        "Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48,
        "Bass": 24, "A1": 33, "E1": 40, "G1": 43,
    },
    "Tekno": {
        # Baby Audio Tekno v1.001 — C1→F2 séquentiel
        "Kick":  36,  # Kick A  — C1
        "Bass":  37,  # Kick B  — C#1
        "Snare": 38,  # Snare A — D1
        "E1":    39,  # Snare B — D#1
        "HiHat": 40,  # Hat A   — E1  (≠ GM)
        "G1":    41,  # Hat B   — F1
        "A1":    42,  # Hat Op  — F#1
        "Tom":   43,  # Tom L   — G1  (≠ GM)
    },
    "LinnDrum": {
        "Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48,
        "Bass": 43, "A1": 46, "E1": 37, "G1": 41,
    },
    "Volca Kick": {
        "VKick": 60,   # C3 — pitch initial du kick (note → hauteur de l'oscillateur)
    },
    "Volca FM": {
        "FM1": 36,  # C1 — voix grave
        "FM2": 43,  # G1 — quinte
        "FM3": 48,  # C2 — octave
    },
    "MicroFreak": {
        "MF1": 45,  # A2 — lead principal
        "MF2": 40,  # E2 — contre-voix
        "MF3": 36,  # C2 — note grave
    },
}

# ---------------------------------------------------------------------------
# KSP presets (root + scale + gravity + chord par piste), verbatim from web.py:357
# ---------------------------------------------------------------------------

KSP_PRESETS_BUILTIN: dict[str, dict] = {
    "Dark Penta": {
        "root": "A", "scale": "penta_min", "gravity": 0.75,
        "chords": {"KSP Lead": "minor", "KSP Bass": "power", "KSP Chord": "m7", "KSP Arp": "mono"},
    },
    "Dorian Jazz": {
        "root": "D", "scale": "dorian", "gravity": 0.60,
        "chords": {"KSP Lead": "m7", "KSP Bass": "power", "KSP Chord": "M7", "KSP Arp": "sus2"},
    },
    "Phrygian Noise": {
        "root": "E", "scale": "phrygian", "gravity": 0.85,
        "chords": {"KSP Lead": "dim", "KSP Bass": "power", "KSP Chord": "minor", "KSP Arp": "mono"},
    },
    "Lydian Dream": {
        "root": "C", "scale": "lydian", "gravity": 0.55,
        "chords": {"KSP Lead": "M7", "KSP Bass": "mono", "KSP Chord": "sus2", "KSP Arp": "aug"},
    },
    "Blues Minor": {
        "root": "A", "scale": "minor", "gravity": 0.70,
        "chords": {"KSP Lead": "minor", "KSP Bass": "power", "KSP Chord": "dom7", "KSP Arp": "minor"},
    },
}


# ---------------------------------------------------------------------------
# Custom-preset JSON persistence (parametrized path, mirror web.py:340/381)
# ---------------------------------------------------------------------------

def _load_json_dict(path: str | Path) -> dict:
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_json_dict(path: str | Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_custom_presets(path: str | Path) -> dict:
    """Load user-saved drum presets from a JSON file (mirror web._load_custom_presets)."""
    return _load_json_dict(path)


def save_custom_presets(path: str | Path, data: dict) -> None:
    """Persist user-saved drum presets to a JSON file (mirror web._save_custom_presets)."""
    _save_json_dict(path, data)


def load_ksp_presets(path: str | Path) -> dict:
    """Load user-saved KSP presets from a JSON file (mirror web._load_ksp_presets)."""
    return _load_json_dict(path)


def save_ksp_presets(path: str | Path, data: dict) -> None:
    """Persist user-saved KSP presets to a JSON file (mirror web._save_ksp_presets)."""
    _save_json_dict(path, data)


# ---------------------------------------------------------------------------
# Groove application
# ---------------------------------------------------------------------------

def apply_groove(
    voices: list[tuple[int, str, str]],
    groove_name: str,
) -> list[tuple[int, str, str]]:
    """Overwrite the first 4 non-CC voices' DNA with GROOVE_PRESETS[groove_name].

    Returns a new list (input is not mutated). Mirror of web.py `/groove/apply`
    (web.py:3115): CC voices are skipped, and empty groove slots leave the voice
    untouched. Unknown groove names return the input unchanged.
    """
    preset = GROOVE_PRESETS.get(groove_name)
    result = list(voices)
    if not preset:
        return result
    pi = 0
    for vi, (note, dna, vtype) in enumerate(result):
        if vtype == "cc":
            continue
        if pi < len(preset) and preset[pi]:
            result[vi] = (note, preset[pi], vtype)
        pi += 1
    return result


# ---------------------------------------------------------------------------
# Full-session JSON export / import (duck-typed BangSession)
# ---------------------------------------------------------------------------

def session_to_dict(session) -> dict:
    """Serialize a BangSession's full state to a JSON-ready dict.

    Mirror of web.py `/session/export` (web.py:3565). Operates on a
    BangSession-like object via attribute access — no BangSession import.
    """
    voices = getattr(session, "voices", []) or []
    last_p = getattr(session, "last_p", None) or {}
    return {
        "bang_version":  getattr(session, "bang_version", "qt6"),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "seed":          getattr(session, "last_seed", "") or "",
        "params":        last_p,
        "voices":        [{"note": n, "pattern": d, "type": t} for n, d, t in voices],
        "voice_thin":    dict(getattr(session, "voice_thin", {}) or {}),
        "voice_density": dict(getattr(session, "voice_density", {}) or {}),
        "voice_chords":  dict(getattr(session, "voice_chords", {}) or {}),
        "note_remap":    dict(getattr(session, "note_remap", {}) or {}),
        "max_poly":      int(getattr(session, "max_poly", 0) or 0),
        "locked_voices": sorted(getattr(session, "locked_voices", set()) or set()),
    }


def session_from_dict(session, data: dict) -> None:
    """Restore a BangSession's full state from a dict (in place).

    Mirror of web.py `/session/import` (web.py:3589). Reassembles the engine
    when both params and voices are present, matching the webapp.
    """
    session.voices = [(v["note"], v["pattern"], v["type"]) for v in data.get("voices", [])]
    session.voice_thin    = data.get("voice_thin", {}) or {}
    session.voice_density = data.get("voice_density", {}) or {}
    session.voice_chords  = data.get("voice_chords", {}) or {}
    session.note_remap    = data.get("note_remap", {}) or {}
    if hasattr(session, "max_poly"):
        session.max_poly = int(data.get("max_poly", 0) or 0)
    session.last_seed = data.get("seed", "") or ""
    session.locked_voices = set(data.get("locked_voices", []) or [])
    if data.get("params"):
        session.last_p = data["params"]
    if session.last_p and session.voices:
        session.engine = pl.assemble_engine(
            session.last_p, session.voices, weather=getattr(session, "weather", None)
        )


if __name__ == "__main__":
    # Smoke test — no Qt, no session object needed for the pure helpers.
    assert len(DRUM_PRESETS) == 10
    assert len(GROOVE_PRESETS) == 16
    assert len(KSP_PRESETS_BUILTIN) == 5

    demo_voices = [(36, "x---x---", "drum"), (38, "----x---", "drum"),
                   (42, "x-x-x-x-", "drum"), (24, "x-------", "drum"),
                   (0, "CC74", "cc")]
    grooved = apply_groove(demo_voices, "Techno")
    assert grooved[0][1] == GROOVE_PRESETS["Techno"][0]
    assert grooved[4] == (0, "CC74", "cc")  # CC untouched
    assert demo_voices[0][1] == "x---x---"  # input not mutated

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "presets.json"
        save_custom_presets(f, {"MyKit": {"Kick": 35}})
        assert load_custom_presets(f) == {"MyKit": {"Kick": 35}}

    print("✓ presets_lib.py smoke test OK")
