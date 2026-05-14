import numpy as np
import mido
from mido import Message, MidiFile, MidiTrack

# --- CONFIGURATION DES VOIX (Note MIDI) ---
# 36=Kick, 38=Snare, 42=Closed Hat, 48=Tom/Glitch
VOICES = [36, 38, 42, 48] 
STEPS = 16

def generate_multi_dna():
    # Création d'une matrice (Voix x Pas x Paramètres)
    # Paramètres: [Trigger, Velocity, Prob, Ratchet]
    matrix = np.zeros((len(VOICES), STEPS, 4))
    
    for v in range(len(VOICES)):
        for s in range(STEPS):
            # Logique de génération simplifiée (Kick sur 1 et 9, le reste aléatoire)
            trigger = 1 if (v == 0 and s % 8 == 0) else (1 if np.random.rand() > 0.7 else 0)
            velocity = np.random.randint(80, 120) if trigger else 0
            prob = 1.0
            ratchet = 3 if (np.random.rand() > 0.9) else 1
            
            matrix[v, s] = [trigger, velocity, prob, ratchet]
    return matrix

def export_midi(matrix):
    mid = MidiFile()
    track = MidiTrack()
    mid.tracks.append(track)
    
    ticks_per_step = 120  # Résolution standard
    
    for s in range(STEPS):
        for v in range(len(VOICES)):
            data = matrix[v, s]
            if data[0] == 1: # Si Trigger
                note = VOICES[v]
                vel = int(data[1])
                ratchet = int(data[3])
                
                # Gestion du Ratchet (subdivision du pas)
                for r in range(ratchet):
                    track.append(Message('note_on', note=note, velocity=vel, time=0))
                    track.append(Message('note_off', note=note, velocity=0, time=int(ticks_per_step/ratchet)))
            else:
                # Si pas de trigger sur cette voix, on avance quand même le temps pour la première voix
                if v == 0:
                    track.append(Message('note_off', note=0, velocity=0, time=ticks_per_step))

    mid.save('bang_multi_fork.mid')
    print("✔ Export terminé : bang_multi_fork.mid (4 voix, 16 pas)")

dna = generate_multi_dna()
export_midi(dna)