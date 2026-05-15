from bang_engine import (
    BangEngine,
    MarkovChain,
    dark_chain,
    fetch_weather,
    morph_dna,
    mutate_dna,
    random_dna,
    weather_cc_breakpoints,
    weather_dna,
)


def main():
    # --- SESSION 1 : polyrhythmie brute ---
    session1 = BangEngine(bpm=110)
    kick = morph_dna("x---x---x---x---", "x---?---x↺--░---")
    (session1
        .add_voice(36, kick)
        .add_voice(38, "----x-------x---")
        .add_voice(42, "x-x-x-x-x-x-x-x")
        .add_voice(24, "x-?-░"))
    session1.export_midi(num_steps=64, filename="bang_output.mid")

    # --- SESSION 2 : kick corrompu à 40% ---
    session2 = BangEngine(bpm=110)
    (session2
        .add_voice(36, mutate_dna(kick, intensity=0.4))
        .add_voice(38, "----x-------x---")
        .add_voice(42, "x-x-x-x-x-x-x-x")
        .add_voice(24, "x-?-░"))
    session2.export_midi(num_steps=64, filename="bang_corrupted.mid")

    # --- SESSION 3 : DNA aléatoire pur + régénération ---
    session3 = BangEngine(bpm=124)
    dnas3 = [random_dna(length=16) for _ in range(4)]
    for note, dna in zip([36, 38, 42, 48], dnas3):
        session3.add_voice(note, dna)
    session3.export_midi(num_steps=32, filename="bang_random.mid")

    session3_bis = BangEngine(bpm=124)
    for note, dna in zip([36, 38, 42, 48], dnas3):
        session3_bis.add_voice(note, dna)
    session3_bis.export_midi(num_steps=32, filename="bang_random_regen.mid", seed=session3.last_seed)
    print(f"Seed réutilisée : {session3.last_seed}")

    # --- SESSION 4 : entropie météo de Scaër ---
    w = fetch_weather()
    if w:
        print(f"\nMétéo Scaër : {w['temperature']}°C, vent {w['wind_speed']} km/h")
        session4 = BangEngine(bpm=110)
        (session4
            .add_voice(36, weather_dna(w, length=16))
            .add_voice(38, weather_dna(w, length=8))
            .add_voice(42, weather_dna(w, length=16))
            .add_voice(24, weather_dna(w, length=5)))
        session4.export_midi(num_steps=64, filename="bang_meteo.mid", weather=w)
    else:
        print("\nMétéo Scaër : hors-ligne, session météo ignorée")

    # =========================================================================
    # PHASE 2
    # =========================================================================

    # --- SESSION 5 : Markov + polyrythmie dynamique + drone CC ---
    #
    # Kick en polyrythmie dynamique : 3 patterns qui se succèdent cycle après cycle
    #   - "x---x---"     : 8 pas, régulier
    #   - "x---x--x"     : 8 pas, ghost sur le dernier
    #   - "x-x-x---"     : 8 pas, push vers l'avant
    # Basse Markov sur pentatonique mineure grave (A1–G2)
    # CC 74 (filtre) : sweep de 20 → 95 → 20 sur 128 steps
    print("\n--- Phase 2 ---")
    chain = dark_chain()
    session5 = BangEngine(bpm=100)
    (session5
        .add_voice(36, ["x---x---", "x---x--x", "x-x-x---"])
        .add_voice(38, "----x-------x---")
        .add_voice(42, "x-x-x-x-x-x-x-x")
        .add_markov_voice(chain, trigger_dna=["x-?-░", "x---?---"])
        .add_cc_drone(control=74, breakpoints=[20, 60, 95, 70, 40, 20]))
    session5.export_midi(num_steps=128, filename="bang_phase2.mid")

    # --- SESSION 6 : chaîne Markov custom + météo ---
    # Chaîne plus tendue : sauts de quarte, gravité moindre
    tense_chain = MarkovChain(
        notes=[33, 36, 39, 41, 44],  # A1, C2, Eb2, F2, Ab2 (mineure naturelle)
        transitions={
            33: {33: 0.20, 36: 0.35, 39: 0.25, 41: 0.15, 44: 0.05},
            36: {33: 0.25, 36: 0.20, 39: 0.30, 41: 0.20, 44: 0.05},
            39: {33: 0.15, 36: 0.20, 39: 0.25, 41: 0.25, 44: 0.15},
            41: {33: 0.10, 36: 0.20, 39: 0.25, 41: 0.30, 44: 0.15},
            44: {33: 0.10, 36: 0.15, 39: 0.25, 41: 0.30, 44: 0.20},
        },
    )
    if w:
        bps = weather_cc_breakpoints(w, num_points=7)
        session6 = BangEngine(bpm=100)
        (session6
            .add_voice(36, ["x---x---", "x---x--x"])
            .add_voice(38, weather_dna(w, length=16))
            .add_markov_voice(tense_chain, trigger_dna=weather_dna(w, length=8), velocity=90)
            .add_cc_drone(control=74, breakpoints=bps)
            .add_cc_drone(control=91, breakpoints=list(reversed(bps))))  # réverb inverse
        session6.export_midi(num_steps=128, filename="bang_phase2_meteo.mid", weather=w)
        print(f"CC filtre breakpoints : {bps}")
    else:
        print("Météo hors-ligne : session6 ignorée")


if __name__ == "__main__":
    main()
