from bang_engine import BangEngine, fetch_weather, morph_dna, mutate_dna, random_dna, weather_dna


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

    # --- SESSION 3 : DNA aléatoire pur ---
    session3 = BangEngine(bpm=124)
    dnas3 = [random_dna(length=16) for _ in range(4)]
    for note, dna in zip([36, 38, 42, 48], dnas3):
        session3.add_voice(note, dna)
    session3.export_midi(num_steps=32, filename="bang_random.mid")

    # --- RÉGÉNÉRATION : même seed + même DNA → MIDI bit-à-bit identique ---
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
            .add_voice(36, weather_dna(w, length=16))   # kick sculpté par la temp
            .add_voice(38, weather_dna(w, length=8))    # snare plus court
            .add_voice(42, weather_dna(w, length=16))   # hihat
            .add_voice(24, weather_dna(w, length=5)))   # bass drone (polyrhythmie)
        session4.export_midi(num_steps=64, filename="bang_meteo.mid", weather=w)
    else:
        print("\nMétéo Scaër : hors-ligne, session météo ignorée")


if __name__ == "__main__":
    main()
