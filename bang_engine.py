import hashlib
import json
import math
import os
import random
import time as _time
import urllib.request
from pathlib import Path

import mido
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack

# BANG DNA syntax: each character encodes [trigger, velocity, prob, ratchet, jitter]
DNA_SYMBOLS = ['x', '-', '?', '↺', '░']

_CHAR_MAP = {
    'x': [1, 105, 1.0, 1,  0],   # hit fort, certain
    '-': [0,   0, 0.0, 1,  0],   # silence
    '?': [1,  90, 0.5, 1,  0],   # hit probabiliste (50%)
    '↺': [1, 110, 1.0, 3,  0],   # ratchet x3
    '░': [1,  85, 1.0, 1, 25],   # hit avec jitter ±25 ticks
}

_LOG_FILE = Path(__file__).parent / "bang_sessions.jsonl"
_SSH_KEY_PATHS = ["~/.ssh/id_ed25519", "~/.ssh/id_rsa", "~/.ssh/id_ecdsa"]
_SCAER_LAT = 48.0253
_SCAER_LON = -3.6854


# ---------------------------------------------------------------------------
# Météo — Scaër
# ---------------------------------------------------------------------------

def fetch_weather(timeout: int = 5) -> dict | None:
    """
    Récupère température (°C) et vent (km/h) à Scaër via Open-Meteo (sans clé API).
    Retourne None si hors-ligne ou timeout.
    """
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={_SCAER_LAT}&longitude={_SCAER_LON}"
        "&current=temperature_2m,wind_speed_10m"
        "&forecast_days=1"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read())
        c = data["current"]
        return {"temperature": c["temperature_2m"], "wind_speed": c["wind_speed_10m"]}
    except Exception:
        return None


def weather_dna(weather: dict, length: int = 16) -> str:
    """
    DNA dont la texture est dictée par la météo :
      - Température froide → sparse (silences)
      - Température chaude → dense (triggers)
      - Vent fort → ratchets (↺) et jitter (░)
    """
    temp        = weather.get("temperature", 10.0)
    wind        = weather.get("wind_speed",  10.0)
    density     = max(0.15, min(0.85, (temp + 10) / 40))
    wind_factor = min(1.0, wind / 60)
    result = []
    for _ in range(length):
        if random.random() > density:
            result.append('-')
        else:
            r = random.random()
            if r < wind_factor * 0.25:
                result.append('↺')
            elif r < wind_factor * 0.50:
                result.append('░')
            elif r < 0.40:
                result.append('?')
            else:
                result.append('x')
    return ''.join(result)


def weather_cc_breakpoints(weather: dict, num_points: int = 5) -> list[int]:
    """
    Breakpoints CC pour automation de filtre, modulés par la météo :
      - Froid → cutoff bas (sombre), chaud → cutoff haut (lumineux)
      - Vent fort → amplitude de modulation élevée
    """
    temp  = weather.get("temperature", 10.0)
    wind  = weather.get("wind_speed",  10.0)
    base  = int(max(10, min(100, (temp + 10) / 40 * 110)))
    depth = int(min(60, wind / 60 * 80))
    return [
        max(0, min(127, int(base + math.sin(i / (num_points - 1) * math.pi) * depth)))
        for i in range(num_points)
    ]


# ---------------------------------------------------------------------------
# Entropie & seed
# ---------------------------------------------------------------------------

def generate_seed(weather: dict | None = None) -> str:
    """SHA-256 sur os.urandom + time_ns + clé SSH locale + météo si fournie."""
    entropy = os.urandom(16) + str(_time.time_ns()).encode()
    for path in _SSH_KEY_PATHS:
        full = os.path.expanduser(path)
        if os.path.exists(full):
            try:
                key_data = Path(full).read_bytes()
                mid = len(key_data) // 2
                entropy += key_data[mid:mid + 64]
            except OSError:
                pass
            break
    if weather:
        entropy += f"{weather['temperature']:.1f}{weather['wind_speed']:.1f}".encode()
    return hashlib.sha256(entropy).hexdigest()


