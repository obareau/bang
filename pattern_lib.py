"""BANG! Pattern Library — logique de génération partagée (web.py + Qt6).

Extrait de web.py : _build_voices, _assemble_engine, transforms de voix,
p-locks synth. Framework-agnostic (pas de FastAPI, pas d'état global) —
tout est passé en paramètre pour que web.py et l'app Qt6 partagent
exactement le même comportement sans dupliquer la logique.
"""
from __future__ import annotations

import math
import random

from bang_engine import (
    BangEngine,
    DNA_SYMBOLS,
    MarkovChain,
    SCALE_INTERVALS,
    build_markov_chain,
    morph_dna,
    mutate_dna,
    random_dna,
    weather_cc_breakpoints,
    weather_dna,
)

# ---------------------------------------------------------------------------
# Constantes partagées
# ---------------------------------------------------------------------------

_CHROMATIC = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

ROOTS: dict[str, int] = {
    name: 33 + ((i - 9) % 12)
    for i, name in enumerate(_CHROMATIC)
}  # A→33, A#→34, B→35, C→24, C#→25, … G#→32

NOTE_NAMES: dict[int, str] = {
    24: "Bass", 33: "A1", 36: "Kick", 38: "Snare",
    40: "E1",   42: "HiHat", 43: "G1", 48: "Tom",
}

NOTE_COLOR: dict[int, str] = {
    36: "#38bdf8", 38: "#4ade80", 42: "#fb923c",
    48: "#facc15", 24: "#c084fc", 33: "#67e8f9",
    40: "#f472b6", 43: "#a3e635",
}

VD_PART_NAMES  = ["Punch", "Snap", "HH", "OH", "Perc", "Acc"]
VD_PART_COLORS = ["#38bdf8", "#4ade80", "#fb923c", "#facc15", "#c084fc", "#67e8f9"]

VFM_PART_NAMES  = ["FM1", "FM2", "FM3"]
VFM_PART_COLORS = ["#60a5fa", "#2dd4bf", "#818cf8"]

MF_PART_NAMES  = ["MF1", "MF2", "MF3"]
MF_PART_COLORS = ["#e879f9", "#d946ef", "#a855f7"]

KSP_TRACK_NAMES   = ["Lead", "Bass", "Chord", "Arp"]
KSP_TRACK_COLORS  = ["#c084fc", "#4ade80", "#60a5fa", "#fb923c"]
KSP_OCTAVE_SHIFT  = [24, 0, 12, 24]

VALID_CHORDS = {"mono", "power", "minor", "major", "sus2", "sus4",
                "m7", "M7", "dom7", "dim", "aug"}

GENERATION_MODES = [
    "morph", "random", "weather", "markov", "phase2", "noise", "ambient",
    "babka", "bassline", "volca_kick", "microfreak", "volca_fm",
    "volca_drum", "keystep_pro",
]

# ---------------------------------------------------------------------------
# Chaînes de Markov pondérées par gravité
# ---------------------------------------------------------------------------

def markov_from_gravity(
    gravity: float,
    root_note: int = 33,
    intervals: list | None = None,
) -> MarkovChain:
    ivs  = intervals if intervals is not None else SCALE_INTERVALS["penta_min"]
    base = build_markov_chain(root_note, ivs, num_octaves=1)
    if gravity >= 0.98:
        return base
    notes   = base.notes
    uniform = 1.0 / len(notes)
    matrix  = {
        note: {m: base.matrix[note][m] * gravity + uniform * (1 - gravity) for m in notes}
        for note in notes
    }
    return MarkovChain(notes, matrix)


def bass_chain_from_gravity(
    gravity: float,
    root_note: int = 33,
    intervals: list | None = None,
) -> MarkovChain:
    ivs  = intervals if intervals is not None else SCALE_INTERVALS["penta_min"]
    base = build_markov_chain(root_note, ivs, num_octaves=2)
    if gravity >= 0.98:
        return base
    notes   = base.notes
    uniform = 1.0 / len(notes)
    matrix  = {
        note: {m: base.matrix[note][m] * gravity + uniform * (1 - gravity) for m in notes}
        for note in notes
    }
    return MarkovChain(notes, matrix)


# ---------------------------------------------------------------------------
# Paramètres de génération
# ---------------------------------------------------------------------------

