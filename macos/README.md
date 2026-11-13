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
- **Lecture** (Espace) : horloge sur un thread temps réel. Chaque cycle est re-tiré, donc les `?`, le Markov et les drops varient d'un tour à l'autre ; une édition s'entend tout de suite
- **Batterie électro** : kits **808** et **909** recréés par synthèse analogique (oscillateurs, bruit, filtres, sans échantillons), ou le kit General MIDI. Choix dans KIT (section Presets) ou dans le menu des sorties ; ils jouent le canal 10
- **Sorties** : synthé GM interne, port virtuel **« BANG! »** (à choisir comme entrée dans Ableton, Logic ou SuperCollider) et n'importe quelle destination CoreMIDI
- **Export .mid** (⌘E) type 1 : une piste par voix, des pistes CC drone, la seed en méta. On peut aussi **glisser** le .mid vers un DAW ou le Finder
- **Export .wav** (⇧⌘E) : rendu audio du pattern avec le synthé interne (kit GM, 808 ou 909), 1 à 16 répétitions, WAV 24 bits / 48 kHz normalisé à −1 dBFS. En **boucle parfaite** (par défaut), le fichier dure exactement le pattern et la queue des sons est repliée au début : il boucle sans couture dans un DAW ou un sampler. Sinon, rendu « one-shot » avec la queue à la fin. Nom proposé `preset-variation-date`, ex. `bassline-808-v003-2026-11-13_2150.wav` (la variation augmente à chaque nouveau pattern exporté pour ce preset)
- **Sessions** (⌘S / ⌘O) au format JSON de `session_to_dict` : un fichier issu du webapp s'ouvre ici, et l'inverse aussi. L'état est sauvegardé automatiquement dans `~/Library/Application Support/BANG/state.json`
- **Zoom** : l'interface suit la taille de la fenêtre (1360×820 = 100 %) ; ⌘+ / ⌘− / ⌘0 ajustent en plus
- 16 grooves, 10 mappings de boîtes à rythme, 8 mémoires, météo de Scaër (Open-Meteo)

## À savoir

- **Seeds** : une seed rejoue toujours le même pattern dans l'app native, mais pas le même que dans le webapp, car le générateur aléatoire n'est pas le Mersenne Twister de CPython.
- **Canaux** : l'export utilise les mêmes canaux que la lecture (batterie sur le 10, basse sur le 1, Markov sur le 2, KSP sur les canaux 3 à 6…), et ils sont modifiables voix par voix. Le moteur Python, lui, exportait les batteries sur le canal 1.
- **Pas encore porté** : les LFO par voix, le morphing A→B, OSC/TouchOSC, Ableton OSC, la synchro MIDI clock entrante, le mode Song et les panneaux NTS-1 / MicroFreak.

## Vérifier

```bash
cd macos && swift run bang-check /tmp/bang-mid   # auto-test du moteur + un .mid par mode
```

Diagnostic : `BANG_SELFTEST_WAV_LOOP=/dossier` compare une boucle parfaite au rendu continu ; `BANG_SELFTEST_WAV=/dossier` exporte le pattern en WAV avec chaque kit (`BANG_SELFTEST_WAV_GRID=1` : pattern de contrôle pour vérifier le calage) ; `BANG_SELFTEST_AUDIO=1` mesure le niveau de sortie avec chaque kit ; `BANG_SELFTEST_MODES=1` enchaîne les 14 modes en lecture ; `BANG_SNAPSHOT=/tmp/shot.png BANG_SNAPSHOT_PLAY=1 BANG_SNAPSHOT_QUIT=1 macos/build/BANG.app/Contents/MacOS/BANG` lance la lecture puis enregistre une capture de la fenêtre, sans permission d'enregistrement d'écran.
