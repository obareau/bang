# BANG! — app macOS native (SwiftUI)

Réécriture native de BANG! en Swift : pas de Python, pas de navigateur, pas de serveur.
SwiftUI pour l'interface, CoreMIDI pour la sortie, le synthé DLS d'Apple pour entendre sans matériel.

```bash
bash macos/build_app.sh            # → macos/build/BANG.app
bash macos/build_app.sh --install  # → et copie dans ~/Applications
```

Il suffit des Command Line Tools (Swift 6), Xcode n'est pas nécessaire.

**Compatibilité** : macOS 13 Ventura ou plus récent, binaire universel (Apple Silicon et Intel).

## Ce qui est porté

| Python | Swift (`Sources/BangCore`) |
|---|---|
| `bang_engine.py` : DNA, Markov, gammes, vélocité, export MIDI | `DNA.swift`, `Markov.swift`, `Renderer.swift`, `MIDIFile.swift` |
| `babka.py` : subdivision, alternance, euclidien | `Babka.swift` |
| `pattern_lib.py` : les 14 modes, p-locks synthés, transforms | `Generator.swift`, `DNA.swift` |
| `bang_session.py` : undo, lock/mute/solo, slots, presets | `Session.swift` |
| `presets_lib.py` : grooves, boîtes à rythme, session JSON | `Presets.swift` |
| `live_clock.py` : horloge temps réel | `Sources/BANG/Player.swift` |

## L'app

- **Générer** (⌘G) selon les 14 modes, avec chaos, gravité, CC depth, swing, steps, gamme, seed figeable
- **Grille DNA cliquable** : chaque clic fait tourner `- → x → ? → ↺ → ░` ; les voix Babka s'éditent au clavier (clic sur le nom de la voix)
- Par voix : verrouillage, mute, solo, densité, drop, swing, canal MIDI, accord (voix mélodiques), et les transforms (varier, régénérer, inverser, rotation, miroir, doubler, diviser, euclide, copier/coller)
- **Édition fine par voix** (clic sur le nom) :
  - **lanes VÉL et PROB** dessinées à la souris, une barre par step (⌥ + glisser efface, le contour montre la valeur du symbole) ;
  - **longueur** de la voix (polymétrie), gardée aux générations suivantes ;
  - **décalage** de phase, **Thin** ÷2 / ÷4 ;
  - **note** de sortie (noms de batterie General MIDI ou chromatique).

  Les p-locks des modes synthé s'affichent dans le **piano-roll** (bande du bas, en orange pour la voix sélectionnée).
