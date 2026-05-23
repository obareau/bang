# Changelog — BANG · Dark Umbrae Sequencer

## [0.5.1] — 2026-05-23

### Séquençage & génération

- **Seed cliquable dans le log** (#1) — cliquer un seed dans le log le copie dans le champ seed et le rend réutilisable.
- **Multi-canal Markov** (#2) — paramètre `markov_channel` (MIDI ch 1–16) pour router la voix mélodique Markov sur n'importe quel canal. Gammes configurables (`root` + `scale`) avec 8 gammes disponibles (penta_min/maj, minor, dorian, phrygien, major, mixo, lydien).
- **Chord mode Markov** (#10) — sélecteur d'accord par voix Markov/KSP : mono, power, minor, major, sus2, sus4, m7, M7, dom7, dim, aug. Accords appliqués à l'export MIDI et au player JS.

### Export MIDI

- **P-locks dans le `.mid`** (#3) — automation CC step-par-step incluse dans l'export multi-piste (type 1). Tempo BPM écrit dans la track 0. Priorité CC avant note_on.
- **Export multi-piste** (#5) — `MidiFile(type=1)` : une track par voix + une track par drone CC. Track nommée par voix, track 0 = tempo + seed.

### Interface voix

- **Lock de voix** (#4) — bouton 🔒 par voix : verrouille le pattern lors des regénérations. Indicateur visuel `voice-locked` (bordure gauche colorée).
- **Densité par voix** (#8) — slider 0–1 par voix : multiplie la probabilité de déclenchement. Persisté en session, appliqué à l'export et au player JS.
- **Undo génération** (#6) — bouton ↩ dans le toolbar : ring buffer de 5 snapshots (voix + plocks + params). Restaure l'état complet.
- **Humanisation velocity** (#7) — paramètre `vel_humanize` (0–40) : décalage aléatoire ±N sur la velocity à chaque note. Appliqué export MIDI et player JS.

### Workflow

- **Comparaison A/B** (#9) — slots A et B pour stocker deux snapshots (voix + plocks + params) et switcher en live. Boutons ▸A ▸B (store) et A○/A● B○/B● (load) dans le toolbar. OOB HTMX pour mise à jour synchronisée.

### Nouveaux modes

- **Keystep Pro ♜** (#12) — mode dédié Arturia Keystep Pro : 3 voix drums (ch10) + 4 pistes mélodiques Markov indépendantes sur ch1-4 (Lead, Bass, Chord, Arp). Chaînes de Markov avec registres différenciés. Chord selector par piste. Steps auto 16. Export multi-piste compatible import KSP.

### OSC output

- **OSC output** (#11) — thread serveur UDP temps réel (`python-osc`). Émet au BPM du pattern courant :
  - `/bang/clock [step, total_steps]` à chaque step
  - `/bang/{NomVoix} [step, velocity, note]` par trigger
  - Régénération des notes Markov au début de chaque cycle
  - Bouton OSC ○/● dans le toolbar + modal config host:port (défaut `127.0.0.1:57120`)
  - Compatible SuperCollider, TouchDesigner, Max/MSP

---

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
