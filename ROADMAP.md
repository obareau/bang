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
- [ ] **#7 MIDI Clock IN externe par port** — sync BPM à hardware (Zoom R8, boîte à rythme, DAW master)
- [ ] **#8 Conditional triggers** — conditions type Elektron : every N bars / first only / fill
- [ ] **#9 Transposition globale** — ±24 demi-tons appliqués à toutes les voix mélodiques en live
- [ ] **#10 Multi-port MIDI** — plusieurs ports rtmidi.MidiOut en parallèle, routage port par voix
- [ ] **#11 Voice groups** — grouper des voix (ex : "drums", "mélo") pour mute / solo collectif
- [ ] **#12 Export projet complet** — save / restore état complet comme fichier `.bang` nommé


## Phase 7 : Hardware Synth Control

### NTS-1 (Korg)

- [ ] Profil p-locks `nts1` dans `_SYNTH_PLOCK_PROFILES` : Cutoff CC43, OscShp CC53, OscAlt CC54, LFOInt CC25, Reso CC44, RevMix CC38
- [x] Panel NTS-1 dedie (sidebar) : sections OSC / FILTER / LFO / EG / FX, sliders CC temps reel, indicateur p-lock actif par param
      _fait — nts1_panel.py — 6 sections OSC/FILTER/LFO/EG/FX_
- [x] P-lock interpolation : option linear/cosine/off par piste CC -> MIDI SRV envoie CCs intermediaires entre steps (glisse fluide)
      _fait — p_locks.InterpolationMode LINEAR/COSINE, utilisé par midi_cc_router_

### Microfreak (Arturia)

- [ ] Profil p-locks `microfreak` : Timbre CC28, Wave CC9, Cutoff CC74, Resonance CC71, LFO Rate CC76, LFO Amount CC77, Env Attack CC73, Env Release CC72
- [ ] Oscillateur Speak : phoneme controle via CC28 + CC9 -> articulation formantique par step
- [ ] CC14 (OSC Type) comme p-lock -> change d'oscillateur mid-sequence (Microfreak a ~20 types)

### Ratchet / Step repeat

- [ ] **Ratchet par step** : champ "repeat count" (1-8) par step, subdivise la duree du step en N hits egaux
  - Repeat 1 = normal, 2 = double, 4 = quad (tremolo), 8 = buzz/roll
  - Affiche dans le pianoroll comme mini-barres verticales a l'interieur du step
  - Application cle : p-locks phoneme Speak + ratchet -> stutter speech "a a a | bb | cccc | dd | eeeee"
- [ ] Ratchet avec decay : amplitude decroit sur les hits successifs (roll naturel)
- [ ] Ratchet avec variation Markov : pitch/velocity derivent legerement sur les repetitions internes

### P-lock randomizer borne

- [ ] Bouton par piste CC dans le pianoroll : genere des p-locks aleatoires bornes (min/max) avec density (0-100%)

---

*Dernière mise à jour : 2026-07-31 · v0.9.2 — réconciliation après 145 commits non reflétés*

## Demandes externes (Argus)

<!-- argus:begin -->
- [ ] ⚑ 12+ commits non publiés
      _pourquoi : dernière version 0.9.5-alpha datée du 2026-05-25_
- [x] ⇐ Argus : [health-endpoint] Tout service HTTP expose GET /health répondant 200.
      _pourquoi : Un watchdog ne peut pas surveiller ce qu'il ne peut pas interroger. Sans sonde uniforme, chaque service invente la sienne — ou n'en a aucune, et tombe sans que personne le voie (OpenClaw bloqué 12 h en « active (running) », Navidrome mort 10 h derrière un stream qui continuait de sortir)._
<!-- argus:end -->
