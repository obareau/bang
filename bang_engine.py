import numpy as np
import mido
from mido import Message, MidiFile, MidiTrack
import random
import os

class BangEngine:
    def __init__(self, bpm=124, steps=16):
        self.bpm = bpm
        self.steps = steps
        self.matrix = np.zeros((steps, 5))
        self.dna_pool = ["x---x---x---x---", "x-x-x-x-x-x-x-x-", "x---?---x↺--░---"]

    # --- NOUVEAU : GESTION DE LA MATRICE ---
    def save_matrix(self, filename="last_session.npy"):
        np.save(filename, self.matrix)
        print(f"Matrice sauvegardée : {filename}")

    def load_matrix(self, filename="last_session.npy"):
        if os.path.exists(filename):
            self.matrix = np.load(filename)
            print(f"Matrice chargée : {filename}")
            return True
        return False

    def display_matrix(self):
        print("\n--- ÉTAT ACTUEL DE LA MATRICE BANG ---")
        print(self.matrix)

    # --- NOUVEAU : GÉNÉRATION ALÉATOIRE PURE ---
    def generate_random_dna(self):
        symbols = ['x', '-', '?', '↺', '░']
        return ''.join(random.choices(symbols, k=self.steps))

    # --- CORE LOGIC (V1.3 Optimisée) ---
    def _compile_char(self, char):
        logic = {'x': [1, 105, 1.0, 1, 0], '-': [0, 0, 0.0, 1, 0],
                 '?': [1, 90, 0.5, 1, 0], '↺': [1, 110, 1.0, 3, 0],
                 '░': [1, 85, 1.0, 1, 25]}
        return logic.get(char, [0, 0, 0.0, 1, 0])

    def load_syntax(self, syntax_string):
        """Remplit la matrice et retourne le statut (Suggestion Lica)"""
        try:
            data = [self._compile_char(c) for c in syntax_string[:self.steps]]
            self.matrix = np.array(data)
            return True
        except Exception as e:
            print(f"Erreur : {e}")
            self.matrix = np.zeros((self.steps, 5))
            return False

    def export_midi(self, filename="output.mid", note=36):
        mid = MidiFile(); track = MidiTrack(); mid.tracks.append(track)
        tpb = 480; tps = tpb // 4; current_abs_tick = 0
        
        for i in range(self.steps):
            ideal_start = i * tps
            trig, vel, prob, ratch, jit = self.matrix[i]
            if trig == 1 and random.random() < prob:
                actual_start = max(0, ideal_start + int(random.uniform(-jit, jit)))
                r_div = int(max(1, ratch))
                r_duration = tps // r_div
                for r in range(r_div):
                    note_on_tick = actual_start + (r * r_duration)
                    track.append(Message('note_on', note=note, velocity=int(vel), time=max(0, note_on_tick - current_abs_tick)))
                    track.append(Message('note_off', note=note, velocity=0, time=r_duration))
                    current_abs_tick = note_on_tick + r_duration
        mid.save(filename)
        return filename

    # --- NOUVEAU : WRAPPERS DE GÉNÉRATION ---
    def quick_generate(self, mode="morph", filename="quick_out.mid"):
        """Génère et exporte en une seule commande"""
        dna = self.generate_random_dna() if mode == "random" else self.dna_morph()
        if self.load_syntax(dna):
            return self.export_midi(filename)
        return None

    def dna_morph(self, mutation_rate=0.2):
        p1, p2 = random.sample(self.dna_pool, 2)
        child = list(p1[:self.steps//2] + p2[self.steps//2:])
        symbols = ['x', '-', '?', '↺', '░']
        for i in range(len(child)):
            if random.random() < mutation_rate: child[i] = random.choice(symbols)
        return "".join(child)

if __name__ == "__main__":
    engine = BangEngine()
    # Test du livrable V1.4
    engine.quick_generate(mode="morph", filename="morph_test.mid")
    engine.save_matrix("dna_precieux.npy")
    engine.display_matrix()