- **Ratchets, conditions, p-locks** (détail d'une voix) :
  - lane **RATCH** (1 à 8 répétitions par step) avec **DECAY** (roulement qui s'éteint) et **VARIATION** (vélocité qui dérive, hauteur qui glisse sur la chaîne de Markov) ;
  - **CONDITION** façon Elektron : `1:2`, `2:4`… (un cycle sur N), 1er cycle, sauf 1er, **FILL**, sauf FILL ;
  - **P-LOCKS** : pistes CC générées (modes synthé) ou ajoutées à la main (**+ CC**, gardées d'une génération à l'autre), tirage aléatoire **borné** (densité, min, max), effacement ; interpolation **linéaire / cosinus** entre les valeurs (VÉLOCITÉ & TIMING → P-LOCKS) ;
  - **SORTIE** : un appareil MIDI propre à la voix (multi-port) ; le port virtuel « BANG! » reçoit toujours tout.
- **Groupes** : mute / solo collectif de la batterie, des voix mélodiques ou des voix synthés (barre GROUPES en tête de la liste)
- **Transposition** globale des voix mélodiques (±24 demi-tons, ligne TRANSPO), en direct
- **Réglages avancés** (VÉLOCITÉ & TIMING) : **polyphonie max** (N voix par step), **entropie temporelle** (jitter tiré de l'horloge système, comme le webapp), interpolation des p-locks
- **Presets** : 10 machines intégrées + **mappings personnels** (enregistrer / supprimer) ; **Harmonie (KSP)** : 5 presets (Dark Penta, Dorian Jazz, Phrygian Noise, Lydian Dream, Blues Minor) + harmonies personnelles. Stockés dans `~/Library/Application Support/BANG/presets.json`
- **Lecture** (Espace) : horloge sur un thread temps réel. Chaque cycle est re-tiré, donc les `?`, le Markov et les drops varient d'un tour à l'autre ; une édition s'entend tout de suite
- **Batterie électro** : kits **808** et **909** recréés par synthèse analogique (oscillateurs, bruit, filtres, sans échantillons), ou le kit General MIDI. Choix dans KIT (section Presets) ou dans le menu des sorties ; ils jouent le canal 10
- **Jeu live** (section LIVE) :
  - **Horloge** : tap tempo (médiane des 5 derniers taps) ou **synchro MIDI clock** sur une source au choix — tempo mesuré sur l'horloge entrante, Start / Continue / Stop suivis, notes calées sur les impulsions (24 ppq) ;
  - **Évolution** automatique : une variation tous les 1, 2, 4 ou 8 cycles ;
  - **A / B** : deux patterns à comparer (clic : charger, ⌥ clic : mémoriser) ;
  - **Mémoires** : avance automatique tous les N cycles, tirage pondéré (clic droit : poids 1 à 9) ;
  - **Morph** : passage progressif du pattern courant vers une mémoire en N cycles (probabilités et vélocités mélangées step par step) ;
  - **Song** : enchaînement de mémoires, ex. `1x4 2x2 3` (mémoire 1 × 4 cycles, 2 × 2, 3 × 1, puis reboucle) ;
  - **LFO par voix** (sin / tri / rampe / aléatoire) sur la densité ou le drop, réglable en vitesse et profondeur.

  Les changements de fin de cycle sont préparés un peu à l'avance pour tomber pile sur le premier temps. Les mémoires, poids, A/B et LFO sont sauvegardés avec la session.
- **Connexions** (bouton CONNEXIONS) :
  - **OSC** bidirectionnel : émission (SuperCollider 57120, Max, TouchOSC) de l'état du pattern, de `/bang/clock` et de chaque note pendant la lecture ; réception de `/bang/generate`, `/vary`, `/play`, `/stop`, `/param/…`, `/density/<voix>`, `/lock/<n>`, `/mute/<n>`, `/slot/<n>`, `/evolve`. Moniteur des messages en direct ;
  - **Ableton Live** via AbletonOSC : un clip par voix sur des pistes consécutives, tempo réglé, ou BPM récupéré depuis Live ;
  - **Strudel** : code mini-notation copié en un clic ; **un .mid par voix** dans un dossier ; **gabarit TouchOSC** du dépôt ;
  - **MIDI Learn** : décompte de 2 temps, puis le rythme joué sur des pads devient la DNA de la voix (aussi dans le menu ⋯ de chaque voix) ;
  - **Panneaux NTS-1 et MicroFreak** : potentiomètres CC en direct, avec les numéros officiels (tableau MIDI Korg, documentation Arturia).
- **Sorties** : synthé GM interne, port virtuel **« BANG! »** (à choisir comme entrée dans Ableton, Logic ou SuperCollider) et n'importe quelle destination CoreMIDI
- **Export .mid** (⌘E) : type 1 (une piste par voix, pistes CC drone) ou type 0 (une seule piste), la seed en méta. On peut aussi **glisser** le .mid vers un DAW ou le Finder
- **Export morceau** (⌥⌘E) : le macro-arrangement du webapp — intro ×4, transition, couplet ×8, break, couplet 2 ×4, climax ×4, break 2 ×2, outro ×2, fin ×4 (modes Ambient / Noise, rampes de chaos, morphs entre variations), soit 944 steps. Un `.mid` avec une piste par instrument et un **marqueur par section**, plus en option un `.mid` par section (comme le webapp) et le rendu `.wav`
- **Journal des exports** (menu Fichier) : une ligne par export dans `bang_sessions.jsonl` (seed, mode, BPM, voix…), comme le webapp
- **Export .wav** (⇧⌘E) : rendu audio du pattern avec le synthé interne (kit GM, 808 ou 909), 1 à 16 répétitions, WAV 24 bits / 48 kHz normalisé à −1 dBFS. En **boucle parfaite** (par défaut), le fichier dure exactement le pattern et la queue des sons est repliée au début : il boucle sans couture dans un DAW ou un sampler. Sinon, rendu « one-shot » avec la queue à la fin. Nom proposé `preset-variation-date`, ex. `bassline-808-v003-2026-11-13_2150.wav` (la variation augmente à chaque nouveau pattern exporté pour ce preset)
- **Sessions / projets** (⌘S / ⌘O) : fichier `.bang` (ou `.json`) au format de `session_to_dict` — pattern, réglages par voix, mémoires, A/B, presets appliqués. Un fichier issu du webapp s'ouvre ici, et l'inverse aussi. L'état est sauvegardé automatiquement dans `~/Library/Application Support/BANG/state.json`
- **Zoom** : l'interface suit la taille de la fenêtre (1360×820 = 100 %) ; ⌘+ / ⌘− / ⌘0 ajustent en plus
- 16 grooves, 10 mappings de boîtes à rythme, 8 mémoires, météo de Scaër (Open-Meteo)

## À savoir

- **Seeds** : une seed rejoue toujours le même pattern dans l'app native, mais pas le même que dans le webapp, car le générateur aléatoire n'est pas le Mersenne Twister de CPython.
- **Canaux** : l'export utilise les mêmes canaux que la lecture (batterie sur le 10, basse sur le 1, Markov sur le 2, KSP sur les canaux 3 à 6…), et ils sont modifiables voix par voix. Le moteur Python, lui, exportait les batteries sur le canal 1.
- **CC des synthés** : les panneaux et p-locks Python du NTS-1 et du MicroFreak utilisaient de mauvais numéros (ceux du MiniFreak pour le MicroFreak). L'app native utilise les numéros des tableaux officiels.

## Vérifier

```bash
cd macos && swift run bang-check /tmp/bang-mid   # auto-test du moteur + un .mid par mode
```

Diagnostic : `BANG_SELFTEST_EXTRAS=song:<dossier>|presets|cond|fill|ports:<A>,<B>` teste le morceau, les presets, les conditions, le FILL et le multi-port ; `BANG_SELFTEST_STUDIO=osc|ableton|learn:<source>|cc` (avec `BANG_OSC_TX=hôte:port`, `BANG_OSC_RX=port`, `BANG_ABLETON=hôte:port`) teste les connexions ; `BANG_SELFTEST_LIVE=song|morph|sync:<source>` teste le jeu live (avec `BANG_DEBUG_CLOCK=1` pour tracer impulsions et notes) ; `BANG_SELFTEST_WAV_LOOP=/dossier` compare une boucle parfaite au rendu continu ; `BANG_SELFTEST_WAV=/dossier` exporte le pattern en WAV avec chaque kit (`BANG_SELFTEST_WAV_GRID=1` : pattern de contrôle pour vérifier le calage) ; `BANG_SELFTEST_AUDIO=1` mesure le niveau de sortie avec chaque kit ; `BANG_SELFTEST_MODES=1` enchaîne les 14 modes en lecture ; `BANG_SNAPSHOT=/tmp/shot.png BANG_SNAPSHOT_PLAY=1 BANG_SNAPSHOT_QUIT=1 macos/build/BANG.app/Contents/MacOS/BANG` lance la lecture puis enregistre une capture de la fenêtre, sans permission d'enregistrement d'écran.
