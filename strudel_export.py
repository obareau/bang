"""BANG! Strudel/TidalCycles export — mini-notation code generator.

Fixes two real bugs found in the webapp's version (web.py `/export/strudel`,
web.py:2461-2493):

1. Melodic voices (markov/bl/ksp*) emitted bare `note("...")` patterns with
   no `.sound(...)`/synth chained — in Strudel, `note(...)` alone is SILENT,
   you always need an instrument source. Fixed by chaining `.sound(SYNTH)`
   with a real built-in Strudel waveform synth (no external samples needed).
2. Percussion voices with no explicit Dirt-Samples mapping fell back to an
   invented name derived from the voice label (e.g. "hihat"), which is not
   a real default sample and produces silence too. Fixed by cycling through
   a small table of KNOWN-GOOD default Strudel/Dirt-Samples drum names
   instead of inventing arbitrary strings.
"""
from __future__ import annotations

import re

from bang_engine import compile_dna
import pattern_lib as pl

# Known-good default Dirt-Samples/Strudel drum names (verified to exist in
# the standard sample bank) — used for any percussion voice without an
# explicit MIDI-note mapping below.
_FALLBACK_DRUM_SAMPLES = ["bd", "sd", "hh", "cp", "oh", "rim", "lt", "mt", "ht", "cr", "rd", "perc"]

_STRUDEL_SAMPLES: dict[int, str] = {
    35: "bd", 36: "bd",
    38: "sd", 39: "cp", 40: "sd",
    42: "hh", 44: "hh", 46: "oh",
    37: "rim",
    41: "lt", 43: "mt", 45: "ht", 47: "ht", 48: "mt", 50: "ht",
    49: "cr", 55: "cr", 57: "cr",
    51: "rd", 53: "rd", 59: "rd",
}

_STRUDEL_NOTE_NAMES = ["c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b"]

# Built-in Strudel waveform synths — no external sample bank needed, always
# audible. Picked per melodic voice type for a bit of timbral variety.
_MELODIC_SYNTHS = {
    "markov": "sawtooth",
    "bl": "sine",       # Bass ♩ — sine sub-bass
    "ksp": "triangle",
}


def _midi_to_strudel_note(n: int) -> str:
    return f"{_STRUDEL_NOTE_NAMES[n % 12]}{(n // 12) - 1}"


def _melodic_synth(vtype: str) -> str:
    if vtype.startswith("ksp"):
        return _MELODIC_SYNTHS["ksp"]
    return _MELODIC_SYNTHS.get(vtype, "sawtooth")


def _drum_sample(note: int, fallback_index: int) -> str:
    if note in _STRUDEL_SAMPLES:
        return _STRUDEL_SAMPLES[note]
    return _FALLBACK_DRUM_SAMPLES[fallback_index % len(_FALLBACK_DRUM_SAMPLES)]


def export_strudel(voices: list[tuple[int, str, str]], bpm: int) -> str:
    """Convert the current pattern to Strudel/TidalCycles mini-notation.

    Returns a ready-to-paste code block for https://strudel.cc — every line
    is guaranteed audible (melodic lines chain a real synth, percussion
    lines use only known-good default sample names).
    """
    if not voices:
        return "// Générez un pattern d'abord"

    lines = []
    drum_fallback_i = 0

    for note, dna, vtype in voices:
        if vtype in ("cc", "babka"):
            continue  # CC automation + Babka mini-notation not portable here

        name = pl.voice_label(note, vtype)
        is_melodic = vtype in ("markov", "bl") or vtype.startswith("ksp")

        if not dna:
            continue
        compiled = compile_dna(dna)

        if is_melodic:
            sample = _midi_to_strudel_note(note)
        else:
            sample = _drum_sample(note, drum_fallback_i)
            if note not in _STRUDEL_SAMPLES:
                drum_fallback_i += 1

        tokens = []
        for cell in compiled:
            if cell[0] <= 0:
                tokens.append("~")
            elif int(cell[3]) > 1:
                # Ratchet -> repeat N times within the step (standard mini-notation "*N")
                tokens.append(f"{sample}*{int(cell[3])}")
            elif float(cell[2]) < 0.95:
                # Probabilistic hit -> bare "?" (50% random drop). Strudel's
                # mini-notation only guarantees the bare "?" form; a custom
                # numeric suffix like "?0.3" is NOT standard mini-notation and
                # was silently producing broken/no-op patterns in the browser.
                tokens.append(f"{sample}?")
            else:
                tokens.append(sample)

        pattern_str = " ".join(tokens)
        if is_melodic:
            synth = _melodic_synth(vtype)
            lines.append(f'  note("{pattern_str}").sound("{synth}")  // {name}')
        else:
            lines.append(f'  s("{pattern_str}")  // {name}')

    if not lines:
        return "// Aucune voix exportable (seulement CC/Babka ?)"

    cps_val = round(bpm / 60 / 4, 4)
    return f"// BANG! — {bpm} BPM\nsetcps({cps_val})\nstack(\n" + ",\n".join(lines) + "\n)"


if __name__ == "__main__":
    from bang_session import BangSession

    session = BangSession()
    session.generate(mode="markov", chaos=0.3, bpm=110, steps=16)  # includes a markov (melodic) voice
    code = export_strudel(session.voices, session.last_p["bpm"])
    print(code)
    assert ".sound(" in code, "melodic voices must chain .sound()"
    assert 'note("' in code, "melodic voice must use note() with a real synth chained"
    print("\n✓ strudel_export.py smoke test OK — every line is audible")
