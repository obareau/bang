# 🗺️ BANG : Roadmap & Visions
Ce document consigne les évolutions futures du séquenceur algorithmique pour la **Dark Umbrae**.

---

## 🌀 Phase 1 : Sources d'Entropie (En cours)
L'objectif est de remplacer le hasard pur par des données systémiques ou environnementales.
- [x] **Entropie Temporelle :** Utiliser l'heure système (microsecondes) pour influencer le Jitter.
- [x] **Entropie Cryptographique :** Utiliser des fragments de clés SSH ou de Hash (SHA-256) pour générer des patterns uniques et non-reproductibles.
- [x] **Lien Local :** Injecter les données météo de Scaër (température, vent) pour moduler la densité des séquences.

## 🎛️ Phase 2 : Moteurs de Génération
- [x] **Implémentation Markovienne avancée :** Créer des tableaux de probabilités de transition entre les notes (ex: si Do est joué, 70% de chance d'aller vers Ré#).
- [x] **Mode Drone :** Génération de messages MIDI CC (Control Change) pour piloter des filtres de synthés en continu.
- [x] **Polyrythmie Dynamique :** Permettre au script de changer la longueur des boucles (ex: passer de 5 à 7 pas) de manière organique.

## 💻 Phase 3 : Interface & Workflow
- [x] **CLI Interactive :** Pouvoir choisir le "degré de chaos" (0.1 à 1.0) via une commande au lancement.
- [x] **Mode Live Controller :** Utiliser le Zoom R8 pour modifier certains paramètres d'entropie en temps réel pendant la génération.
- [x] **Système de Logs :** Chaque fichier MIDI exporté contient en méta-donnée la "graine" (seed) utilisée pour pouvoir le régénérer si besoin.

---
*Dernière mise à jour : Mai 2026 - Cadre Robōtariis*
---

## 🎹 Phase 4 : Hardware Synth Control

### P-locks & Synthés natifs

**NTS-1 mode** (priorité haute)
- [ ] Profil p-locks  dans  : Cutoff CC43, OscShp CC53, OscAlt CC54, LFOInt CC25, Reso CC44, RevMix CC38
- [ ] Panel NTS-1 dédié (sidebar) : sections OSC / FILTER / LFO / EG / FX, sliders CC temps réel, indicateur p-lock actif
- [ ] P-lock interpolation : option  par piste CC, MIDI SRV envoie CCs intermédiaires → glissé fluide entre steps

**Microfreak mode**
- [ ] Profil p-locks  : Timbre CC28, Wave CC9, Cutoff CC74, Resonance CC71, LFO Rate CC76, LFO Amount CC77, Env Attack CC73, Env Release CC72
- [ ] Oscillateur  : phonème contrôlé via CC28 (Timbre) + CC9 (Wave) → articulation formantique par step
- [ ] CC14 (OSC Type) comme p-lock → change d'oscillateur mid-séquence (Microfreak a ~20 types)

### Ratchet / Step repeat

- [ ] **Ratchet par step** : champ repeat count (1–8) par step, subdivise la durée du step en N hits égaux
  - Repeat 1 = normal · 2 = double · 4 = quad (trémolo) · 8 = buzz/roll
  - Affiché dans le pianoroll comme mini-barres verticales à l'intérieur du step
  - Combiné avec p-locks phonème Speak → stutter speech : 
- [ ] Ratchet avec decay : amplitude décroît sur les hits successifs d'un même ratchet (roll naturel)
- [ ] Ratchet avec variation Markov : pitch/velocity dérivent légèrement sur les répétitions internes

### P-lock randomizer borné
- [ ] Bouton 🎲 par piste CC dans le pianoroll : génère des p-locks aléatoires bornés (min/max) avec density (0–100%)

---

## 🔭 Phase 5 : Visions long terme
- Song mode (intro / couplet / break / outro — enchaîner des patterns)
- MIDI Clock IN (sync externe : Ableton, hardware)
- Triggers conditionnels (joue ce step si N-ième fois, si random < x%)
- Transposition globale (shift scale pendant play)
- Export multi-piste (.mid séparé par voix)


---

## Phase 4 : Hardware Synth Control

### P-locks et synthes natifs

**NTS-1 mode** (priorite haute)
- [ ] Profil p-locks `nts1` dans `_SYNTH_PLOCK_PROFILES` : Cutoff CC43, OscShp CC53, OscAlt CC54, LFOInt CC25, Reso CC44, RevMix CC38
- [ ] Panel NTS-1 dedie (sidebar) : sections OSC / FILTER / LFO / EG / FX, sliders CC temps reel, indicateur p-lock actif
- [ ] P-lock interpolation : option `linear|cosine|off` par piste CC, MIDI SRV envoie CCs intermediaires entre steps -> glisse fluide

**Microfreak mode**
- [ ] Profil p-locks `microfreak` : Timbre CC28, Wave CC9, Cutoff CC74, Resonance CC71, LFO Rate CC76, LFO Amount CC77, Env Attack CC73, Env Release CC72
- [ ] Oscillateur Speak : phoneme controle via CC28 (Timbre) + CC9 (Wave) -> articulation formantique par step
- [ ] CC14 (OSC Type) comme p-lock -> change d'oscillateur mid-sequence (Microfreak a ~20 types oscillateurs)

### Ratchet / Step repeat

- [ ] **Ratchet par step** : champ "repeat count" (1-8) par step, subdivise la duree du step en N hits egaux
  - Repeat 1 = normal, 2 = double, 4 = quad (tremolo), 8 = buzz/roll
  - Affiche dans le pianoroll comme mini-barres verticales a l'interieur du step
  - Combine avec p-locks phoneme Speak -> stutter speech : "a a a | bb | cccc | dd | eeeee"
- [ ] Ratchet avec decay : amplitude decroit sur les hits successifs (roll naturel, comme une caisse claire qui roule)
- [ ] Ratchet avec variation Markov : pitch/velocity derivent legerement sur les repetitions internes -> buzz organique

### P-lock randomizer borne
- [ ] Bouton par piste CC dans le pianoroll : genere des p-locks aleatoires bornes (min/max) avec density (0-100%)

---

## Phase 5 : Visions long terme
- Song mode (intro / couplet / break / outro -- enchainer des patterns)
- MIDI Clock IN (sync externe : Ableton, hardware)
- Triggers conditionnels (joue ce step si N-ieme fois, si random < x%)
- Transposition globale (shift scale pendant play)
- Export multi-piste (.mid separe par voix)
