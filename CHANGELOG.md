# Changelog — BANG · Dark Umbrae Sequencer

## [0.9.5-alpha] — 2026-05-25

### Fixes · UX · Player browser

- **Fix Drop% spinners** — le spinner Drop% tombait à zéro au premier clic (HTMX swappait `#voices` sur chaque `change`, détruisant le focus). Remplacé par un `fetch()` silencieux via `setVoiceDrop()` : le DOM n'est plus touché, la valeur est arrondie au multiple de 5 le plus proche.
- **Boutons ×1 ÷2 ÷4 restaurés dans les voix** — les boutons de thinning (÷2, ÷4, ×1) avaient disparu. Réintégrés directement dans l'en-tête de chaque voix (`vr-hr`), visibles en permanence sans ouvrir le panneau OPS.
- **Notes Markov réelles dans le player browser** — le player browser utilisait la note fixe `v.note` (ex. 24/C1) pour toutes les notes de la voix Markov. La chaîne de Markov n'était exploitée que par le MIDI SRV serveur-side. Correction : `/pattern` injecte désormais `e.note` dans chaque event des voix `markov` et `bl` en générant la séquence depuis `engine.voices[i].chain`. Le player utilise `e.note ?? v.note` (MIDI + browser synth).
- **Panel VOIX élargi** — largeur passée de 290px à 420px pour une meilleure lisibilité des grilles DNA longues (64 steps).
- **Bouton DEMO retiré de l'UI** (code conservé) — le mode DEMO (`_forceBrowserSynth` + auto-generate + auto-play) sera revu ultérieurement pour un support multi-timbral propre. Le code `toggleDemoMode()` reste présent mais non exposé.

---

## [0.9.4] — 2026-05-25

### LFO serveur · Pattern morphing A→B

- **LFO par voix — côté serveur** — la modulation density/drop par LFO (sin/tri/ramp/rnd) est maintenant appliquée dans `_midi_srv_clock_loop` et `_osc_clock_loop`. Avant, le LFO ne fonctionnait que dans le player navigateur. Maintenant cohérent entre player JS et MIDI serveur. `_lfo_val(shape, phase)` Python miroir de `_lfoValue()` JS.
- **Pattern morphing A→B** — interpolation douce entre deux slots SEQ sur N cycles. Accessible depuis le panel SEQ (section MORPH) : sélectionner deux slots remplis, choisir le nombre de cycles, cliquer `▶`. Le player interpole les probabilités et vélocités de chaque step entre les deux patterns, voix par voix. À la fin du morphing, le slot TO est chargé automatiquement comme pattern actif (côté serveur + player rechargé), garantissant la continuité.
- **Thème light** — fond crème `#f4efe6`, texte gris très sombre `#1e1e1e`. Bouton `LGT` dans la barre de thèmes.
- **Screenshots GitHub** — captures dark/light/setup dans `docs/screenshots/`, intégrées dans le README.

---

## [0.9.3] — 2026-05-25

### Page Setup · Debugger OSC · Swing par voix

- **Page /setup** — nouvelle page dédiée à la configuration : OSC (host/ports/connect), MIDI Serveur (port/canal/connect), Ableton Live. Accessible via le bouton `⚙` dans le toolbar. S'ouvre dans un nouvel onglet pour rester accessible pendant la session.
- **Debugger OSC temps réel** — intégré dans /setup : ring buffer 50 messages, polling HTMX toutes les secondes. Les messages TX (orange) et RX (vert) s'affichent avec timestamp, adresse et arguments. Boutons Pause et Effacer. TX logué : `/bang/clock` au step 0 + triggers voix. RX logué : tous les handlers (`/bang/param/*`, `/bang/generate`, `/bang/vary`, `/bang/density/*`, `/bang/lock/*`).
- **Swing par voix** — slider 0–100% dans le tab MOD de chaque voix. Décale les steps impairs dans le temps (`swing × step_dur × 0.33`). Les events MIDI d'un même step sont collectés, triés par timestamp, puis envoyés dans l'ordre — chaque voix peut donc swinguer différemment sans collision.
- **MIDI canal par voix** — sélecteur `ch MIDI` (auto / ch1–ch16) dans le tab MOD. En mode "auto" : drums → canal drums global, voix mélodiques → canal 1. Override persisté dans `bang_state.json`.
- **Ergonomie toolbar** — panels OSC et MIDI SRV slide-down supprimés. Le bouton `OSC ○/●` toggle directement l'état OSC (HTMX). Le bouton `MIDI ○/●` ouvre /setup. Toolbar sensiblement allégé.

