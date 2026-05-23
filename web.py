"""BANG Web — Interface FastAPI + HTMX pour le séquenceur Dark Umbrae"""

from __future__ import annotations

APP_VERSION = "0.5.1"

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
from fastapi.responses import FileResponse, HTMLResponse, Response
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
FAVORITES_FILE   = BASE_DIR / "bang_favorites.json"
SONG_PARAMS_FILE = BASE_DIR / "bang_song_params.json"
EXPORT_DIR.mkdir(exist_ok=True)

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

app      = App = FastAPI(title="BANG — Dark Umbrae")
jinja    = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html"]),
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
    "current_preset":  "",  # nom du preset actif
    "plocks":          [],  # p-locks par voix (volca_drum uniquement)
    "locked_voices":   set(),  # indices de voix verrouillées
    "history":         deque(maxlen=5),  # ring buffer (voices, plocks, last_p)
    "slot_a":          None,  # snapshot A/B pour comparaison
    "slot_b":          None,
    "ab_current":      None,  # "a" | "b" | None
    "voice_thin":      {},  # voice_name -> factor (1 / 2 / 4)
    "voice_density":   {},  # voice_name -> float (0.0–1.0, défaut 1.0)
    "voice_chords":    {},  # voice_name -> chord_type str (défaut "mono")
    "osc_enabled":     False,
    "osc_host":        "127.0.0.1",
    "osc_port":        57120,
    "osc_thread":      None,  # threading.Thread
    "max_poly":        0,   # 0 = illimité
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

# Notes MIDI customisables par l'utilisateur (remplace _NOTE_NAMES pour les voix)
_custom_notes: dict[int, int] = {}  # slot_index -> note MIDI


