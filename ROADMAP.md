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

- [ ] **#5 Swing per voice** — offset microtiming par voix en % de step_dur, indépendant du swing global
- [ ] **#6 Song mode** — séquencer les 8 slots SEQ dans un ordre défini (A×4 → B×2 → C×1)
- [ ] **#7 MIDI Clock IN externe par port** — sync BPM à hardware (Zoom R8, boîte à rythme, DAW master)
- [ ] **#8 Conditional triggers** — conditions type Elektron : every N bars / first only / fill
- [ ] **#9 Transposition globale** — ±24 demi-tons appliqués à toutes les voix mélodiques en live
- [ ] **#10 Multi-port MIDI** — plusieurs ports rtmidi.MidiOut en parallèle, routage port par voix
- [ ] **#11 Voice groups** — grouper des voix (ex : "drums", "mélo") pour mute / solo collectif
- [ ] **#12 Export projet complet** — save / restore état complet comme fichier `.bang` nommé

---

*Dernière mise à jour : 2026-05-25 · v0.9.2*