def read_form(
    mode: str = "morph",
    chaos: float = 0.30,
    bpm: int = 110,
    steps: int = 64,
    gravity: float = 0.70,
    cc_depth: float = 0.50,
    out: str = "bang_out.mid",
    temporal: bool = False,
    vel_floor: int = 0,
    vel_ceiling: int = 127,
    vel_curve: float = 1.0,
    root: str = "A",
    scale: str = "penta_min",
    seed: str = "",
    swing: float = 0.0,
    markov_channel: int = 9,
    vel_humanize: int = 0,
    microtiming: float = 1.0,
) -> dict:
    """Valide et normalise les paramètres de génération (mirror de web._read_form)."""
    _steps = max(1, int(steps))
    if mode in ("volca_drum", "volca_kick", "volca_fm"):
        _steps = min(_steps, 16)
    elif mode == "bassline" and _steps > 128:
        _steps = 128
    _root  = root  if root  in ROOTS            else "A"
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


# ---------------------------------------------------------------------------
# Génération des voix — 14 modes (portage exact de web._build_voices)
# ---------------------------------------------------------------------------

def build_voices(p: dict, weather: dict | None = None) -> list[tuple[int, str, str]]:
    """Génère les voix (note, dna, vtype) selon le mode choisi.

    weather : dict {"temperature": float, "wind_speed": float} ou None
    (déclenche seed via _seed_to_int en amont si p["seed"] est fourni — a la
    charge de l'appelant, pattern_lib reste pur côté RNG global comme l'original).
    """
    chaos = p["chaos"]
    mode  = p["mode"]
    w     = weather or {"temperature": 10.0, "wind_speed": 10.0}

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
            if weather:
                voices.append((0, "CC91 réverb (météo)", "cc"))
        return voices

    if mode == "noise":
        _NOISE_VOICES = [
            (36, 11), (38, 7),  (42, 13), (48, 5),
            (40, 9),  (43, 11), (24, 7),  (33, 13),
        ]
        w_dense = [2 + chaos * 3, max(0.1, 2 - chaos * 1.5), 1 + chaos, chaos * 1.5, chaos]
        w_hh    = [0.8, 6.0, 0.4, 0.0, 0.0]
        return [
            (note, mutate_dna(
                ''.join(random.choices(DNA_SYMBOLS, weights=(w_hh if note == 42 else w_dense), k=length)),
                intensity=(chaos * 0.08 if note == 42 else chaos * 0.4)
            ), "drum")
            for note, length in _NOISE_VOICES
        ]

    if mode == "ambient":
        length = p["steps"]
        w2 = [0.3 + chaos * 0.3, 9.0, 0.5 + chaos * 0.2, 0.0, 0.0]
        return [
            (note, mutate_dna(
                ''.join(random.choices(DNA_SYMBOLS, weights=w2, k=length)),
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
        if chaos < 0.30:
            trig_a = "x---x---"
            trig_b = "x-------x-------"
        elif chaos < 0.55:
            trig_a = mutate_dna("x---x-x-", intensity=chaos * 0.5)
            trig_b = mutate_dna("x-------x--x----", intensity=chaos * 0.3)
        else:
            trig_a = mutate_dna("x-x--x-?", intensity=chaos * 0.55)
            trig_b = mutate_dna("?--x-x--x---?---", intensity=chaos * 0.45)
        if chaos < 0.30:
            kick_dna  = "x---x---x---x---"
            snare_dna = "----x-------x---"
            hh_dna    = "x-x-x-x-x-x-x-x"
        elif chaos < 0.55:
            kick_dna  = mutate_dna("x---x--x x---x---", intensity=chaos * 0.4)
            snare_dna = mutate_dna("----x-------x---",  intensity=chaos * 0.3)
            hh_dna    = mutate_dna("x-x-x-x-x?x-x-x-",  intensity=chaos * 0.25)
        else:
            kick_dna  = mutate_dna("x--x-x--x-x--x-?",  intensity=chaos * 0.5)
            snare_dna = mutate_dna("----x---?---x-?-",  intensity=chaos * 0.4)
            hh_dna    = mutate_dna("x?x-x?x-x?x-x?x-",  intensity=chaos * 0.35)
        cc_peak = int(20 + p["cc_depth"] * 80)
        voices = [
            (33, trig_a, "bl"),
            (33, trig_b, "bl"),
            (36, kick_dna,  "drum"),
            (38, snare_dna, "drum"),
            (42, hh_dna,    "drum"),
            (0, f"CC74 → 20…{cc_peak}…20", "cc"),
        ]
        if chaos > 0.35:
            port_peak = int(chaos * 60)
            voices.append((0, f"CC5 portamento ↗{port_peak}", "cc"))
        return voices

    if mode == "volca_kick":
        _VK_BASES = [
            ("x---x---x---x---", "x---?---x---?---"),
            ("x-?-x---x-?-x---", "?---x---?---x---"),
            ("x---x-?-x---x-?-", "x---?-x-x---?-x-"),
        ]
        pair = _VK_BASES[int(chaos * len(_VK_BASES)) % len(_VK_BASES)]
        dna  = morph_dna(pair[0], pair[1], mutation_rate=chaos * 0.35)
        dna  = mutate_dna(dna, intensity=chaos * 0.25)
        return [(60, dna, "vk")]

    if mode == "microfreak":
        _MF_NOTES = [45, 40, 36]
        _MF_BASES = [
            ("x---x-x-x---x---", "x--?x-x-x--?x---"),
            ("--x---x---x---x-", "--x---x?--x---?-"),
            ("x-----------x---", "?-----------?---"),
        ]
        voices = []
        for i, ((base_a, base_b), note) in enumerate(zip(_MF_BASES, _MF_NOTES)):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.45)
            dna = mutate_dna(dna, intensity=chaos * 0.30)
            voices.append((note, dna, f"mf{i}"))
        return voices

    if mode == "volca_fm":
        _VFM_NOTES = [36, 43, 48]
        _VFM_BASES = [
            ("x---x---x---x---", "x---x--?x---x---"),
            ("--x---x---x---x-", "--x?--x---x---x-"),
            ("---?---x--------", "---?--------x---"),
        ]
        voices = []
        for i, ((base_a, base_b), note) in enumerate(zip(_VFM_BASES, _VFM_NOTES)):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.45)
            dna = mutate_dna(dna, intensity=chaos * 0.25)
            voices.append((note, dna, f"vfm{i}"))
        return voices

    if mode == "volca_drum":
        _VD_BASES = [
            ("x---x---x---x---", "x---?---x---?---"),
            ("----x-------x---", "---?x-------x?--"),
            ("x-x-x-x-x-x-x-x", "x-x?x-x-x-x?x-x"),
            ("?---?---?---?---", "?--░?---?---░?--"),
            ("x-?-░-?-x-?-░-?", "?-░-x-░-?-x-░-?"),
            ("---x---?---x---?", "x--?---x---?--x-"),
        ]
        voices = []
        for i, (base_a, base_b) in enumerate(_VD_BASES):
            dna = morph_dna(base_a, base_b, mutation_rate=chaos * 0.4)
            dna = mutate_dna(dna, intensity=chaos * 0.3)
            voices.append((60, dna, f"vd{i}"))
        return voices

    if mode == "keystep_pro":
        return [
            (36, mutate_dna("x---x---x---x---", intensity=chaos * 0.3), "drum"),
            (38, mutate_dna("----x-------x---", intensity=chaos * 0.3), "drum"),
            (42, mutate_dna("x-x-x-x-x-x-x-x", intensity=chaos * 0.2), "drum"),
            (0,  mutate_dna("x---?-x-?---x---", intensity=chaos * 0.5), "ksp1"),
            (0,  mutate_dna("x---x-x-x---x---", intensity=chaos * 0.4), "ksp2"),
            (0,  mutate_dna("?---x---?---x---", intensity=chaos * 0.3), "ksp3"),
            (0,  mutate_dna("x-x---x-x-?---x-", intensity=chaos * 0.5), "ksp4"),
        ]

    return []


# ---------------------------------------------------------------------------
# Label + remap + resize
# ---------------------------------------------------------------------------

def voice_label(note: int, vtype: str) -> str:
    if vtype.startswith("vd"):
        return VD_PART_NAMES[int(vtype[2:])]
    if vtype.startswith("vfm"):
        return VFM_PART_NAMES[int(vtype[3:])]
    if vtype.startswith("mf"):
        return MF_PART_NAMES[int(vtype[2:])]
    if vtype.startswith("ksp"):
        return f"KSP {KSP_TRACK_NAMES[min(int(vtype[3:]) - 1, 3)]}"
    if vtype == "babka":
        return NOTE_NAMES.get(note, f"n{note}") + " ⚗"
    if vtype == "bl":
        return "Bass ♩"
    if vtype == "vk":
        return "VKick"
    return NOTE_NAMES.get(note, f"n{note}")


def apply_note_remap(voices: list, remap: dict) -> list:
    if not remap:
        return voices
    return [
        (n if (vtype.startswith("vd") or vtype.startswith("ksp") or vtype == "bl") else
         remap.get("VKick", n) if vtype == "vk" else
         remap.get(VFM_PART_NAMES[int(vtype[3:])], n) if vtype.startswith("vfm") else
         remap.get(MF_PART_NAMES[int(vtype[2:])], n) if vtype.startswith("mf") else
         remap.get(NOTE_NAMES.get(n, f"n{n}"), n), dna, vtype)
        for n, dna, vtype in voices
    ]


def resize_dna(dna: str, n: int) -> str:
    if not dna or n <= 0 or len(dna) == n:
        return dna
    if len(dna) > n:
        return dna[:n]
    return (dna * (n // len(dna) + 1))[:n]


def apply_voice_steps(voices: list, overrides: dict) -> list:
    if not overrides:
        return voices
    result = []
    for note, dna, vtype in voices:
        if vtype != "cc":
            n = overrides.get(voice_label(note, vtype), 0)
            if n > 0:
                dna = resize_dna(dna, n)
        result.append((note, dna, vtype))
    return result


def apply_locks(new_voices: list, current_voices: list, locked_indices: set) -> list:
    """Remplace les voix lockées dans new_voices par celles de current_voices."""
    result = list(new_voices)
    for idx in locked_indices:
        if idx < len(current_voices) and idx < len(result):
            result[idx] = current_voices[idx]
    return result


def euclid_dna(n: int, k: int) -> str:
    """Distribue k hits sur n steps (Bresenham)."""
    if n <= 0:
        return ""
    k = max(0, min(k, n))
    if k == 0:
        return "-" * n
    return "".join("x" if (i * k % n) < k else "-" for i in range(n))


# ---------------------------------------------------------------------------
# Transforms de voix individuelles (invert / rotate / reverse / double / halve)
# ---------------------------------------------------------------------------

def voice_invert(dna: str) -> str:
    inv = {"x": "-", "-": "x"}
    return "".join(inv.get(c, c) for c in dna)


def voice_rotate(dna: str, n: int) -> str:
    if not dna:
        return dna
    shift = n % len(dna)
    return dna[-shift:] + dna[:-shift] if shift else dna


def voice_reverse(dna: str) -> str:
    return dna[::-1]


def voice_double(dna: str) -> str:
    return dna + dna


def voice_halve(dna: str) -> str:
    if not dna:
        return dna
    return dna[:max(1, len(dna) // 2)]


def voice_vary(dna: str, intensity: float = 0.15) -> str:
    """Mutation garantie non-triviale (retente jusqu'à 8x si rien ne change)."""
    new_dna = mutate_dna(dna, intensity=intensity)
    for _ in range(8):
        if new_dna != dna:
            break
        new_dna = mutate_dna(dna, intensity=intensity)
    return new_dna


# ---------------------------------------------------------------------------
# Assemblage moteur — voices tuples -> BangEngine configuré
# ---------------------------------------------------------------------------

def assemble_engine(p: dict, voices: list[tuple[int, str, str]], weather: dict | None = None) -> BangEngine:
    engine      = BangEngine(
        bpm=p["bpm"],
        vel_floor=p.get("vel_floor", 0),
        vel_ceiling=p.get("vel_ceiling", 127),
        vel_curve=p.get("vel_curve", 1.0),
    )
    root_midi   = ROOTS.get(p.get("root", "A"), 33)
    intervals   = SCALE_INTERVALS.get(p.get("scale", "penta_min"), SCALE_INTERVALS["penta_min"])
    chain       = markov_from_gravity(p["gravity"], root_note=root_midi, intervals=intervals)
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
            engine.add_voice(note, dna, channel=0)
        elif vtype.startswith("vfm"):
            engine.add_voice(note, dna, channel=0)
        elif vtype.startswith("mf"):
            engine.add_voice(note, dna, channel=0)
        elif vtype == "markov":
            engine.add_markov_voice(chain, trigger_dna=dna, channel=p.get("markov_channel", 9))
        elif vtype.startswith("ksp"):
            ch        = int(vtype[3:]) - 1
            oct_shift = KSP_OCTAVE_SHIFT[min(ch, 3)]
            n_octs    = 1 if ch == 1 else 2
            ksp_chain = build_markov_chain(root_midi + oct_shift, intervals, num_octaves=n_octs)
            engine.add_markov_voice(ksp_chain, trigger_dna=dna, channel=ch)
        elif vtype == "bl":
            if bl_chain is None:
                bl_chain = bass_chain_from_gravity(p["gravity"], root_note=root_midi, intervals=intervals)
            engine.add_markov_voice(bl_chain, trigger_dna=dna)
        elif p["mode"] == "phase2" and note == 36 and not kick_done:
            engine.add_voice(note, [dna, mutate_dna("x---x--x", intensity=p["chaos"] * 0.8)])
            kick_done = True
        else:
            engine.add_voice(note, dna)

    if p["mode"] in ("markov", "phase2"):
        engine.add_cc_drone(control=74, breakpoints=breakpoints)
        if p["mode"] == "phase2" and weather:
            bps = weather_cc_breakpoints(weather, num_points=7)
            engine.add_cc_drone(control=91, breakpoints=list(reversed(bps)))

    if p["mode"] == "bassline":
        engine.add_cc_drone(control=74, breakpoints=breakpoints)
        if p["chaos"] > 0.35:
            port_peak = int(p["chaos"] * 60)
            engine.add_cc_drone(control=5, breakpoints=[0, port_peak, port_peak // 2, 0])

    return engine


# ---------------------------------------------------------------------------
# P-locks synthés (Volca Drum / Kick / FM / MicroFreak)
# ---------------------------------------------------------------------------

VD_PLOCK_PROFILE: list[list[tuple]] = [
    [(20, "Rel",     "sweep"),
     (23, "Pitch",   "sweep"),
     (49, "BitCrsh", "spike")],
    [(21, "Rel",     "sweep"),
     (26, "ModAmt",  "texture"),
     (51, "Drive",   "spike")],
    [(29, "ModRate", "texture"),
     (23, "Pitch",   "texture"),
     (50, "Fold",    "spike")],
    [(21, "Rel",     "sweep"),
     (117,"WGDecay", "sweep"),
     (118,"WGBody",  "texture")],
    [(24, "Pitch",   "sweep"),
     (27, "ModAmt",  "texture"),
     (30, "ModRate", "texture")],
    [(49, "BitCrsh", "spike"),
     (50, "Fold",    "spike"),
     (51, "Drive",   "texture")],
]

SYNTH_PLOCK_PROFILES: dict[str, list[tuple]] = {
    "vk": [
        (40, "Pitch",  "sweep"),
        (45, "Decay",  "sweep"),
        (46, "Drive",  "texture"),
        (47, "Fold",   "texture"),
        (48, "BitRed", "spike"),
    ],
    "vfm0": [
        (40, "Algo",   "spike"),
        (41, "Feedbk", "texture"),
        (44, "Op1Lvl", "sweep"),
        (45, "Op2Lvl", "sweep"),
        (42, "LFOSpd", "texture"),
    ],
    "mf0": [
        (13, "Cutoff",  "sweep"),
        (11, "Timbre",  "texture"),
        (12, "Shape",   "texture"),
        (16, "LFOAmt",  "spike"),
        (15, "LFORate", "sweep"),
    ],
}


def plock_values(style: str, steps: int, chaos: float, phase: float = 0.0) -> list[int | None]:
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


def generate_plocks(voices: list, p: dict) -> list:
    """Génère des p-locks (valeurs CC par step) pour les voix synth."""
    volca_modes = ("volca_drum", "volca_kick", "volca_fm")
    steps = min(p["steps"], 16) if p["mode"] in volca_modes else p["steps"]
    chaos = p["chaos"]
    result = []

    for note, dna, vtype in voices:
        if vtype.startswith("vd"):
            idx     = int(vtype[2:])
            profile = VD_PLOCK_PROFILE[idx % len(VD_PLOCK_PROFILE)]
            phase   = idx * 1.4
        elif vtype in SYNTH_PLOCK_PROFILES:
            profile = SYNTH_PLOCK_PROFILES[vtype]
            phase   = 0.0
        else:
            result.append([])
            continue

        result.append([
            {"cc": cc, "name": name, "style": style,
             "values": plock_values(style, steps, chaos, phase)}
            for cc, name, style in profile
        ])

    return result