---

## [0.9.2] — 2026-05-25

### MIDI output routing par voix · LFO par voix · Copy/Paste DNA

- **MIDI output routing par voix** — sélecteur `ch MIDI` dans le tab MOD de chaque voix. Permet d'assigner un canal MIDI 1–16 fixe (ou "auto" = drums ch10 / mélodique ch1). Persisté dans `bang_state.json`. Appliqué dans le MIDI serveur rtmidi. Utile pour les setups multi-timbre (un synth par canal).
- **LFO par voix** — modulation automatique de `density` ou `drop` selon une forme d'onde (sin / tri / ramp / rnd). Fréquence configurable en cycles (÷4 à ×8). Profondeur 0–100%. Calculé JS-side au tick du player. Bouton `LFO` dans le tab MOD, panel inline sans rechargement.
- **Copy / Paste DNA entre voix** — bouton `C` copie le DNA courant dans le presse-papier JS. Bouton `P` (grisé par défaut, activé après copie) colle sur n'importe quelle autre voix. Correction du bug HTMX : le POST `/voice/pattern` utilisait `htmx.trigger` qui sérialisait tout le formulaire `#voice-notes` (8 inputs `name="pattern"`), écrasant la valeur JS modifiée. Remplacé par `htmx.ajax` avec valeurs explicites `{ idx, pattern }`.

---

## [0.9.0-beta] — 2026-05-24

### MIDI serveur · OSC panel · Pianoroll amélioré

- **MIDI serveur (rtmidi)** — sortie MIDI server-side sans dépendance Chrome/Web MIDI. Bouton `SRV` dans le toolbar ouvre un panneau de configuration : sélection du port (virtuel ou physique), toggle ON/OFF. Envoie Note On/Off depuis Python, drums sur ch9 (GM), voix mélodiques sur ch0. Horloge synchronisée sur le BPM courant. Gate 75% du step. Fonctionne avec n'importe quel navigateur, DAW, ou depuis un script headless.
- **OSC panel redesign** — le modal OSC est remplacé par un panneau slide-down (pattern SEQ), accessible sans popup. HOST / PORT TX / PORT RX configurables en ligne, connect/disconnect immédiat. Config persistée dans `bang_state.json`.
- **Pianoroll — couleurs par vélocité** — chaque step déclenché est rendu dans la couleur de sa voix avec une opacité proportionnelle à la vélocité (`0.3 + vel/127 × 0.7`). Les overrides du velocity lane sont prioritaires. Les steps vides affichent un `·` couleur voix à 15% d'opacité.
- **Pianoroll — P-locks SVG** — les P-locks (automation CC step par step) sont visualisés sous le pianoroll principal sous forme de barres verticales groupées par voix.cc, avec label et fond coloré.
- **Pianoroll — playhead auto-scroll horizontal** — pendant la lecture, le pianoroll défile automatiquement pour garder le playhead dans le champ de vue (scroll à 30% de la largeur visible).
- **Pianoroll — scroll vers la voix active** — ouvrir le panneau d'édition d'une voix fait défiler verticalement le pianoroll jusqu'à la ligne correspondante.
- **TouchOSC gen — fix ports** — inversion `sendPort`/`receivePort` corrigée dans `tools/gen_touchosc.py`. Le `.tosc` généré configure désormais correctement TX→RX.

---

## [0.8.2] — 2026-05-24

### DNA grid · Velocity lane · SEQ poids de transition

