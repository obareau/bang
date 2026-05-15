from bang_engine import BangEngine, morph_dna, mutate_dna, random_dna


def main():
    # --- SESSION 1 : polyrhythmie brute ---
    # Kick (8 pas) + Snare (8 pas) + Hihat (16 pas) + Bass drone (5 pas)
    # Le décalage Kick/Bass se répète toutes les 40 steps → groove qui respire
    session1 = BangEngine(bpm=110)
    kick = morph_dna("x---x---x---x---", "x---?---x↺--░---")
    (session1
        .add_voice(36, kick)
        .add_voice(38, "----x-------x---")
        .add_voice(42, "x-x-x-x-x-x-x-x")
        .add_voice(24, "x-?-░"))
    session1.export_midi(num_steps=64, filename="bang_output.mid")

    # --- SESSION 2 : même structure, kick corrompu à 40% ---
    session2 = BangEngine(bpm=110)
    (session2
        .add_voice(36, mutate_dna(kick, intensity=0.4))
        .add_voice(38, "----x-------x---")
        .add_voice(42, "x-x-x-x-x-x-x-x")
        .add_voice(24, "x-?-░"))
    session2.export_midi(num_steps=64, filename="bang_corrupted.mid")

    # --- SESSION 3 : DNA aléatoire pur ---
    session3 = BangEngine(bpm=124)
    for note in [36, 38, 42, 48]:
        session3.add_voice(note, random_dna(length=16))
    session3.export_midi(num_steps=32, filename="bang_random.mid")


if __name__ == "__main__":
    main()
