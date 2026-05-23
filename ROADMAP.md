# BANG! — Roadmap

> État : v0.5.1 · Mis à jour : 2026-05-23

Légende effort : 🟢 < 1h · 🟡 2–4h · 🔴 5h+

---

## Acquis (v0.1 → v0.5.4)

- Entropie multi-sources (temporelle, cryptographique, météo Scaër)
- Markov, Babka, P-locks, presets hardware (Volca Drum/Kick/FM, MicroFreak)
- Web MIDI player + pianoroll synchronisé
- Gammes configurables (12 toniques × 8 modes)
- Swing, seed fixe, session import/export
- **Seed cliquable** dans le log ✅
- **Multi-canal Markov** — `markov_channel` 1–16 ✅
- **P-locks dans le `.mid`** — CC events par step dans l'export ✅
- **Lock de voix** — bouton 🔒, ring buffer undo ✅
- **Export multi-piste** — `MidiFile(type=1)`, une track par voix ✅
- **Undo génération** — ring buffer 5 snapshots ✅
- **Humanisation velocity** — `vel_humanize` ±N ✅
- **Densité par voix** — slider 0–1 par voix ✅
- **Comparaison A/B** — slots store/load, toolbar ▸A ▸B ✅
- **Chord mode Markov** — 11 types (mono→aug), export + player JS ✅
- **OSC output** — thread UDP, `/bang/clock`, `/bang/{voix}` ✅
- **Mode Keystep Pro ♜** — 4 pistes Markov ch1-4 + drums ✅
- **Euclidien par voix** — bouton `E` par voix, input `k` hits → applique E(n,k) sur la voix ✅
- **Variation automatique** — bouton `∿ Varier` + raccourci `V`, mutate légère (0.12) sans regénération ✅
- **Micro-timing global** — slider MICRO 0–100% : offset aléatoire ±12% step par trigger, export MIDI + player JS ✅

---

## Prochaines pistes

### Musicales

| Item | Effort | Notes |
|------|--------|-------|
| **Micro-timing global** | 🟡 2h | Quantize strength 0–1 : à 0 = free, à 1 = on-grid. Interpolation du swing step-par-step. |
| **Variation automatique** | 🟡 3h | Bouton "Varier" : mutate légèrement le pattern courant sans tout régénérer (entre Undo et Generate). |
| **Polymetry** | 🔴 5h | Longueurs de pattern indépendantes par voix (ex. 5 steps sur Kick, 7 sur Snare). Déjà partiellement là via `trigger_dna` list. |

### Export / intégration

| Item | Effort | Notes |
|------|--------|-------|
| **Ableton Live Clip** | 🟡 3h | Export `.als` ou MIDI drag-to-clip avec markers. |
| **OSC bidirectionnel** | 🟡 3h | Recevoir OSC (changement de params, trigger force) en plus d'émettre. |
| **Export audio preview** | 🔴 6h | Rendu audio via FluidSynth ou simple sine waves pour pré-écoute sans MIDI hardware. |

### Infrastructure

| Item | Effort | Notes |
|------|--------|-------|
| **Preset KSP** | 🟢 30min | Sauvegarder les configs KSP (chord par voix, gravity, gamme) comme presets nommés. |
| **MIDI input (learn)** | 🔴 6h | Enregistrer un pattern depuis un pad MIDI physique → convertir en DNA. |

---

## Ordre suggéré (suite v0.5.4)

1. 🟡 OSC bidirectionnel — intégration écosystème complète
4. 🟡 OSC bidirectionnel — intégration écosystème complète
5. 🔴 Polymetry — nouveau territoire rythmique
6. 🔴 MIDI input — franchissement de seuil majeur
