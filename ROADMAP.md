# BANG! — Roadmap

Séquenceur MIDI algorithmique pour la **Dark Umbrae** / Robōtariis.

---

## Phase 1 — Sources d'entropie ✅

- [x] Entropie temporelle — microsecondes système → jitter
- [x] Entropie cryptographique — fragments SSH / SHA-256 → seeds non-reproductibles
- [x] Entropie météo — température + vent de Scaër (open-meteo) → densité / CC

## Phase 2 — Moteurs de génération ✅

- [x] Chaînes de Markov — tableaux de probabilités de transition inter-notes
- [x] Mode Drone — messages CC continus pour filtres / LFO hardware
- [x] Polyrythmie dynamique — cycle indépendant configurable par voix

## Phase 3 — Interface & workflow ✅

- [x] CLI interactive — degré de chaos 0.1–1.0 au lancement
- [x] MIDI Learn — capture pattern depuis clavier/pad via Web MIDI
- [x] Logs de session — seed embarquée dans les métadonnées `.mid`

## Phase 4 — Séquenceur live (v0.5–v0.9) ✅

- [x] Interface web FastAPI + HTMX — accessible depuis tout le LAN
- [x] DNA grid editor — grille cliquable par voix, cycle `-/x/?/↺/░`
- [x] Velocity lane — drawbar par step, drag pointer events
- [x] Probability lane — override probabilité par step (barre ambre)
- [x] SEQ 8 slots — mémorisation presets, avance automatique, poids par slot
- [x] Pattern morphing A→B — interpolation douce sur N cycles entre deux slots
- [x] Groove presets — 16 grooves (Boom Bap, Trap, Techno, D'n'B…)
- [x] Euclidien par voix — Bresenham, paramètre k via UI
- [x] Undo — ring buffer 5 snapshots
- [x] A/B slots — comparaison instantanée deux snapshots
- [x] Lock voix — protection lors des regénérations
- [x] Drop probability — silence sur tout le cycle (≠ densité step)
- [x] Densité par voix — slider 0–1, survit aux `∿ Varier`
- [x] Polymétrie par voix — cycle indépendant N steps
- [x] Phase offset par voix
- [x] Thin ÷2/÷4 · Invert · Rotate · Reverse · Double · Halve DNA
- [x] Chord mode — 11 types (mono → aug)
- [x] Export MIDI multi-piste (type 1, P-locks inclus)
- [x] Clips Ableton par voix — ↓ + drag-and-drop session view
- [x] Export Strudel / TidalCycles
- [x] Player Web MIDI + Web Audio + synthé intégré
- [x] Pianoroll SVG — playhead, couleurs vélocité, P-locks, auto-scroll
- [x] OSC bidirectionnel — SuperCollider, Max, TouchOSC
- [x] TouchOSC — génération `.tosc` LAN + Tailscale
- [x] Ableton Live sync — push clips + BPM via AbletonOSC
- [x] MIDI Clock IN (SYNC) — 24 ppq, transport Start/Stop auto
- [x] Tap tempo — médiane 5 taps
- [x] Swing global — décalage steps impairs 0–100%

## Phase 5 — Contrôle par voix (v0.9.x) ✅

- [x] **Copy / paste DNA entre voix** — presse-papier JS, htmx.ajax explicite
- [x] **LFO par voix** — sin / tri / ramp / rnd · cibles : density / drop · fréquence en cycles
- [x] **MIDI output routing par voix** — canal MIDI 1–16 ou auto (drums ch10 / mélo ch1)

## Phase 6 — Performance live (à venir)

- [x] **#5 Swing per voice** — offset microtiming par voix en % de step_dur, indépendant du swing global
      _fait — bang_session.set_voice_swing + voice_swing appliqué dans live_clock_
- [x] **#6 Song mode** — séquencer les 8 slots SEQ dans un ordre défini (A×4 → B×2 → C×1)
      _fait — song_panel.py + SongPanel câblé dans qt_app_
- [x] **#7 MIDI Clock IN externe par port** — sync BPM à hardware (Zoom R8, boîte à rythme, DAW master)
      _fait dans l'app macOS (`Player` + `MIDIClockIn`) : source au choix, Start / Continue / Stop, notes calées sur les impulsions_
- [x] **#8 Conditional triggers** — conditions type Elektron : every N bars / first only / fill
      _fait dans l'app macOS, par voix : 1:2…4:4, 1er cycle, sauf 1er, FILL, sauf FILL (bouton FILL, OSC `/bang/fill`)_
- [x] **#9 Transposition globale** — ±24 demi-tons appliqués à toutes les voix mélodiques en live
      _fait dans l'app macOS (ligne TRANSPO, OSC `/bang/param/transpose`)_
- [x] **#10 Multi-port MIDI** — plusieurs ports rtmidi.MidiOut en parallèle, routage port par voix
      _fait dans l'app macOS : SORTIE par voix (CoreMIDI), relâchements diffusés sur tous les ports à l'arrêt_
- [x] **#11 Voice groups** — grouper des voix (ex : "drums", "mélo") pour mute / solo collectif
      _fait dans l'app macOS : groupes automatiques Batterie / Mélodie / Synthés_
- [x] **#12 Export projet complet** — save / restore état complet comme fichier `.bang` nommé
      _fait dans l'app macOS : ⌘S / ⌘O en `.bang` (session JSON complète : pattern, réglages, mémoires, A/B)_


## Phase 7 : Hardware Synth Control

### NTS-1 (Korg)

- [ ] Profil p-locks `nts1` dans `_SYNTH_PLOCK_PROFILES` : Cutoff CC43, OscShp CC54, OscAlt CC55, LFOInt (OSC LFO depth) CC26, Reso CC44, RevMix CC36
      _CC vérifiés sur le tableau MIDI officiel Korg « NTS-1 digital kit » (2019) ; OSC type = CC53_