- **DNA grid editor** — grille cliquable sous chaque DNA de voix. Chaque case cycle entre `-` / `x` / `?` / `↺` / `░` au clic. Sync bidirectionnelle avec l'input texte. Défilement horizontal si le DNA est long. Même colonne = même step.
- **Velocity lane** — mini éditeur de vélocité par voix (20px, barres verticales). Cliquer-glisser verticalement pour définir la vélocité step par step. Sync immédiate avec le player (prise en compte au prochain Play). Les valeurs du lane overrident les paramètres globaux VEL MIN/MAX/CURVE pour cette voix. Pas de lane = comportement global. Effacer = remettre tout à 0 → retour au mode global.
- **SEQ poids de transition** — champ `1–9` sous le bouton 💾 de chaque slot. En mode AUTO, le prochain slot est tiré au sort selon les poids (`random.choices`). Poids 3 = sélectionné 3× plus souvent que poids 1. Avance linéaire si un seul slot occupé.

---

## [0.8.1] — 2026-05-24

### Groove presets · Page /files · BPM sync Ableton

- **16 groove presets** intégrés : MPC Boom Bap, Trap, Bossa Nova, Reggae, Afrobeat, Techno, Drum'n'Bass, Hip-Hop Swing, Breakbeat, Cumbia, Soca, Clave 3-2, Waltz 3/4, Shuffle, Minimal Techno, Straight. Sélecteur `— Groove —` dans le toolbar : applique les DNA positionnellement sur les voix (voix 0→kick, 1→snare, 2→hh, 3→perc ; hors CC). Undo fonctionne.
- **Page `/files`** — liste tous les fichiers MIDI exportés. Nom, taille, date, bouton ↓ téléchargement direct, bouton copier URL. Accessible via `http://host/files`. Lien 📁 ajouté dans le toolbar. Accessible depuis n'importe quelle machine sur le réseau.
- **↻ BPM Ableton** — bouton dans le modal Ableton (`→ Abl`). Lit le BPM courant depuis Ableton Live via OSC (`/live/song/get/tempo`), met à jour le champ BPM dans BANG!. Timeout 0.8s, UDP socket direct (contourne la limite du client OSC unidirectionnel).

---

## [0.8.0] — 2026-05-24

### Séquenceur de presets

- **8 slots** de mémorisation. Bouton **SEQ** dans le toolbar affiche/cache le panel.
- **Cliquer sur un slot vide** → sauvegarde l'état courant (DNA + params) dans ce slot.
- **Cliquer sur un slot sauvegardé** → charge ce slot immédiatement (voices + pianoroll mis à jour, undo disponible).
- **× par slot** → vide le slot.
- **▶ AUTO** → active l'avance automatique : à chaque N cycles complets, BANG! passe au slot suivant non vide (boucle). Le slot courant est mis en surbrillance.
- **`[N] cycles/slot`** — champ configurable (1–64 cycles par slot).
- Re-fetch de `/pattern` 250ms après l'avance pour que le player MIDI pickup la nouvelle DNA sans stop/start.
- Persisté dans `bang_state.json`.

---

## [0.7.9] — 2026-05-24

### Intégration AbletonOSC

- **Bouton `→ Abl`** dans le toolbar. Ouvre un modal de configuration : Host, Port (défaut 11000), Track offset (quelle track Ableton reçoit la voix 0), Slot (quel clip slot).
- **Config** — mémorise host/port/track/slot dans l'état serveur (persisté dans `bang_state.json`).
- **Envoyer** — envoie toutes les voix (hors CC) vers Ableton Live via OSC :
  - `POST /live/song/set/tempo` — synchronise le BPM
  - `POST /live/clip_slot/create_clip` par voix — crée un clip de la bonne longueur
  - `POST /live/clip/add_notes` par voix — envoie les hits compilés (ratchet géré, velocity mappée)
