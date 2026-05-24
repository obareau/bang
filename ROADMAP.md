# BANG! — Roadmap

> État : v0.9.0-beta · Mis à jour : 2026-05-24

Légende effort : 🟢 < 1h · 🟡 2–4h · 🔴 5h+

---

## Acquis (v0.1 → v0.9.0-beta)

### Moteur & génération
- Entropie multi-sources (temporelle, cryptographique, météo Scaër)
- Markov, Babka, VFM, Bass, VKick, P-locks, MFq
- Presets hardware : Volca Drum/Kick/FM, MicroFreak, TR-808/909, MPC60, GM, LinnDrum, Tekno, Battery4, KSP
- Gammes configurables (12 toniques × 8 modes) — chord mode 11 types (mono→aug)
- Swing, micro-timing, humanisation velocity, densité par voix
- Seed fixe, log de session, variation automatique (mutate 0.12), auto-évolve
- Song export structuré (30 fichiers, 9 groupes, morphing DNA cohérent)
- Archive + favoris ⭐
- 16 groove presets (MPC Boom Bap, Trap, Bossa Nova…)

### Interface voix (panneau DNA)
- Lock 🔒 · Mute M · Solo S
- Euclidien par voix (bouton E, Bresenham)
- Polymétrie par voix (cycle indépendant N steps)
- Phase offset par voix
- DNA rotate ◀▶ · reverse ↔ · double ×2 · halve ÷2 · invert ¬
- Variation par voix `~` · Regen ⟳
- Drop probability % par cycle
- Density slider
- **DNA grid editor** — grille cliquable `-/x/?/↺/░`, sync bidirectionnelle avec input texte
- **Velocity lane** — éditeur drawbar par step, drag pointer events, override global vel

### Player & MIDI
- Web MIDI output + pianoroll synchronisé
- Browser synth (Web Audio API) — kick/snare/HH/tom/tone, sans MIDI requis
- Toggle 🔊 force synthé navigateur
- **MIDI serveur rtmidi** — sortie MIDI server-side sans Chrome (SRV panel, drums ch9, melodic ch0, gate 75%)
- Tap Tempo (médiane 5 taps) · MIDI Clock Sync 0xF8 24ppq (Start/Stop transport)
- MIDI Learn ⏺ par voix (Web MIDI API, count-in 2 temps, quantification)
- Comparaison A/B (2 snapshots, store/load)
- Undo 5 niveaux (ring buffer)
- Randomize params 🎲 (BPM, chaos, gravity, swing, micro-timing, steps)

### SEQ — Séquenceur de presets
- 8 slots de mémorisation (save 💾 / load / clear ×)
- Mode AUTO : avance automatique tous les N cycles
- **Poids par slot** (1–9) — tirage pondéré `random.choices` en mode AUTO

### Pianoroll
- SVG multi-voix synchronisé avec playhead temps réel
- **Couleurs par vélocité** — opacity = 0.3 + vel/127 × 0.7, couleur par voix
- **P-locks SVG** — barres verticales groupées par voix.cc sous le pianoroll
- **Auto-scroll horizontal** — suit le playhead pendant la lecture
- **Scroll vertical vers voix active** — ouvrir un panneau DNA scroll le pianoroll
- **Probability lane** — barre ambre (top step) si probabilité override < 100%
- **Velocity lane** — override global, drag pointer events
- Marqueurs de frontière polymétrie

### Export & intégration
- Export MIDI multi-piste (type 1, P-locks CC inclus)
- Export clip par voix `↓` + zip toutes voix · drag → Ableton
- Export audio WebM (MediaRecorder + AudioContext, bouton ⏺ REC)
- Export Strudel/TidalCycles (notation mini, `setcps`)
- AbletonOSC : envoyer toutes les voix comme clips Live + sync BPM ↻
- **OSC panel redesign** — slide-down (était modal), HOST/TX/RX en ligne
- OSC bidirectionnel (tx + rx 57121, 10 commandes entrantes)
- Page `/files` : liste des exports MIDI, téléchargement direct
- Persistance de session (`bang_state.json`, middleware POST autosave)

---

## Prochaines pistes

### Musicales

| Item | Effort | Notes |
|------|--------|-------|
| **LFO par voix** | 🟡 3h | Modulation automatique de la densité ou du drop% selon une forme (sin/tri/ramp/random). Fréquence en cycles. |
| **Pattern morphing A→B** | 🔴 5h | Interpolation douce entre deux slots SEQ sur N cycles : chaque step passe progressivement d'un DNA à l'autre. |
| **Chord mode Babka/VFM** | 🟡 2h | Étendre le sélecteur d'accord aux voix Babka et VFM (actuellement réservé à Markov/KSP). |

### Workflow

| Item | Effort | Notes |
|------|--------|-------|
| **Copy/paste DNA entre voix** | 🟢 1h | Bouton copier sur une voix → coller sur une autre. Accélère la construction de patterns liés. |
| **MIDI output routing par voix** | 🔴 5h | Sélectionner un port MIDI de sortie différent par voix (actuellement global). Utile multi-synth. |
| **Preset nommés de sessions** | 🟡 3h | Sauvegarder / charger l'état complet sous un nom libre (au-delà des 8 slots SEQ). Liste dans `/files`. |

### Infrastructure

| Item | Effort | Notes |
|------|--------|-------|
| **Historique des seeds** | 🟢 30min | Conserver les N derniers seeds générés dans le log, cliquables pour recharger un état exact. |
| **OSC → velocity lane** | 🟡 2h | Commande OSC `/bang/vel/<voix> [v0 v1 … vN]` pour piloter la velocity lane depuis l'extérieur. |

---

## Ordre suggéré (suite v0.9.0-beta)

1. 🟢 **Copy/paste DNA entre voix** — gain workflow immédiat, effort minimal
2. 🟡 **LFO par voix** — densité vivante sans intervention manuelle
3. 🔴 **Pattern morphing A→B** — feature signature pour sets live
4. 🔴 **MIDI output routing par voix** — multi-synth, prochaine étape naturelle après MIDI serveur
