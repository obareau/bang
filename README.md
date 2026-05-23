# BANG! — Générateur MIDI algorithmique

> **v0.5.1**

BANG! génère des fichiers `.mid` — c'est tout ce qu'il fait, et c'est tout ce qu'il fera.

Pas de séquenceur temps réel. Pas de timeline. Pas de mixage. BANG produit des patterns MIDI exportés vers Logic, Ableton, ou n'importe quel DAW. Le workflow est clair : générer → écouter → ajuster → exporter.

---

## Ce que BANG! est

- Un **générateur de patterns** selon des modes qui correspondent à des usages prédéfinis : batterie algorithmique, ligne de basse Markov, synths dédiés (Volca Drum, Volca Kick, Volca FM, MicroFreak), ambient, noise, babka euclidien
- Des **presets qui collent au matériel** : notes MIDI et canaux câblés pour Volca Drum (6 canaux split), Volca Kick, Volca FM, MicroFreak, TR-808/909, GM, MPC60, etc.
- Des **gammes configurables** pour les modes mélodiques (Markov, Phase 2, Bassline) : 12 toniques × 8 modes (pentatonique, mineur, dorian, phrygien, majeur, mixolydien, lydien)
- Un **swing** réglable (0–100%) — décalage des steps impairs, appliqué à l'export MIDI et au player Web MIDI
- Une **seed fixe** optionnelle — reproduire exactement un pattern en collant sa seed dans le formulaire. La seed est **cliquable dans le log** : cliquer dessus la copie directement dans le champ.
- Une **fonction Play** intégrée dans l'interface — lecture MIDI du pattern courant dans le navigateur, avec pianoroll synchronisé, sans export
- Une **fonction Preview** live — toute modification de pattern DNA met à jour le pianoroll en temps réel, avant d'exporter quoi que ce soit
- Des **P-locks par step** pour les synths hardware (Volca Drum, Volca Kick, Volca FM, MicroFreak) — automation CC générée algorithmiquement, incluse dans l'export MIDI multi-piste

## Ce que BANG! n'est pas

- Un séquenceur temps réel — les patterns ne tournent pas en live dans BANG
- Un DAW — aucune gestion de clips, de timeline, de routing audio
- Un plugin — c'est une app web locale, servie par FastAPI sur le réseau local

Le rendu final se fait dans le DAW. BANG s'occupe uniquement de générer des `.mid` intéressants.

---

![Workflow BANG](workflow.png)

---

## Modes

| Mode | Cible | Steps | Description |
|------|-------|-------|-------------|
| `morph` | Batterie | libre | DNA morphé + mutation chaos |
| `random` | Batterie | libre | DNA entièrement aléatoire |
| `weather` | Batterie | libre | Densité/texture depuis météo Scaër |
| `markov` | Batterie + mélodie | libre | Voix mélodique chaîne de Markov + drone CC |
| `phase2` | Batterie + mélodie | libre | Markov + kick polyrhythmique + météo CC |
| `noise` | Batterie | libre | 8 voix, cycles asymétriques — percussion industrielle |
| `ambient` | Ambiance | libre | 3 voix ultra-sparse |
| `babka` | Batterie | libre | Syntaxe Babka (subdivision, euclidien, alternance) |
| `bassline` | Basse | ≤128 | Ligne de basse Markov, 2 voix, portamento CC |
| `volca_kick` ★ | Korg Volca Kick | ≤16 | 1 voix + P-locks (Pitch, Decay, Drive, Fold, BitRed) |
| `volca_fm` ⚡ | Korg Volca FM | ≤16 | 3 voix polyphoniques FM + P-locks sur FM1 |
| `volca_drum` ★ | Korg Volca Drum | ≤16 | 6 parts, 6 canaux MIDI, P-locks par part |
| `microfreak` ◈ | Arturia MicroFreak | ≤64 | 3 voix paraphoniques + P-locks (Cutoff, Timbre, LFO) |
| `keystep_pro` ♜ | Arturia Keystep Pro | 16 | 3 voix drums (ch10) + 4 pistes Markov indépendantes (ch1–4) |

---

## Presets hardware

Les presets mappent les noms de voix aux notes MIDI du matériel cible. Sélectionnable depuis l'interface.

| Preset | Cible | Notes |
|--------|-------|-------|
| GM | Batterie GM standard | Kick 36, Snare 38, HH 42… |
| TR-808 / TR-909 | Roland TR-8 | Mapping authentique |
| MPC60 | Akai MPC60/3000 | — |
| Battery 4 | NI Battery 4 | GM-compatible |
| Tekno | Baby Audio Tekno | C1→F2 séquentiel |
| LinnDrum | LinnDrum | — |
| Volca Kick | Korg Volca Kick | VKick 60 (C3) |
| Volca FM | Korg Volca FM | FM1 36, FM2 43, FM3 48 |
| MicroFreak | Arturia MicroFreak | MF1 45, MF2 40, MF3 36 |