- [x] Panel NTS-1 dedie (sidebar) : sections OSC / FILTER / LFO / EG / FX, sliders CC temps reel, indicateur p-lock actif par param
      _fait — nts1_panel.py — 6 sections OSC/FILTER/LFO/EG/FX_
- [x] P-lock interpolation : option linear/cosine/off par piste CC -> MIDI SRV envoie CCs intermediaires entre steps (glisse fluide)
      _fait — p_locks.InterpolationMode LINEAR/COSINE, utilisé par midi_cc_router_

### Microfreak (Arturia)

- [x] Profil p-locks `microfreak` (`mf0`) : Cutoff CC23, Timbre CC12, Shape CC13, Resonance CC83 (+ Type CC9, Wave CC10)
      _CC confirmés par Arturia ; les anciens CC28/74/71/76/77/73/72 étaient ceux du MiniFreak ou inventés. LFO / enveloppe : CC à vérifier_
- [ ] Oscillateur Speak : phoneme controle via CC12 (Timbre) + CC10 (Wave) -> articulation formantique par step
- [ ] CC9 (OSC Type) comme p-lock -> change d'oscillateur mid-sequence (Microfreak a ~20 types)

### Ratchet / Step repeat

- [x] **Ratchet par step** : champ "repeat count" (1-8) par step, subdivise la duree du step en N hits egaux
      _fait dans l'app macOS : lane RATCH par voix_
  - Repeat 1 = normal, 2 = double, 4 = quad (tremolo), 8 = buzz/roll
  - Affiche dans le pianoroll comme mini-barres verticales a l'interieur du step
  - Application cle : p-locks phoneme Speak + ratchet -> stutter speech "a a a | bb | cccc | dd | eeeee"
- [x] Ratchet avec decay : amplitude decroit sur les hits successifs (roll naturel)
- [x] Ratchet avec variation Markov : pitch/velocity derivent legerement sur les repetitions internes
      _faits dans l'app macOS (DECAY / VARIATION par voix)_

### P-lock randomizer borne

- [x] Bouton par piste CC dans le pianoroll : genere des p-locks aleatoires bornes (min/max) avec density (0-100%)
      _fait dans l'app macOS : ligne P-LOCKS de chaque voix (TIRER / EFFACER, + pistes CC ajoutées à la main)_

## Phase 8 — App macOS native (`macos/`) ✅

Le serveur (`bang.service`, `bang.lan`) n'existe plus : BANG! passe en apps natives.
Releases `macos-v1.0.0` → `macos-v1.3.0` (la dernière est la « Latest » du dépôt).

- [x] Moteur porté en Swift (`BangCore`) : DNA, Babka, Markov / gammes, les 14 modes, p-locks, export `.mid`, session JSON compatible webapp
- [x] App SwiftUI : grille DNA, piano-roll, lecture temps réel (CoreMIDI + port virtuel « BANG! »), synthé GM intégré, interface qui suit la taille de la fenêtre
- [x] Kits batterie **808 / 909** recréés par synthèse ; export **.wav** en boucle parfaite (nom `preset-variation-date`)
- [x] Jeu live : synchro MIDI clock, tap, évolution auto, A/B, mémoires auto pondérées, morph, mode Song, LFO par voix
- [x] Mémoires et A ↔ B lisibles : bouton ENREGISTRER, actions en clic droit (vider, copier, échanger), case modifiée signalée, fondu au clic sur une mémoire (TRANSITION), **crossfader A ↔ B** avec GLISSER ; fondus appariés par nom de voix
- [x] Édition fine : lanes VÉL / PROB, longueur (polymétrie), décalage, Thin, note de sortie, p-locks visibles
- [x] Connexions : OSC bidirectionnel, Ableton (AbletonOSC), Strudel, `.mid` par voix, gabarit TouchOSC, MIDI Learn, panneaux NTS-1 / MicroFreak
- [x] CC NTS-1 / MicroFreak vérifiés sur les tableaux officiels — corrigés aussi côté Python
- [x] Parité avec le webapp : presets machines personnels, presets KSP (+ personnels), export morceau (macro-arrangement, sections, WAV), polyphonie max, entropie temporelle, MIDI type 0/1, journal des exports, interpolation des p-locks
- [ ] Vérifier l'export Strudel sur strudel.cc (l'app Qt l'avait abandonné : patterns qui ne jouaient pas)
- [ ] Tester avec un vrai Ableton + AbletonOSC, un vrai maître MIDI clock et de vrais NTS-1 / MicroFreak
- [ ] Notarisation Apple (supprimer le « clic droit → Ouvrir ») — nécessite un compte développeur
- [ ] Tester sur Mac Intel et sous macOS 13

---

*Dernière mise à jour : 2026-11-14 · app macOS — parité webapp + phase 6 terminée, ratchets et p-locks bornés*

## Demandes externes (Argus)

<!-- argus:begin -->
- [ ] ⚑ 12+ commits non publiés
      _pourquoi : dernière version 0.9.5-alpha datée du 2026-05-25_
- [x] ⇐ Argus : [health-endpoint] Tout service HTTP expose GET /health répondant 200.
      _pourquoi : Un watchdog ne peut pas surveiller ce qu'il ne peut pas interroger. Sans sonde uniforme, chaque service invente la sienne — ou n'en a aucune, et tombe sans que personne le voie (OpenClaw bloqué 12 h en « active (running) », Navidrome mort 10 h derrière un stream qui continuait de sortir)._
<!-- argus:end -->
