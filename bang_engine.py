import hashlib
import json
import os
import random
import time as _time
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

# Chemins SSH candidats pour l'entropie additionnelle
_SSH_KEY_PATHS = ["~/.ssh/id_ed25519", "~/.ssh/id_rsa", "~/.ssh/id_ecdsa"]


# ---------------------------------------------------------------------------
# Entropie & seed
# ---------------------------------------------------------------------------

def generate_seed() -> str:
    """
    Seed cryptographique SHA-256 issue de :
      - os.urandom(16) : entropie système
      - time.time_ns() : unicité temporelle (microsecondes)
      - fragment de clé SSH locale si disponible
    """
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
    return hashlib.sha256(entropy).hexdigest()


def _seed_to_int(seed: str) -> int:
    return int(seed[:16], 16)


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

def _log_session(filename: str, seed: str, engine: "BangEngine") -> None:
    entry = {
        "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seed": seed,
        "filename": os.path.basename(filename),
        "bpm": engine.bpm,
        "voices": [
            {"note": v["note"], "pattern_len": len(v["matrix"])}
            for v in engine.voices
        ],
    }
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
# Moteur
# ---------------------------------------------------------------------------

class BangEngine:
    """
    Séquenceur MIDI multi-voix basé sur la syntaxe DNA BANG.

    Chaque voix a sa propre longueur de pattern → polyrhythmie naturelle.
    Ex: kick 8 pas + bass 5 pas = décalage cyclique toutes les 40 steps.

    La seed cryptographique est embarquée dans chaque MIDI exporté et loggée
    dans bang_sessions.jsonl pour pouvoir régénérer un fichier à l'identique.
    """

    def __init__(self, bpm: int = 124, ticks_per_step: int = 120):
        self.bpm = bpm
        # 120 ticks/step = 16th note à 480 ticks/beat (standard MIDI)
        self.ticks_per_step = ticks_per_step
        self.voices: list[dict] = []
        self.last_seed: str | None = None

    def add_voice(self, note: int, dna: str) -> "BangEngine":
        self.voices.append({"note": note, "matrix": compile_dna(dna)})
        return self

    def export_midi(
        self,
        num_steps: int = 64,
        filename: str = "output.mid",
        seed: str | None = None,
    ) -> str:
        if seed is None:
            seed = generate_seed()
        random.seed(_seed_to_int(seed))
        np.random.seed(_seed_to_int(seed) % (2 ** 32))
        self.last_seed = seed

        events: list[tuple] = []

        for voice in self.voices:
            note = voice["note"]
            matrix = voice["matrix"]
            pattern_len = len(matrix)

            for i in range(num_steps):
                trig, vel, prob, ratch, jit = matrix[i % pattern_len]
                if trig != 1 or random.random() >= prob:
                    continue

                abs_start = i * self.ticks_per_step
                actual_start = max(0, abs_start + int(random.uniform(-jit, jit)))
                r_div = int(max(1, ratch))
                r_dur = self.ticks_per_step // r_div

                for r in range(r_div):
                    t_on = actual_start + r * r_dur
                    events.append((t_on,         1, 'note_on',  note, int(vel)))
                    events.append((t_on + r_dur, 0, 'note_off', note, 0))

        events.sort(key=lambda e: (e[0], e[1]))

        mid = MidiFile(ticks_per_beat=480)
        track = MidiTrack()
        mid.tracks.append(track)

        # Seed embarquée dans les métadonnées MIDI → régénération possible
        track.append(MetaMessage('text', text=f'BANG_SEED:{seed}', time=0))

        current_tick = 0
        for abs_tick, _, msg_type, note, vel in events:
            delta = abs_tick - current_tick
            track.append(Message(msg_type, note=note, velocity=vel, time=delta))
            current_tick = abs_tick

        mid.save(filename)
        _log_session(filename, seed, self)
        print(f"Exported: {os.path.abspath(filename)}  [seed: {seed[:16]}…]")
        return filename

    def save_session(self, filename: str = "session.npy") -> None:
        data = [{"note": v["note"], "matrix": v["matrix"]} for v in self.voices]
        np.save(filename, data, allow_pickle=True)
        print(f"Session sauvegardée : {filename}")

    def load_session(self, filename: str = "session.npy") -> bool:
        if not os.path.exists(filename):
            return False
        data = np.load(filename, allow_pickle=True)
        self.voices = [{"note": int(d["note"]), "matrix": d["matrix"]} for d in data]
        print(f"Session chargée : {filename}")
        return True


if __name__ == "__main__":
    engine = BangEngine(bpm=110)
    kick = morph_dna("x---x---x---x---", "x---?---x↺--░---")
    engine.add_voice(36, kick)
    engine.add_voice(38, "----x-------x---")
    engine.add_voice(42, "x-x-x-x-x-x-x-x")
    engine.add_voice(24, "x-?-░")
    engine.export_midi(num_steps=64, filename="morph_test.mid")
    engine.save_session("dna_precieux.npy")
