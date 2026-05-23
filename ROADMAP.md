# BANG! — Roadmap

> État : v0.5.1 · Mis à jour : 2026-05-23

Légende effort : 🟢 < 1h · 🟡 2–4h · 🔴 5h+

---

## Acquis (v0.1 → v0.5.1)

- Entropie multi-sources (temporelle, cryptographique, météo Scaër)
- Markov, Babka, P-locks, presets hardware (Volca Drum/Kick/FM, MicroFreak)
- Web MIDI player + pianoroll synchronisé
- Gammes configurables (12 toniques × 8 modes)
- Swing, seed fixe, session import/export

---

## Trous dans l'existant

| Item | Effort | Notes |
|------|--------|-------|
| **P-locks dans le `.mid` exporté** | 🟡 3h | Générés pour le player mais pas écrits dans le fichier. Passer `plocks` de `web.py` à `export_midi()`, ajouter les CC events dans la track avant chaque note. Implique de refactorer la signature d'`export_midi`. |
| **Multi-canal Markov** | 🟢 1h | Voix mélodique sur ch10 en dur. Ajouter `markov_channel` dans `_read_form()` + select dans le form. Un seul endroit à changer dans `_assemble_engine`. |
| **Seed cliquable dans le log** | 🟢 30min | `onclick` sur la seed dans `_log_entry.html` → remplir `#seed-input`. Zéro backend. |

---

## Features musicales

| Item | Effort | Notes |
|------|--------|-------|
| **Lock de voix** | 🟡 3h | Verrouiller une voix pendant Generate. `_state["locked_voices"]` (set d'index), modifier `_build_voices` pour conserver les voix lockées, bouton 🔒 dans `_voices.html`. Pattern DNA préservé, le reste se régénère autour. |
| **Densité par voix** | 🟡 2h | Curseur 0–1 par voix. Multiplicateur de probabilité sur les triggers au pianoroll et à l'export. Similaire à `voice_thin` mais continu. |
| **Humanisation velocity** | 🟢 1h | Champ `±N` global ou par voix. `random.randint(-n, n)` sur chaque velocity avant clamp. Infrastructure `vel_map` déjà là. |
| **Chord mode Markov** | 🔴 5h | 2–4 notes simultanées depuis la chaîne Markov (intervalles : tierce, quinte, octave). Nouveau vtype `chord`, refacto d'`add_markov_voice`. Pianoroll à adapter pour les clusters. |

---

## Infrastructure

| Item | Effort | Notes |
|------|--------|-------|
| **Export multi-piste** | 🟡 3h | Un `MidiTrack` par voix (actuellement tout sur une track). `MidiFile` le supporte nativement. Ableton/Logic importent ça en clips séparés — grosse amélioration DAW. |
| **Undo génération** | 🟢 1h | Ring buffer des 5 derniers states `(voices, engine, plocks)`. Bouton Undo dans le toolbar, `POST /undo`. Zéro impact sur l'existant. |
| **Comparaison A/B** | 🟡 3h | Deux slots de pattern (`slot_a` / `slot_b`), boutons Store/Compare. Pianoroll toggle ou side-by-side. Utile pour choisir entre deux générations. |

---

## Ambitieux

| Item | Effort | Notes |
|------|--------|-------|
| **OSC output** | 🔴 5h | Envoyer les patterns en OSC en parallèle du MIDI (`python-osc`). Endpoint `/play/osc`. Utile pour SuperCollider, Max/MSP, TouchDesigner. |
| **Mode Keystep Pro** | 🔴 6h | Export formaté pour le séquenceur pas-à-pas Arturia : Gate, Tie, Rest, Slide. Format SysEx propriétaire. Nouveau mode `keystep`. |

---

## Ordre suggéré

1. 🟢 Seed cliquable — 30min, QoL immédiat
2. 🟢 Multi-canal Markov — 1h, débloque le routing DAW
3. 🟡 P-locks dans le `.mid` — 3h, cohérence critique hardware
4. 🟡 Lock de voix — 3h, workflow fondamental
5. 🟡 Export multi-piste — 3h, grosse amélioration DAW
6. 🟢 Undo — 1h, filet de sécurité
7. 🟢 Humanisation velocity — 1h, finition musicale
8. 🟡 Densité par voix — 2h, contrôle fin
9. 🟡 A/B — 3h, workflow exploration
10. 🔴 Chord mode — 5h, nouveau territoire musical
11. 🔴 OSC — 5h, intégration écosystème
12. 🔴 Keystep Pro — 6h, niche mais puissant