def _build_pianoroll_rows(voices: list, steps: int, plocks: list | None = None) -> list:
    rows = []
    for note, dna, vtype in voices:
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
                         "color": "#e879f9", "boundaries": [], "plocks": []})
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
            atom    = _atom_label(prob, ratchet, jitter) if trigger else "-"
            cells.append({
                "trigger": trigger,
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
    return jinja.get_template("_pianoroll.html").render(rows=rows, steps=steps)


def _build_voices_html(voices: list) -> str:
    return jinja.get_template("_voices.html").render(
        voices=[(n, dna_html(d), d, t, _voice_label(n, t)) for n, d, t in voices],
        voice_thin=_state["voice_thin"],
        voice_density=_state["voice_density"],
        voice_chords=_state.get("voice_chords", {}),
        locked_voices=_state.get("locked_voices", set()),
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
    chaos = p["chaos"]
    mode  = p["mode"]
    w     = _state["weather"] or {"temperature": 10.0, "wind_speed": 10.0}

    if mode == "random":
        return [(n, random_dna(16), "drum") for n in [36, 38, 42, 48]]

    if mode == "morph":
        base = morph_dna("x---x---x---x---", "x---?---x↺--░---", mutation_rate=chaos * 0.5)
        return [
            (36, mutate_dna(base, intensity=chaos * 0.6), "drum"),
            (38, "----x-------x---",                       "drum"),
            (42, "x-x-x-x-x-x-x-x",                       "drum"),
            (24, "x-?-░",                                  "drum"),
        ]

    if mode == "weather":
        return [
            (note, mutate_dna(weather_dna(w, length), intensity=chaos * 0.4), "drum")
            for note, length in [(36, 16), (38, 8), (42, 16), (24, 5)]
        ]

    if mode in ("markov", "phase2"):
        voices = [
            (36, mutate_dna("x---x---", intensity=chaos * 0.4), "drum"),
            (38, "----x-------x---",                             "drum"),
            (42, "x-x-x-x-x-x-x-x",                             "drum"),
            (24, "x-?-░",                                        "markov"),
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
                (36, "x---x---",            "babka"),
                (38, "x(3,8)",              "babka"),
                (42, "[x x]-x-[x x]-x-",   "babka"),
                (24, "?-░-",               "babka"),
            ]
        elif chaos < 0.7:
            return [
                (36, "<x---x--- x-[x-]x-->",     "babka"),
                (38, "?(3,8)",                    "babka"),
                (42, "<[x x]-x- x-[x x]->",      "babka"),
                (24, "↺(2,8)",                   "babka"),
            ]
        else:
            n_snare = min(7, max(2, int(chaos * 8)))
            return [
                (36, "<x-[x x]- [x x]-->",             "babka"),
                (38, f"?({n_snare},8)",                 "babka"),
                (42, "<[x x x]-x- x-[x x]->",          "babka"),
                (24, "<↺(2,8) ░(3,8)>",               "babka"),
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
        (n if (vtype.startswith("vd") or vtype == "bl") else
         remap.get("VKick", n) if vtype == "vk" else
         remap.get(_VFM_PART_NAMES[int(vtype[3:])], n) if vtype.startswith("vfm") else
         remap.get(_MF_PART_NAMES[int(vtype[2:])], n) if vtype.startswith("mf") else
         remap.get(_NOTE_NAMES.get(n, f"n{n}"), n), dna, vtype)
        for n, dna, vtype in voices
    ]


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

        host = _state.get("osc_host", "127.0.0.1")
        port = _state.get("osc_port", 57120)
        if (host, port) != last_addr:
            client    = SimpleUDPClient(host, int(port))
            last_addr = (host, port)

        t0 = time.perf_counter()

        # Régénération des notes Markov au début de chaque cycle
        if step == 0:
            markov_notes = {}
            engine = _state.get("engine")
            if engine:
                mk_idx = 0   # index dans engine.voices (skip CC)
                for note, dna, vtype in voices:
                    if vtype == "cc":
                        continue
                    if vtype in ("markov", "bl") and mk_idx < len(engine.voices):
                        ev = engine.voices[mk_idx]
                        if ev.get("type") == "markov":
                            name = _voice_label(note, vtype)
                            markov_notes[name] = ev["chain"].generate(n_steps)
                    mk_idx += 1

        # /bang/clock step total_steps
        try:
            assert client is not None
            client.send_message("/bang/clock", [step, n_steps])

            for note, dna, vtype in voices:
                if vtype == "cc" or note == 0:
                    continue
                name    = _voice_label(note, vtype)
                density = _state["voice_density"].get(name, 1.0)

                if vtype == "babka":
                    continue  # timing Babka incompatible avec un clock step-par-step

                compiled = compile_dna(dna)
                row      = compiled[step % len(compiled)]
                trig, vel, prob, ratch, jit = row

                if trig and random.random() < prob * density:
                    osc_note = markov_notes.get(name, [note] * n_steps)[step] if vtype in ("markov", "bl") else note
                    client.send_message(f"/bang/{name}", [step, int(vel), int(osc_note)])
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


def _osc_stop() -> None:
    _state["osc_enabled"] = False
    t = _state.get("osc_thread")
    if t and t.is_alive():
        t.join(timeout=1.0)
    _state["osc_thread"] = None


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
        osc_host=_state.get("osc_host", "127.0.0.1"),
        osc_port=_state.get("osc_port", 57120),
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
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal,
                   vel_floor, vel_ceiling, vel_curve, root, scale, seed, swing, markov_channel, vel_humanize)
    # Snapshot avant génération (pour undo)
    if _state["voices"] and _state["last_p"]:
        _state["history"].append((_state["voices"][:], list(_state["plocks"]), dict(_state["last_p"])))

    _state["last_p"]     = p
    _state["ab_current"] = None  # nouvelle génération = hors slot A/B
    voices = _apply_note_remap(_apply_locks(_build_voices(p)))
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
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal,
                   vel_floor, vel_ceiling, vel_curve, root, scale, seed, swing, markov_channel, vel_humanize)

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

    voices = _apply_note_remap(_build_voices(_state["last_p"]))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(_state["last_p"], voices)

    voices_html = jinja.get_template("_voices.html").render(
        voices=[(n, dna_html(d), d, t, _NOTE_NAMES.get(n, f"n{n}")) for n, d, t in voices],
        voice_thin=_state["voice_thin"],
    )
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

    for note, dna, vtype in _state["voices"]:
        if vtype == "cc" or note == 0:
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
            row = compiled[i % dna_len]
            if row[0] <= 0:
                continue
            events.append({
                "step":     i,
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
        else:
            channel = 9
            name    = _NOTE_NAMES.get(note, f"n{note}")
        # Appliquer thinning par voix
        thin = _state["voice_thin"].get(name, 1)
        events = _thin_events(events, thin)
        density = _state["voice_density"].get(name, 1.0)
        if density < 1.0:
            events = [{**e, "prob": round(e["prob"] * density, 3)} for e in events]
        voice_plocks = _state["plocks"][len(voices_data)] if len(voices_data) < len(_state["plocks"]) else []
        voices_data.append({
            "note":    note,
            "name":    name,
            "channel": channel,
            "type":    vtype,
            "events":  events,
            "plocks":  voice_plocks,
            "chord":   _state["voice_chords"].get(name, "mono"),
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

@app.post("/voice/chord", response_class=HTMLResponse)
async def voice_chord(name: Annotated[str, Form()], chord_type: Annotated[str, Form()] = "mono"):
    if chord_type in _VALID_CHORDS:
        _state["voice_chords"][name] = chord_type
    return HTMLResponse(_build_voices_html(_state["voices"]))


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


@app.post("/osc/toggle", response_class=HTMLResponse)
async def osc_toggle():
    if _state.get("osc_enabled"):
        _osc_stop()
    else:
        _osc_start()
    return HTMLResponse(_build_osc_btn())


@app.post("/osc/config", response_class=HTMLResponse)
async def osc_config(host: Annotated[str, Form()] = "127.0.0.1",
                     port: Annotated[int, Form()] = 57120):
    _state["osc_host"] = host.strip() or "127.0.0.1"
    _state["osc_port"] = max(1, min(65535, port))
    return HTMLResponse(_build_osc_btn())


def _build_osc_btn() -> str:
    enabled = _state.get("osc_enabled", False)
    host    = _state.get("osc_host", "127.0.0.1")
    port    = _state.get("osc_port", 57120)
    cls     = "btn-osc active" if enabled else "btn-osc"
    label   = f"OSC ●" if enabled else "OSC ○"
    tip     = f"OSC → {host}:{port} (cliquer pour {'arrêter' if enabled else 'démarrer'})"
    return (f'<span id="osc-btn">'
            f'<button class="{cls}" hx-post="/osc/toggle" hx-target="#osc-btn" hx-swap="outerHTML" title="{tip}">{label}</button>'
            f'</span>')


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
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("BANG_PORT", 7777))
    print(f"BANG Web — http://0.0.0.0:{port}")
    print(f"Sur Tailscale : http://100.64.201.127:{port}")
    uvicorn.run("web:app", host="0.0.0.0", port=port, reload=True)
