"""BANG Web — Interface FastAPI + HTMX pour le séquenceur Dark Umbrae"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from bang_engine import (
    BangEngine,
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

BASE_DIR   = Path(__file__).parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

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
    "log":        [],   # list of str (HTML)
    "last_file":  None,
    "last_seed":  None,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOTE_NAMES = {
    24: "Bass", 33: "A1", 36: "Kick", 38: "Snare",
    40: "E1",   42: "HiHat", 43: "G1", 48: "Tom",
}

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

    return []


def _assemble_engine(p: dict, voices: list[tuple[int, str, str]]) -> BangEngine:
    engine      = BangEngine(bpm=p["bpm"])
    chain       = _markov_from_gravity(p["gravity"])
    cc_peak     = int(20 + p["cc_depth"] * 100)
    breakpoints = [20, cc_peak, cc_peak, int((20 + cc_peak) / 2), 20]
    kick_done   = False

    for note, dna, vtype in voices:
        if vtype == "cc":
            continue
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
    return {
        "mode":     mode,
        "chaos":    max(0.0, min(1.0, float(chaos))),
        "bpm":      max(1, int(bpm)),
        "steps":    max(1, int(steps)),
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
        voices=[(n, dna_html(d), t, _NOTE_NAMES.get(n, f"n{n}")) for n, d, t in _state["voices"]],
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
    voices = _build_voices(p)
    _state["voices"] = voices
    _state["engine"] = _assemble_engine(p, voices)

    return render("_voices.html",
        voices=[(n, dna_html(d), t, _NOTE_NAMES.get(n, f"n{n}")) for n, d, t in voices],
    )


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
):
    p = _read_form(mode, chaos, bpm, steps, gravity, cc_depth, out, temporal)

    if _state["engine"] is None:
        voices = _build_voices(p)
        _state["voices"] = voices
        _state["engine"] = _assemble_engine(p, voices)

    export_path = str(EXPORT_DIR / p["out"])
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


@app.get("/download/{filename}")
async def download(filename: str):
    path = EXPORT_DIR / filename
    if not path.exists():
        return HTMLResponse("<p>Fichier introuvable</p>", status_code=404)
    return FileResponse(str(path), filename=filename, media_type="audio/midi")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("BANG Web — http://0.0.0.0:8000")
    print(f"Sur Tailscale : http://100.64.201.127:8000")
    uvicorn.run("web:app", host="0.0.0.0", port=8000, reload=True)
