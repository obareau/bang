import mido
from mido import Message, MidiFile, MidiTrack
import time
import random
import os

# --- CONFIGURATION ---
BPM = 110  # On ralentit pour plus de lourdeur
TICK = 120 # Ticks MIDI par double-croche

# Pattern Drums (8 pas)
pattern_drums = [
    (36, 110, 1.0), (None, 0, 0), (42, 80, 0.6), (None, 0, 0),
    (38, 100, 1.0), (None, 0, 0), (42, 90, 0.8), (45, 70, 0.3)
]

# Pattern Bass / Drone (5 pas -> crée un décalage cyclique)
# Note, Vélocité, Probabilité
pattern_bass = [
    (24, 70, 0.9),  # Note grave
    (24, 60, 0.4),
    (26, 75, 0.2),  # Variation de tension
    (None, 0, 0),
    (24, 65, 0.6)
]

# Ajoute cette petite fonction au-dessus de ton bloc principal
def mutate(note, intensity):
    """Décale la note aléatoirement selon l'intensité de corruption."""
    if note and random.random() < intensity:
        return note + random.choice([-1, 1, 12, -12]) # Glissement d'un demi-ton ou d'une octave
    return note

# Dans ta boucle de génération, on pourrait l'utiliser comme ça :
# note_b = mutate(note_b, i / num_steps * 0.5) # La corruption grimpe jusqu'à 50% à la fin

def generate_industrial_session(num_steps=64):
    mid = MidiFile()
    
    # Création des deux pistes
    track_drums = MidiTrack()
    track_bass = MidiTrack()
    mid.tracks.extend([track_drums, track_bass])

    print(f"--- BANG V2 : GÉNÉRATION POLYRYTHMIQUE ({num_steps} steps) ---")

    for i in range(num_steps):
        # --- LOGIQUE DRUMS ---
        note_d, vel_d, prob_d = pattern_drums[i % len(pattern_drums)]
        if note_d and random.random() < prob_d:
            track_drums.append(Message('note_on', note=note_d, velocity=vel_d, time=0))
            track_drums.append(Message('note_off', note=note_d, velocity=0, time=TICK))
        else:
            track_drums.append(Message('note_off', note=0, velocity=0, time=TICK))

        # --- LOGIQUE BASS (Polyrythmie ici : i % 5) ---
        note_b, vel_b, prob_b = pattern_bass[i % len(pattern_bass)]
        if note_b and random.random() < prob_b:
            track_bass.append(Message('note_on', note=note_b, velocity=vel_b, time=0))
            track_bass.append(Message('note_off', note=note_b, velocity=0, time=TICK))
        else:
            track_bass.append(Message('note_off', note=0, velocity=0, time=TICK))

    # Sauvegarde
    filename = "bang_polyrythm.mid"
    mid.save(filename)
    print(f"--- EXPORT RÉUSSI : {os.path.abspath(filename)} ---")

if __name__ == "__main__":
    generate_industrial_session(128) # On génère une séquence plus longue