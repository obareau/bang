"""BANG Web — Interface FastAPI + HTMX pour le séquenceur Dark Umbrae"""

from __future__ import annotations

APP_VERSION = "0.9.5-alpha"

# ---------------------------------------------------------------------------
# SSE ??? Live sync browser ??? ??tat OSC/MIDI
# ---------------------------------------------------------------------------
_sse_loop:    asyncio.AbstractEventLoop | None = None
_sse_event:   asyncio.Event | None             = None
_sse_dirty:   set[str]                         = set()
_sse_clients: list[asyncio.Queue]              = []

import io
import json
import os
import random
import re
import secrets
import threading
import time
import zipfile
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
import asyncio
from jinja2 import Environment, FileSystemLoader, select_autoescape

from bang_engine import (
    BangEngine,
    DNA_SYMBOLS,
    SCALE_INTERVALS,
    build_markov_chain,
    compile_dna,
    fetch_weather,
    morph_dna,
    mutate_dna,
    random_dna,
    _seed_to_int,
    weather_cc_breakpoints,
    weather_dna,
)
from cli import _bass_chain_from_gravity, _markov_from_gravity
import babka as _babka

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent
EXPORT_DIR       = BASE_DIR / "exports"
PRESETS_FILE     = BASE_DIR / "bang_presets.json"
KSP_PRESETS_FILE = BASE_DIR / "bang_ksp_presets.json"
FAVORITES_FILE   = BASE_DIR / "bang_favorites.json"
SONG_PARAMS_FILE = BASE_DIR / "bang_song_params.json"
STATE_FILE       = BASE_DIR / "bang_state.json"
EXPORT_DIR.mkdir(exist_ok=True)

# Groove presets — DNA 16 steps par voix (kick, snare, hh, perc)
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
# Drum machine presets  (voice_name -> MIDI note)
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
# Korg Volca Drum — implémentation MIDI complète (Split Channel mode)
# ---------------------------------------------------------------------------

# CC par part (envoyés sur le canal de la part, ch1→6)
VOLCA_DRUM_CC: dict[int, str] = {
    7:   "Level",
    14:  "Select Lyr1",    # sélection couche sonore 1
    15:  "Select Lyr2",    # sélection couche sonore 2
    16:  "Select 1+2",
    17:  "Attack Lyr1",
    18:  "Attack Lyr2",
    19:  "Attack 1+2",
    20:  "Release Lyr1",
    21:  "Release Lyr2",
    22:  "Release 1+2",
    23:  "Pitch Lyr1",
    24:  "Pitch Lyr2",
    25:  "Pitch 1+2",
    26:  "Mod Amt Lyr1",
    27:  "Mod Amt Lyr2",
    28:  "Mod Amt 1+2",
    29:  "Mod Rate Lyr1",
    30:  "Mod Rate Lyr2",
    31:  "Mod Rate 1+2",
    49:  "Bit Crush",       # caché, firmware ≥1.11
    50:  "Fold",            # wave folding, firmware ≥1.11
    51:  "Drive",           # overdrive, firmware ≥1.11
    52:  "Dry Gain",        # firmware ≥1.11
    103: "Send",            # send effet global
    # CC globaux (envoyés sur ch1, affectent tout le Waveguide)
    116: "WG Model",        # modèle de résonance
    117: "WG Decay",        # déclin du waveguide
    118: "WG Body",         # body tuning
    119: "WG Tone",         # tone/filtrage sortie
}

# Profil de p-locks par part : (cc, nom_court, style)
# style: "sweep" = sinus lent, "texture" = variation rythmique, "spike" = impulsions rares
_VD_PLOCK_PROFILE: list[list[tuple]] = [
    # Part 0 — Punch (kick)
    [(20, "Rel",     "sweep"),
     (23, "Pitch",   "sweep"),
     (49, "BitCrsh", "spike")],
    # Part 1 — Snap (snare)
    [(21, "Rel",     "sweep"),
     (26, "ModAmt",  "texture"),
     (51, "Drive",   "spike")],
    # Part 2 — HH (closed hi-hat)
    [(29, "ModRate", "texture"),
     (23, "Pitch",   "texture"),
     (50, "Fold",    "spike")],
    # Part 3 — OH (open hi-hat / cymbal)
    [(21, "Rel",     "sweep"),
     (117,"WGDecay", "sweep"),
     (118,"WGBody",  "texture")],
    # Part 4 — Perc (percussion synthétique)
    [(24, "Pitch",   "sweep"),
     (27, "ModAmt",  "texture"),
     (30, "ModRate", "texture")],
    # Part 5 — Acc (accent / layer)
    [(49, "BitCrsh", "spike"),
     (50, "Fold",    "spike"),
     (51, "Drive",   "texture")],
]


# ---------------------------------------------------------------------------
# Korg Volca Kick — MIDI CC
# ---------------------------------------------------------------------------

VOLCA_KICK_CC: dict[int, str] = {
    40: "Pitch",         # hauteur oscillateur
    44: "Amp Attack",    # attaque amplitude
    45: "Amp Decay",     # déclin amplitude
    46: "Drive",         # saturation
    47: "Fold",          # wavefolder
    48: "Bit Reduction", # réduction de bits
    49: "Gate Time",     # durée de gate
}

# ---------------------------------------------------------------------------
# Korg Volca FM — MIDI CC (DX7-compatible, 4 opérateurs)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Arturia MicroFreak — MIDI CC (paraphonique 4 voix, filtres Steiner-Parker)
# ---------------------------------------------------------------------------

MICROFREAK_CC: dict[int, str] = {
    5:  "Portamento",  # glide
    9:  "Osc Type",    # type d'oscillateur / wavetable
    10: "Wave",        # position wavetable
    11: "Timbre",      # paramètre timbre (dépend du type)
    12: "Shape",       # morphing forme d'onde
    13: "Cutoff",      # coupure filtre Steiner-Parker
    14: "Resonance",   # résonance filtre
    15: "LFO Rate",    # vitesse LFO
    16: "LFO Amount",  # profondeur LFO
    17: "Rise",        # attaque enveloppe
    18: "Fall",        # déclin enveloppe
}

VOLCA_FM_CC: dict[int, str] = {
    40: "Algorithm",    # algorithme FM (0-127 → 8 algos)
    41: "Feedback",     # auto-feedback opérateur 1
    42: "LFO Rate",     # vitesse LFO (vibrato/tremolo)
    43: "LFO Depth",    # profondeur pitch LFO
    44: "Op1 Level",    # niveau opérateur 1 (porteur)
    45: "Op2 Level",    # niveau opérateur 2 (modulateur)
    46: "Op3 Level",    # niveau opérateur 3
    47: "Op4 Level",    # niveau opérateur 4
}

# ---------------------------------------------------------------------------
# Profils P-locks génériques (vk, puis vfm, vmf à venir)
# ---------------------------------------------------------------------------

_SYNTH_PLOCK_PROFILES: dict[str, list[tuple]] = {
    "vk": [
        (40, "Pitch",  "sweep"),    # sweep de pitch — punch caractéristique
        (45, "Decay",  "sweep"),    # longueur du kick
        (46, "Drive",  "texture"),  # saturation variable
        (47, "Fold",   "texture"),  # contenu harmonique
        (48, "BitRed", "spike"),    # artefacts lo-fi
    ],
    "vfm0": [
        (40, "Algo",   "spike"),    # changement d'algorithme — rupture timbre
        (41, "Feedbk", "texture"),  # auto-feedback — densité harmonique
        (44, "Op1Lvl", "sweep"),    # balance porteur/modulateur
        (45, "Op2Lvl", "sweep"),    # balance porteur/modulateur
        (42, "LFOSpd", "texture"),  # vitesse vibrato
    ],
    "mf0": [
        (13, "Cutoff",  "sweep"),   # filtre — ouverture/fermeture
        (11, "Timbre",  "texture"), # timbre wavetable — variation sonore
        (12, "Shape",   "texture"), # morphing forme d'onde
        (16, "LFOAmt",  "spike"),   # accents LFO expressifs
        (15, "LFORate", "sweep"),   # vitesse vibrato variable
    ],
}


def _plock_values(style: str, steps: int, chaos: float, phase: float = 0.0) -> list[int | None]:
    """Génère une liste de valeurs P-lock (ou None) pour un step selon le style."""
    import math
    values: list[int | None] = []
    for step in range(steps):
        t = step / steps
        if style == "sweep":
            base    = int(55 + 50 * math.sin(2 * math.pi * t + phase))
            jitter  = int(chaos * 28 * (random.random() * 2 - 1))
            val     = max(0, min(127, base + jitter))
            density = 0.45 + chaos * 0.3
        elif style == "texture":
            base    = int(38 + 52 * abs(math.sin(4 * math.pi * t + phase)))
            jitter  = int(chaos * 44 * (random.random() * 2 - 1))
            val     = max(0, min(127, base + jitter))
            density = 0.4 + chaos * 0.35
        else:  # spike
            val     = random.randint(60, 127) if random.random() < chaos * 0.55 else random.randint(0, 35)
            density = 0.18 + chaos * 0.42
        values.append(val if random.random() < density else None)
    return values


def _generate_plocks(voices: list, p: dict) -> list:
    """Génère des p-locks (valeurs CC par step) pour les voix synth (Volca Drum, Volca Kick…)."""
    volca_modes = ("volca_drum", "volca_kick", "volca_fm")
    steps = min(p["steps"], 16) if p["mode"] in volca_modes else p["steps"]
    chaos = p["chaos"]
    result = []

    for note, dna, vtype in voices:
        if vtype.startswith("vd"):
            idx     = int(vtype[2:])
            profile = _VD_PLOCK_PROFILE[idx % len(_VD_PLOCK_PROFILE)]
            phase   = idx * 1.4
        elif vtype in _SYNTH_PLOCK_PROFILES:
            profile = _SYNTH_PLOCK_PROFILES[vtype]
            phase   = 0.0
        else:
            result.append([])
            continue

        result.append([
            {"cc": cc, "name": name, "style": style,
             "values": _plock_values(style, steps, chaos, phase)}
            for cc, name, style in profile
        ])

    return result


