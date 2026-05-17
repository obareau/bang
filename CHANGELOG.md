# Changelog — BANG · Dark Umbrae Sequencer

## [0.2.0] — 2026-05-17

### Modes de génération

- **Noise ◼** — 8 voix aux cycles asymétriques (5/7/9/11/13 pas), haute entropie, hihat ultra-contrôlé (~2 impacts par pattern). Pour le Rhythmic Noise.
- **Ambient ◌** — 3 voix ultra-sparse sur la longueur totale du pattern, silences longs, jitter minimal. Pour le Dark Ambient.

### Presets drum machine

- **Tekno** — Baby Audio Tekno v1.001, mapping séquentiel C1→G1 (Hat A = E1, Tom L = G1).
- **Battery 4** — NI Battery 4, mapping GM standard.
- **LinnDrum** — mapping historique Linn LM-1.
- **Volca Drum** ★ — 6 parts indépendantes sur canaux MIDI 1–6, avec p-locks CC générés automatiquement (sweep / texture / spike).

### Song export ⬡

Export structuré en **30 fichiers MIDI** organisés en 9 groupes avec préfixe numéroté :

| Groupe | Fichiers | Mode | Rôle |
|--------|----------|------|------|
| `01a–01d` | 4 | Ambient | Intro — montée progressive |
| `02a` | 1 | Noise | Transition |
| `03a–03h` | 8 | Noise | Couplets — variations subtiles |
| `04a` | 1 | Ambient | Break — rupture volontaire |
| `05a–05d` | 4 | Noise | Couplet 2 |
| `06a–06d` | 4 | Noise | Climax — chaos maximal |
| `07a–07b` | 2 | Ambient | Break 2 |
| `08a–08b` | 2 | Ambient | Outro — dissolution |
| `09a–09d` | 4 | Ambient | Fin — ultra-sparse |

**Cohérence temporelle** : chaque variation morphe le DNA de la précédente (`mutate_dna`). Les breaks sont régénérés indépendamment pour rompre délibérément la continuité.

### Archive ☰

- Modal de navigation de tous les exports serveur, groupés par session song.
- **Favoris ⭐** — épingler une session réussie en haut de la liste (persisté dans `bang_favorites.json`).
- **Régénération ↺** — relancer 30 nouveaux fichiers depuis les mêmes paramètres chaos/BPM/gravity/cc_depth. Params persistés dans `bang_song_params.json`.

### Autres

- **Drag & drop MIDI → DAW** — glisser un fichier depuis le log vers Ableton Live / Logic (Chrome, API DownloadURL).
- **Track MIDI nommé** — le nom de piste dans le .mid correspond au nom du fichier (sans `.mid`), visible dans le piano roll du DAW.

---

## [0.1.0] — 2025 (initial)

- Moteur DNA (`bang_engine.py`) — polyrythmie, chaîne de Markov, météo, seeds SHA-256.
- Interfaces : Web (FastAPI + HTMX), TUI (Textual), CLI (argparse + MIDI physique).
- Modes : `morph`, `random`, `weather`, `markov`, `phase2`.
- Presets : GM, TR-808, TR-909, MPC60.
- Export MIDI simple, log de session, seed embedé dans le fichier.