- Nécessite [AbletonOSC](https://github.com/AbletonOSC/AbletonOSC) installé comme Control Surface dans Live (Préférences → MIDI → Control Surfaces → AbletonOSC).
- Fonctionne en local (127.0.0.1) ou réseau (IP Ableton sur LAN).

---

## [0.7.8] — 2026-05-24

### Invert DNA · Drop probability · Regen voix individuelle

- **¬ Invert** — dans le groupe `dna-ops` : permute `x` ↔ `-` sur tout le DNA. Les symboles spéciaux (`?`, `↺`, `░`) sont inchangés. Crée le pattern "complémentaire" d'un rythme.
- **Drop probability** — champ `%` par voix (0–100). À chaque début de cycle global, la voix passe un test aléatoire : si elle "drop", elle est silencieuse pour tout le cycle. 100% = toujours joue (défaut). Distinct de la densité (qui filtre les steps individuels). Évalué JS-side, persisté serveur. Réinitialise chaque cycle.
- **⟳ Regen voix individuelle** — bouton à côté du `~` vary. Régénère un nouveau DNA pour cette seule voix (même note, même type, nouveau random). Les voix lockées ne peuvent pas être régénérées. Undo fonctionne.

---

## [0.7.7] — 2026-05-24

### Pattern double / halve par voix

- **×2** — concatène le DNA avec lui-même (longueur doublée). `x-x-` → `x-x-x-x-`. Permet de construire des patterns longs avec variation interne en chaînant rotate/reverse avant de doubler.
- **÷2** — tronque le DNA à sa première moitié. Minimum 1 caractère garanti. Utile pour réduire une boucle longue à son essence.
- Boutons dans le groupe `dna-ops` avec ◀ ▶ ↔. Disponibles hors CC et Babka. OOB pianoroll mis à jour. Undo fonctionne.

---

## [0.7.6] — 2026-05-24

### DNA Rotate + Reverse par voix

- **◀ / ▶** — décale le DNA d'un step vers la gauche ou la droite (rotation cyclique). Le dernier/premier caractère revient de l'autre côté. Modifie le DNA réel (contrairement au phase offset qui est playback-only), donc affecte l'export MIDI et le Strudel.
- **↔** — inverse le DNA (rétrograde) : `x-x--` devient `--x-x`. Idéal pour créer des contrepoints ou tester la version miroir d'un rythme.
- Boutons disponibles sur toutes les voix hors CC et Babka. Conservé après Vary, Lock, slots A/B. Undo fonctionne.
- OOB pianoroll mis à jour à chaque opération.

---

## [0.7.5] — 2026-05-24

### Mute + Solo par voix

- **Boutons M / S** par voix (hors CC) dans le panneau DNA, avant le 🔒. Purement JS player-side — ne modifie pas le DNA ni l'état serveur.
- **Mute** — exclut la voix du player (MIDI + browser synth). La row est assombrie visuellement. Toggle : cliquer à nouveau pour démuter.
- **Solo** — seule la voix solo'd joue, toutes les autres sont silencieuses. Cliquer à nouveau sur S pour quitter le solo. M et S sont indépendants : un solo efface les mutes visuels mais les conserve en mémoire.
- **Reset automatique** sur `⚡ Générer` (full regen). Les opérations `∿ Varier`, `~` par voix et slots A/B conservent l'état mute/solo.
- Synchronisation visuelle : `htmx:afterSwap` rappelle `_syncMuteState()` après chaque swap HTMX pour maintenir les états visuels.

---

## [0.7.4] — 2026-05-24

### Export Strudel / TidalCycles

- **Bouton Strudel** dans le toolbar. Ouvre un modal avec le pattern courant converti en mini-notation Strudel. Bouton `Copier` → clipboard. Lien direct vers strudel.cc.
- **Conversion DNA → mini-notation** : `x` → sample name (mappé GM/standard : bd/sd/hh/oh/cp/rim/lt/mt/ht/cr/rd), `-` → `~`, `?` (prob < 0.75) → `sample?0.N`, `?` (prob < 0.95) → `sample?`, `↺` → `sample*N`. Voix mélodiques (Markov, Bass, KSP) → `note("c4 e4 g4…")` avec note MIDI convertie.
- **Header** : `setcps(bpm/60/4)` pour synchroniser le tempo. Voix CC et Babka exclues.
- Endpoint : `GET /export/strudel` → JSON `{ok, code}`.

---

## [0.7.3] — 2026-05-24

### Randomize params

- **Bouton 🎲** dans le toolbar (à côté de ⚡ Générer). Randomise en un clic : BPM (parmi 19 valeurs musicales de 60 à 180), chaos (0.10–0.80), gravity (0.30–1.00), swing (0–0.45), micro-timing (0.50–1.00), steps (16/32/64/128, pondéré 64). Mise à jour immédiate de tous les sliders + labels. Flash visuel à chaque press. Purement JS-side, aucun backend impliqué.

---

## [0.7.2] — 2026-05-24

### Phase offset par voix

- **Bouton `+Ns` par voix** dans le panneau DNA (à côté de `Ns` polymétrie, hors CC/Babka). Cliquer ouvre un champ numérique : entrer N steps + Entrée décale le départ du cycle de N steps. `0` remet à zéro.
- **Appliqué au player** : dans `/pattern`, les events de la voix sont décalés de N modulo le nombre de steps total, puis triés. Combiné à la polymétrie, crée des relations de phasing entre voix impossible à obtenir autrement.
- **Persisté** dans `bang_state.json` (`voice_offset`). Survit aux restart.
- **Endpoint** : `POST /voice/offset` (params : `name`, `n`).

---

## [0.7.1] — 2026-05-24

### Export audio WebM

- **Bouton ⏺ REC** dans le player (bottom bar, à droite de 🔊). Démarre l'enregistrement de la sortie du synthé browser via `MediaRecorder` + `AudioContext.createMediaStreamDestination()`. Le bouton pulse en rouge pendant l'enregistrement. Arrêt auto quand le player s'arrête (ou manuellement en recliquant REC) → téléchargement du fichier `bang-YYYY-MM-DD-HH-MM-SS.webm`.
- Si le synthé browser n'est pas encore initialisé au moment du REC, il l'est automatiquement (force `_forceBrowserSynth`).
- Compatible Chrome, Firefox, Safari (WebM/Opus partout ou WebM natif en fallback).

---

## [0.7.0] — 2026-05-24

### Release — Persistance · Live · Sync

Consolidation des features v0.6.x en release stable.

**Persistance de session** — état complet sauvegardé dans `bang_state.json` après chaque action POST, restauré au démarrage. Survit aux `systemctl restart`.

**Tap Tempo + MIDI Clock Sync** — tempo libre via TAP (médiane 5 taps) ou synchronisation MIDI hardware via SYNC (0xF8, 24 ppq) : BPM calculé en temps réel, transport Start/Stop automatique, flash visuel au beat.

**Variation par voix + Auto-évolve** — bouton `~` par voix pour muter une seule voix ; sélecteur ÉVOLVE (×1/×2/×4/×8 cycles) pour variation automatique pendant la lecture.

---

## [0.6.3] — 2026-05-24

### MIDI Clock Sync

- **Bouton SYNC** dans le toolbar (à côté de TAP). Activer : BANG! écoute les messages MIDI clock entrants (0xF8, 24 par quarter note) sur tous les ports disponibles. BPM calculé à chaque beat par médiane des 4 derniers intervalles (robustesse aux jitters). Mise à jour live du champ BPM + du `step_ms` du player en cours de lecture → le tempo suit l'horloge maître en temps réel.
- **Transport MIDI** — messages Start (0xFA) / Continue (0xFB) déclenchent `▶ Play` automatiquement ; Stop (0xFC) déclenche `■ Stop`. Synchronisation transport complète avec un DAW ou une groovebox.
- **Flash beat** — le bouton SYNC clignote visuellement à chaque beat reçu.
- Requiert Chrome/Chromium (Web MIDI API). Réutilise `_midiAccess` du MIDI Learn si déjà initialisé.

---

## [0.6.2] — 2026-05-24

### Auto-évolve

- **Auto-évolve** — sélecteur `ÉVOLVE` dans le toolbar (OFF / ×1 / ×2 / ×4 / ×8). Pendant la lecture, déclenche automatiquement `∿ Varier` toutes les N cycles complets. Purement JS-side : compte les passages à step 0, appelle `POST /vary` avec le délai exact du step (AudioContext scheduling), met à jour le panneau DNA et le pianoroll via HTMX. Réinitialise le compteur à chaque start/stop.

---

## [0.6.1] — 2026-05-24

### Persistance de session + Tap Tempo

- **Persistance de session** — `bang_state.json` écrit automatiquement après chaque action (middleware POST). Restauré au démarrage du service via `@app.on_event("startup")`. Persiste : voix + DNA, paramètres (bpm, mode, steps, chaos…), densités, locks, polymétrie, chords, note_remap, preset actif, settings OSC, slots A/B. L'état survit aux `systemctl restart bang`.
- **Fix OSC modal** — `#osc-modal.open` manquait dans la règle CSS `.open { display: flex }` — le modal était invisible. Ajouté à côté de `#export-modal.open`.
- **Tap Tempo** — bouton `TAP` dans le toolbar. Taper le tempo : premier tap = reset, dès le 2e tap l'écart inter-tap est mesuré et converti en BPM (40–240). Après 3 taps, la médiane des 4 derniers intervalles est utilisée pour plus de précision. Timeout 3s sans tap = reset auto. Le champ BPM est mis à jour visuellement sans rechargement.
- **Variation par voix** — bouton `~` par voix dans le panneau DNA. Applique `mutate_dna` à la voix seule (intensité configurable, défaut 0.12) sans toucher aux autres voix. Pianoroll mis à jour via OOB. Les voix verrouillées ignorent le bouton.

---

## [0.5.9] — 2026-05-23

### Audio Preview dans le navigateur

- **Player sans MIDI** — `▶ Play` fonctionne même sans port MIDI sélectionné. Synthèse Web Audio API (drumsynth embarqué) : kick sub-oscillateur (sine + gain env), snare (noise filtré), hihat (noise highpass), tom (sine decay), tone scie pour les voix mélodiques.
- **Toggle 🔊 Synth** — bouton `🔊` dans la zone player, à côté du sélecteur MIDI. Force le synthé navigateur même quand un port MIDI est connecté. Actif = amber, inactif = muted. Mode `_forceBrowserSynth` : les MIDI sends restent actifs en parallèle.
- **Compatibilité** — Web Audio API disponible dans tous les navigateurs modernes (Chrome, Firefox, Safari, Edge). Le synthé se crée paresseusement au premier `▶ Play` (contrainte autoplay navigateur).

---

## [0.5.8] — 2026-05-23

### Export clips Ableton Live

- **Bouton ↓ par voix** — dans le panneau DNA, chaque voix non-CC expose un bouton `↓` : téléchargement direct du clip MIDI de cette voix uniquement.
- **Drag → Ableton** — les boutons `↓` sont draggables. Glisser vers la session Ableton ou une piste MIDI insère le clip directement (Web API `DownloadURL`, Chrome/Chromium uniquement).
- **Clic sur le label pianoroll** — les labels de voix dans le pianoroll SVG sont maintenant cliquables → téléchargement du clip de la voix correspondante.
- **`↓ Tous les clips`** — bouton en bas du panneau DNA : génère un zip de tous les clips MIDI individuels et le télécharge.
- **Endpoints** — `GET /export/clip?idx=N` → `.mid` mono-voix · `GET /export/clips` → zip de toutes les voix.

---

## [0.5.7] — 2026-05-23

### MIDI Learn — capture de pattern depuis un clavier MIDI

- **Bouton ⏺ par voix** — dans le panneau DNA, un bouton `⏺` lance le mode capture MIDI pour cette voix. L'interface passe en mode armé : fond rouge clignotant, attente de signal MIDI entrant.
- **Count-in 2 temps** — au premier hit MIDI reçu, un décompte visuel de 2 steps démarre (basé sur le BPM courant) avant d'enregistrer. Les hits reçus pendant le count-in sont ignorés.
- **Capture et quantification** — les hits sont quantifiés sur la grille du nombre de steps courant. La durée d'enregistrement = 1 cycle (`steps × step_ms`). Le pattern capturé remplace le DNA de la voix.
- **Web MIDI API** — implémentation browser-side (pas de rtmidi côté serveur). Requiert Chrome ou Chromium (Firefox ne supporte pas encore Web MIDI sans flag).
- **Accès via le modal MIDI** — bouton `🎹 MIDI` dans le toolbar ouvre le modal de sélection de port entrant + liste des ports disponibles.

---

## [0.5.6] — 2026-05-23

### Polymétrie par voix

- **Bouton `Ns` par voix** — dans le panneau DNA, chaque voix (hors CC et Babka) expose un bouton indiquant le nombre de steps courant (ex. `16s`). Cliquer ouvre un champ numérique : entrer N + Entrée applique un cycle indépendant de N steps à cette voix. `0` remet la longueur à la valeur par défaut.
- **Cycles indépendants** — le DNA de la voix est tronqué ou répété/tronqué pour correspondre à N. L'engine joue `dna[step % dna_len]` — les longueurs de cycle différentes créent une polymétrie naturelle.
- **Résiste aux opérations** — le cycle custom survit aux `∿ Varier`, `↺ Undo` et regénérations partielles (voix verrouillées). Un `Generate` complet sur une voix non verrouillée remet la longueur par défaut.
- **Pianoroll** — les marqueurs de frontière de cycle sont affichés en tirets sur le pianoroll pour chaque voix à cycle indépendant.
- **Endpoint** — `POST /voice/steps` (params : `name`, `n`). OOB update pianoroll simultané.

---

## [0.5.5] — 2026-05-23

### OSC bidirectionnel

- **Récepteur OSC** — serveur UDP sur port d'écoute dédié (défaut `0.0.0.0:57121`), démarré en même temps que l'émetteur. Commandes acceptées en entrée :
  - `/bang/param/bpm <int>` (40–240), `/bang/param/chaos <float>`, `/bang/param/gravity <float>`, `/bang/param/swing <float>`, `/bang/param/microtiming <float>`, `/bang/param/steps <int>`, `/bang/param/cc_depth <float>`
  - `/bang/generate` — regénération complète avec les params courants
  - `/bang/vary` — variation légère (même algo que le bouton ∿ Varier)
  - `/bang/density/<NomVoix> <float 0–1>` — densité d'une voix
  - `/bang/lock/<idx> <0|1>` — verrouiller / déverrouiller une voix par index
- **PORT ↓ dans le modal OSC** — nouveau champ `PORT ↓` (rx) aux côtés du `PORT ↑` (tx). Configurable à chaud : le serveur rx est relancé sans interrompre l'émetteur.
- **Tooltip mis à jour** — affiche `↑host:port ↓:rx_port` pour distinguer les deux directions.

---

## [0.5.4] — 2026-05-23

### Timing & groove

- **Micro-timing global** — slider `MICRO` (0–100%) dans le toolbar. À 100% : on-grid strict (comportement précédent). À 0% : offset aléatoire ±12% du step appliqué à chaque trigger. Appliqué à l'export MIDI **et** au player JS. Voix Babka incluses. Combinable avec swing et vel_humanize.

---

## [0.5.3] — 2026-05-23

### Séquençage & génération

- **Variation automatique** — bouton `∿ Varier` dans le toolbar (raccourci `V`) : mute légèrement le pattern courant (intensité 0.12, algo Bresenham) sans tout régénérer. Seules les voix non verrouillées et non-Babka/CC sont affectées. Push automatique dans le ring buffer Undo avant mutation.

---

## [0.5.2] — 2026-05-23

### Séquençage & génération

- **Euclidien par voix** — bouton `E` par voix dans le panneau DNA. Cliquer ouvre un champ numérique ; entrer `k` (nombre de hits) et valider avec Entrée applique le rythme euclidien E(n,k) sur la longueur du pattern courant. Algorithme Bresenham. Mise à jour pianoroll et engine immédiate.

---

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