---

## Installation

```bash
git clone git@github.com:obareau/bang.git
cd bang
uv sync
```

Python 3.12+ · [uv](https://github.com/astral-sh/uv)

---

## Interface Web

```bash
uv run python web.py
# → http://localhost:7777

BANG_PORT=8888 uv run python web.py
```

### Thèmes TUI

5 thèmes couleur mémorisés dans `localStorage` : AMB (amber), GRN, RED, TRQ, WHT.

### Raccourcis clavier

| Touche | Action |
|--------|--------|
| `G` | Générer |
| `E` | Exporter MIDI |
| `W` | Rafraîchir météo |

### Toolbar

| Bouton | Description |
|--------|-------------|
| `Generate` | Génère un nouveau pattern |
| `Export` | Exporte le `.mid` courant |
| `↩` | Undo — restaure l'état précédent (ring buffer 5 snapshots) |
| `▸A` / `▸B` | Store — sauvegarde l'état courant dans le slot A ou B |
| `A○` / `B○` | Load — charge le slot A ou B (● = slot rempli) |
| `OSC ○` | Active/désactive l'émission OSC temps réel |

### Édition inline

Cliquer sur la représentation DNA d'une voix ouvre un champ d'édition. Le pianoroll se met à jour en temps réel (debounce 350ms). `Enter` valide, `Escape` annule.

---

## Contrôles par voix

Chaque voix dispose de contrôles individuels dans le panneau de gauche.

### Lock 🔒

Verrouille une voix : elle ne sera **pas régénérée** lors des prochains clics sur `Generate`. Indiqué par une bordure colorée sur la ligne de voix. Utile pour fixer le groove et explorer les variations sur les autres voix.

```
[🔒] → voix figée, survive aux régénérations
[ 🔓] → voix libre (comportement par défaut)
```

**Undo** préserve les locks : le ring buffer stocke l'état complet incluant quelles voix étaient verrouillées.

### Densité (0–1)

Slider par voix qui multiplie la probabilité de déclenchement de chaque step. 

- `1.0` = comportement normal (pas de filtrage)
- `0.5` = moitié des triggers supprimés aléatoirement
- `0.0` = voix silencieuse

La densité est appliquée au player JS et à l'export MIDI. Elle est persistée dans la session.

### Chord selector (voix Markov / KSP)

Pour les voix de type `markov` et `ksp`, un sélecteur d'accord est disponible. Il transforme chaque note déclenchée en accord en ajoutant des intervalles fixes.

| Type | Intervalles (demi-tons) |
|------|------------------------|
| `mono` | — (note seule) |
| `power` | +7 |
| `minor` | +3, +7 |
| `major` | +4, +7 |
| `sus2` | +2, +7 |
| `sus4` | +5, +7 |
| `m7` | +3, +7, +10 |
| `M7` | +4, +7, +11 |
| `dom7` | +4, +7, +10 |
| `dim` | +3, +6 |
| `aug` | +4, +8 |

Les accords sont appliqués à l'export MIDI **et** au player JS en temps réel.

---

## Undo — Ring buffer

Le bouton `↩` dans le toolbar restaure le snapshot précédent. BANG conserve les **5 derniers états** (voix + p-locks + paramètres). Chaque `Generate` empile un nouveau snapshot.

```
snapshot[0] ← état courant
snapshot[1] ← avant dernière génération
...
snapshot[4] ← il y a 5 générations
```

`↩` remonte d'un cran et restaure l'état complet : DNA de toutes les voix, p-locks, paramètres chaos/bpm/swing, locks actifs.

---

## Comparaison A/B

Deux slots indépendants pour comparer des variantes d'un pattern.

```
▸A   → sauvegarde l'état courant dans le slot A
▸B   → sauvegarde dans le slot B
A●   → charge le slot A (● = slot rempli, ○ = vide)
B●   → charge le slot B
```

Workflow typique :

1. Générer un pattern qui semble intéressant → `▸A`
2. Générer une variation → `▸B`
3. `A●` / `B●` pour écouter et comparer
4. Exporter le meilleur

Les slots A et B sont inclus dans l'export/import de session JSON.

---

## Multi-canal Markov

Le paramètre `markov_channel` (1–16) route la voix mélodique Markov sur un canal MIDI spécifique. Par défaut : canal 1.

Utile pour router vers un synth externe précis dans le DAW, ou pour séparer basse/mélodie sur des canaux différents.

```bash
# Via l'interface : sélecteur "MIDI CH" visible en mode markov/phase2/bassline
# Via l'API Python :
e.add_markov_voice(chain, "x-?-", channel=4)   # canal 5 (0-indexé)
```

---

## Mode Keystep Pro ♜

Mode dédié à l'Arturia Keystep Pro. Génère **7 voix** :

| Voix | Canal MIDI | Registre | Description |
|------|-----------|----------|-------------|
| Kick | ch10 | C2 | Kick drum |
| Snare | ch10 | D2 | Snare |
| HiHat | ch10 | F#2 | Hi-hat |
| KSP Lead | ch1 | 2 octaves, medium-high | Mélodie principale |
| KSP Bass | ch2 | 1 octave, grave | Ligne de basse |
| KSP Chord | ch3 | 2 octaves, medium | Harmonie |
| KSP Arp | ch4 | 2 octaves, medium-high | Arpège |

Les 4 pistes mélodiques utilisent des chaînes de Markov indépendantes avec des registres différenciés. Chaque piste KSP a son propre **chord selector**.

L'export MIDI produit un fichier **type 1 multi-piste**, directement importable dans le Keystep Pro via MIDI SysEx ou drag-and-drop DAW.

```
Steps auto-fixés à 16 en mode keystep_pro (cohérence KSP natif)
```

---

## Export MIDI multi-piste

L'export génère un fichier **MidiFile type 1** : une track par voix + une track tempo.

| Track | Contenu |
|-------|---------|
| Track 0 | Tempo (BPM) + seed embedée dans les métadonnées |
| Track 1..N | Une piste par voix, nommée d'après le type de voix |
| Track CC | P-locks : automation CC step-par-step par voix concernée |

Les **P-locks** sont inclus dans l'export comme événements CC avant chaque `note_on`. Les DAWs les lisent comme de l'automation de clip.

Les **accords Markov** (chord selector) sont inclus dans l'export : chaque note déclenchée émet les tons de l'accord sur la même track MIDI.

---

## OSC Output

BANG émet des messages OSC en UDP en temps réel, synchronisés au BPM du pattern courant.

### Activer

Cliquer sur `OSC ○` dans le toolbar → modal de configuration (host:port) → `Start`. Le bouton passe à `OSC ●` quand actif.

Défaut : `127.0.0.1:57120` (SuperCollider).

### Format des messages

| Message | Arguments | Description |
|---------|-----------|-------------|
| `/bang/clock` | `[step, total_steps]` | Émis à chaque step |
| `/bang/{NomVoix}` | `[step, velocity, note]` | Par trigger, par voix |

`NomVoix` correspond au label de la voix (`Kick`, `Snare`, `HH`, `Markov`, `KSP Lead`, etc.).

### Exemples d'utilisation

**SuperCollider** :

```supercollider
OSCdef(\bangClock, { |msg|
    var step = msg[1], total = msg[2];
    ("step " ++ step ++ "/" ++ total).postln;
}, '/bang/clock');

OSCdef(\bangKick, { |msg|
    var step = msg[1], vel = msg[2], note = msg[3];
    Synth(\kick, [\amp, vel/127]);
}, '/bang/Kick');
```

**Max/MSP** : utiliser un objet `udpreceive 57120` + `route /bang/clock /bang/Kick /bang/Markov`

**TouchDesigner** : OSC In DAT sur port 57120, filtrer par address `/bang/*`

### Comportement

- Les notes Markov sont **régénérées au début de chaque cycle** (step 0) depuis la même chaîne de Markov, donc elles évoluent au fil des cycles.
- Les voix Babka sont **exclues** de l'OSC (timing fractionnel incompatible avec le tick step-par-step).
- L'OSC s'arrête automatiquement si on clique `OSC ●` ou si l'interface est fermée.

---

## Syntaxe DNA

| Symbole | Comportement |
|---------|-------------|
| `x` | Trigger — vélocité 105, 100% |
| `-` | Silence |
| `?` | Probabiliste 50% |
| `↺` | Ratchet ×3 |
| `░` | Ghost — jitter ±25ms |

## Humanisation velocity

Le paramètre `vel_humanize` (0–40) ajoute un décalage aléatoire ±N à la velocity de chaque note. Appliqué à l'export MIDI et au player JS.

- `0` = velocities exactes (comportement machine)
- `10` = légère humanisation (recommandé)
- `40` = variations importantes

## Gammes (modes Markov, Phase 2, Bassline, Keystep Pro)

Sélectionnables depuis l'interface (sélecteurs ROOT + SCALE, visibles uniquement sur les modes mélodiques).

| Gamme | Intervalles |
|-------|-------------|
| `penta_min` | 0 3 5 7 10 |
| `penta_maj` | 0 2 4 7 9 |
| `minor` | 0 2 3 5 7 8 10 |
| `dorian` | 0 2 3 5 7 9 10 |
| `phrygian` | 0 1 3 5 7 8 10 |
| `major` | 0 2 4 5 7 9 11 |
| `mixo` | 0 2 4 5 7 9 10 |
| `lydian` | 0 2 4 6 7 9 11 |

La chaîne de Markov est construite algorithmiquement (distance de degré, gravité tonique/quinte) via `build_markov_chain(root_note, intervals, num_octaves)`.

---

## Syntaxe Babka ⚗

| Opérateur | Syntaxe | Comportement |
|-----------|---------|-------------|
| `[ ]` | `[a b c]` | Subdivision — n atomes dans 1 step |
| `< >` | `<a b c>` | Alternance par cycle |
| `( )` | `x(n,k)` | Euclidien inline (Bresenham) |

---

## CLI

```bash
uv run bang --mode morph --chaos 0.4 --bpm 120 --steps 64 --out session.mid
uv run bang --mode weather --weather --temporal
uv run bang --controller "Launchpad" --cc-map "80:chaos,81:bpm" --capture 4
```

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `--mode` | `morph` | Mode de génération |
| `--chaos` | `0.30` | Taux de mutation (0.0–1.0) |
| `--bpm` | `110` | Tempo |
| `--steps` | `64` | Nombre de pas |
| `--gravity` | `0.70` | Attraction graves (Markov) |
| `--seed` | auto | Graine fixe pour reproduire |
| `--weather` | off | Entropie météo |
| `--temporal` | off | Jitter nanoseconde (non-reproductible) |

---

## API HTTP

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Interface principale |
| POST | `/generate` | Génère patterns + pianoroll |
| POST | `/export` | Exporte le fichier `.mid` |
| POST | `/export/song` | Song complète multi-fichiers |
| GET | `/pattern` | JSON état courant |
| POST | `/voice/preview` | Preview pianoroll sans validation |
| POST | `/voice/pattern` | Valide pattern édité |
| POST | `/voice/thin` | Thinning ×1/÷2/÷4 |
| POST | `/voice/chord` | Change le type d'accord d'une voix Markov/KSP |
| POST | `/voice/density` | Change la densité (0–1) d'une voix |
| POST | `/lock_voice` | Verrouille/déverrouille une voix |
| POST | `/undo` | Restaure le snapshot précédent |
| POST | `/ab/store` | Sauvegarde l'état dans le slot A ou B |
| POST | `/ab/load` | Charge le slot A ou B |
| POST | `/osc/toggle` | Active/désactive l'émission OSC |
| POST | `/osc/config` | Configure host:port OSC |
| POST | `/notes` | Remap notes MIDI |
| GET | `/session/export` | Exporte session JSON |
| POST | `/session/import` | Charge session JSON |
| GET | `/presets` | Liste presets |
| POST | `/preset/apply` | Applique preset |
| GET | `/doc` | Documentation complète |

---

## BangEngine — API Python

```python
from bang_engine import BangEngine, build_markov_chain, SCALE_INTERVALS

e = BangEngine(bpm=120, vel_floor=20, vel_ceiling=110, vel_curve=0.7)
e.add_voice(36, "x---x---")
e.add_voice(42, ["x-x-", "x--x"])                          # polyrythmie

chain = build_markov_chain(root_note=50, intervals=SCALE_INTERVALS["dorian"], num_octaves=2)
e.add_markov_voice(chain, "x-?-", channel=0)               # mélodie Markov D dorian 2 octaves, ch1

bass = build_markov_chain(root_note=26, intervals=SCALE_INTERVALS["penta_min"], num_octaves=2)
e.add_markov_voice(bass, "x---x-", channel=1)              # basse pentatonique mineure, ch2

e.add_babka_voice(38, "x(3,8)")
e.add_cc_drone(control=74, breakpoints=[20, 100, 20])

# voice_chords : dict nom_voix → type d'accord pour l'export
e.export_midi(
    num_steps=64,
    filename="out.mid",
    swing=0.3,
    seed="abc123",
    voice_chords={"markov-ch1": "minor", "markov-ch2": "power"},
)
```

---

## Structure

```
bang/
├── bang_engine.py      # Moteur (DNA, Markov, MIDI, météo, seeds)
├── babka.py            # Parser Babka
├── cli.py              # CLI + contrôleurs MIDI
├── web.py              # Interface Web FastAPI+HTMX
├── templates/
│   ├── index.html
│   ├── _voices.html
│   ├── _pianoroll.html
│   └── doc.html
└── exports/            # Fichiers .mid générés
```

---

## Licence

Projet réalisé dans le cadre du méta-univers **Robōtariis**.