def _seed_to_int(seed: str) -> int:
    return int(seed[:16], 16)


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def _log_session(filename: str, seed: str, engine: "BangEngine", weather: dict | None = None) -> None:
    entry = {
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": seed,
        "filename": os.path.basename(filename),
        "bpm": engine.bpm,
        "voices": [
            {
                "type": v["type"],
                "note": v.get("note"),
                "pattern_lengths": [len(p) for p in v["patterns"]],
            }
            for v in engine.voices
        ],
    }
    if weather:
        entry["weather"] = weather
    with open(_LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# DNA helpers
# ---------------------------------------------------------------------------

def compile_dna(dna: str) -> np.ndarray:
    return np.array([_CHAR_MAP.get(c, _CHAR_MAP['-']) for c in dna], dtype=float)


def random_dna(length: int = 16) -> str:
    return ''.join(random.choices(DNA_SYMBOLS, k=length))


def morph_dna(p1: str, p2: str, mutation_rate: float = 0.2) -> str:
    """Croisement + mutation entre deux patterns DNA."""
    length = min(len(p1), len(p2))
    mid = length // 2
    child = list(p1[:mid] + p2[mid:length])
    for i in range(len(child)):
        if random.random() < mutation_rate:
            child[i] = random.choice(DNA_SYMBOLS)
    return ''.join(child)


def mutate_dna(dna: str, intensity: float = 0.2) -> str:
    """Corruption progressive : glisse chaque caractère vers un symbole adjacent."""
    result = []
    for c in dna:
        if random.random() < intensity:
            idx = DNA_SYMBOLS.index(c) if c in DNA_SYMBOLS else 0
            shift = random.choice([-1, 1])
            result.append(DNA_SYMBOLS[max(0, min(len(DNA_SYMBOLS) - 1, idx + shift))])
        else:
            result.append(c)
    return ''.join(result)


# ---------------------------------------------------------------------------
# Chaîne de Markov
# ---------------------------------------------------------------------------

class MarkovChain:
    """
    Tableau de probabilités de transition entre notes MIDI.
    Génère des lignes mélodiques/basse avec mémoire d'un pas.
    """

    def __init__(self, notes: list[int], transitions: dict | None = None):
        self.notes = notes
        if transitions:
            self.matrix = {n: dict(row) for n, row in transitions.items()}
            self._normalize()
        else:
            uniform = 1.0 / len(notes)
            self.matrix = {n: {m: uniform for m in notes} for n in notes}

    def _normalize(self) -> None:
        for row in self.matrix.values():
            total = sum(row.values())
            if total > 0:
                for k in row:
                    row[k] /= total

    def next_note(self, current: int) -> int:
        row = self.matrix.get(current, {n: 1 / len(self.notes) for n in self.notes})
        return random.choices(list(row.keys()), weights=list(row.values()), k=1)[0]

    def generate(self, length: int, start: int | None = None) -> list[int]:
        note = start if start is not None else random.choice(self.notes)
        seq = [note]
        for _ in range(length - 1):
            note = self.next_note(note)
            seq.append(note)
        return seq


def dark_chain() -> MarkovChain:
    """
    Pentatonique mineure en registre grave (A1–G2), gravité vers les basses.
    A1=33, C2=36, D2=38, E2=40, G2=43.
    """
    notes = [33, 36, 38, 40, 43]
    return MarkovChain(notes, transitions={
        33: {33: 0.40, 36: 0.30, 38: 0.20, 40: 0.07, 43: 0.03},
        36: {33: 0.30, 36: 0.30, 38: 0.25, 40: 0.12, 43: 0.03},
        38: {33: 0.20, 36: 0.25, 38: 0.30, 40: 0.20, 43: 0.05},
        40: {33: 0.15, 36: 0.20, 38: 0.30, 40: 0.25, 43: 0.10},
        43: {33: 0.10, 36: 0.15, 38: 0.30, 40: 0.30, 43: 0.15},
    })


# ---------------------------------------------------------------------------
# Moteur
# ---------------------------------------------------------------------------

class BangEngine:
    """
    Séquenceur MIDI multi-voix basé sur la syntaxe DNA BANG.

    Trois types de voix :
    - add_voice()        : voix rythmique. dna peut être une liste de patterns
                           (polyrythmie dynamique : les patterns se succèdent cycle après cycle).
    - add_markov_voice() : voix mélodique — rythme par DNA, hauteur par chaîne de Markov.
    - add_cc_drone()     : automation CC continue (filtre, réverb…) interpolée sur la séquence.

    Chaque export est seedé de façon déterministe et loggé dans bang_sessions.jsonl.
    """

    def __init__(self, bpm: int = 124, ticks_per_step: int = 120):
        self.bpm = bpm
        self.ticks_per_step = ticks_per_step
        self.voices: list[dict] = []
        self.cc_tracks: list[dict] = []
        self.last_seed: str | None = None

    def add_voice(self, note: int, dna: str | list[str], channel: int = 0) -> "BangEngine":
        """
        Voix rythmique/harmonique.
        dna : une string ou une liste de strings pour la polyrythmie dynamique.
        Avec une liste, le moteur passe au pattern suivant après chaque cycle complet.
        """
        patterns = [compile_dna(d) for d in ([dna] if isinstance(dna, str) else dna)]
        self.voices.append({"type": "drum", "note": note, "patterns": patterns, "channel": channel})
        return self

    def add_markov_voice(
        self,
        chain: MarkovChain,
        trigger_dna: str | list[str],
        velocity: int = 95,
        channel: int = 0,
    ) -> "BangEngine":
        """
        Voix mélodique : le rythme est défini par trigger_dna (DNA classique),
        la hauteur des notes est générée par la chaîne de Markov.
        trigger_dna peut aussi être une liste pour la polyrythmie dynamique.
        """
        patterns = [compile_dna(d) for d in ([trigger_dna] if isinstance(trigger_dna, str) else trigger_dna)]
        self.voices.append({
            "type": "markov",
            "chain": chain,
            "patterns": patterns,
            "velocity": velocity,
            "channel": channel,
        })
        return self

    def add_cc_drone(
        self,
        control: int = 74,
        channel: int = 0,
        breakpoints: list[int] | None = None,
    ) -> "BangEngine":
        """
        Automation CC continue, interpolée linéairement sur la durée de la séquence.
        breakpoints : valeurs (0-127) réparties uniformément sur num_steps.
        Ex: [20, 100, 20] → sweep up/down du filtre.
        """
        self.cc_tracks.append({
            "control": control,
            "channel": channel,
            "breakpoints": breakpoints or [64],
        })
        return self

    def export_midi(
        self,
        num_steps: int = 64,
        filename: str = "output.mid",
        seed: str | None = None,
        weather: dict | None = None,
    ) -> str:
        if seed is None:
            seed = generate_seed(weather=weather)
        random.seed(_seed_to_int(seed))
        np.random.seed(_seed_to_int(seed) % (2 ** 32))
        self.last_seed = seed

        # Tuple: (abs_tick, priority, msg_type, channel, param, value)
        # msg_type 'note_on'/'note_off' → param=note, value=velocity
        # msg_type 'control_change'     → param=control, value=cc_value
        events: list[tuple] = []

        # --- Voix note (drum + markov) ---
        for voice in self.voices:
            patterns = voice["patterns"]
            channel  = voice.get("channel", 0)

            markov_notes = None
            if voice["type"] == "markov":
                markov_notes = voice["chain"].generate(num_steps)

            pattern_idx     = 0
            step_in_pattern = 0

            for i in range(num_steps):
                pattern              = patterns[pattern_idx]
                trig, vel, prob, ratch, jit = pattern[step_in_pattern]

                if voice["type"] == "markov":
                    note = markov_notes[i]
                    vel  = float(voice["velocity"])
                else:
                    note = voice["note"]

                if trig == 1 and random.random() < prob:
                    abs_start    = i * self.ticks_per_step
                    actual_start = max(0, abs_start + int(random.uniform(-jit, jit)))
                    r_div = int(max(1, ratch))
                    r_dur = self.ticks_per_step // r_div

                    for r in range(r_div):
                        t_on = actual_start + r * r_dur
                        events.append((t_on,         1, 'note_on',  channel, note, int(vel)))
                        events.append((t_on + r_dur, 0, 'note_off', channel, note, 0))

                # Avance dans le pattern courant, passe au suivant après un cycle complet
                step_in_pattern += 1
                if step_in_pattern >= len(pattern):
                    step_in_pattern = 0
                    pattern_idx = (pattern_idx + 1) % len(patterns)

        # --- Automation CC ---
        for cc in self.cc_tracks:
            control = cc["control"]
            channel = cc["channel"]
            bps     = cc["breakpoints"]

            for i in range(num_steps):
                if len(bps) == 1:
                    val = bps[0]
                else:
                    t    = i / (num_steps - 1) * (len(bps) - 1)
                    idx  = int(t)
                    frac = t - idx
                    a    = bps[min(idx,     len(bps) - 1)]
                    b    = bps[min(idx + 1, len(bps) - 1)]
                    val  = int(a * (1 - frac) + b * frac)
                events.append((i * self.ticks_per_step, 0, 'control_change', channel, control, max(0, min(127, val))))

        events.sort(key=lambda e: (e[0], e[1]))

        mid   = MidiFile(ticks_per_beat=480)
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('text', text=f'BANG_SEED:{seed}', time=0))

        current_tick = 0
        for abs_tick, _, msg_type, channel, param, value in events:
            delta = abs_tick - current_tick
            if msg_type == 'control_change':
                track.append(Message('control_change', control=param, value=value, channel=channel, time=delta))
            else:
                track.append(Message(msg_type, note=param, velocity=value, channel=channel, time=delta))
            current_tick = abs_tick

        mid.save(filename)
        _log_session(filename, seed, self, weather=weather)
        print(f"Exported: {os.path.abspath(filename)}  [seed: {seed[:16]}…]")
        return filename

    def save_session(self, filename: str = "session.npy") -> None:
        data = [
            {"note": v["note"], "matrix": v["patterns"][0]}
            for v in self.voices
            if v["type"] == "drum"
        ]
        np.save(filename, data, allow_pickle=True)
        print(f"Session sauvegardée : {filename}")

    def load_session(self, filename: str = "session.npy") -> bool:
        if not os.path.exists(filename):
            return False
        data = np.load(filename, allow_pickle=True)
        for d in data:
            matrix = d["matrix"]
            self.voices.append({
                "type": "drum",
                "note": int(d["note"]),
                "patterns": [matrix],
                "channel": 0,
            })
        print(f"Session chargée : {filename}")
        return True


if __name__ == "__main__":
    engine = BangEngine(bpm=110)
    kick = morph_dna("x---x---x---x---", "x---?---x↺--░---")
    engine.add_voice(36, kick)
    engine.add_voice(38, "----x-------x---")
    engine.add_voice(42, "x-x-x-x-x-x-x-x")
    engine.add_markov_voice(dark_chain(), trigger_dna=["x-?-░", "x---?---"])
    engine.add_cc_drone(control=74, breakpoints=[20, 80, 100, 60, 20])
    engine.export_midi(num_steps=64, filename="morph_test.mid")
    engine.save_session("dna_precieux.npy")