def _load_custom_presets() -> dict:
    if PRESETS_FILE.exists():
        try:
            return json.loads(PRESETS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_custom_presets(custom: dict) -> None:
    PRESETS_FILE.write_text(json.dumps(custom, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# KSP presets  (root + scale + gravity + chord par piste)
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


def _load_ksp_presets() -> dict:
    if KSP_PRESETS_FILE.exists():
        try:
            return json.loads(KSP_PRESETS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_ksp_presets(custom: dict) -> None:
    KSP_PRESETS_FILE.write_text(json.dumps(custom, indent=2, ensure_ascii=False))


def _load_favorites() -> list[str]:
    if FAVORITES_FILE.exists():
        try: return json.loads(FAVORITES_FILE.read_text())
        except Exception: return []
    return []

def _save_favorites(favs: list[str]) -> None:
    FAVORITES_FILE.write_text(json.dumps(favs))

def _load_song_params() -> dict:
    if SONG_PARAMS_FILE.exists():
        try: return json.loads(SONG_PARAMS_FILE.read_text())
        except Exception: return {}
    return {}

def _save_song_params(p: dict) -> None:
    SONG_PARAMS_FILE.write_text(json.dumps(p, indent=2))


# ---------------------------------------------------------------------------
# Persistance de session (bang_state.json)
# ---------------------------------------------------------------------------

def _snap_to_dict(snap: dict | None) -> dict | None:
    if not snap:
        return None
    return {
        "voices": [[n, d, t] for n, d, t in (snap.get("voices") or [])],
        "plocks": snap.get("plocks", []),
        "last_p": snap.get("last_p"),
    }

def _dict_to_snap(data: dict | None) -> dict | None:
    if not data:
        return None
    return {
        "voices": [(n, d, t) for n, d, t in (data.get("voices") or [])],
        "plocks": data.get("plocks", []),
        "last_p": data.get("last_p"),
    }

def _save_state() -> None:
    try:
        data = {
            "bang_version":      APP_VERSION,
            "last_p":            _state.get("last_p"),
            "last_seed":         _state.get("last_seed"),
            "voices":            [[n, d, t] for n, d, t in (_state.get("voices") or [])],
            "plocks":            _state.get("plocks", []),
            "note_remap":        _state.get("note_remap", {}),
            "voice_thin":        _state.get("voice_thin", {}),
            "voice_density":     _state.get("voice_density", {}),
            "voice_chords":      _state.get("voice_chords", {}),
            "voice_steps":       _state.get("voice_steps", {}),
            "voice_offset":      _state.get("voice_offset", {}),
            "voice_drop":        _state.get("voice_drop", {}),
            "voice_vel_lane":    _state.get("voice_vel_lane", {}),
            "voice_prob_lane":   _state.get("voice_prob_lane", {}),
            "voice_lfo":         _state.get("voice_lfo", {}),
            "voice_midi_ch":     _state.get("voice_midi_ch", {}),
            "voice_swing":       _state.get("voice_swing", {}),
            "seq_weights":       _state.get("seq_weights", [1]*8),
            "ableton_host":         _state.get("ableton_host", "127.0.0.1"),
            "ableton_port":         _state.get("ableton_port", 11000),
            "ableton_track_offset": _state.get("ableton_track_offset", 0),
            "ableton_slot":         _state.get("ableton_slot", 0),
            "seq_slots":   [(_snap_to_dict(s) if s else None) for s in _state.get("seq_slots", [None]*8)],
            "seq_current": _state.get("seq_current", 0),
            "seq_cycles":  _state.get("seq_cycles", 2),
            "locked_voices":     sorted(_state.get("locked_voices", set())),
            "current_preset":    _state.get("current_preset", ""),
            "current_ksp_preset":_state.get("current_ksp_preset", ""),
            "max_poly":          _state.get("max_poly", 0),
            "osc_host":          _state.get("osc_host", "100.64.201.127"),
            "osc_port":          _state.get("osc_port", 57120),
            "osc_rx_port":       _state.get("osc_rx_port", 57121),
            "slot_a":            _snap_to_dict(_state.get("slot_a")),
            "slot_b":            _snap_to_dict(_state.get("slot_b")),
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[state] save error: {e}")

def _load_state() -> None:
    if not STATE_FILE.exists():
        return
    try:
        data = json.loads(STATE_FILE.read_text())
        voices = [(n, d, t) for n, d, t in (data.get("voices") or [])]
        _state["voices"]             = voices
        _state["last_p"]             = data.get("last_p")
        _state["last_seed"]          = data.get("last_seed")
        _state["plocks"]             = data.get("plocks", [])
        _state["note_remap"]         = data.get("note_remap", {})
        _state["voice_thin"]         = data.get("voice_thin", {})
        _state["voice_density"]      = data.get("voice_density", {})
        _state["voice_chords"]       = data.get("voice_chords", {})
        _state["voice_steps"]        = data.get("voice_steps", {})
        _state["voice_offset"]       = data.get("voice_offset", {})
        _state["voice_drop"]         = data.get("voice_drop", {})
        _state["voice_vel_lane"]     = data.get("voice_vel_lane", {})
        _state["voice_prob_lane"]    = data.get("voice_prob_lane", {})
        _state["voice_lfo"]          = data.get("voice_lfo", {})
        _state["voice_midi_ch"]      = data.get("voice_midi_ch", {})
        _state["voice_swing"]        = data.get("voice_swing", {})
        _state["seq_weights"]        = data.get("seq_weights", [1]*8)
        _state["ableton_host"]         = data.get("ableton_host", "127.0.0.1")
        _state["ableton_port"]         = data.get("ableton_port", 11000)
        _state["ableton_track_offset"] = data.get("ableton_track_offset", 0)
        _state["ableton_slot"]         = data.get("ableton_slot", 0)
        raw_slots = data.get("seq_slots", [None]*8)
        _state["seq_slots"]   = [(_dict_to_snap(s) if s else None) for s in raw_slots]
        _state["seq_current"] = data.get("seq_current", 0)
        _state["seq_cycles"]  = data.get("seq_cycles", 2)
        _state["locked_voices"]      = set(data.get("locked_voices", []))
        _state["current_preset"]     = data.get("current_preset", "")
        _state["current_ksp_preset"] = data.get("current_ksp_preset", "")
        _state["max_poly"]           = data.get("max_poly", 0)
        _state["osc_host"]           = data.get("osc_host", "127.0.0.1")
        _state["osc_port"]           = data.get("osc_port", 57120)
        _state["osc_rx_port"]        = data.get("osc_rx_port", 57121)
        _state["slot_a"]             = _dict_to_snap(data.get("slot_a"))
        _state["slot_b"]             = _dict_to_snap(data.get("slot_b"))
        if voices and _state["last_p"]:
            try:
                _state["engine"] = _assemble_engine(_state["last_p"], voices)
            except Exception:
                pass
        print(f"[state] restauré ({len(voices)} voix)")
    except Exception as e:
        print(f"[state] load error: {e}")


app      = App = FastAPI(title="BANG — Dark Umbrae")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
jinja    = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html"]),
)


@app.middleware("http")
async def autosave_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method == "POST":
        _save_state()
    return response


@app.on_event("startup")
async def on_startup():
    global _sse_loop, _sse_event
    _sse_loop  = asyncio.get_event_loop()
    _sse_event = asyncio.Event()
    asyncio.create_task(_sse_broadcaster())
    _load_state()


# ---------------------------------------------------------------------------
# SSE ??? broadcaster, payload, endpoint
# ---------------------------------------------------------------------------

async def _sse_broadcaster() -> None:
    """Debounce 50 ms puis pousse les fragments HTML aux clients connect??s."""
    while True:
        await _sse_event.wait()
        _sse_event.clear()
        await asyncio.sleep(0.05)                     # absorbe les rafales potard
        dirty = set(_sse_dirty)
        _sse_dirty.clear()
        payload = _build_sse_payload(dirty)
        if payload:
            dead = []
            for q in list(_sse_clients):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                _sse_clients.remove(q)


def _build_sse_payload(dirty: set[str]) -> str:
    """Construit les fragments HTML HTMX OOB correspondant aux ??l??ments dirty."""
    parts: list[str] = []
    p = _state.get("last_p") or {}

    # Params globaux (bpm, chaos, gravity, swing, microtiming, steps)
    param_ids = {
        "bpm":         "bpm-input",
        "chaos":       "inp-chaos",
        "gravity":     "inp-gravity",
        "swing":       "swing-range",
        "microtiming": "micro-range",
        "steps":       "inp-steps",
    }
    for item in dirty:
        if item.startswith("param:"):
            name = item[6:]
            val  = p.get(name, "")
            eid  = param_ids.get(name, f"inp-{name}")
            parts.append(
                f'<input id="{eid}" name="{name}" value="{val}" hx-swap-oob="true">'
            )

    # Density par voix
    for item in dirty:
        if item.startswith("density:"):
            voice = item[8:]
            val   = _state.get("voice_density", {}).get(voice, 1.0)
            parts.append(
                f'<input id="inp-density-{voice}" value="{val:.3f}" hx-swap-oob="true">'
            )

    # Pattern (generate / vary) ??? pianoroll complet
    if "pattern" in dirty and _state.get("voices") and p.get("steps"):
        try:
            pr = _build_pr_html(_state["voices"], p["steps"],
                                _state.get("plocks") or None)
            parts.append(f'<div id="pianoroll" hx-swap-oob="true">{pr}</div>')
        except Exception:
            pass

    return "".join(parts)


def _sse_signal(key: str) -> None:
    """Marque un ??l??ment dirty et r??veille le broadcaster (thread-safe)."""
    _sse_dirty.add(key)
    if _sse_loop and _sse_event:
        _sse_loop.call_soon_threadsafe(_sse_event.set)


@app.get("/events")
async def sse_stream(request: Request):
    """Endpoint SSE ??? une connexion persistante par tab browser."""
    q: asyncio.Queue = asyncio.Queue(maxsize=20)
    _sse_clients.append(q)
    async def _gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": ka\n\n"   # keepalive anti-timeout proxy
        finally:
            if q in _sse_clients:
                _sse_clients.remove(q)
    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def render(template_name: str, **ctx) -> HTMLResponse:
    return HTMLResponse(jinja.get_template(template_name).render(**ctx))

# State serveur (usage local mono-utilisateur)
_state: dict = {
    "weather":    None,
    "voices":     [],   # list of (note, dna, type)
    "engine":     None,
    "log":        [],
    "last_file":  None,
    "last_seed":  None,
    "last_p":     None,
    "note_remap":      {},  # voice_name -> midi_note
    "recent_dirs":     [],  # derniers dossiers utilisés (max 5)
    "current_preset":     "",  # nom du preset actif (drum machine)
    "current_ksp_preset": "",  # nom du preset KSP actif
    "plocks":          [],  # p-locks par voix (volca_drum uniquement)
    "locked_voices":   set(),  # indices de voix verrouillées
    "history":         deque(maxlen=5),  # ring buffer (voices, plocks, last_p)
    "slot_a":          None,  # snapshot A/B pour comparaison
    "slot_b":          None,
    "ab_current":      None,  # "a" | "b" | None
    "voice_thin":      {},  # voice_name -> factor (1 / 2 / 4)
    "voice_density":   {},  # voice_name -> float (0.0–1.0, défaut 1.0)
    "voice_chords":    {},  # voice_name -> chord_type str (défaut "mono")
    "voice_steps":     {},  # voice_name -> int override (0 = natural / disabled)
    "voice_offset":    {},  # voice_name -> int phase offset in steps (0 = none)
    "voice_drop":      {},  # voice_name -> float 0.0–1.0 (proba de jouer ce cycle, défaut 1.0)
    "voice_vel_lane":  {},  # voice_name -> list[int] 0-127, indexé par position DNA
    "voice_prob_lane": {},  # voice_name -> list[int] 0-100, indexé par position DNA (0 = no override)
    "voice_lfo":       {},  # voice_name -> {shape, target, freq, depth}
    "voice_midi_ch":   {},  # voice_name -> int 0-15 (MIDI ch 1-16), absent = auto
    "voice_swing":     {},  # voice_name -> float 0.0–1.0 (swing offset sur steps impairs)
    "seq_weights":     [1] * 8,  # poids de sélection aléatoire par slot SEQ (1-9)
    "ableton_host":         "127.0.0.1",
    "ableton_port":         11000,
    "ableton_track_offset": 0,
    "ableton_slot":         0,
    "seq_slots":            [None] * 8,
    "seq_current":          0,
    "seq_cycles":           2,
    "osc_enabled":     False,
    "osc_host":        "100.64.201.127",
    "osc_port":        57120,
    "osc_thread":      None,  # threading.Thread
    "osc_rx_port":     57121,
    "osc_rx_thread":   None,
    "osc_rx_server":   None,
    "midi_srv_enabled": False,
    "midi_srv_port":    0,      # index dans rtmidi.get_ports()
    "midi_srv_thread":  None,
    "midi_srv_channel": 9,      # 0-based (9 = MIDI ch10 drums)
    "max_poly":        0,   # 0 = illimité
    "osc_log":         deque(maxlen=50),  # ring buffer log TX/RX OSC
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Chromatic roots: name → MIDI offset in octave 1 (A1=33 = A in oct-2)
_ROOTS: dict[str, int] = {
    name: 33 + ((i - 9) % 12)
    for i, name in enumerate(_CHROMATIC)
}  # A→33, A#→34, B→35, C→24, C#→25, … G#→32


def _atom_label(prob: float, ratchet: int, jitter: int) -> str:
    """Reverse-map d'un BabkaStep/DNA row vers le symbole atom source."""
    if ratchet >= 3: return '↺'
    if jitter >= 20: return '░'
    if prob < 1.0:   return '?'
    return 'x'


def midi_note_name(n: int) -> str:
    """Convention Roland/GM : C-2=0, C1=36 (Kick GM), Middle C=C3=60."""
    return f"{_CHROMATIC[n % 12]}{n // 12 - 2}"


jinja.globals["midi_note_name"] = midi_note_name

_NOTE_NAMES = {
    24: "Bass", 33: "A1", 36: "Kick", 38: "Snare",
    40: "E1",   42: "HiHat", 43: "G1", 48: "Tom",
}

_NOTE_COLOR = {
    36: "#38bdf8", 38: "#4ade80", 42: "#fb923c",
    48: "#facc15", 24: "#c084fc", 33: "#67e8f9",
    40: "#f472b6", 43: "#a3e635",
}

# Keystep Pro : 4 pistes mélodiques
_KSP_TRACK_NAMES  = ["Lead", "Bass", "Chord", "Arp"]
_KSP_TRACK_COLORS = ["#c084fc", "#4ade80", "#60a5fa", "#fb923c"]
_KSP_OCTAVE_SHIFT = [24, 0, 12, 24]    # décalage en demi-tons par rapport à root_midi

# Notes MIDI customisables par l'utilisateur (remplace _NOTE_NAMES pour les voix)
_custom_notes: dict[int, int] = {}  # slot_index -> note MIDI

# Strudel / TidalCycles export
_STRUDEL_SAMPLES = {
    35: "bd", 36: "bd",
    38: "sd", 39: "cp", 40: "sd",
    42: "hh", 44: "hh", 46: "oh",
    37: "rim",
    41: "lt", 43: "mt", 45: "ht", 47: "ht", 48: "mt", 50: "ht",
    49: "cr", 55: "cr", 57: "cr",
    51: "rd", 53: "rd", 59: "rd",
}
_STRUDEL_NOTE_NAMES = ["c","cs","d","ds","e","f","fs","g","gs","a","as","b"]

def _midi_to_strudel_note(n: int) -> str:
    return f"{_STRUDEL_NOTE_NAMES[n % 12]}{(n // 12) - 1}"


def _build_pianoroll_rows(voices: list, steps: int, plocks: list | None = None) -> list:
    rows = []
    for voice_idx, (note, dna, vtype) in enumerate(voices):
        if vtype == "cc":
            continue

        if vtype == "babka":
            bsteps  = _babka.parse(dna, cycle=0)
            tot_dur = sum(s.duration for s in bsteps) or 1.0
            cells   = [{"trigger": False, "opacity": 0.0, "ratchet": 1, "atom": "-"} for _ in range(steps)]
            pos = 0.0
            for s in bsteps:
                if s.trigger:
                    cyc_pos = pos
                    while cyc_pos < steps:
                        cell = int(cyc_pos)  # floor — identique au player JS
                        if cell < steps:
                            opacity = round(0.35 + s.prob * 0.65, 2)
                            if not cells[cell]["trigger"] or cells[cell]["opacity"] < opacity:
                                atom = _atom_label(s.prob, s.ratchet, getattr(s, "jitter", 0))
                                cells[cell] = {"trigger": True, "opacity": opacity, "ratchet": s.ratchet, "atom": atom}
                        cyc_pos += tot_dur
                pos += s.duration
            name = _NOTE_NAMES.get(note, f"n{note}")
            cells = _thin_cells(cells, _state["voice_thin"].get(name + " ⚗", 1))
            rows.append({"name": name + " ⚗", "cells": cells, "dna_len": int(tot_dur),
                         "color": "#e879f9", "boundaries": [], "plocks": [],
                         "voice_idx": voice_idx})
            continue

        compiled = compile_dna(dna)
        dna_len  = len(compiled)
        cells    = []
        for i in range(steps):
            step    = compiled[i % dna_len]
            trigger = bool(step[0] > 0)
            prob    = float(step[2])
            ratchet = int(step[3])
            jitter  = int(step[4])
            vel     = int(step[1])
            atom    = _atom_label(prob, ratchet, jitter) if trigger else "-"
            cells.append({
                "trigger": trigger,
                "vel":     vel,
                "opacity": round(0.35 + prob * 0.65, 2) if trigger else 0.0,
                "ratchet": ratchet,
                "atom":    atom,
            })
        boundaries = [j * dna_len for j in range(1, steps // dna_len + 1) if j * dna_len < steps]
        if vtype.startswith("vd"):
            idx   = int(vtype[2:])
            color = _VD_PART_COLORS[idx]
            name  = _VD_PART_NAMES[idx]
        elif vtype.startswith("vfm"):
            idx   = int(vtype[3:])
            color = _VFM_PART_COLORS[idx]
            name  = _VFM_PART_NAMES[idx]
        elif vtype.startswith("mf"):
            idx   = int(vtype[2:])
            color = _MF_PART_COLORS[idx]
            name  = _MF_PART_NAMES[idx]
        elif vtype.startswith("ksp"):
            idx   = min(int(vtype[3:]) - 1, 3)
            color = _KSP_TRACK_COLORS[idx]
            name  = f"KSP {_KSP_TRACK_NAMES[idx]}"
        elif vtype == "bl":
            bl_idx = sum(1 for r in rows if r.get("vtype") == "bl")
            color  = "#a78bfa"
            name   = "Bass ♩" if bl_idx == 0 else f"Bass {bl_idx + 1} ♩"
        elif vtype == "vk":
            color = "#f97316"   # orange — kick synthétique
            name  = "VKick"
        else:
            color = _NOTE_COLOR.get(note, "#94a3b8")
            name  = _NOTE_NAMES.get(note, f"n{note}")
        cells = _thin_cells(cells, _state["voice_thin"].get(name, 1))
        voice_plocks = plocks[len(rows)] if plocks and len(rows) < len(plocks) else []
        rows.append({
            "name": name, "cells": cells,
            "dna_len": dna_len, "color": color,
            "boundaries": boundaries,
            "plocks": voice_plocks,
            "vtype": vtype,
            "voice_idx": voice_idx,
        })
    return rows

def _thin_cells(cells: list, factor: int) -> list:
    """Piano-roll : garde 1 trigger sur `factor` (÷2 / ÷4)."""
    if factor <= 1:
        return cells
    trig_idx = 0
    result = []
    for cell in cells:
        if cell["trigger"]:
            keep = (trig_idx % factor == 0)
            result.append(cell if keep else {**cell, "trigger": False, "opacity": 0.0, "atom": "-"})
            trig_idx += 1
        else:
            result.append(cell)
    return result


def _thin_events(events: list, factor: int) -> list:
    """MIDI player : garde 1 event sur `factor`."""
    if factor <= 1:
        return events
    return [e for i, e in enumerate(events) if i % factor == 0]


def _apply_poly_to_rows(rows: list, max_poly: int) -> list:
    """Per-step : si plus de max_poly voix simultanées, les dernières sont muettes."""
    if max_poly <= 0 or not rows:
        return rows
    steps = max(len(r["cells"]) for r in rows)
    for step in range(steps):
        active = [ri for ri, r in enumerate(rows)
                  if step < len(r["cells"]) and r["cells"][step]["trigger"]]
        for ri in active[max_poly:]:
            c = rows[ri]["cells"][step]
            rows[ri]["cells"][step] = {**c, "trigger": False, "opacity": 0.0, "atom": "-"}
    return rows


def _apply_poly_to_events(voices_data: list, max_poly: int) -> list:
    """MIDI player : per-step, garde les max_poly premières voix."""
    if max_poly <= 0:
        return voices_data
    step_count: dict[int, int] = defaultdict(int)
    result = []
    for v in voices_data:
        new_events = []
        for e in v["events"]:
            if step_count[e["step"]] < max_poly:
                new_events.append(e)
                step_count[e["step"]] += 1
        result.append({**v, "events": new_events})
    return result


def _build_pr_html(voices: list, steps: int, plocks: list | None = None) -> str:
    rows = _build_pianoroll_rows(voices, steps, plocks)
    rows = _apply_poly_to_rows(rows, _state["max_poly"])
    vel_lane  = _state.get("voice_vel_lane",  {})
    prob_lane = _state.get("voice_prob_lane", {})
    for row in rows:
        name = row["name"]
        row["vel_lane"]  = vel_lane.get(name,  [])
        row["prob_lane"] = prob_lane.get(name, [])
    return jinja.get_template("_pianoroll.html").render(rows=rows, steps=steps)


def _build_voices_html(voices: list) -> str:
    return jinja.get_template("_voices.html").render(
        voices=[(n, dna_html(d), d, t, _voice_label(n, t)) for n, d, t in voices],
        voice_thin=_state["voice_thin"],
        voice_density=_state["voice_density"],
        voice_chords=_state.get("voice_chords", {}),
        voice_steps=_state.get("voice_steps", {}),
        voice_offset=_state.get("voice_offset", {}),
        voice_drop=_state.get("voice_drop", {}),
        voice_vel_lane=_state.get("voice_vel_lane", {}),
        voice_prob_lane=_state.get("voice_prob_lane", {}),
        voice_lfo=_state.get("voice_lfo", {}),
        voice_midi_ch=_state.get("voice_midi_ch", {}),
        voice_swing=_state.get("voice_swing", {}),
        locked_voices=_state.get("locked_voices", set()),
    )


def _build_seq_html() -> str:
    return jinja.get_template("_seq.html").render(
        slots=_state.get("seq_slots", [None]*8),
        current=_state.get("seq_current", 0),
        cycles=_state.get("seq_cycles", 2),
        weights=_state.get("seq_weights", [1]*8),
    )


def _apply_locks(new_voices: list) -> list:
    """Remplace les voix lockées dans new_voices par celles de l'état courant."""
    locked  = _state.get("locked_voices", set())
    current = _state.get("voices") or []
    result  = list(new_voices)
    for idx in locked:
        if idx < len(current) and idx < len(result):
            result[idx] = current[idx]
    return result


_DNA_CLASS = {
    "x": "dx", "-": "dd", "?": "dq", "↺": "dr", "░": "db",
    "[": "dbk", "]": "dbk", "<": "dalt", ">": "dalt",
    "(": "deuc", ")": "deuc",
}


def dna_html(dna: str, max_len: int = 24) -> str:
    parts = []
    for c in dna[:max_len]:
        cls = _DNA_CLASS.get(c, "")
        parts.append(f'<span class="{cls}">{c}</span>')
    if len(dna) > max_len:
        parts.append('<span class="dd">…</span>')
    return " ".join(parts)


def _build_voices(p: dict) -> list[tuple[int, str, str]]:
    # Fix seed: reproductibilite des motifs quand un seed est fourni
    if p.get("seed"):
        random.seed(_seed_to_int(p["seed"]))
    chaos = p["chaos"]
    mode  = p["mode"]
    w     = _state["weather"] or {"temperature": 10.0, "wind_speed": 10.0}

    if mode == "random":
        return [(n, random_dna(16), "drum") for n in [36, 38, 42, 48]]

    if mode == "morph":
        base = morph_dna("x---x---x---x---", "x---?---x↺--░---", mutation_rate=chaos * 0.5)
        return [
            (36, mutate_dna(base, intensity=chaos * 0.6), "drum"),
            (38, mutate_dna("----x-------x---",  intensity=chaos * 0.25), "drum"),
            (42, mutate_dna("x-x-x-x-x-x-x-x",  intensity=chaos * 0.2),  "drum"),
            (24, mutate_dna("x-?-░",              intensity=chaos * 0.3),  "drum"),
        ]

    if mode == "weather":
        return [
            (note, mutate_dna(weather_dna(w, length), intensity=chaos * 0.4), "drum")
            for note, length in [(36, 16), (38, 8), (42, 16), (24, 5)]
        ]

    if mode in ("markov", "phase2"):
        voices = [
            (36, mutate_dna("x---x---", intensity=chaos * 0.4), "drum"),
            (38, mutate_dna("----x-------x---",  intensity=chaos * 0.25), "drum"),
            (42, mutate_dna("x-x-x-x-x-x-x-x",  intensity=chaos * 0.2),  "drum"),
            (24, mutate_dna("x-?-░",              intensity=chaos * 0.3),  "markov"),
        ]
        if mode == "phase2":
            cc_peak = int(20 + p["cc_depth"] * 100)
            voices.append((0, f"CC74 → 20…{cc_peak}…20", "cc"))
            if _state["weather"]:
                voices.append((0, "CC91 réverb (météo)", "cc"))
        return voices

    if mode == "noise":
        # Rhythmic Noise — 8 voix, cycles asymétriques, haute entropie
        _NOISE_VOICES = [
            (36, 11), (38, 7),  (42, 13), (48, 5),
            (40, 9),  (43, 11), (24, 7),  (33, 13),
        ]
        w_dense = [2 + chaos * 3, max(0.1, 2 - chaos * 1.5), 1 + chaos, chaos * 1.5, chaos]
        w_hh    = [0.8, 6.0, 0.4, 0.0, 0.0]  # ~2 hits par pattern, no ratchet/jitter
        return [
            (note, mutate_dna(
                ''.join(random.choices(DNA_SYMBOLS, weights=(w_hh if note == 42 else w_dense), k=length)),
                intensity=(chaos * 0.08 if note == 42 else chaos * 0.4)
            ), "drum")
            for note, length in _NOISE_VOICES
        ]

    if mode == "ambient":
        # Dark Ambient — 3 voix ultra-sparse, longues silences
        length = p["steps"]
        # x=rare, -=dominant, ?=épars, ↺=jamais, ░=jamais
        w = [0.3 + chaos * 0.3, 9.0, 0.5 + chaos * 0.2, 0.0, 0.0]
        return [
            (note, mutate_dna(
                ''.join(random.choices(DNA_SYMBOLS, weights=w, k=length)),
                intensity=chaos * 0.05
            ), "drum")
            for note in [36, 24, 33]
        ]

    if mode == "babka":
        if chaos < 0.4:
            return [
                (36, mutate_dna("x---x---",          intensity=chaos * 0.3),  "babka"),
                (38, mutate_dna("x(3,8)",            intensity=chaos * 0.2),  "babka"),
                (42, mutate_dna("[x x]-x-[x x]-x-", intensity=chaos * 0.15), "babka"),
                (24, mutate_dna("?-░-",             intensity=chaos * 0.3),  "babka"),
            ]
        elif chaos < 0.7:
            return [
                (36, mutate_dna("<x---x--- x-[x-]x-->",  intensity=chaos * 0.25), "babka"),
                (38, mutate_dna("?(3,8)",                 intensity=chaos * 0.2),  "babka"),
                (42, mutate_dna("<[x x]-x- x-[x x]->",   intensity=chaos * 0.15), "babka"),
                (24, mutate_dna("↺(2,8)",                 intensity=chaos * 0.25), "babka"),
            ]
        else:
            n_snare = min(7, max(2, int(chaos * 8)))
            return [
                (36, mutate_dna("<x-[x x]- [x x]-->",        intensity=chaos * 0.3),  "babka"),
                (38, mutate_dna(f"?({n_snare},8)",            intensity=chaos * 0.25), "babka"),
                (42, mutate_dna("<[x x x]-x- x-[x x]->",     intensity=chaos * 0.2),  "babka"),
                (24, mutate_dna("<↺(2,8) ░(3,8)>",       intensity=chaos * 0.3),  "babka"),
            ]

    if mode == "bassline":
        # Patterns rythmiques selon chaos — groove syncopé, tension variable
        if chaos < 0.30:
            trig_a = "x---x---"
            trig_b = "x-------x-------"
        elif chaos < 0.55:
            trig_a = mutate_dna("x---x-x-", intensity=chaos * 0.5)
            trig_b = mutate_dna("x-------x--x----", intensity=chaos * 0.3)
        else:
            trig_a = mutate_dna("x-x--x-?", intensity=chaos * 0.55)
            trig_b = mutate_dna("?--x-x--x---?---", intensity=chaos * 0.45)
        cc_peak = int(20 + p["cc_depth"] * 80)
        voices = [
            (33, trig_a, "bl"),   # A1 — ligne principale
            (33, trig_b, "bl"),   # A1 — contre-rythme
            (0, f"CC74 → 20…{cc_peak}…20", "cc"),
        ]
        if chaos > 0.35:
            port_peak = int(chaos * 60)
            voices.append((0, f"CC5 portamento ↗{port_peak}", "cc"))
        return voices

    if mode == "volca_kick":
        _VK_BASES = [
            ("x---x---x---x---", "x---?---x---?---"),  # 4-on-the-floor
            ("x-?-x---x-?-x---", "?---x---?---x---"),  # syncopé
            ("x---x-?-x---x-?-", "x---?-x-x---?-x-"),  # avec swing
        ]
        pair = _VK_BASES[int(chaos * len(_VK_BASES)) % len(_VK_BASES)]
        dna  = morph_dna(pair[0], pair[1], mutation_rate=chaos * 0.35)
        dna  = mutate_dna(dna, intensity=chaos * 0.25)
        return [(60, dna, "vk")]  # C3 — pitch initial

    if mode == "microfreak":
        # 3 voix paraphoniques — canal ch1, lead mélodique / synth
        # Notes : A2=45 (lead), E2=40 (contre), C2=36 (grave)
        _MF_NOTES = [45, 40, 36]
        _MF_BASES = [
            # MF1 (lead) — séquence mélodique principale, syncopes
            ("x---x-x-x---x---", "x--?x-x-x--?x---"),
            # MF2 (contre) — réponses et fills
            ("--x---x---x---x-", "--x---x?--x---?-"),
            # MF3 (pédale) — note grave, très sparse
            ("x-----------x---", "?-----------?---"),
        ]
        voices = []
        for i, ((base_a, base_b), note) in enumerate(zip(_MF_BASES, _MF_NOTES)):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.45)
            dna = mutate_dna(dna, intensity=chaos * 0.30)
            voices.append((note, dna, f"mf{i}"))
        return voices

    if mode == "volca_fm":
        # 3 voix polyphoniques FM — canal unique ch1 (index 0)
        # Notes : C1=36 (grave), G1=43 (quinte), C2=48 (octave)
        # DNA limité à 16 steps
        _VFM_NOTES = [36, 43, 48]
        _VFM_BASES = [
            # FM1 (grave) — ligne principale, syncopes avec silence
            ("x---x---x---x---", "x---x--?x---x---"),
            # FM2 (quinte) — contre-rythme, plus épars
            ("--x---x---x---x-", "--x?--x---x---x-"),
            # FM3 (octave) — atmosphérique, rare
            ("---?---x--------", "---?--------x---"),
        ]
        voices = []
        for i, ((base_a, base_b), note) in enumerate(zip(_VFM_BASES, _VFM_NOTES)):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.45)
            dna = mutate_dna(dna, intensity=chaos * 0.25)
            voices.append((note, dna, f"vfm{i}"))
        return voices

    if mode == "volca_drum":
        # 6 parts, chacun sur son canal MIDI (ch 1→6 = index 0→5)
        # Note indifférente (on envoie 60/C3) — seul le canal compte
        # DNA limité à 16 steps (séquenceur interne du Volca Drum)
        _VD_BASES = [
            ("x---x---x---x---", "x---?---x---?---"),  # P1 Punch — kick-ish
            ("----x-------x---", "---?x-------x?--"),  # P2 Snap  — snare-ish
            ("x-x-x-x-x-x-x-x", "x-x?x-x-x-x?x-x"),  # P3 HH    — closed hi-hat
            ("?---?---?---?---", "?--░?---?---░?--"),  # P4 OH    — open / cymbal
            ("x-?-░-?-x-?-░-?", "?-░-x-░-?-x-░-?"),  # P5 Perc  — synth perc
            ("---x---?---x---?", "x--?---x---?--x-"),  # P6 Acc   — layer/accent
        ]
        voices = []
        for i, (base_a, base_b) in enumerate(_VD_BASES):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.4)
            dna = mutate_dna(dna, intensity=chaos * 0.3)
            voices.append((60, dna, f"vd{i}"))
        return voices

    if mode == "keystep_pro":
        # 3 voix drums (ch10) + 4 pistes mélodiques Markov (ch1-4)
        return [
            (36, mutate_dna("x---x---x---x---", intensity=chaos * 0.3), "drum"),   # Kick
            (38, mutate_dna("----x-------x---", intensity=chaos * 0.3), "drum"),   # Snare
            (42, mutate_dna("x-x-x-x-x-x-x-x", intensity=chaos * 0.2), "drum"),   # HH
            (0,  mutate_dna("x---?-x-?---x---", intensity=chaos * 0.5), "ksp1"),   # Lead  ch1
            (0,  mutate_dna("x---x-x-x---x---", intensity=chaos * 0.4), "ksp2"),   # Bass  ch2
            (0,  mutate_dna("?---x---?---x---", intensity=chaos * 0.3), "ksp3"),   # Chord ch3
            (0,  mutate_dna("x-x---x-x-?---x-", intensity=chaos * 0.5), "ksp4"),  # Arp   ch4
        ]

    return []


_VD_PART_NAMES  = ["Punch", "Snap", "HH", "OH", "Perc", "Acc"]
_VD_PART_COLORS = ["#38bdf8", "#4ade80", "#fb923c", "#facc15", "#c084fc", "#67e8f9"]

_VFM_PART_NAMES  = ["FM1", "FM2", "FM3"]
_VFM_PART_COLORS = ["#60a5fa", "#2dd4bf", "#818cf8"]  # bleu, teal, indigo

_MF_PART_NAMES  = ["MF1", "MF2", "MF3"]
_MF_PART_COLORS = ["#e879f9", "#d946ef", "#a855f7"]  # fuchsia, pink, violet


def _voice_label(note: int, vtype: str) -> str:
    if vtype.startswith("vd"):
        return _VD_PART_NAMES[int(vtype[2:])]
    if vtype.startswith("vfm"):
        return _VFM_PART_NAMES[int(vtype[3:])]
    if vtype.startswith("mf"):
        return _MF_PART_NAMES[int(vtype[2:])]
    if vtype.startswith("ksp"):
        return f"KSP {_KSP_TRACK_NAMES[min(int(vtype[3:]) - 1, 3)]}"
    if vtype == "babka":
        return _NOTE_NAMES.get(note, f"n{note}") + " ⚗"
    if vtype == "bl":
        return "Bass ♩"
    if vtype == "vk":
        return "VKick"
    return _NOTE_NAMES.get(note, f"n{note}")


def _apply_note_remap(voices: list) -> list:
    remap = _state["note_remap"]
    if not remap:
        return voices
    return [
        (n if (vtype.startswith("vd") or vtype.startswith("ksp") or vtype == "bl") else
         remap.get("VKick", n) if vtype == "vk" else
         remap.get(_VFM_PART_NAMES[int(vtype[3:])], n) if vtype.startswith("vfm") else
         remap.get(_MF_PART_NAMES[int(vtype[2:])], n) if vtype.startswith("mf") else
         remap.get(_NOTE_NAMES.get(n, f"n{n}"), n), dna, vtype)
        for n, dna, vtype in voices
    ]


def _resize_dna(dna: str, n: int) -> str:
    if not dna or n <= 0 or len(dna) == n:
        return dna
    if len(dna) > n:
        return dna[:n]
    return (dna * (n // len(dna) + 1))[:n]


def _apply_voice_steps(voices: list) -> list:
    overrides = _state.get("voice_steps", {})
    if not overrides:
        return voices
    result = []
    for note, dna, vtype in voices:
        if vtype != "cc":
            n = overrides.get(_voice_label(note, vtype), 0)
            if n > 0:
                dna = _resize_dna(dna, n)
        result.append((note, dna, vtype))
    return result


def _assemble_engine(p: dict, voices: list[tuple[int, str, str]]) -> BangEngine:
    engine      = BangEngine(
        bpm=p["bpm"],
        vel_floor=p.get("vel_floor", 0),
        vel_ceiling=p.get("vel_ceiling", 127),
        vel_curve=p.get("vel_curve", 1.0),
    )
    root_midi   = _ROOTS.get(p.get("root", "A"), 33)
    intervals   = SCALE_INTERVALS.get(p.get("scale", "penta_min"), SCALE_INTERVALS["penta_min"])
    chain       = _markov_from_gravity(p["gravity"], root_note=root_midi, intervals=intervals)
    cc_peak     = int(20 + p["cc_depth"] * 100)
    breakpoints = [20, cc_peak, cc_peak, int((20 + cc_peak) / 2), 20]
    kick_done   = False

    bl_chain = None
    for note, dna, vtype in voices:
        if vtype == "cc":
            continue
        elif vtype == "babka":
            engine.add_babka_voice(note, dna)
        elif vtype.startswith("vd"):
            engine.add_voice(note, dna, channel=int(vtype[2:]))
        elif vtype == "vk":
            engine.add_voice(note, dna, channel=0)  # MIDI ch1
        elif vtype.startswith("vfm"):
            engine.add_voice(note, dna, channel=0)  # MIDI ch1 — polyphonique
        elif vtype.startswith("mf"):
            engine.add_voice(note, dna, channel=0)  # MIDI ch1 — paraphonique
        elif vtype == "markov":
            engine.add_markov_voice(chain, trigger_dna=dna, channel=p.get("markov_channel", 9))
        elif vtype.startswith("ksp"):
            ch        = int(vtype[3:]) - 1  # ksp1→0, ksp2→1, ksp3→2, ksp4→3
            oct_shift = _KSP_OCTAVE_SHIFT[min(ch, 3)]
            n_octs    = 1 if ch == 1 else 2   # basse sur 1 octave, les autres sur 2
            ksp_chain = build_markov_chain(root_midi + oct_shift, intervals, num_octaves=n_octs)
            engine.add_markov_voice(ksp_chain, trigger_dna=dna, channel=ch)
        elif vtype == "bl":
            if bl_chain is None:
                bl_chain = _bass_chain_from_gravity(p["gravity"], root_note=root_midi, intervals=intervals)
            engine.add_markov_voice(bl_chain, trigger_dna=dna)
        elif p["mode"] == "phase2" and note == 36 and not kick_done:
            engine.add_voice(note, [dna, mutate_dna("x---x--x", intensity=p["chaos"] * 0.8)])
            kick_done = True
        else:
            engine.add_voice(note, dna)

    if p["mode"] in ("markov", "phase2"):
        engine.add_cc_drone(control=74, breakpoints=breakpoints)
        if p["mode"] == "phase2" and _state["weather"]:
            bps = weather_cc_breakpoints(_state["weather"], num_points=7)
            engine.add_cc_drone(control=91, breakpoints=list(reversed(bps)))

    if p["mode"] == "bassline":
        engine.add_cc_drone(control=74, breakpoints=breakpoints)
        if p["chaos"] > 0.35:
            port_peak = int(p["chaos"] * 60)
            engine.add_cc_drone(control=5, breakpoints=[0, port_peak, port_peak // 2, 0])

    return engine


def _read_form(
    mode:        str   = "morph",
    chaos:       float = 0.30,
    bpm:         int   = 110,
    steps:       int   = 64,
    gravity:     float = 0.70,
    cc_depth:    float = 0.50,
    out:         str   = "bang_out.mid",
    temporal:    str   = "",
    vel_floor:   int   = 0,
    vel_ceiling: int   = 127,
    vel_curve:   float = 1.0,
    root:        str   = "A",
    scale:       str   = "penta_min",
    seed:           str   = "",
    swing:          float = 0.0,
    markov_channel: int   = 9,
    vel_humanize:   int   = 0,
    microtiming:    float = 1.0,
) -> dict:
    _steps = max(1, int(steps))
    if mode in ("volca_drum", "volca_kick", "volca_fm"):
        _steps = min(_steps, 16)
    elif mode == "bassline" and _steps > 128:
        _steps = 128
    _root  = root  if root  in _ROOTS          else "A"
    _scale = scale if scale in SCALE_INTERVALS else "penta_min"
    return {
        "mode":        mode,
        "chaos":       max(0.0, min(1.0, float(chaos))),
        "bpm":         max(1, int(bpm)),
        "steps":       _steps,
        "gravity":     max(0.0, min(1.0, float(gravity))),
        "cc_depth":    max(0.0, min(1.0, float(cc_depth))),
        "out":         out or "bang_out.mid",
        "temporal":    bool(temporal),
        "vel_floor":   max(0, min(126, int(vel_floor))),
        "vel_ceiling": max(1, min(127, int(vel_ceiling))),
        "vel_curve":   max(0.1, min(4.0, float(vel_curve))),
        "root":        _root,
        "scale":       _scale,
        "seed":           str(seed).strip(),
        "swing":          max(0.0, min(1.0, float(swing))),
        "markov_channel": max(0, min(15, int(markov_channel))),
        "vel_humanize":   max(0, min(40, int(vel_humanize))),
        "microtiming":    max(0.0, min(1.0, float(microtiming))),
    }


def _build_ab_html() -> str:
    """Génère le bloc #ab-controls pour le toolbar (store + load A/B)."""
    sa  = _state["slot_a"]  is not None
    sb  = _state["slot_b"]  is not None
    cur = _state.get("ab_current")

    def _store(slot: str) -> str:
        lbl = slot.upper()
        return (f'<button class="btn-ab btn-ab-store" '
                f'hx-post="/ab/store" hx-vals=\'{{"slot":"{slot}"}}\' '
                f'hx-target="#ab-controls" hx-swap="outerHTML" '
                f'title="Stocker dans {lbl}">▸{lbl}</button>')

    def _load(slot: str) -> str:
        filled  = sa if slot == "a" else sb
        active  = cur == slot
        lbl     = slot.upper()
        icon    = "●" if filled else "○"
        cls     = "btn-ab" + (" btn-ab-active" if active else "") + (" btn-ab-empty" if not filled else "")
        dis     = "" if filled else " disabled"
        return (f'<button class="{cls}"{dis} '
                f'hx-post="/ab/load" hx-vals=\'{{"slot":"{slot}"}}\' '
                f'hx-target="#voices" hx-swap="innerHTML" '
                f'title="Charger {lbl}">{lbl}{icon}</button>')

    return (f'<div id="ab-controls" class="tb-group" style="display:flex;gap:2px">'
            f'{_store("a")}{_store("b")}'
            f'<span style="color:var(--border);padding:0 2px">|</span>'
            f'{_load("a")}{_load("b")}'
            f'</div>')


# ---------------------------------------------------------------------------
# OSC clock — thread serveur
# ---------------------------------------------------------------------------

def _sync_vary() -> None:
    """Mutation légère du pattern courant (appelable depuis le thread OSC)."""
    if not _state["voices"] or not _state["last_p"]:
        return
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    locked    = _state.get("locked_voices", set())
    new_voices = []
    for idx, (note, dna, vtype) in enumerate(_state["voices"]):
        if idx in locked or vtype == "cc":
            new_voices.append((note, dna, vtype))
        else:
            new_voices.append((note, mutate_dna(dna, intensity=0.12), vtype))
    _state["voices"] = new_voices
    _state["engine"] = _assemble_engine(_state["last_p"], new_voices)


def _sync_generate() -> None:
    """Regénération complète avec les params courants (appelable depuis le thread OSC)."""
    p = _state.get("last_p") or _read_form()
    _state["last_p"] = p
    if _state["voices"]:
        _state["history"].append((_state["voices"][:], list(_state["plocks"]), dict(p)))
    voices = _apply_voice_steps(_apply_note_remap(_apply_locks(_build_voices(p))))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(p, voices)
    if p["mode"] in ("volca_drum", "volca_kick", "volca_fm", "microfreak"):
        _state["plocks"] = _generate_plocks(voices, p)


_PARAM_CLAMPS: dict[str, tuple] = {
    "bpm":         (40,   240,  int),
    "chaos":       (0.0,  1.0,  float),
    "gravity":     (0.0,  1.0,  float),
    "swing":       (0.0,  1.0,  float),
    "microtiming": (0.0,  1.0,  float),
    "steps":       (8,    256,  int),
    "cc_depth":    (0.0,  1.0,  float),
}
_regen_timer: threading.Timer | None = None


def _schedule_regen(delay: float = 0.4) -> None:
    global _regen_timer
    if _regen_timer is not None:
        _regen_timer.cancel()
    _regen_timer = threading.Timer(delay, _sync_generate)
    _regen_timer.daemon = True
    _regen_timer.start()


def _osc_handle_param(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    if not args:
        return
    if not _state.get("last_p"):
        _state["last_p"] = _read_form()
    parts = address.strip("/").split("/")   # ["bang","param","bpm"]
    if len(parts) < 3:
        return
    name = parts[2]
    if name not in _PARAM_CLAMPS:
        return
    lo, hi, cast = _PARAM_CLAMPS[name]
    try:
        val = cast(max(lo, min(hi, cast(args[0]))))
    except (TypeError, ValueError):
        return
    _state["last_p"][name] = val
    _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"] or [])
    _sse_signal(f"param:{name}")
    if name in ("chaos", "gravity", "swing") and _state.get("voices"):
        _schedule_regen()


def _osc_handle_generate(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    _sync_generate()
    _sse_signal("pattern")


def _osc_handle_vary(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    _sync_vary()
    _sse_signal("pattern")


def _osc_handle_density(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    if not args:
        return
    parts = address.strip("/").split("/")   # ["bang","density","Kick"]
    if len(parts) < 3:
        return
    name = parts[2]
    try:
        val = max(0.0, min(1.0, float(args[0])))
    except (TypeError, ValueError):
        return
    _state["voice_density"][name] = val
    _sse_signal(f"density:{name}")
    if _state.get("voices"):
        _schedule_regen()


def _osc_handle_mute(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    parts = address.strip("/").split("/")   # ["bang","mute","2"]
    if len(parts) < 3:
        return
    try:
        idx = int(parts[2])
        mute = bool(int(args[0])) if args else True
    except (TypeError, ValueError):
        return
    muted = _state.get("muted_voices", set())
    if mute:
        muted.add(idx)
    else:
        muted.discard(idx)
    _state["muted_voices"] = muted


def _osc_handle_lock(address: str, *args) -> None:
    _osc_log_entry("RX", address, args)
    parts = address.strip("/").split("/")   # ["bang","lock","2"]
    if len(parts) < 3:
        return
    try:
        idx = int(parts[2])
        lock = bool(int(args[0])) if args else True
    except (TypeError, ValueError):
        return
    locked = _state.get("locked_voices", set())
    if lock:
        locked.add(idx)
    else:
        locked.discard(idx)


def _osc_rx_start(port: int) -> None:
    try:
        from pythonosc.dispatcher import Dispatcher
        from pythonosc.osc_server import ThreadingOSCUDPServer
    except ImportError:
        print("OSC RX: python-osc non installé.")
        return

    prev = _state.get("osc_rx_server")
    if prev:
        try:
            prev.shutdown()
        except Exception:
            pass

    disp = Dispatcher()
    disp.map("/bang/param/*",   _osc_handle_param)
    disp.map("/bang/generate",  _osc_handle_generate)
    disp.map("/bang/vary",      _osc_handle_vary)
    disp.map("/bang/density/*", _osc_handle_density)
    disp.map("/bang/lock/*",    _osc_handle_lock)
    disp.map("/bang/mute/*",    _osc_handle_mute)

    try:
        server = ThreadingOSCUDPServer(("0.0.0.0", port), disp)
    except OSError as e:
        print(f"OSC RX: impossible de lier le port {port} — {e}")
        return

    _state["osc_rx_server"] = server
    t = threading.Thread(target=server.serve_forever, daemon=True, name="osc-rx")
    t.start()
    _state["osc_rx_thread"] = t


def _osc_rx_stop() -> None:
    server = _state.get("osc_rx_server")
    if server:
        try:
            server.shutdown()
        except Exception:
            pass
    _state["osc_rx_server"] = None
    _state["osc_rx_thread"] = None


def _osc_log_entry(direction: str, addr: str, args) -> None:
    _state["osc_log"].appendleft({
        "ts":   time.strftime("%H:%M:%S"),
        "dir":  direction,
        "addr": addr,
        "args": str(list(args))[:80] if args else "",
    })


def _lfo_val(shape: str, phase: float) -> float:
    """Valeur LFO normalisée [0..1] pour une phase [0..1]."""
    import math
    if shape == "sin":  return 0.5 + 0.5 * math.sin(2 * math.pi * phase)
    if shape == "tri":  return 2 * phase if phase < 0.5 else 2 * (1 - phase)
    if shape == "ramp": return phase
    return random.random()  # rnd


def _osc_clock_loop() -> None:
    """Thread background : émet les triggers OSC au BPM du pattern courant."""
    try:
        from pythonosc.udp_client import SimpleUDPClient
    except ImportError:
        print("OSC: python-osc non installé. Faites : uv add python-osc")
        _state["osc_enabled"] = False
        return

    client: SimpleUDPClient | None = None
    last_addr = (None, None)
    step = 0
    cycle_count = 0
    dropped_voices: set[str] = set()
    markov_notes: dict[str, list[int]] = {}

    while _state.get("osc_enabled"):
        p      = _state.get("last_p")
        voices = _state.get("voices") or []

        if not p or not voices:
            time.sleep(0.05)
            continue

        bpm      = p["bpm"]
        n_steps  = p["steps"]
        step_dur = 60.0 / (bpm * 4)   # durée 1 step (double-croche)

        host = _state.get("osc_host", "100.64.201.127")
        port = _state.get("osc_port", 57120)
        if (host, port) != last_addr:
            client    = SimpleUDPClient(host, int(port))
            last_addr = (host, port)

        t0 = time.perf_counter()

        # Régénération des notes Markov + LFO drop au début de chaque cycle
        if step == 0:
            cycle_count += 1
            markov_notes = {}
            engine = _state.get("engine")
            if engine:
                mk_idx = 0   # index dans engine.voices (skip CC)
                for note, dna, vtype in voices:
                    if vtype == "cc":
                        continue
                    if (vtype in ("markov", "bl") or vtype.startswith("ksp")) and mk_idx < len(engine.voices):
                        ev = engine.voices[mk_idx]
                        if ev.get("type") == "markov":
                            name = _voice_label(note, vtype)
                            markov_notes[name] = ev["chain"].generate(n_steps)
                    mk_idx += 1
            # Décision drop par voix (voice_drop + LFO target=drop)
            voice_lfo_map  = _state.get("voice_lfo", {})
            voice_drop_map = _state.get("voice_drop", {})
            dropped_voices = set()
            for _n, _d, _vt in voices:
                if _vt in ("cc", "babka"): continue
                _nm  = _voice_label(_n, _vt)
                _drop = voice_drop_map.get(_nm, 1.0)
                _lfo = voice_lfo_map.get(_nm)
                if _lfo and _lfo.get("target") == "drop":
                    _ph = (cycle_count * _lfo["freq"]) % 1.0
                    _lv = _lfo_val(_lfo["shape"], _ph)
                    _drop = max(0.0, min(1.0, _drop * (1 - _lfo["depth"] + _lv * _lfo["depth"])))
                if _drop < 1.0 and random.random() > _drop:
                    dropped_voices.add(_nm)

        # /bang/clock step total_steps
        try:
            assert client is not None
            client.send_message("/bang/clock", [step, n_steps])
            if step == 0:
                _osc_log_entry("TX", "/bang/clock", [0, n_steps])

            voice_lfo_map = _state.get("voice_lfo", {})
            for note, dna, vtype in voices:
                if vtype == "cc" or (note == 0 and not vtype.startswith("ksp")):
                    continue
                name    = _voice_label(note, vtype)
                if name in dropped_voices:
                    continue
                density = _state["voice_density"].get(name, 1.0)
                _lfo = voice_lfo_map.get(name)
                if _lfo and _lfo.get("target") == "density":
                    _ph = ((step / n_steps) * _lfo["freq"]) % 1.0
                    _lv = _lfo_val(_lfo["shape"], _ph)
                    density = max(0.0, min(1.0, density * (1 - _lfo["depth"] + _lv * _lfo["depth"])))

                if vtype == "babka":
                    continue  # timing Babka incompatible avec un clock step-par-step

                compiled = compile_dna(dna)
                row      = compiled[step % len(compiled)]
                trig, vel, prob, ratch, jit = row

                if trig and random.random() < prob * density:
                    osc_note = markov_notes.get(name, [note] * n_steps)[step] if (vtype in ("markov", "bl") or vtype.startswith("ksp")) else note
                    client.send_message(f"/bang/{name}", [step, int(vel), int(osc_note)])
                    _osc_log_entry("TX", f"/bang/{name}", [step, int(vel), int(osc_note)])
        except Exception:
            pass   # perte réseau → on continue

        step = (step + 1) % n_steps

        elapsed   = time.perf_counter() - t0
        remaining = step_dur - elapsed
        if remaining > 0:
            time.sleep(remaining)


def _osc_start() -> None:
    if _state.get("osc_thread") and _state["osc_thread"].is_alive():
        return
    _state["osc_enabled"] = True
    t = threading.Thread(target=_osc_clock_loop, daemon=True, name="osc-clock")
    t.start()
    _state["osc_thread"] = t
    _osc_rx_start(_state.get("osc_rx_port", 57121))


def _osc_stop() -> None:
    _state["osc_enabled"] = False
    t = _state.get("osc_thread")
    if t and t.is_alive():
        t.join(timeout=1.0)
    _state["osc_thread"] = None
    _osc_rx_stop()


# ---------------------------------------------------------------------------
# MIDI serveur (rtmidi)
# ---------------------------------------------------------------------------

def _midi_srv_ports() -> list[str]:
    try:
        import rtmidi
        m = rtmidi.MidiOut()
        return m.get_ports()
    except Exception:
        return []


def _midi_srv_clock_loop() -> None:
    try:
        import rtmidi
    except ImportError:
        print("MIDI: python-rtmidi non installé.")
        _state["midi_srv_enabled"] = False
        return

    midi_out = rtmidi.MidiOut()
    port_idx = int(_state.get("midi_srv_port", 0))
    ports = midi_out.get_ports()
    if not ports:
        print("MIDI: aucun port disponible.")
        _state["midi_srv_enabled"] = False
        return
    port_idx = min(port_idx, len(ports) - 1)

    try:
        midi_out.open_port(port_idx)
    except Exception as e:
        print(f"MIDI: impossible d'ouvrir le port {port_idx}: {e}")
        _state["midi_srv_enabled"] = False
        return

    step = 0
    cycle_count = 0
    dropped_voices: set[str] = set()
    markov_notes: dict[str, list[int]] = {}
    pending_off: list[tuple[float, int, int]] = []  # (time, channel, note)

    while _state.get("midi_srv_enabled"):
        p      = _state.get("last_p")
        voices = _state.get("voices") or []

        if not p or not voices:
            time.sleep(0.05)
            continue

        bpm      = p["bpm"]
        n_steps  = p["steps"]
        step_dur = 60.0 / (bpm * 4)
        gate_dur = step_dur * 0.75
        ch_drums     = int(_state.get("midi_srv_channel", 9))
        ch_melodic   = 0 if ch_drums != 0 else 1
        voice_ch_map = _state.get("voice_midi_ch", {})
        voice_sw_map = _state.get("voice_swing", {})

        t0 = time.perf_counter()

        # Envoyer les note-off en attente
        still = []
        for off_t, ch, n in pending_off:
            if t0 >= off_t:
                try: midi_out.send_message([0x80 | ch, n, 0])
                except Exception: pass
            else:
                still.append((off_t, ch, n))
        pending_off = still

        # Régénération Markov + LFO drop au début du cycle
        if step == 0:
            cycle_count += 1
            markov_notes = {}
            engine = _state.get("engine")
            if engine:
                mk_idx = 0
                for note, dna, vtype in voices:
                    if vtype == "cc":
                        continue
                    if (vtype in ("markov", "bl") or vtype.startswith("ksp")) and mk_idx < len(engine.voices):
                        ev = engine.voices[mk_idx]
                        if ev.get("type") == "markov":
                            name = _voice_label(note, vtype)
                            markov_notes[name] = ev["chain"].generate(n_steps)
                    mk_idx += 1
            # Décision drop par voix (voice_drop + LFO target=drop)
            voice_lfo_map  = _state.get("voice_lfo", {})
            voice_drop_map = _state.get("voice_drop", {})
            dropped_voices = set()
            for _n, _d, _vt in voices:
                if _vt in ("cc", "babka"): continue
                _nm   = _voice_label(_n, _vt)
                _drop = voice_drop_map.get(_nm, 1.0)
                _lfo  = voice_lfo_map.get(_nm)
                if _lfo and _lfo.get("target") == "drop":
                    _ph = (cycle_count * _lfo["freq"]) % 1.0
                    _lv = _lfo_val(_lfo["shape"], _ph)
                    _drop = max(0.0, min(1.0, _drop * (1 - _lfo["depth"] + _lv * _lfo["depth"])))
                if _drop < 1.0 and random.random() > _drop:
                    dropped_voices.add(_nm)

        # Collecter les triggers de ce step, triés par temps de déclenchement
        voice_lfo_map = _state.get("voice_lfo", {})
        events: list[tuple[float, int, int, int]] = []  # (trigger_t, ch, midi_note, vel)
        for note, dna, vtype in voices:
            if vtype in ("cc", "babka") or (note == 0 and not vtype.startswith("ksp")):
                continue
            name    = _voice_label(note, vtype)
            if name in dropped_voices:
                continue
            density = _state["voice_density"].get(name, 1.0)
            _lfo = voice_lfo_map.get(name)
            if _lfo and _lfo.get("target") == "density":
                _ph = ((step / n_steps) * _lfo["freq"]) % 1.0
                _lv = _lfo_val(_lfo["shape"], _ph)
                density = max(0.0, min(1.0, density * (1 - _lfo["depth"] + _lv * _lfo["depth"])))
            compiled = compile_dna(dna)
            row      = compiled[step % len(compiled)]
            trig, vel, prob, ratch, jit = row
            if trig and random.random() < prob * density:
                is_melodic = vtype in ("markov", "bl") or vtype.startswith(("ksp", "vd", "vfm", "mf"))
                ch         = voice_ch_map.get(name, ch_melodic if is_melodic else ch_drums)
                midi_note  = markov_notes.get(name, [note] * n_steps)[step] if is_melodic else note
                # Swing : décalage sur steps impairs
                sw = voice_sw_map.get(name, 0.0)
                swing_delay = (sw * step_dur * 0.33) if (step % 2 == 1 and sw > 0) else 0.0
                events.append((t0 + swing_delay, ch, int(midi_note) & 0x7F, int(vel) & 0x7F))

        # Envoyer les events dans l'ordre chronologique
        events.sort(key=lambda e: e[0])
        for trigger_t, ch, midi_note, vel in events:
            delay = trigger_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            try:
                midi_out.send_message([0x90 | ch, midi_note, vel])
                pending_off.append((time.perf_counter() + gate_dur, ch, midi_note))
            except Exception:
                pass

        step = (step + 1) % n_steps
        elapsed   = time.perf_counter() - t0
        remaining = step_dur - elapsed
        if remaining > 0:
            time.sleep(remaining)

    # Note-off sur tous les sons en cours à l'arrêt
    for _, ch, n in pending_off:
        try: midi_out.send_message([0x80 | ch, n, 0])
        except Exception: pass
    midi_out.close_port()


def _midi_srv_start() -> None:
    if _state.get("midi_srv_thread") and _state["midi_srv_thread"].is_alive():
        return
    _state["midi_srv_enabled"] = True
    t = threading.Thread(target=_midi_srv_clock_loop, daemon=True, name="midi-srv")
    t.start()
    _state["midi_srv_thread"] = t


def _midi_srv_stop() -> None:
    _state["midi_srv_enabled"] = False
    t = _state.get("midi_srv_thread")
    if t and t.is_alive():
        t.join(timeout=2.0)
    _state["midi_srv_thread"] = None


def _build_midi_srv_btn() -> str:
    enabled = _state.get("midi_srv_enabled", False)
    ports   = _midi_srv_ports()
    port_i  = int(_state.get("midi_srv_port", 0))
    port_n  = ports[port_i] if ports and port_i < len(ports) else "—"
    cls     = "btn-midi-srv active" if enabled else "btn-midi-srv"
    label   = f"MIDI ●" if enabled else "MIDI ○"
    tip     = f"MIDI serveur — {port_n} ({'actif' if enabled else 'inactif'})"
    return f'<span id="midi-srv-btn"><button class="{cls}" onclick="bangToggleMidiSrvPanel(this)" title="{tip}">{label}</button></span>'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render("index.html",
        voices=[(n, dna_html(d), d, t, _voice_label(n, t)) for n, d, t in _state["voices"]],
        voice_thin=_state["voice_thin"],
        max_poly=_state["max_poly"],
        log=_state["log"][-20:],
        weather=_state["weather"],
        last_seed=_state["last_seed"],
        last_p=_state["last_p"],
        app_version=APP_VERSION,
        osc_enabled=_state.get("osc_enabled", False),
        osc_host=_state.get("osc_host", "100.64.201.127"),
        osc_port=_state.get("osc_port", 57120),
        osc_rx_port=_state.get("osc_rx_port", 57121),
        midi_srv_enabled=_state.get("midi_srv_enabled", False),
        ableton_host=_state.get("ableton_host", "127.0.0.1"),
        ableton_port=_state.get("ableton_port", 11000),
        ableton_track_offset=_state.get("ableton_track_offset", 0),
        ableton_slot=_state.get("ableton_slot", 0),
        seq_html=_build_seq_html(),
        pr_html=_build_pr_html(_state['voices'], _state['last_p']['steps'], _state.get('plocks') or None) if _state.get('voices') and _state.get('last_p') else '',
        voice_density=_state.get("voice_density", {}),
        voice_chords=_state.get("voice_chords", {}),
        voice_steps=_state.get("voice_steps", {}),
        voice_offset=_state.get("voice_offset", {}),
        voice_drop=_state.get("voice_drop", {}),
        voice_vel_lane=_state.get("voice_vel_lane", {}),
        voice_prob_lane=_state.get("voice_prob_lane", {}),
        voice_lfo=_state.get("voice_lfo", {}),
        voice_midi_ch=_state.get("voice_midi_ch", {}),
        voice_swing=_state.get("voice_swing", {}),
        locked_voices=_state.get("locked_voices", set()),
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request:     Request,
    mode:        Annotated[str,   Form()] = "morph",
    chaos:       Annotated[float, Form()] = 0.30,
    bpm:         Annotated[int,   Form()] = 110,
    steps:       Annotated[int,   Form()] = 64,
    gravity:     Annotated[float, Form()] = 0.70,
    cc_depth:    Annotated[float, Form()] = 0.50,
    out:         Annotated[str,   Form()] = "bang_out.mid",
    temporal:    Annotated[str,   Form()] = "",
    vel_floor:   Annotated[int,   Form()] = 0,
    vel_ceiling: Annotated[int,   Form()] = 127,
    vel_curve:   Annotated[float, Form()] = 1.0,
    root:        Annotated[str,   Form()] = "A",
    scale:       Annotated[str,   Form()] = "penta_min",
    seed:           Annotated[str,   Form()] = "",
    swing:          Annotated[float, Form()] = 0.0,
    markov_channel: Annotated[int,   Form()] = 9,
    vel_humanize:   Annotated[int,   Form()] = 0,
    microtiming:    Annotated[float, Form()] = 1.0,
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal,
                   vel_floor, vel_ceiling, vel_curve, root, scale, seed, swing, markov_channel, vel_humanize, microtiming)
    # Snapshot avant génération (pour undo)
    if _state["voices"] and _state["last_p"]:
        _state["history"].append((_state["voices"][:], list(_state["plocks"]), dict(_state["last_p"])))

    _state["last_p"]     = p
    _state["ab_current"] = None  # nouvelle génération = hors slot A/B
    voices = _apply_voice_steps(_apply_note_remap(_apply_locks(_build_voices(p))))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(p, voices)

    plocks = _generate_plocks(voices, p) if p["mode"] in ("volca_drum", "volca_kick", "volca_fm", "microfreak") else []
    _state["plocks"] = plocks

    pr_html = _build_pr_html(voices, p["steps"], plocks)
    oob     = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/export", response_class=HTMLResponse)
async def export(
    request:     Request,
    mode:        Annotated[str,   Form()] = "morph",
    chaos:       Annotated[float, Form()] = 0.30,
    bpm:         Annotated[int,   Form()] = 110,
    steps:       Annotated[int,   Form()] = 64,
    gravity:     Annotated[float, Form()] = 0.70,
    cc_depth:    Annotated[float, Form()] = 0.50,
    out:         Annotated[str,   Form()] = "bang_out.mid",
    temporal:    Annotated[str,   Form()] = "",
    dest_dir:    Annotated[str,   Form()] = "",
    vel_floor:   Annotated[int,   Form()] = 0,
    vel_ceiling: Annotated[int,   Form()] = 127,
    vel_curve:   Annotated[float, Form()] = 1.0,
    root:        Annotated[str,   Form()] = "A",
    scale:       Annotated[str,   Form()] = "penta_min",
    seed:           Annotated[str,   Form()] = "",
    swing:          Annotated[float, Form()] = 0.0,
    markov_channel: Annotated[int,   Form()] = 9,
    vel_humanize:   Annotated[int,   Form()] = 0,
    microtiming:    Annotated[float, Form()] = 1.0,
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal,
                   vel_floor, vel_ceiling, vel_curve, root, scale, seed, swing, markov_channel, vel_humanize, microtiming)

    if _state["engine"] is None:
        voices = _apply_note_remap(_build_voices(p))
        _state["voices"] = voices
        _state["engine"] = _assemble_engine(p, voices)
        if p["mode"] in ("volca_drum", "volca_kick", "volca_fm", "microfreak"):
            _state["plocks"] = _generate_plocks(voices, p)

    target_dir = Path(dest_dir).expanduser() if dest_dir.strip() else EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    if dest_dir.strip() and str(target_dir) not in _state["recent_dirs"]:
        _state["recent_dirs"] = ([str(target_dir)] + _state["recent_dirs"])[:5]

    export_path = str(target_dir / p["out"])
    try:
        densities = [
            _state["voice_density"].get(_voice_label(n, t), 1.0)
            for n, _d, t in _state["voices"]
        ]
        chord_types = [
            _state["voice_chords"].get(_voice_label(n, t), "mono")
            for n, _d, t in _state["voices"]
        ]
        _state["engine"].export_midi(
            num_steps=p["steps"],
            filename=export_path,
            weather=_state["weather"],
            temporal_jitter=p["temporal"],
            seed=p["seed"] or None,
            swing=p["swing"],
            plocks=_state.get("plocks") or None,
            vel_humanize=p.get("vel_humanize", 0),
            densities=densities,
            voice_chords=chord_types,
            microtiming=p.get("microtiming", 1.0),
        )
        seed        = (_state["engine"].last_seed or "")[:16]
        _state["last_seed"] = _state["engine"].last_seed
        _state["last_file"] = p["out"]

        meteo  = f"{_state['weather']['temperature']}°C" if _state["weather"] else ""
        tmp    = "+temporal" if p["temporal"] else ""
        ts     = datetime.now().strftime("%H:%M:%S")
        entry  = {
            "ts":    ts,
            "file":  p["out"],
            "seed":  seed,
            "bpm":   p["bpm"],
            "mode":  p["mode"],
            "meteo": meteo,
            "tmp":   tmp,
            "ok":    True,
        }
    except Exception as e:
        ts    = datetime.now().strftime("%H:%M:%S")
        entry = {"ts": ts, "file": p["out"], "error": str(e), "ok": False}

    _state["log"].append(entry)

    log_html  = jinja.get_template("_log_entry.html").render(entry=entry)
    last_seed = _state.get("last_seed") or ""
    seed_oob  = (
        f'<input id="seed-input" name="seed" type="text" class="tb-w-lg" '
        f'placeholder="seed (optionnel)" value="{last_seed}" '
        f'hx-swap-oob="outerHTML:#seed-input">'
    )
    return HTMLResponse(log_html + seed_oob)


_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_TAG_RE  = re.compile(r"-(\d{8}-[0-9a-f]{8})$")

# (group_num, basename, mode, chaos_mult_start, chaos_mult_end, steps, count, is_break)
_SONG_STRUCTURE = [
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


def _morph_voices(voices: list, intensity: float) -> list:
    """Morphe le DNA de chaque voix pour rester proche de la variation précédente."""
    return [(note, mutate_dna(dna, intensity=intensity), vtype) for note, dna, vtype in voices]


def _generate_song(chaos: float, bpm: int, gravity: float, cc_depth: float) -> tuple[str, str, list[str]]:
    """Génère 30 fichiers MIDI + ZIP, persiste les params. Retourne (html_log, tag, files)."""
    uid  = secrets.token_hex(4)
    date = datetime.now().strftime("%Y%m%d")
    tag  = f"{date}-{uid}"
    ts   = datetime.now().strftime("%H:%M:%S")

    # Persister les paramètres pour la fonction regen
    song_params = _load_song_params()
    song_params[tag] = {"chaos": chaos, "bpm": bpm, "gravity": gravity, "cc_depth": cc_depth}
    _save_song_params(song_params)

    files: list[str] = []
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for grp_num, basename, mode, cstart, cend, steps, count, is_break in _SONG_STRUCTURE:
            prev_voices: list | None = None
            for i in range(count):
                letter        = _LETTERS[i]
                cmult         = cstart if count == 1 else cstart + (i / (count - 1)) * (cend - cstart)
                section_chaos = min(1.0, chaos * cmult)
                if count == 1:
                    section_name = basename
                elif basename[-1].isdigit():
                    section_name = f"{basename}-{i + 1}"
                else:
                    section_name = f"{basename}{i + 1}"
                fname = f"{grp_num:02d}{letter}-{section_name}-{tag}.mid"
                p = {
                    "mode": mode, "chaos": section_chaos,
                    "bpm": bpm, "steps": steps,
                    "gravity": gravity, "cc_depth": cc_depth,
                    "out": fname, "temporal": False,
                }
                if is_break or prev_voices is None:
                    voices = _apply_note_remap(_build_voices(p))
                else:
                    morph_intensity = 0.08 + section_chaos * 0.06
                    voices = _morph_voices(prev_voices, morph_intensity)
                prev_voices = voices
                engine = _assemble_engine(p, voices)
                fpath  = str(EXPORT_DIR / fname)
                engine.export_midi(num_steps=steps, filename=fpath, weather=_state["weather"])
                zf.write(fpath, fname)
                files.append(fname)

    zip_name = f"bang-{tag}.zip"
    (EXPORT_DIR / zip_name).write_bytes(zip_buf.getvalue())

    html  = f'<div class="log-entry log-song" style="flex-direction:column;gap:.3rem;padding:.5rem 0">'
    html += f'<div style="display:flex;gap:.75rem;align-items:center">'
    html += f'<span class="log-ts">{ts}</span>'
    html += f'<strong style="color:var(--primary)">SONG</strong>'
    html += f'<span class="log-tag">{bpm} BPM</span>'
    html += f'<span class="log-tag">{tag}</span>'
    html += (f'<a href="/download/{zip_name}" download '
             f'style="color:var(--primary);text-decoration:none;font-weight:bold" draggable="true" '
             f'ondragstart="event.dataTransfer.setData(\'DownloadURL\',\'application/zip:{zip_name}:\''
             f'+window.location.origin+\'/download/{zip_name}\')">⬡ {zip_name}</a>')
    html += f'</div><div style="display:flex;flex-wrap:wrap;gap:.4rem .75rem">'
    for fname in files:
        m     = _TAG_RE.search(Path(fname).stem)
        label = Path(fname).stem[:m.start()] if m else fname
        html += (
            f'<a class="log-file" href="/download/{fname}" download draggable="true" '
            f'title="Drag → Live" '
            f'ondragstart="event.dataTransfer.setData(\'DownloadURL\',\'audio/midi:{fname}:\''
            f'+window.location.origin+\'/download/{fname}\')">⠿ {label}</a>'
        )
    html += '</div></div>'
    return html, tag, files


@app.post("/export/song", response_class=HTMLResponse)
async def export_song(
    request:  Request,
    chaos:    Annotated[float, Form()] = 0.50,
    bpm:      Annotated[int,   Form()] = 110,
    gravity:  Annotated[float, Form()] = 0.70,
    cc_depth: Annotated[float, Form()] = 0.50,
):
    html, tag, files = _generate_song(chaos, bpm, gravity, cc_depth)
    return HTMLResponse(html, headers={
        "X-Song-Tag":   tag,
        "X-Song-Files": ",".join(files),
    })


def _scan_archive() -> tuple[dict, list]:
    """Retourne (songs_by_tag, individuals) — détection par suffixe YYYYMMDD-xxxxxxxx."""
    songs: dict[str, list[tuple[str, float]]] = {}
    individuals: list[tuple[str, float]] = []
    for f in EXPORT_DIR.glob("*.mid"):
        mtime = f.stat().st_mtime
        m = _TAG_RE.search(f.stem)
        if m:
            songs.setdefault(m.group(1), []).append((f.name, mtime))
        else:
            individuals.append((f.name, mtime))
    songs_sorted = dict(sorted(
        songs.items(),
        key=lambda kv: max(mt for _, mt in kv[1]),
        reverse=True,
    ))
    individuals.sort(key=lambda x: x[1], reverse=True)
    return songs_sorted, individuals


def _drag(fname: str, mime: str = "audio/midi") -> str:
    return (
        f'ondragstart="event.dataTransfer.setData(\'DownloadURL\','
        f'\'{mime}:{fname}:\'+window.location.origin+\'/download/{fname}\')"'
    )


def _build_archive_html() -> str:
    songs, individuals = _scan_archive()
    favs       = set(_load_favorites())
    all_params = _load_song_params()

    # Favoris en tête, puis tri par mtime desc
    songs_items = sorted(
        songs.items(),
        key=lambda kv: (kv[0] not in favs, -max(mt for _, mt in kv[1])),
    )

    h = '<div class="archive-wrap">'
    h += '<h4 class="archive-head">Songs</h4>'
    if not songs_items:
        h += '<p class="archive-empty">Aucune song générée.</p>'

    for tag, files in songs_items:
        files_sorted = sorted(files, key=lambda x: x[0])
        zip_name   = f"bang-{tag}.zip"
        zip_exists = (EXPORT_DIR / zip_name).exists()
        is_fav     = tag in favs
        params     = all_params.get(tag, {})
        card_cls   = "archive-song is-fav" if is_fav else "archive-song"
        star       = "⭐" if is_fav else "☆"
        fav_title  = "Retirer des favoris" if is_fav else "Ajouter aux favoris"

        h += f'<div class="{card_cls}"><div class="archive-song-head">'
        h += f'<span class="archive-tag">{tag}</span>'
        h += (f'<button class="archive-fav" hx-post="/song/favorite/{tag}" '
              f'hx-target="#archive-content" hx-swap="innerHTML" '
              f'title="{fav_title}">{star}</button>')
        if params:
            h += f'<span class="log-tag">{params.get("bpm", "?")} BPM</span>'
            h += (f'<button class="archive-regen" '
                  f'hx-post="/song/regen/{tag}" '
                  f'hx-target="#log-entries" hx-swap="afterbegin" '
                  f'hx-on:htmx:after-request="closeArchive()" '
                  f'title="Régénérer depuis ces paramètres">↺ Regen</button>')
        if zip_exists:
            h += (f'<a class="archive-zip" href="/download/{zip_name}" download draggable="true" '
                  f'{_drag(zip_name, "application/zip")}>⬡ ZIP</a>')
        h += '</div><div class="archive-sections">'
        for fname, _ in files_sorted:
            m     = _TAG_RE.search(Path(fname).stem)
            label = Path(fname).stem[:m.start()] if m else fname
            h += (f'<a class="log-file" href="/download/{fname}" download '
                  f'draggable="true" title="{fname}" {_drag(fname)}>⠿ {label}</a>')
        h += '</div></div>'

    h += '<h4 class="archive-head" style="margin-top:1rem">Exports individuels</h4>'
    if not individuals:
        h += '<p class="archive-empty">Aucun export individuel.</p>'
    for fname, mtime in individuals:
        ts_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        h += (f'<div class="log-entry"><span class="log-ts">{ts_str}</span>'
              f'<a class="log-file" href="/download/{fname}" download draggable="true" '
              f'title="{fname}" {_drag(fname)}>⠿ {fname}</a></div>')

    h += '</div>'
    return h


@app.get("/archive", response_class=HTMLResponse)
async def archive():
    return HTMLResponse(_build_archive_html())


@app.post("/song/favorite/{tag}", response_class=HTMLResponse)
async def toggle_favorite(tag: str):
    favs = _load_favorites()
    if tag in favs:
        favs.remove(tag)
    else:
        favs.insert(0, tag)
    _save_favorites(favs)
    return HTMLResponse(_build_archive_html())


@app.post("/song/regen/{tag}", response_class=HTMLResponse)
async def regen_song(tag: str):
    p        = _load_song_params().get(tag, {})
    chaos    = float(p.get("chaos",    0.50))
    bpm      = int(p.get("bpm",        110))
    gravity  = float(p.get("gravity",  0.70))
    cc_depth = float(p.get("cc_depth", 0.50))
    html, new_tag, files = _generate_song(chaos, bpm, gravity, cc_depth)
    return HTMLResponse(html, headers={
        "X-Song-Tag":   new_tag,
        "X-Song-Files": ",".join(files),
    })


@app.post("/weather", response_class=HTMLResponse)
async def weather_route(request: Request):
    w = fetch_weather()
    if w:
        _state["weather"] = w
    return render("_weather.html", weather=w)


@app.get("/browse")
async def browse(path: str = ""):
    target = Path(path).expanduser().resolve() if path else Path.home()
    try:
        dirs = sorted(
            [d for d in target.iterdir() if d.is_dir() and not d.name.startswith(".")],
            key=lambda d: d.name.lower(),
        )
    except (PermissionError, FileNotFoundError):
        dirs = []
    parent = str(target.parent) if target != target.parent else None
    return {
        "path":   str(target),
        "parent": parent,
        "dirs":   [{"name": d.name, "path": str(d)} for d in dirs],
    }


@app.get("/next-filename")
async def next_filename(mode: str = "morph", dest_dir: str = ""):
    target_dir = Path(dest_dir).expanduser() if dest_dir else EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(target_dir.glob(f"gen-{mode}-*.mid"))
    if not existing:
        next_name = f"gen-{mode}-001.mid"
    else:
        last = existing[-1].stem
        m = re.search(r"-(\d+)$", last)
        n = int(m.group(1)) + 1 if m else 1
        next_name = f"gen-{mode}-{n:03d}.mid"
    return {
        "filename":    next_name,
        "current_dir": str(target_dir),
        "recent_dirs": _state["recent_dirs"],
        "default_dir": str(EXPORT_DIR),
    }


@app.post("/notes", response_class=HTMLResponse)
async def notes_remap(request: Request):
    form = await request.form()
    for key, val in form.items():
        if key.startswith("remap_"):
            name = key[6:]
            try:
                _state["note_remap"][name] = max(0, min(127, int(val)))
            except ValueError:
                pass

    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")

    voices = _apply_voice_steps(_apply_note_remap(_build_voices(_state["last_p"])))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)

    voices_html = _build_voices_html(voices)
    pr_rows = _build_pianoroll_rows(voices, _state["last_p"]["steps"])
    pr_html = jinja.get_template("_pianoroll.html").render(rows=pr_rows, steps=_state["last_p"]["steps"])
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(voices_html + oob)


@app.get("/download/{filename}")
async def download(filename: str):
    path = EXPORT_DIR / filename
    if not path.exists():
        return HTMLResponse("<p>Fichier introuvable</p>", status_code=404)
    return FileResponse(str(path), filename=filename, media_type="audio/midi")


def _export_single_voice(idx: int) -> tuple[str, str] | None:
    """Génère un clip MIDI pour une seule voix. Retourne (fpath, fname) ou None."""
    if not _state["voices"] or not _state["last_p"]:
        return None
    if not (0 <= idx < len(_state["voices"])):
        return None
    note, dna, vtype = _state["voices"][idx]
    if vtype == "cc":
        return None
    name = _voice_label(note, vtype)
    p    = _state["last_p"]
    engine = _assemble_engine(p, [(note, dna, vtype)])
    safe_name = re.sub(r"[^\w\-]", "_", name)
    fname = f"{safe_name}-clip.mid"
    fpath = str(EXPORT_DIR / fname)
    engine.export_midi(
        num_steps=p["steps"],
        filename=fpath,
        swing=p.get("swing", 0.0),
        microtiming=p.get("microtiming", 1.0),
        densities=[_state["voice_density"].get(name, 1.0)],
        voice_chords=[_state.get("voice_chords", {}).get(name, "mono")],
        weather=_state["weather"],
    )
    return fpath, fname


@app.get("/export/clip")
async def export_clip(idx: int = 0):
    """Clip MIDI mono-voix — pour drag-to-Ableton."""
    result = _export_single_voice(idx)
    if result is None:
        return HTMLResponse("No voice", status_code=404)
    fpath, fname = result
    return FileResponse(fpath, filename=fname, media_type="audio/midi")


@app.get("/export/clips")
async def export_clips():
    """Toutes les voix en clips MIDI séparés — archive zip."""
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("No voices", status_code=404)
    ts      = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_name = f"bang-clips-{ts}.zip"
    zip_path = EXPORT_DIR / zip_name
    zip_buf  = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx in range(len(_state["voices"])):
            result = _export_single_voice(idx)
            if result:
                fpath, fname = result
                zf.write(fpath, fname)
    zip_path.write_bytes(zip_buf.getvalue())
    return FileResponse(str(zip_path), filename=zip_name, media_type="application/zip")


@app.get("/export/strudel")
async def export_strudel():
    """Convertit le pattern courant en mini-notation Strudel/TidalCycles."""
    if not _state["voices"] or not _state["last_p"]:
        return {"ok": False, "code": "// Générez un pattern d'abord"}
    p   = _state["last_p"]
    bpm = p["bpm"]
    lines = []
    for note, dna, vtype in _state["voices"]:
        if vtype in ("cc", "babka"):
            continue
        name       = _voice_label(note, vtype)
        is_melodic = vtype in ("markov", "bl") or vtype.startswith("ksp")
        sample     = (_midi_to_strudel_note(note) if is_melodic
                      else _STRUDEL_SAMPLES.get(note,
                           re.sub(r"[^\w]", "", name.lower())[:8]))
        compiled   = compile_dna(dna)
        tokens     = []
        for cell in compiled:
            if cell[0] <= 0:
                tokens.append("~")
            elif int(cell[3]) > 1:
                tokens.append(f"{sample}*{int(cell[3])}")
            elif float(cell[2]) < 0.75:
                tokens.append(f"{sample}?{float(cell[2]):.1f}")
            elif float(cell[2]) < 0.95:
                tokens.append(f"{sample}?")
            else:
                tokens.append(sample)
        fn   = "note" if is_melodic else "s"
        lines.append(f'  {fn}("{" ".join(tokens)}") // {name}')
    cps_val = round(bpm / 60 / 4, 4)
    code    = f"// BANG! {APP_VERSION} — {bpm} BPM\nsetcps({cps_val})\nstack(\n" + ",\n".join(lines) + "\n)"
    return {"ok": True, "code": code}


@app.get("/touchosc/minimal")
async def download_touchosc_minimal():
    """Fichier TouchOSC minimal pour tester la compatibilité du format."""
    import tempfile, zipfile, uuid
    u = lambda: str(uuid.uuid4()).upper()
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<lexml version="3.0.0">
  <connections>
    <connection type="OSC" host="192.168.1.100" sendPort="57121" receivePort="57120" enabled="1" />
  </connections>
  <node ID="{u()}" type="GROUP">
    <properties>
      <property name="frame" type="r"><x>0.000000</x><y>0.000000</y><w>1366.000000</w><h>1024.000000</h></property>
      <property name="name" type="s"><value>bang</value></property>
      <property name="visible" type="b"><value>1</value></property>
      <property name="interactive" type="b"><value>1</value></property>
      <property name="color" type="c"><r>0.05</r><g>0.05</g><b>0.03</b><a>1.0</a></property>
    </properties>
  </node>
</lexml>'''
    out = Path(tempfile.mktemp(suffix=".tosc"))
    with zipfile.ZipFile(str(out), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.xml", xml.encode("utf-8"))
    return FileResponse(str(out), filename="bang_minimal.tosc", media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="bang_minimal.tosc"'})


@app.get("/touchosc")
async def download_touchosc(host: str = ""):
    """Télécharge le fichier TouchOSC pré-configuré pour BANG!
    ?host=lan       → 192.168.1.100
    ?host=tailscale → 100.64.201.127
    ?host=<ip>      → IP custom
    """
    import subprocess, tempfile, sys
    _HOST_ALIASES = {"lan": "192.168.1.100", "tailscale": "100.64.201.127"}
    resolved = _HOST_ALIASES.get(host.lower(), host) or "192.168.1.100"
    gen = BASE_DIR / "tools" / "gen_touchosc.py"
    rx  = _state.get("osc_rx_port", 57121)
    tx  = _state.get("osc_port", 57120)
    out = Path(tempfile.mktemp(suffix=".tosc"))
    subprocess.run([sys.executable, str(gen),
                    "--host", resolved, "--tx-port", str(tx), "--rx-port", str(rx),
                    "--out", str(out)], check=True)
    label = host.lower() if host else "lan"
    return FileResponse(str(out), filename=f"bang_control_{label}.tosc",
                        media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="bang_control_{label}.tosc"'})


@app.get("/morph/prepare")
async def morph_prepare(from_slot: int, to_slot: int):
    from bang_engine import vel_map as _vel_map
    slots  = _state.get("seq_slots", [None]*8)
    snap_a = slots[from_slot] if 0 <= from_slot < 8 else None
    snap_b = slots[to_slot]   if 0 <= to_slot   < 8 else None
    if not snap_a:
        return {"ok": False, "error": f"Slot {from_slot+1} vide"}
    if not snap_b:
        return {"ok": False, "error": f"Slot {to_slot+1} vide"}

    def _snap_events(snap):
        p     = snap.get("last_p") or _state.get("last_p") or {}
        steps = p.get("steps", 16)
        vf  = p.get("vel_floor",   0)
        vc  = p.get("vel_ceiling", 127)
        vcu = p.get("vel_curve",   1.0)
        result = []
        for note, dna, vtype in snap.get("voices", []):
            if vtype == "cc" or (note == 0 and not vtype.startswith("ksp")):
                continue
            compiled = compile_dna(dna)
            dna_len  = len(compiled)
            evts     = []
            for i in range(steps):
                row = compiled[i % dna_len]
                if row[0] <= 0:
                    continue
                evts.append({
                    "step":     i,
                    "dna_pos":  i % dna_len,
                    "velocity": _vel_map(int(row[1]), vf, vc, vcu),
                    "prob":     round(float(row[2]), 2),
                    "ratchet":  int(row[3]),
                })
            result.append({"events": evts})
        return result

    return {"ok": True, "from": _snap_events(snap_a), "to": _snap_events(snap_b)}


@app.get("/pattern")
async def get_pattern():
    if not _state["voices"] or not _state["last_p"]:
        return {"ok": False, "error": "Aucun pattern généré"}
    p     = _state["last_p"]
    steps = p["steps"]
    bpm   = p["bpm"]
    step_ms = round(60_000 / (bpm * 4), 3)   # durée d'une double-croche en ms

    vf  = p.get("vel_floor",   0)
    vc  = p.get("vel_ceiling", 127)
    vcu = p.get("vel_curve",   1.0)

    from bang_engine import vel_map as _vel_map

    voices_data = []
    cc_drones   = []

    # Extraire les drones CC (bassline, phase2…) — envoyés séparément par le player
    engine = _state.get("engine")
    if engine and hasattr(engine, "cc_tracks"):
        for drone in engine.cc_tracks:
            cc_drones.append({
                "control":     drone.get("control"),
                "channel":     drone.get("channel", 0),
                "breakpoints": drone.get("breakpoints", []),
            })

    # Associer chaque voix à son éventuelle chaîne de Markov dans l'engine
    # engine.voices et _state["voices"] sont construits dans le même ordre (cc exclus)
    _ev_iter = iter(engine.voices if engine else [])
    _voices_chains: list[object | None] = []
    for _n, _d, _vt in _state["voices"]:
        if _vt == "cc" or (_n == 0 and not _vt.startswith("ksp")):
            _voices_chains.append(None)
        else:
            _ev = next(_ev_iter, None)
            _voices_chains.append(_ev.get("chain") if _ev else None)

    for (note, dna, vtype), _chain in zip(_state["voices"], _voices_chains):
        if vtype == "cc" or (note == 0 and not vtype.startswith("ksp")):
            continue

        if vtype == "babka":
            events  = []
            cursor  = 0.0
            cyc     = 0
            while cursor < steps:
                bsteps = _babka.parse(dna, cycle=cyc)
                if not bsteps:
                    break
                for s in bsteps:
                    if cursor >= steps:
                        break
                    if s.trigger:
                        events.append({
                            "step":     round(cursor, 4),
                            "dur":      round(s.duration, 4),
                            "velocity": _vel_map(s.velocity, vf, vc, vcu),
                            "prob":     round(s.prob, 2),
                            "ratchet":  s.ratchet,
                            "atom":     _atom_label(s.prob, s.ratchet, s.jitter),
                        })
                    cursor += s.duration
                cyc += 1
            name = _NOTE_NAMES.get(note, f"n{note}")
            voices_data.append({
                "note": note, "name": name + " ⚗", "channel": 9,
                "type": vtype, "events": events, "plocks": [],
            })
            continue

        compiled = compile_dna(dna)
        dna_len  = len(compiled)
        events   = []
        for i in range(steps):
            dna_pos = i % dna_len
            row = compiled[dna_pos]
            if row[0] <= 0:
                continue
            events.append({
                "step":     i,
                "dna_pos":  dna_pos,
                "velocity": _vel_map(int(row[1]), vf, vc, vcu),
                "prob":     round(float(row[2]), 2),
                "ratchet":  int(row[3]),
                "atom":     _atom_label(float(row[2]), int(row[3]), int(row[4])),
            })
        if vtype.startswith("vd"):
            channel = int(vtype[2:])
            name    = _VD_PART_NAMES[channel]
        elif vtype == "bl":
            channel = 0
            name    = "Bass ♩"
            if _chain and events:
                _mnotes = _chain.generate(len(events))
                for _i, _evt in enumerate(events):
                    _evt["note"] = _mnotes[_i]
        elif vtype == "vk":
            channel = 0
            name    = "VKick"
        elif vtype.startswith("vfm"):
            channel = 0
            name    = _VFM_PART_NAMES[int(vtype[3:])]
        elif vtype.startswith("mf"):
            channel = 0
            name    = _MF_PART_NAMES[int(vtype[2:])]
        elif vtype == "markov":
            channel = p.get("markov_channel", 9)
            name    = _NOTE_NAMES.get(note, f"n{note}")
            if _chain and events:
                _mnotes = _chain.generate(len(events))
                for _i, _evt in enumerate(events):
                    _evt["note"] = _mnotes[_i]
        elif vtype.startswith("ksp"):
            ch      = int(vtype[3:]) - 1
            channel = ch
            name    = f"KSP {_KSP_TRACK_NAMES[min(ch, 3)]}"
        else:
            channel = 9
            name    = _NOTE_NAMES.get(note, f"n{note}")
        # Appliquer thinning par voix
        thin = _state["voice_thin"].get(name, 1)
        events = _thin_events(events, thin)
        density = _state["voice_density"].get(name, 1.0)
        if density < 1.0:
            events = [{**e, "prob": round(e["prob"] * density, 3)} for e in events]
        offset = _state.get("voice_offset", {}).get(name, 0)
        if offset:
            events = [{**e, "step": (e["step"] + offset) % steps} for e in events]
            events.sort(key=lambda e: e["step"])
        voice_plocks = _state["plocks"][len(voices_data)] if len(voices_data) < len(_state["plocks"]) else []
        vel_lane  = _state.get("voice_vel_lane",  {}).get(name, [])
        prob_lane = _state.get("voice_prob_lane", {}).get(name, [])
        voices_data.append({
            "note":      note,
            "name":      name,
            "channel":   channel,
            "type":      vtype,
            "events":    events,
            "plocks":    voice_plocks,
            "chord":     _state["voice_chords"].get(name, "mono"),
            "offset":    offset,
            "drop":      _state.get("voice_drop", {}).get(name, 1.0),
            "vel_lane":  vel_lane,
            "prob_lane": prob_lane,
            "lfo":       _state.get("voice_lfo", {}).get(name),
            "dna_len":   dna_len,
        })

    # Appliquer le filtre de polyphonie globale
    voices_data = _apply_poly_to_events(voices_data, _state["max_poly"])

    return {
        "ok":           True,
        "bpm":          bpm,
        "steps":        steps,
        "step_ms":      step_ms,
        "swing":        p.get("swing", 0.0),
        "vel_humanize": p.get("vel_humanize", 0),
        "microtiming":  p.get("microtiming", 1.0),
        "voices":       voices_data,
        "cc_drones":    cc_drones,
    }


@app.post("/voice/thin", response_class=HTMLResponse)
async def voice_thin(name: Annotated[str, Form()], factor: Annotated[int, Form()] = 1):
    _state["voice_thin"][name] = max(1, factor)
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse(_build_voices_html([]))
    pr_html = _build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/voice/density", response_class=HTMLResponse)
async def voice_density(name: Annotated[str, Form()], density: Annotated[float, Form()] = 1.0):
    _state["voice_density"][name] = max(0.0, min(1.0, float(density)))
    return HTMLResponse(_build_voices_html(_state["voices"]))


_VALID_CHORDS = {"mono","power","minor","major","sus2","sus4","m7","M7","dom7","dim","aug"}


def _euclid_dna(n: int, k: int) -> str:
    """Distribue k hits sur n steps (Bresenham)."""
    if n <= 0:
        return ""
    k = max(0, min(k, n))
    if k == 0:
        return "-" * n
    return "".join("x" if (i * k % n) < k else "-" for i in range(n))


@app.post("/voice/euclidean", response_class=HTMLResponse)
async def voice_euclidean(idx: Annotated[int, Form()], k: Annotated[int, Form()]):
    if not _state["voices"] or not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, raw, vtype = _state["voices"][idx]
    n = len(raw)
    if n == 0:
        return HTMLResponse("")
    new_dna = _euclid_dna(n, k)
    _state["voices"][idx] = (note, new_dna, vtype)
    if _state["last_p"]:
        _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"])
        pr_html = _build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None)
        oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    else:
        oob = ""
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/voice/chord", response_class=HTMLResponse)
async def voice_chord(name: Annotated[str, Form()], chord_type: Annotated[str, Form()] = "mono"):
    if chord_type in _VALID_CHORDS:
        _state["voice_chords"][name] = chord_type
    return HTMLResponse(_build_voices_html(_state["voices"]))


@app.post("/voice/steps", response_class=HTMLResponse)
async def voice_steps_set(name: Annotated[str, Form()], n: Annotated[int, Form()] = 0):
    if n <= 0:
        _state["voice_steps"].pop(name, None)
    else:
        _state["voice_steps"][name] = n
        for idx, (note, dna, vtype) in enumerate(_state["voices"]):
            if _voice_label(note, vtype) == name and vtype != "cc":
                _state["voices"][idx] = (note, _resize_dna(dna, n), vtype)
                break
    if _state["last_p"]:
        _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"])
        pr_html = _build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None)
        oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    else:
        oob = ""
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/voice/offset", response_class=HTMLResponse)
async def voice_offset_set(name: Annotated[str, Form()], n: Annotated[int, Form()] = 0):
    vo = _state.setdefault("voice_offset", {})
    if n <= 0:
        vo.pop(name, None)
    else:
        vo[name] = n
    return HTMLResponse(_build_voices_html(_state["voices"]))


@app.post("/voice/invert", response_class=HTMLResponse)
async def voice_invert(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    inv = {"x": "-", "-": "x"}
    new_dna = "".join(inv.get(c, c) for c in dna)
    voices = list(_state["voices"])
    voices[idx] = (note, new_dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/drop", response_class=HTMLResponse)
async def voice_drop_set(name: Annotated[str, Form()], pct: Annotated[int, Form()] = 100):
    vd = _state.setdefault("voice_drop", {})
    val = max(0, min(100, pct)) / 100.0
    if val >= 1.0:
        vd.pop(name, None)
    else:
        vd[name] = round(val, 2)
    return HTMLResponse(_build_voices_html(_state["voices"]))


@app.post("/voice/vel_lane", response_class=HTMLResponse)
async def voice_vel_lane_set(name: Annotated[str, Form()], lane: Annotated[str, Form()] = "[]"):
    try:
        vals = [max(0, min(127, int(round(float(v))))) for v in json.loads(lane)]
    except Exception:
        return HTMLResponse("")
    vll = _state.setdefault("voice_vel_lane", {})
    if all(v == 0 for v in vals):
        vll.pop(name, None)
    else:
        vll[name] = vals
    return HTMLResponse("")


@app.post("/voice/prob_lane", response_class=HTMLResponse)
async def voice_prob_lane_set(name: Annotated[str, Form()], lane: Annotated[str, Form()] = "[]"):
    try:
        vals = [max(0, min(100, int(round(float(v))))) for v in json.loads(lane)]
    except Exception:
        return HTMLResponse("")
    vpl = _state.setdefault("voice_prob_lane", {})
    if all(v == 0 for v in vals):
        vpl.pop(name, None)
    else:
        vpl[name] = vals
    return HTMLResponse("")


@app.post("/voice/lfo", response_class=HTMLResponse)
async def voice_lfo_set(
    name:   Annotated[str,   Form()],
    shape:  Annotated[str,   Form()] = "off",
    target: Annotated[str,   Form()] = "density",
    freq:   Annotated[float, Form()] = 1.0,
    depth:  Annotated[float, Form()] = 0.5,
):
    vl = _state.setdefault("voice_lfo", {})
    if shape == "off":
        vl.pop(name, None)
    else:
        vl[name] = {"shape": shape, "target": target, "freq": freq, "depth": round(depth, 3)}
    return HTMLResponse("")


@app.post("/voice/swing", response_class=HTMLResponse)
async def voice_swing_set(name: Annotated[str, Form()], pct: Annotated[int, Form()] = 0):
    vs = _state.setdefault("voice_swing", {})
    val = max(0, min(100, int(pct)))
    if val == 0:
        vs.pop(name, None)
    else:
        vs[name] = round(val / 100, 2)
    return HTMLResponse("")


@app.post("/voice/midi_ch", response_class=HTMLResponse)
async def voice_midi_ch_set(name: Annotated[str, Form()], ch: Annotated[int, Form()] = -1):
    vmc = _state.setdefault("voice_midi_ch", {})
    if ch < 0:
        vmc.pop(name, None)
    else:
        vmc[name] = max(0, min(15, ch))
    return HTMLResponse("")


@app.post("/voice/regen", response_class=HTMLResponse)
async def voice_regen(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    if idx in _state.get("locked_voices", set()):
        return HTMLResponse(_build_voices_html(_state["voices"]))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    fresh = _build_voices(_state["last_p"])
    if idx < len(fresh):
        _, new_dna, _ = fresh[idx]
    else:
        new_dna = mutate_dna(dna, intensity=0.9)
    voices = list(_state["voices"])
    voices[idx] = (note, new_dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/rotate", response_class=HTMLResponse)
async def voice_rotate(idx: Annotated[int, Form()], n: Annotated[int, Form()] = 1):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    if not dna:
        return HTMLResponse(_build_voices_html(_state["voices"]))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    shift = n % len(dna)
    new_dna = dna[-shift:] + dna[:-shift] if shift else dna
    voices = list(_state["voices"])
    voices[idx] = (note, new_dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/reverse", response_class=HTMLResponse)
async def voice_reverse(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    voices = list(_state["voices"])
    voices[idx] = (note, dna[::-1], vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/double", response_class=HTMLResponse)
async def voice_double(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    if not dna:
        return HTMLResponse(_build_voices_html(_state["voices"]))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    voices = list(_state["voices"])
    voices[idx] = (note, dna + dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/halve", response_class=HTMLResponse)
async def voice_halve(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    if not dna:
        return HTMLResponse(_build_voices_html(_state["voices"]))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    voices = list(_state["voices"])
    new_dna = dna[:max(1, len(dna) // 2)]
    voices[idx] = (note, new_dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/voice/preview", response_class=HTMLResponse)
async def voice_preview(idx: Annotated[int, Form()], pattern: Annotated[str, Form()]):
    pattern = pattern.strip()
    if not pattern or not _state["last_p"] or not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, _, vtype = _state["voices"][idx]
    _state["voices"][idx] = (note, pattern, vtype)
    _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"])
    return HTMLResponse(_build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None))


@app.post("/voice/pattern", response_class=HTMLResponse)
async def voice_pattern(idx: Annotated[int, Form()], pattern: Annotated[str, Form()]):
    pattern = pattern.strip()
    if pattern and 0 <= idx < len(_state["voices"]):
        note, _, vtype = _state["voices"][idx]
        _state["voices"][idx] = (note, pattern, vtype)
        if _state["last_p"]:
            _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"])
    voices = _state["voices"]
    if _state["last_p"]:
        pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
        oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    else:
        oob = ""
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/vary", response_class=HTMLResponse)
async def vary():
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    locked = _state.get("locked_voices", set())
    new_voices = []
    for idx, (note, dna, vtype) in enumerate(_state["voices"]):
        if idx in locked or vtype == "cc":
            new_voices.append((note, dna, vtype))
        else:
            new_voices.append((note, mutate_dna(dna, intensity=0.12), vtype))
    _state["voices"] = new_voices
    _state["engine"] = _assemble_engine(_state["last_p"], new_voices)
    pr_html = _build_pr_html(new_voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(new_voices) + oob)


@app.post("/voice/vary", response_class=HTMLResponse)
async def voice_vary(idx: Annotated[int, Form()]):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    if not (0 <= idx < len(_state["voices"])):
        return HTMLResponse("")
    note, dna, vtype = _state["voices"][idx]
    if idx in _state.get("locked_voices", set()) or vtype == "cc":
        return HTMLResponse(_build_voices_html(_state["voices"]))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    new_dna = mutate_dna(dna, intensity=0.15)
    for _ in range(8):                 # garantit >=1 mutation reelle
        if new_dna != dna:
            break
        new_dna = mutate_dna(dna, intensity=0.15)
    voices  = list(_state["voices"])
    voices[idx] = (note, new_dna, vtype)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob     = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.get("/grooves")
async def grooves_list():
    return {"grooves": list(GROOVE_PRESETS.keys())}


@app.post("/groove/apply", response_class=HTMLResponse)
async def groove_apply(name: Annotated[str, Form()]):
    preset = GROOVE_PRESETS.get(name)
    if not preset or not _state["voices"] or not _state["last_p"]:
        return HTMLResponse(_build_voices_html(_state.get("voices", [])))
    _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    locked = _state.get("locked_voices", set())
    voices = list(_state["voices"])
    pi = 0
    for vi, (note, dna, vtype) in enumerate(voices):
        if vtype == "cc":
            continue
        if vi not in locked and pi < len(preset) and preset[pi]:
            voices[vi] = (note, preset[pi], vtype)
        pi += 1
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    _save_state()
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    import datetime
    host = request.headers.get("host", "localhost:7777")
    files = []
    if EXPORT_DIR.exists():
        for f in sorted(EXPORT_DIR.glob("*.mid"), key=lambda x: x.stat().st_mtime, reverse=True):
            st = f.stat()
            files.append({
                "name":    f.name,
                "size_kb": round(st.st_size / 1024, 1),
                "date":    datetime.datetime.fromtimestamp(st.st_mtime).strftime("%d/%m %H:%M"),
            })
    return HTMLResponse(jinja.get_template("files.html").render(
        files=files, host=host, app_version=APP_VERSION
    ))


def _query_ableton_tempo(host: str, port: int, timeout: float = 0.8) -> float | None:
    import socket as _sock
    try:
        from pythonosc.osc_message_builder import OscMessageBuilder
        from pythonosc.osc_message import OscMessage
        msg = OscMessageBuilder(address="/live/song/get/tempo").build()
        with _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(msg.dgram, (host, port))
            data, _ = s.recvfrom(1024)
            return float(OscMessage(data).params[0])
    except Exception:
        return None


@app.get("/ableton/sync_bpm")
async def ableton_sync_bpm():
    host = _state.get("ableton_host", "127.0.0.1")
    port = int(_state.get("ableton_port", 11000))
    bpm = _query_ableton_tempo(host, port)
    if bpm is None:
        return {"ok": False, "error": "Pas de réponse (AbletonOSC actif ?)"}
    bpm_int = max(20, min(300, int(round(bpm))))
    if _state.get("last_p"):
        _state["last_p"]["bpm"] = bpm_int
    return {"ok": True, "bpm": bpm_int}


@app.post("/seq/save", response_class=HTMLResponse)
async def seq_save(idx: Annotated[int, Form()]):
    if not (0 <= idx < 8) or not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    slots = _state.setdefault("seq_slots", [None]*8)
    slots[idx] = {
        "voices": list(_state["voices"]),
        "plocks": list(_state["plocks"]),
        "last_p": dict(_state["last_p"]),
    }
    oob = f'<div id="seq-panel" hx-swap-oob="innerHTML">{_build_seq_html()}</div>'
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/seq/load", response_class=HTMLResponse)
async def seq_load(idx: Annotated[int, Form()]):
    if not (0 <= idx < 8):
        return HTMLResponse("")
    slots = _state.get("seq_slots", [None]*8)
    slot  = slots[idx]
    if slot is None:
        return HTMLResponse("")
    if _state["voices"] and _state["last_p"]:
        _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    _state["voices"]      = list(slot["voices"])
    _state["plocks"]      = list(slot["plocks"])
    _state["last_p"]      = dict(slot["last_p"])
    _state["seq_current"] = idx
    _state["engine"]      = _assemble_engine(_state["last_p"], _state["voices"])
    voices  = _state["voices"]
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = (f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
           f'<div id="seq-panel" hx-swap-oob="innerHTML">{_build_seq_html()}</div>')
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/seq/clear", response_class=HTMLResponse)
async def seq_clear(idx: Annotated[int, Form()]):
    if not (0 <= idx < 8):
        return HTMLResponse("")
    slots = _state.setdefault("seq_slots", [None]*8)
    slots[idx] = None
    oob = f'<div id="seq-panel" hx-swap-oob="innerHTML">{_build_seq_html()}</div>'
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/seq/advance", response_class=HTMLResponse)
async def seq_advance():
    slots   = _state.get("seq_slots", [None]*8)
    weights = _state.get("seq_weights", [1]*8)
    cur     = _state.get("seq_current", 0)
    occupied = [(i, slots[i]) for i in range(8) if slots[i] is not None]
    if not occupied:
        return HTMLResponse("")
    others   = [(i, s) for i, s in occupied if i != cur]
    pool     = others if others else occupied
    wts      = [weights[i] for i, _ in pool]
    next_idx = random.choices([i for i, _ in pool], weights=wts, k=1)[0]
    slot = slots[next_idx]
    if _state["voices"] and _state["last_p"]:
        _state["history"].append((list(_state["voices"]), list(_state["plocks"]), dict(_state["last_p"])))
    _state["voices"]      = list(slot["voices"])
    _state["plocks"]      = list(slot["plocks"])
    _state["last_p"]      = dict(slot["last_p"])
    _state["seq_current"] = next_idx
    _state["engine"]      = _assemble_engine(_state["last_p"], _state["voices"])
    voices  = _state["voices"]
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    oob = (f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
           f'<div id="seq-panel" hx-swap-oob="innerHTML">{_build_seq_html()}</div>')
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/seq/config", response_class=HTMLResponse)
async def seq_config_set(cycles: Annotated[int, Form()] = 2):
    _state["seq_cycles"] = max(1, min(64, cycles))
    return HTMLResponse("")


@app.post("/seq/weight", response_class=HTMLResponse)
async def seq_weight_set(idx: Annotated[int, Form()], weight: Annotated[int, Form()] = 1):
    weights = _state.setdefault("seq_weights", [1]*8)
    if 0 <= idx < 8:
        weights[idx] = max(1, min(9, weight))
    return HTMLResponse("")


@app.post("/ableton/config", response_class=HTMLResponse)
async def ableton_config_set(
    host:         Annotated[str, Form()] = "127.0.0.1",
    port:         Annotated[int, Form()] = 11000,
    track_offset: Annotated[int, Form()] = 0,
    slot:         Annotated[int, Form()] = 0,
):
    _state["ableton_host"]         = host.strip() or "127.0.0.1"
    _state["ableton_port"]         = max(1, min(65535, port))
    _state["ableton_track_offset"] = max(0, track_offset)
    _state["ableton_slot"]         = max(0, slot)
    return HTMLResponse('<span style="color:var(--success)">Config sauvée.</span>')


@app.post("/ableton/send", response_class=HTMLResponse)
async def ableton_send():
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse('<span style="color:var(--danger)">Aucun pattern généré.</span>')

    host         = _state.get("ableton_host", "127.0.0.1")
    port         = int(_state.get("ableton_port", 11000))
    track_offset = int(_state.get("ableton_track_offset", 0))
    slot         = int(_state.get("ableton_slot", 0))
    p            = _state["last_p"]

    try:
        from pythonosc.udp_client import SimpleUDPClient
        client = SimpleUDPClient(host, port)

        client.send_message("/live/song/set/tempo", float(p["bpm"]))

        steps          = p["steps"]
        clip_len_beats = steps / 4.0

        vf  = p.get("vel_floor",   0)
        vc  = p.get("vel_ceiling", 127)
        vcu = p.get("vel_curve",   1.0)
        from bang_engine import vel_map as _vel_map

        sent = 0
        vi   = 0
        for note, dna, vtype in _state["voices"]:
            if vtype == "cc":
                continue
            track_id = track_offset + vi

            client.send_message("/live/clip_slot/create_clip",
                                [track_id, slot, clip_len_beats])

            compiled  = compile_dna(dna)
            dna_len   = len(compiled)
            note_args = []
            for i in range(steps):
                row = compiled[i % dna_len]
                if row[0] <= 0:
                    continue
                vel     = _vel_map(int(row[1]), vf, vc, vcu)
                ratchet = max(1, int(row[3]))
                if ratchet > 1:
                    rd = 0.25 / ratchet
                    for r in range(ratchet):
                        note_args.extend([note, i / 4.0 + r * rd, rd * 0.85, vel, 0])
                else:
                    note_args.extend([note, i / 4.0, 0.225, vel, 0])

            if note_args:
                client.send_message("/live/clip/add_notes",
                                    [track_id, slot] + note_args)
            vi   += 1
            sent += 1

        last = track_offset + sent - 1
        return HTMLResponse(
            f'<span style="color:var(--success)">✓ {sent} voix → tracks {track_offset}–{last}, slot {slot}</span>'
        )
    except Exception as e:
        return HTMLResponse(f'<span style="color:var(--danger)">Erreur : {e}</span>')


@app.post("/undo", response_class=HTMLResponse)
async def undo():
    if not _state["history"]:
        return HTMLResponse("")
    voices, plocks, last_p = _state["history"].pop()
    _state["voices"]  = voices
    _state["plocks"]  = plocks
    _state["last_p"]  = last_p
    _state["engine"]  = _assemble_engine(last_p, voices)
    pr_html = _build_pr_html(voices, last_p["steps"], plocks or None)
    oob     = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/ab/store", response_class=HTMLResponse)
async def ab_store(slot: Annotated[str, Form()] = "a"):
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse(_build_ab_html())
    snapshot = (_state["voices"][:], list(_state["plocks"]), dict(_state["last_p"]))
    if slot == "b":
        _state["slot_b"] = snapshot
    else:
        _state["slot_a"] = snapshot
    return HTMLResponse(_build_ab_html())


@app.post("/ab/load", response_class=HTMLResponse)
async def ab_load(slot: Annotated[str, Form()] = "a"):
    snap = _state["slot_b"] if slot == "b" else _state["slot_a"]
    if snap is None:
        return HTMLResponse("")
    voices, plocks, last_p = snap
    _state["voices"]     = voices
    _state["plocks"]     = plocks
    _state["last_p"]     = last_p
    _state["engine"]     = _assemble_engine(last_p, voices)
    _state["ab_current"] = slot
    pr_html = _build_pr_html(voices, last_p["steps"], plocks or None)
    oob_pr  = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    oob_ab  = f'<div id="ab-controls" hx-swap-oob="outerHTML:#ab-controls">{_build_ab_html()}</div>'
    return HTMLResponse(_build_voices_html(voices) + oob_pr + oob_ab)




@app.post("/ctrl")
async def ctrl_param(
    key: Annotated[str,   Form()],
    val: Annotated[str,   Form()],
):
    from starlette.responses import Response as _R
    p2 = _state.get("last_p")
    if p2 is not None and key in p2:
        try:
            if key in ("bpm", "steps", "vel_floor", "vel_ceiling", "markov_channel"):
                p2[key] = int(float(val))
            else:
                p2[key] = round(float(val), 4)
        except (ValueError, TypeError):
            pass
    return _R(status_code=204)


@app.get("/live", response_class=HTMLResponse)
async def live_dashboard():
    p2  = _state.get("last_p") or {}
    vs  = _state.get("voices") or []
    den = _state.get("voice_density", {})
    locked = _state.get("locked_voices", set())
    NOTE_NAMES = {
        36:"Kick", 38:"Snare", 42:"HH", 46:"OH", 47:"Tom",
        49:"Crash", 51:"Ride", 24:"Bass", 33:"Bass2", 48:"Tom2",
        40:"Snare2", 43:"Tom3",
    }
    voices_data = []
    for idx, (note, dna, vtype) in enumerate(vs):
        if vtype == "cc":
            continue
        name = NOTE_NAMES.get(note, f"V{note}")
        density = den.get(name, den.get(name.lower(), 0.5))
        voices_data.append({
            "idx": idx, "note": note, "name": name, "vtype": vtype,
            "density": round(float(density), 3), "locked": idx in locked,
        })
    tpl = jinja.get_template("live.html")
    return HTMLResponse(tpl.render(
        p=p2, voices=voices_data,
        modes=["morph","random","babka","noise","ambient","weather","markov","phase2","bassline"],
        version=APP_VERSION,
    ))

@app.get("/params/live")
async def params_live():
    p = _state.get("last_p") or {}
    return {
        "bpm":         p.get("bpm", 110),
        "chaos":       round(p.get("chaos", 0.3), 3),
        "gravity":     round(p.get("gravity", 0.7), 3),
        "steps":       p.get("steps", 64),
        "swing":       round(p.get("swing", 0.0), 3),
        "microtiming": round(p.get("microtiming", 1.0), 3),
    }


@app.get("/pianoroll/live")
async def pianoroll_live():
    if not _state.get("voices") or not _state.get("last_p"):
        from starlette.responses import Response
        return Response(status_code=204)
    pr_html = _build_pr_html(_state["voices"], _state["last_p"]["steps"], _state.get("plocks") or None)
    return HTMLResponse(pr_html)

@app.post("/osc/toggle", response_class=HTMLResponse)
async def osc_toggle():
    if _state.get("osc_enabled"):
        _osc_stop()
    else:
        _osc_start()
    return HTMLResponse(_build_osc_btn())


@app.post("/osc/config", response_class=HTMLResponse)
async def osc_config(host:    Annotated[str, Form()] = "127.0.0.1",
                     port:    Annotated[int, Form()] = 57120,
                     rx_port: Annotated[int, Form()] = 57121):
    _state["osc_host"]    = host.strip() or "100.64.201.127"
    _state["osc_port"]    = max(1, min(65535, port))
    _state["osc_rx_port"] = max(1, min(65535, rx_port))
    if _state.get("osc_enabled"):
        _osc_rx_stop()
        _osc_rx_start(_state["osc_rx_port"])
    return HTMLResponse(_build_osc_btn())


def _build_osc_btn() -> str:
    enabled  = _state.get("osc_enabled", False)
    host     = _state.get("osc_host", "100.64.201.127")
    port     = _state.get("osc_port", 57120)
    rx_port  = _state.get("osc_rx_port", 57121)
    cls      = "btn-osc active" if enabled else "btn-osc"
    label    = "OSC ●" if enabled else "OSC ○"
    tip      = f"OSC ↑{host}:{port} ↓:{rx_port} ({'actif' if enabled else 'inactif'})"
    return (f'<span id="osc-btn">'
            f'<button class="{cls}" hx-post="/osc/toggle" hx-target="#osc-btn" hx-swap="outerHTML" title="{tip}">{label}</button>'
            f'</span>')


@app.get("/osc/log", response_class=HTMLResponse)
async def osc_log_view():
    entries = list(_state.get("osc_log", []))
    if not entries:
        return HTMLResponse(
            '<tr><td colspan="4" class="osc-log-empty">Aucun message OSC — activer OSC et jouer un pattern</td></tr>'
        )
    rows = []
    for e in entries[:40]:
        dir_cls = "osc-log-tx" if e["dir"] == "TX" else "osc-log-rx"
        rows.append(
            f'<tr class="{dir_cls}">'
            f'<td class="osc-log-ts">{e["ts"]}</td>'
            f'<td class="osc-log-dir">{e["dir"]}</td>'
            f'<td class="osc-log-addr">{e["addr"]}</td>'
            f'<td class="osc-log-args">{e["args"]}</td>'
            f'</tr>'
        )
    return HTMLResponse("".join(rows))


@app.post("/osc/log/clear", response_class=HTMLResponse)
async def osc_log_clear():
    _state["osc_log"].clear()
    return HTMLResponse('<tr><td colspan="4" class="osc-log-empty">Log effacé</td></tr>')


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return render("setup.html",
        osc_enabled=_state.get("osc_enabled", False),
        osc_host=_state.get("osc_host", "100.64.201.127"),
        osc_port=_state.get("osc_port", 57120),
        osc_rx_port=_state.get("osc_rx_port", 57121),
        midi_srv_enabled=_state.get("midi_srv_enabled", False),
        midi_srv_port=_state.get("midi_srv_port", 0),
        midi_srv_channel=_state.get("midi_srv_channel", 9),
        ableton_host=_state.get("ableton_host", "127.0.0.1"),
        ableton_port=_state.get("ableton_port", 11000),
        ableton_track_offset=_state.get("ableton_track_offset", 0),
        ableton_slot=_state.get("ableton_slot", 0),
        app_version=APP_VERSION,
    )


@app.post("/lock_voice", response_class=HTMLResponse)
async def lock_voice(idx: Annotated[int, Form()]):
    locked = _state["locked_voices"]
    if idx in locked:
        locked.discard(idx)
    else:
        locked.add(idx)
    return HTMLResponse(_build_voices_html(_state["voices"]))


@app.post("/poly", response_class=HTMLResponse)
async def set_poly(max_poly: Annotated[int, Form()] = 0):
    _state["max_poly"] = max(0, max_poly)
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    return HTMLResponse(_build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None))


@app.get("/doc", response_class=HTMLResponse)
async def doc_page():
    return render("doc.html", app_version=APP_VERSION)


@app.get("/session/export")
async def session_export():
    payload = {
        "bang_version": APP_VERSION,
        "timestamp":    datetime.utcnow().isoformat(),
        "seed":         _state["last_seed"],
        "params":       _state["last_p"] or {},
        "voices":       [{"note": n, "pattern": d, "type": t} for n, d, t in _state["voices"]],
        "voice_thin":    _state["voice_thin"],
        "voice_density": _state["voice_density"],
        "voice_chords":  _state["voice_chords"],
        "note_remap":    _state["note_remap"],
        "max_poly":     _state["max_poly"],
        "locked_voices": sorted(_state["locked_voices"]),
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="bang-session-{ts}.json"'},
    )


@app.post("/session/import")
async def session_import(file: UploadFile = File(...)):
    from fastapi.responses import RedirectResponse
    try:
        data = json.loads(await file.read())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HTMLResponse("Fichier JSON invalide", status_code=400)

    _state["voices"]       = [(v["note"], v["pattern"], v["type"]) for v in data.get("voices", [])]
    _state["voice_thin"]    = data.get("voice_thin", {})
    _state["voice_density"] = data.get("voice_density", {})
    _state["voice_chords"]  = data.get("voice_chords", {})
    _state["note_remap"]    = data.get("note_remap", {})
    _state["max_poly"]     = int(data.get("max_poly", 0))
    _state["last_seed"]    = data.get("seed", "")
    if data.get("params"):
        _state["last_p"]   = data["params"]
    if _state["last_p"] and _state["voices"]:
        _state["engine"]   = _assemble_engine(_state["last_p"], _state["voices"])
    return RedirectResponse(url="/", status_code=303)


@app.get("/presets")
async def list_presets():
    custom = _load_custom_presets()
    return {
        "builtin": list(DRUM_PRESETS.keys()),
        "custom":  list(custom.keys()),
        "current": _state["current_preset"],
    }


def _rebuild_after_remap() -> str:
    if not _state["last_p"]:
        return ""
    voices = _apply_note_remap(_build_voices(_state["last_p"]))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)
    pr_html = _build_pr_html(voices, _state["last_p"]["steps"], _state["plocks"] or None)
    return _build_voices_html(voices) + f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'


@app.post("/preset/apply", response_class=HTMLResponse)
async def apply_preset(request: Request, name: Annotated[str, Form()]):
    all_presets = {**DRUM_PRESETS, **_load_custom_presets()}
    if name not in all_presets:
        return HTMLResponse("")
    _state["note_remap"]     = dict(all_presets[name])
    _state["current_preset"] = name
    return HTMLResponse(_rebuild_after_remap())


@app.post("/preset/save")
async def save_preset(name: Annotated[str, Form()]):
    name = name.strip()
    if not name:
        return {"ok": False, "error": "Nom vide"}
    if name in DRUM_PRESETS:
        return {"ok": False, "error": "Nom réservé (preset built-in)"}
    custom = _load_custom_presets()
    custom[name] = dict(_state["note_remap"]) if _state["note_remap"] else {}
    _save_custom_presets(custom)
    _state["current_preset"] = name
    return {"ok": True, "name": name}


@app.delete("/preset/{name}")
async def delete_preset(name: str):
    custom = _load_custom_presets()
    custom.pop(name, None)
    _save_custom_presets(custom)
    if _state["current_preset"] == name:
        _state["current_preset"] = ""
    return {"ok": True}


# ---------------------------------------------------------------------------
# KSP presets
# ---------------------------------------------------------------------------

@app.get("/ksp/presets")
async def ksp_presets():
    custom = _load_ksp_presets()
    return {
        "builtin": list(KSP_PRESETS_BUILTIN.keys()),
        "custom":  list(custom.keys()),
        "current": _state["current_ksp_preset"],
    }


@app.post("/ksp/preset/save")
async def ksp_preset_save(name: Annotated[str, Form()]):
    name = name.strip()
    if not name:
        return {"ok": False, "error": "Nom vide"}
    if name in KSP_PRESETS_BUILTIN:
        return {"ok": False, "error": "Nom réservé (preset built-in)"}
    p = _state.get("last_p") or {}
    chords = {k: v for k, v in _state.get("voice_chords", {}).items() if k.startswith("KSP")}
    preset = {
        "root":    p.get("root",    "A"),
        "scale":   p.get("scale",   "penta_min"),
        "gravity": p.get("gravity", 0.70),
        "chords":  chords,
    }
    custom = _load_ksp_presets()
    custom[name] = preset
    _save_ksp_presets(custom)
    _state["current_ksp_preset"] = name
    return {"ok": True, "name": name}


@app.post("/ksp/preset/load")
async def ksp_preset_load(name: Annotated[str, Form()]):
    all_presets = {**KSP_PRESETS_BUILTIN, **_load_ksp_presets()}
    if name not in all_presets:
        return {"ok": False, "error": "Preset introuvable"}
    preset = all_presets[name]
    # Mettre à jour voice_chords pour les voix KSP
    for voice_name, chord in preset.get("chords", {}).items():
        if chord in _VALID_CHORDS:
            _state["voice_chords"][voice_name] = chord
    # Patcher last_p si un pattern est en mémoire
    if _state["last_p"]:
        _state["last_p"]["root"]    = preset["root"]
        _state["last_p"]["scale"]   = preset["scale"]
        _state["last_p"]["gravity"] = preset["gravity"]
        _state["engine"] = _assemble_engine(_state["last_p"], _state["voices"])
    _state["current_ksp_preset"] = name
    return {
        "ok":      True,
        "root":    preset["root"],
        "scale":   preset["scale"],
        "gravity": preset["gravity"],
        "chords":  preset.get("chords", {}),
    }


@app.delete("/ksp/preset/{name}")
async def ksp_preset_delete(name: str):
    if name in KSP_PRESETS_BUILTIN:
        return {"ok": False, "error": "Preset built-in — non supprimable"}
    custom = _load_ksp_presets()
    custom.pop(name, None)
    _save_ksp_presets(custom)
    if _state["current_ksp_preset"] == name:
        _state["current_ksp_preset"] = ""
    return {"ok": True}


# ---------------------------------------------------------------------------
# MIDI serveur — routes
# ---------------------------------------------------------------------------

@app.get("/midi/ports")
async def midi_ports():
    return {"ports": _midi_srv_ports()}


@app.post("/midi/toggle", response_class=HTMLResponse)
async def midi_srv_toggle():
    if _state.get("midi_srv_enabled"):
        _midi_srv_stop()
    else:
        _midi_srv_start()
    return HTMLResponse(_build_midi_srv_btn())


@app.post("/midi/config", response_class=HTMLResponse)
async def midi_srv_config(port: Annotated[int, Form()] = 0,
                          channel: Annotated[int, Form()] = 9):
    _state["midi_srv_port"]    = max(0, port)
    _state["midi_srv_channel"] = max(0, min(15, channel))
    if _state.get("midi_srv_enabled"):
        _midi_srv_stop()
        _midi_srv_start()
    return HTMLResponse(_build_midi_srv_btn())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("BANG_PORT", 7777))
    print(f"BANG Web — http://0.0.0.0:{port}")
    print(f"Sur Tailscale : http://100.64.201.127:{port}")
    uvicorn.run("web:app", host="0.0.0.0", port=port, reload=False)
