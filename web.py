"""BANG Web — Interface FastAPI + HTMX pour le séquenceur Dark Umbrae"""

from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from bang_engine import (
    BangEngine,
    DNA_SYMBOLS,
    compile_dna,
    fetch_weather,
    morph_dna,
    mutate_dna,
    random_dna,
    weather_cc_breakpoints,
    weather_dna,
)
from cli import _markov_from_gravity

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR      = Path(__file__).parent
EXPORT_DIR    = BASE_DIR / "exports"
PRESETS_FILE  = BASE_DIR / "bang_presets.json"
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


def _generate_plocks(voices: list, p: dict) -> list:
    """Génère des p-locks (valeurs CC par step) pour les parts Volca Drum."""
    import math
    steps = min(p["steps"], 16)
    chaos = p["chaos"]

    result = []
    for note, dna, vtype in voices:
        if not vtype.startswith("vd"):
            result.append([])
            continue

        idx     = int(vtype[2:])
        profile = _VD_PLOCK_PROFILE[idx % len(_VD_PLOCK_PROFILE)]
        plocks  = []

        for cc_num, cc_short, style in profile:
            values: list[int | None] = []
            for step in range(steps):
                t = step / steps

                if style == "sweep":
                    base    = int(55 + 50 * math.sin(2 * math.pi * t + idx * 1.4))
                    jitter  = int(chaos * 28 * (random.random() * 2 - 1))
                    val     = max(0, min(127, base + jitter))
                    density = 0.45 + chaos * 0.3

                elif style == "texture":
                    base    = int(38 + 52 * abs(math.sin(4 * math.pi * t + idx)))
                    jitter  = int(chaos * 44 * (random.random() * 2 - 1))
                    val     = max(0, min(127, base + jitter))
                    density = 0.4 + chaos * 0.35

                else:  # spike
                    # Impulsions rares mais dramatiques
                    if random.random() < chaos * 0.55:
                        val = random.randint(60, 127)
                    else:
                        val = random.randint(0, 35)
                    density = 0.18 + chaos * 0.42

                values.append(val if random.random() < density else None)

            plocks.append({
                "cc":     cc_num,
                "name":   cc_short,
                "style":  style,
                "values": values,
            })

        result.append(plocks)

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
    "voice_thin":      {},  # voice_name -> factor (1 / 2 / 4)
    "max_poly":        0,   # 0 = illimité
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


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
        compiled = compile_dna(dna)
        dna_len  = len(compiled)
        cells    = []
        for i in range(steps):
            step    = compiled[i % dna_len]
            trigger = bool(step[0] > 0)
            prob    = float(step[2])
            ratchet = int(step[3])
            cells.append({
                "trigger": trigger,
                "opacity": round(0.35 + prob * 0.65, 2) if trigger else 0.0,
                "ratchet": ratchet,
            })
        boundaries = [j * dna_len for j in range(1, steps // dna_len + 1) if j * dna_len < steps]
        if vtype.startswith("vd"):
            idx   = int(vtype[2:])
            color = _VD_PART_COLORS[idx]
            name  = _VD_PART_NAMES[idx]
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
            result.append(cell if keep else {**cell, "trigger": False, "opacity": 0.0})
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
            rows[ri]["cells"][step] = {**c, "trigger": False, "opacity": 0.0}
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
        voices=[(n, dna_html(d), t, _voice_label(n, t)) for n, d, t in voices],
        voice_thin=_state["voice_thin"],
    )


_DNA_CLASS = {"x": "dx", "-": "dd", "?": "dq", "↺": "dr", "░": "db"}


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
        w_hh    = [0.5 + chaos, 3.0, 1.5 + chaos, chaos * 0.5, chaos * 0.3]  # hihat plus sparse
        return [
            (note, mutate_dna(
                ''.join(random.choices(DNA_SYMBOLS, weights=(w_hh if note == 42 else w_dense), k=length)),
                intensity=chaos * 0.4
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


def _voice_label(note: int, vtype: str) -> str:
    if vtype.startswith("vd"):
        return _VD_PART_NAMES[int(vtype[2:])]
    return _NOTE_NAMES.get(note, f"n{note}")


def _apply_note_remap(voices: list) -> list:
    remap = _state["note_remap"]
    if not remap:
        return voices
    return [
        (n if vtype.startswith("vd") else remap.get(_NOTE_NAMES.get(n, f"n{n}"), n), dna, vtype)
        for n, dna, vtype in voices
    ]


def _assemble_engine(p: dict, voices: list[tuple[int, str, str]]) -> BangEngine:
    engine      = BangEngine(bpm=p["bpm"])
    chain       = _markov_from_gravity(p["gravity"])
    cc_peak     = int(20 + p["cc_depth"] * 100)
    breakpoints = [20, cc_peak, cc_peak, int((20 + cc_peak) / 2), 20]
    kick_done   = False

    for note, dna, vtype in voices:
        if vtype == "cc":
            continue
        elif vtype.startswith("vd"):
            engine.add_voice(note, dna, channel=int(vtype[2:]))
        elif vtype == "markov":
            engine.add_markov_voice(chain, trigger_dna=dna)
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

    return engine


def _read_form(
    mode:      str   = "morph",
    chaos:     float = 0.30,
    bpm:       int   = 110,
    steps:     int   = 64,
    gravity:   float = 0.70,
    cc_depth:  float = 0.50,
    out:       str   = "bang_out.mid",
    temporal:  str   = "",
) -> dict:
    _steps = max(1, int(steps))
    if mode == "volca_drum":
        _steps = min(_steps, 16)
    return {
        "mode":     mode,
        "chaos":    max(0.0, min(1.0, float(chaos))),
        "bpm":      max(1, int(bpm)),
        "steps":    _steps,
        "gravity":  max(0.0, min(1.0, float(gravity))),
        "cc_depth": max(0.0, min(1.0, float(cc_depth))),
        "out":      out or "bang_out.mid",
        "temporal": bool(temporal),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render("index.html",
        voices=[(n, dna_html(d), t, _voice_label(n, t)) for n, d, t in _state["voices"]],
        voice_thin=_state["voice_thin"],
        max_poly=_state["max_poly"],
        log=_state["log"][-20:],
        weather=_state["weather"],
        last_seed=_state["last_seed"],
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request:  Request,
    mode:     Annotated[str,   Form()] = "morph",
    chaos:    Annotated[float, Form()] = 0.30,
    bpm:      Annotated[int,   Form()] = 110,
    steps:    Annotated[int,   Form()] = 64,
    gravity:  Annotated[float, Form()] = 0.70,
    cc_depth: Annotated[float, Form()] = 0.50,
    out:      Annotated[str,   Form()] = "bang_out.mid",
    temporal: Annotated[str,   Form()] = "",
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal)
    _state["last_p"] = p
    voices = _apply_note_remap(_build_voices(p))
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(p, voices)

    plocks = _generate_plocks(voices, p) if p["mode"] == "volca_drum" else []
    _state["plocks"] = plocks

    pr_html = _build_pr_html(voices, p["steps"], plocks)
    oob     = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(voices) + oob)


@app.post("/export", response_class=HTMLResponse)
async def export(
    request:  Request,
    mode:     Annotated[str,   Form()] = "morph",
    chaos:    Annotated[float, Form()] = 0.30,
    bpm:      Annotated[int,   Form()] = 110,
    steps:    Annotated[int,   Form()] = 64,
    gravity:  Annotated[float, Form()] = 0.70,
    cc_depth: Annotated[float, Form()] = 0.50,
    out:      Annotated[str,   Form()] = "bang_out.mid",
    temporal: Annotated[str,   Form()] = "",
    dest_dir: Annotated[str,   Form()] = "",
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal)

    if _state["engine"] is None:
        voices = _apply_note_remap(_build_voices(p))
        _state["voices"] = voices
        _state["engine"] = _assemble_engine(p, voices)

    target_dir = Path(dest_dir).expanduser() if dest_dir.strip() else EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    if dest_dir.strip() and str(target_dir) not in _state["recent_dirs"]:
        _state["recent_dirs"] = ([str(target_dir)] + _state["recent_dirs"])[:5]

    export_path = str(target_dir / p["out"])
    try:
        _state["engine"].export_midi(
            num_steps=p["steps"],
            filename=export_path,
            weather=_state["weather"],
            temporal_jitter=p["temporal"],
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

    return render("_log_entry.html", entry=entry)


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
    import re
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
        voices=[(n, dna_html(d), t, _NOTE_NAMES.get(n, f"n{n}")) for n, d, t in voices],
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

    voices_data = []
    for note, dna, vtype in _state["voices"]:
        if vtype == "cc" or note == 0:
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
                "velocity": int(row[1]),
                "prob":     round(float(row[2]), 2),
                "ratchet":  int(row[3]),
            })
        if vtype.startswith("vd"):
            channel = int(vtype[2:])
            name    = _VD_PART_NAMES[channel]
        else:
            channel = 9
            name    = _NOTE_NAMES.get(note, f"n{note}")
        # Appliquer thinning par voix
        thin = _state["voice_thin"].get(name, 1)
        events = _thin_events(events, thin)
        voice_plocks = _state["plocks"][len(voices_data)] if len(voices_data) < len(_state["plocks"]) else []
        voices_data.append({
            "note":    note,
            "name":    name,
            "channel": channel,
            "type":    vtype,
            "events":  events,
            "plocks":  voice_plocks,
        })

    # Appliquer le filtre de polyphonie globale
    voices_data = _apply_poly_to_events(voices_data, _state["max_poly"])

    return {
        "ok":      True,
        "bpm":     bpm,
        "steps":   steps,
        "step_ms": step_ms,
        "voices":  voices_data,
    }


@app.post("/voice/thin", response_class=HTMLResponse)
async def voice_thin(name: Annotated[str, Form()], factor: Annotated[int, Form()] = 1):
    _state["voice_thin"][name] = max(1, factor)
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse(_build_voices_html([]))
    pr_html = _build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None)
    oob = f'<div id="pianoroll" hx-swap-oob="innerHTML">{pr_html}</div>'
    return HTMLResponse(_build_voices_html(_state["voices"]) + oob)


@app.post("/poly", response_class=HTMLResponse)
async def set_poly(max_poly: Annotated[int, Form()] = 0):
    _state["max_poly"] = max(0, max_poly)
    if not _state["voices"] or not _state["last_p"]:
        return HTMLResponse("")
    return HTMLResponse(_build_pr_html(_state["voices"], _state["last_p"]["steps"], _state["plocks"] or None))


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
