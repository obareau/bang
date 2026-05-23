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

import babka as _babka

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

def _log_session(filename: str, seed: str, engine: "BangEngine", weather: dict | None = None, temporal_jitter: bool = False) -> None:
    entry = {
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": seed,
        "filename": os.path.basename(filename),
        "bpm": engine.bpm,
        "voices": [
            {
                "type": v["type"],
                "note": v.get("note"),
                "pattern_lengths": (
                    [len(v["pattern"])] if v["type"] == "babka"
                    else [len(p) for p in v["patterns"]]
                ),
            }
            for v in engine.voices
        ],
    }
    if weather:
        entry["weather"] = weather
    if temporal_jitter:
        entry["temporal_jitter"] = True
    with open(_LOG_FILE, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Velocity processing
# ---------------------------------------------------------------------------

def vel_map(vel: int, floor: int = 0, ceiling: int = 127, curve: float = 1.0) -> int:
    """Map velocity to [floor, ceiling] with optional dynamics shaping.

    curve < 1 : compression  (brings velocities closer together)
    curve = 1 : linear       (just rescales to [floor, ceiling])
    curve > 1 : expansion    (exaggerates dynamic differences)
    """
    if ceiling <= floor:
        return max(1, floor)
    t = max(0.0, min(1.0, vel / 127.0))
    if curve != 1.0:
        t = t ** curve
    return max(1, int(floor + t * (ceiling - floor)))


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


def bass_chain() -> MarkovChain:
    """
    Ligne de basse — Am pentatonique sur 2 octaves (A1→C3).
    Mouvement orienté groove : sauts de quarte/quinte, retour fréquent à la fondamentale.
    A1=33, C2=36, D2=38, E2=40, G2=43, A2=45, C3=48
    """
    notes = [33, 36, 38, 40, 43, 45, 48]
    return MarkovChain(notes, transitions={
        33: {33: 0.18, 36: 0.28, 38: 0.20, 40: 0.14, 43: 0.10, 45: 0.07, 48: 0.03},
        36: {33: 0.22, 36: 0.16, 38: 0.26, 40: 0.16, 43: 0.12, 45: 0.06, 48: 0.02},
        38: {33: 0.14, 36: 0.22, 38: 0.16, 40: 0.24, 43: 0.14, 45: 0.08, 48: 0.02},
        40: {33: 0.10, 36: 0.18, 38: 0.22, 40: 0.16, 43: 0.20, 45: 0.10, 48: 0.04},
        43: {33: 0.08, 36: 0.14, 38: 0.18, 40: 0.22, 43: 0.16, 45: 0.16, 48: 0.06},
        45: {33: 0.14, 36: 0.14, 38: 0.16, 40: 0.18, 43: 0.20, 45: 0.12, 48: 0.06},
        48: {33: 0.20, 36: 0.22, 38: 0.18, 40: 0.16, 43: 0.14, 45: 0.08, 48: 0.02},
    })


# ---------------------------------------------------------------------------
# Gammes configurables — construction algorithmique de chaînes de Markov
# ---------------------------------------------------------------------------

SCALE_INTERVALS: dict[str, list[int]] = {
    "penta_min": [0, 3, 5, 7, 10],        # pentatonique mineure
    "penta_maj": [0, 2, 4, 7, 9],          # pentatonique majeure
    "minor":     [0, 2, 3, 5, 7, 8, 10],   # mineur naturel (éolien)
    "dorian":    [0, 2, 3, 5, 7, 9, 10],   # dorien
    "phrygian":  [0, 1, 3, 5, 7, 8, 10],   # phrygien
    "major":     [0, 2, 4, 5, 7, 9, 11],   # majeur (ionien)
    "mixo":      [0, 2, 4, 5, 7, 9, 10],   # mixolydien
    "lydian":    [0, 2, 4, 6, 7, 9, 11],   # lydien
}


def build_markov_chain(root_note: int, intervals: list[int], num_octaves: int = 1) -> MarkovChain:
    """
    Construit une chaîne de Markov musicale pour n'importe quelle gamme.
    La matrice de transitions est générée algorithmiquement :
    - mouvement par degrés favorisé (décroissance exponentielle avec la distance)
    - gravité vers la tonique et la quinte
    - répétition pénalisée
    """
    notes: list[int] = []
    for oct_i in range(num_octaves):
        for iv in intervals:
            n = root_note + oct_i * 12 + iv
            if 21 <= n <= 108:
                notes.append(n)
    # Note de fermeture — octave supérieure de la fondamentale
    closing = root_note + num_octaves * 12
    if 21 <= closing <= 108:
        notes.append(closing)
    notes = sorted(set(notes))
    if not notes:
        notes = [root_note]

    root_class  = root_note % 12
    fifth_class = (root_note + 7) % 12

    matrix: dict[int, dict[int, float]] = {}
    for i, src in enumerate(notes):
        weights: dict[int, float] = {}
        for j, dst in enumerate(notes):
            dist = abs(i - j)                    # distance en degrés de gamme
            w    = math.exp(-dist * 0.45)        # décroissance par degrés
            if dst % 12 == root_class:
                w *= 1.5                          # gravité vers la tonique
            elif dst % 12 == fifth_class:
                w *= 1.2                          # légère attraction vers la quinte
            if i == j:
                w *= 0.35                         # pénalité répétition
            weights[dst] = w
        total = sum(weights.values())
        matrix[src] = {n: w / total for n, w in weights.items()}

    return MarkovChain(notes, matrix)


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

    def __init__(
        self,
        bpm: int = 124,
        ticks_per_step: int = 120,
        vel_floor: int = 0,
        vel_ceiling: int = 127,
        vel_curve: float = 1.0,
    ):
        self.bpm = bpm
        self.ticks_per_step = ticks_per_step
        self.vel_floor   = vel_floor
        self.vel_ceiling = vel_ceiling
        self.vel_curve   = vel_curve
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

    def add_babka_voice(self, note: int, pattern: str, channel: int = 0) -> "BangEngine":
        """Voix rythmique avec syntaxe Babka (DNA + mini-notation Strudel).

        pattern : chaîne Babka — ex: "x-[x x]-?(3,8)" ou "<x-x- ?-?->"
        Supporte subdivision [...], alternance <...> et euclidien x(n,k) / [x(n,k)].
        """
        self.voices.append({"type": "babka", "note": note, "pattern": pattern, "channel": channel})
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
        temporal_jitter: bool = False,
        swing: float = 0.0,
        plocks: list | None = None,
        vel_humanize: int = 0,
        densities: list[float] | None = None,
    ) -> str:
        """
        temporal_jitter=True : chaque note dont jit>0 reçoit un décalage supplémentaire
        basé sur time_ns() % 1000 — rend chaque performance unique même seed identique.
        """
        if seed is None:
            seed = generate_seed(weather=weather)
        random.seed(_seed_to_int(seed))
        np.random.seed(_seed_to_int(seed) % (2 ** 32))
        self.last_seed = seed

        # Tuple: (abs_tick, priority, msg_type, channel, param, value)
        voice_events: list[list[tuple]] = []

        # --- Voix note (drum + markov + babka) ---
        for vi, voice in enumerate(self.voices):
            channel      = voice.get("channel", 0)
            voice_plocks = plocks[vi] if plocks and vi < len(plocks) else []
            v_density    = densities[vi] if densities and vi < len(densities) else 1.0
            v_events: list[tuple] = []

            # --- Babka ---
            if voice["type"] == "babka":
                note        = voice["note"]
                pat_str     = voice["pattern"]
                total_ticks = num_steps * self.ticks_per_step
                cursor_tick = 0.0
                cyc         = 0
                while cursor_tick < total_ticks:
                    bsteps = _babka.parse(pat_str, cycle=cyc)
                    if not bsteps:
                        break
                    for s in bsteps:
                        if cursor_tick >= total_ticks:
                            break
                        dur_ticks = s.duration * self.ticks_per_step
                        if s.trigger and random.random() < s.prob:
                            base_jit = int(random.uniform(-s.jitter, s.jitter))
                            if temporal_jitter and s.jitter > 0:
                                micro     = _time.time_ns() % 1000
                                base_jit += int((micro / 1000 - 0.5) * s.jitter * 0.5)
                            actual_start = max(0, int(cursor_tick + base_jit))
                            r_div    = int(max(1, s.ratchet))
                            r_dur    = max(1, int(dur_ticks) // r_div)
                            raw_vel  = s.velocity + (random.randint(-vel_humanize, vel_humanize) if vel_humanize else 0)
                            out_vel  = vel_map(raw_vel, self.vel_floor, self.vel_ceiling, self.vel_curve)
                            for r in range(r_div):
                                t_on = actual_start + r * r_dur
                                v_events.append((t_on,         1, 'note_on',  channel, note, out_vel))
                                v_events.append((t_on + r_dur, 0, 'note_off', channel, note, 0))
                        cursor_tick += dur_ticks
                    cyc += 1
                voice_events.append(v_events)
                continue

            patterns = voice["patterns"]

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

                if trig == 1 and random.random() < prob * v_density:
                    swing_off = int(swing * self.ticks_per_step * 0.5) if i % 2 == 1 else 0
                    abs_start = i * self.ticks_per_step + swing_off
                    base_jit  = int(random.uniform(-jit, jit))
                    # Entropie temporelle : microsecondes système → décalage supplémentaire
                    if temporal_jitter and jit > 0:
                        micro    = _time.time_ns() % 1000
                        base_jit += int((micro / 1000 - 0.5) * jit * 0.5)
                    actual_start = max(0, abs_start + base_jit)
                    r_div = int(max(1, ratch))
                    r_dur = self.ticks_per_step // r_div

                    raw_vel = int(vel) + (random.randint(-vel_humanize, vel_humanize) if vel_humanize else 0)
                    out_vel = vel_map(raw_vel, self.vel_floor, self.vel_ceiling, self.vel_curve)
                    for r in range(r_div):
                        t_on = actual_start + r * r_dur
                        v_events.append((t_on,         1, 'note_on',  channel, note, out_vel))
                        v_events.append((t_on + r_dur, 0, 'note_off', channel, note, 0))

                # P-locks : CC step-par-step, indépendants du trigger
                for pl in voice_plocks:
                    vals = pl.get("values", [])
                    if i < len(vals) and vals[i] is not None:
                        v_events.append((i * self.ticks_per_step, 0, 'control_change', channel, pl["cc"], vals[i]))

                step_in_pattern += 1
                if step_in_pattern >= len(pattern):
                    step_in_pattern = 0
                    pattern_idx = (pattern_idx + 1) % len(patterns)

            voice_events.append(v_events)

        # --- Automation CC (drones) ---
        cc_events: list[list[tuple]] = []
        for cc in self.cc_tracks:
            control = cc["control"]
            channel = cc["channel"]
            bps     = cc["breakpoints"]
            cv: list[tuple] = []
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
                cv.append((i * self.ticks_per_step, 0, 'control_change', channel, control, max(0, min(127, val))))
            cc_events.append(cv)

        # --- Assemblage MIDI multi-piste (type 1) ---
        basename = os.path.splitext(os.path.basename(filename))[0]
        mid = MidiFile(type=1, ticks_per_beat=480)

        # Track 0 : tempo + métadonnées
        tempo_track = MidiTrack()
        mid.tracks.append(tempo_track)
        tempo_track.append(MetaMessage('track_name', name=basename, time=0))
        tempo_track.append(MetaMessage('text', text=f'BANG_SEED:{seed}', time=0))
        tempo_track.append(MetaMessage('set_tempo', tempo=int(60_000_000 / self.bpm), time=0))

        def _write_track(trk: MidiTrack, evts: list[tuple]) -> None:
            evts.sort(key=lambda e: (e[0], e[1]))
            cur = 0
            for abs_tick, _, msg_type, ch, param, value in evts:
                delta = abs_tick - cur
                if msg_type == 'control_change':
                    trk.append(Message('control_change', control=param, value=value, channel=ch, time=delta))
                else:
                    trk.append(Message(msg_type, note=param, velocity=value, channel=ch, time=delta))
                cur = abs_tick

        # Une track par voix note
        for vi, (voice, v_events) in enumerate(zip(self.voices, voice_events)):
            vtype = voice["type"]
            ch    = voice.get("channel", 0)
            if vtype == "markov":
                tname = f"markov-ch{ch + 1}"
            elif vtype in ("babka", "drum"):
                tname = f"{vtype}-{voice.get('note', vi)}"
            else:
                tname = f"{vtype}-{vi}"
            trk = MidiTrack()
            mid.tracks.append(trk)
            trk.append(MetaMessage('track_name', name=tname, time=0))
            _write_track(trk, v_events)

        # Une track par drone CC
        for cc, cv in zip(self.cc_tracks, cc_events):
            trk = MidiTrack()
            mid.tracks.append(trk)
            trk.append(MetaMessage('track_name', name=f"CC{cc['control']}", time=0))
            _write_track(trk, cv)

        mid.save(filename)
        _log_session(filename, seed, self, weather=weather, temporal_jitter=temporal_jitter)
        label = f"[seed: {seed[:16]}…]" + (" [+temporal]" if temporal_jitter else "")
        print(f"Exported: {os.path.abspath(filename)}  {label}")
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
