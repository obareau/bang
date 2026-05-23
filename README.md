# BANG! — Dark Umbrae Sequencer

Moteur de génération MIDI algorithmique pour le projet **Robōtariis**.  
BANG produit des fichiers `.mid` évolutifs, non-répétitifs, destinés à être sculptés dans Logic Pro ou Ableton Live.

---

![Workflow BANG](workflow.png)

---

## Concept

BANG repose sur une logique de **complexité sous-marine** : des structures simples en surface, des mécanismes chaotiques en profondeur.

- **DNA** — chaque voix est encodée en une chaîne de caractères : `x` (trigger), `-` (silence), `?` (probabiliste 50%), `↺` (ratchet ×3), `░` (ghost — jitter ±25ms). Ces caractères compilent en matrices `[trigger, vélocité, probabilité, ratchet, jitter]`.
- **Babka ⚗** — extension de DNA inspirée de Strudel/TidalCycles : `[a b c]` subdivision, `<a b c>` alternance, `x(n,k)` euclidien.
- **Polyrythmie native** — chaque voix a sa propre longueur de pattern. Les cycles se décalent naturellement, le motif ne se répète jamais à l'identique.
- **Entropie multi-sources** — graine SHA-256 composée de `os.urandom`, horloge nanoseconde, fragment de clé SSH, données météo.
- **Chaîne de Markov** — voix mélodiques pilotées par une matrice de transitions sur la gamme pentatonique mineure (A1–G2).

---

## Installation

```bash
git clone git@github.com:obareau/bang.git
cd bang
uv sync
```

Python 3.12+ requis. [uv](https://github.com/astral-sh/uv) pour la gestion des dépendances.

---

## Interface Web — FastAPI + HTMX

L'interface principale. TUI monochrome dans le navigateur, accessible en réseau.

```bash
uv run python web.py
# → http://localhost:7777

BANG_PORT=8888 uv run python web.py   # port custom
```

### Thèmes TUI

5 thèmes couleur, mémorisés dans `localStorage` :

| Bouton | Couleur accent |
|--------|---------------|
| AMB | Amber `rgb(255,170,0)` — défaut |
| GRN | Green `rgb(0,255,65)` |
| RED | Red `rgb(255,34,0)` |
| TRQ | Turquoise `rgb(0,220,200)` |
| WHT | White `rgb(200,200,200)` |

### Layout

| Zone | Description |
|------|-------------|
| Header | Sélecteur de thème + version |
| Panneau gauche | Formulaire : mode, BPM, steps, chaos, gravity, CC depth, dynamics, poly, météo |
| Panneau central | Voix générées — DNA coloré cliquable, boutons thin (×1/÷2/÷4), tags Markov/Babka/CC |
| Panneau droit | Pianoroll SVG + zoom ×0.5→×3 |
| Bas | Historique exports + contrôles session/presets |

### Édition de pattern

Cliquer sur la représentation DNA d'une voix ouvre un champ d'édition inline. La modification met à jour le pianoroll en temps réel (debounce 350ms) sans perdre le focus. `Enter` valide, `Escape` annule.

### Raccourcis clavier

| Touche | Action |
|--------|--------|
| `G` | Générer les patterns |
| `E` | Exporter le fichier MIDI |
| `W` | Rafraîchir la météo |

---

## CLI — Ligne de commande

Interface sans UI, pour les scripts et l'automatisation. **Seule interface** qui supporte les contrôleurs MIDI physiques.

```bash
# Génération simple
uv run bang --mode morph --chaos 0.4 --bpm 120 --steps 64 --out session.mid

# Avec entropie météo + jitter temporel
uv run bang --mode weather --weather --temporal

# Avec contrôleur MIDI physique
uv run bang --controller "Launchpad" --cc-map "80:chaos,81:bpm" --capture 4
```

**Paramètres :**

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `--mode` | `morph` | Voir tableau des modes ci-dessous |
| `--chaos` | `0.30` | Taux de mutation (0.0–1.0) |
| `--bpm` | `110` | Tempo |
| `--steps` | `64` | Nombre de pas MIDI |
| `--gravity` | `0.70` | Attraction vers les graves (Markov) |
| `--cc-depth` | `0.50` | Amplitude drone CC |
| `--out` | `bang_out.mid` | Fichier de sortie |
| `--weather` | off | Entropie météo Scaër |
| `--temporal` | off | Jitter nanoseconde (non-reproductible) |
| `--seed` | auto | Graine fixe pour reproduire une session |
| `--list-ports` | — | Liste les ports MIDI disponibles |
| `--learn` | — | Mode écoute MIDI |
| `--controller` | — | Nom du port MIDI (sous-chaîne) |
| `--cc-map` | — | Mapping CC→paramètre |
| `--capture` | `4` | Durée de capture en secondes |

---

## Modes de génération

| Mode | Description |
|------|-------------|
| `morph` | DNA morphé + mutation proportionnelle au chaos |
| `random` | DNA entièrement aléatoire |
| `weather` | Densité/texture dérivée de la météo Scaër (température, vent) |
| `markov` | Voix mélodique via chaîne de Markov + drone CC74 |
| `phase2` | Markov + kick polyrhythmique + drone CC91 modulé météo |
| `noise` | 8 voix, cycles asymétriques, haute entropie — percussion industrielle |
| `ambient` | 3 voix ultra-sparse — espace, respiration |
| `babka` | Syntaxe Babka — 3 niveaux de complexité selon chaos |
| `volca_drum` | 6 parts sur canaux MIDI 1–6, P-locks CC par step — Korg Volca Drum natif |

---

## Syntaxe DNA

Les atomes s'enchaînent sans séparateur :

| Symbole | Nom | Trigger | Velocity | Prob | Ratchet | Jitter |
|---------|-----|---------|----------|------|---------|--------|
| `x` | Hit | oui | 105 | 100% | ×1 | — |
| `-` | Silence | non | — | — | — | — |
| `?` | Probable | oui | 90 | 50% | ×1 | — |
| `↺` | Ratchet | oui | 110 | 100% | ×3 | — |
| `░` | Ghost | oui | 85 | 100% | ×1 | ±25ms |

```
x---x---       → kick sur 1 et 3
x-x-x-x-       → hi-hat double-croche
?-?-?-?-       → pattern 50% aléatoire
x-░-x-░-      → ghost notes sur les temps faibles
↺---x---      → ratchet sur le 1
```

---

## Syntaxe Babka ⚗

Extension de DNA. Tout pattern DNA reste valide en Babka.

| Opérateur | Syntaxe | Comportement |
|-----------|---------|-------------|
| `[ ]` | `[a b c]` | Subdivision — n atomes partagent 1 step |
| `< >` | `<a b c>` | Alternance — une alternative par cycle |
| `( )` | `x(n,k)` | Euclidien inline — n triggers sur k steps (Bresenham) |
| `[x(n,k)]` | overlay | Euclidien compressé dans 1 step |

```
[x x]-x-[x x]-x-   → subdivisions (32e)
x(3,8)              → 3 hits euclidiens sur 8 steps
<x-x- ?-?->         → alternance deux patterns
↺(2,8)             → 2 ratchets euclidiens
<[x x]- x-->        → subdivision dans alternance
```

---

## API HTTP

L'interface web expose une API REST utilisable par des clients externes.

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Interface principale |
| POST | `/generate` | Génère voix + pianoroll (form: mode, chaos, bpm, steps, …) |
| POST | `/export` | Génère + écrit le fichier MIDI |
| POST | `/export/song` | Song complète multi-fichiers (structure intro→outro) |
| GET | `/pattern` | JSON état courant — bpm, steps, voices[].events |
| POST | `/voice/preview` | Preview pianoroll en live sans rechargement voix |
| POST | `/voice/pattern` | Valide un pattern édité |
| POST | `/voice/thin` | Thinning ×1/÷2/÷4 sur une voix |
| POST | `/notes` | Remap notes MIDI |
| POST | `/poly` | Max polyphonie |
| GET | `/session/export` | Télécharge session JSON |
| POST | `/session/import` | Charge session JSON |
| GET | `/presets` | Liste presets built-in + custom |
| POST | `/preset/apply` | Applique un preset |
| POST | `/preset/save` | Sauvegarde preset courant |
| DELETE | `/preset/{name}` | Supprime preset custom |
| GET | `/download/{filename}` | Télécharge un MIDI depuis exports/ |
| GET | `/doc` | Documentation complète |

```bash
# Récupérer le pattern courant en JSON
curl http://localhost:7777/pattern | jq '.voices[0].events[:3]'
```

---

## Sessions & Presets

### Session

Sauvegarde l'état complet (patterns, remaps, params) dans un fichier JSON exporté/importé depuis l'interface.

```json
{
  "bang_version": "0.3.0",
  "params": { "mode": "babka", "bpm": 120, "steps": 16, "chaos": 0.3 },
  "voices": [
    {"note": 36, "pattern": "x---x---", "type": "dna"},
    {"note": 38, "pattern": "x(3,8)",   "type": "babka"}
  ],
  "voice_thin": {},
  "note_remap": {},
  "max_poly": 0
}
```

### Presets

Presets built-in (808, 909, Volca Drum…) + presets custom dans `~/.bang_presets.json`. Un preset est un mapping nom-de-voix → note MIDI.

---

## Entropie et seeds

Chaque export génère une graine SHA-256 loggée dans `bang_sessions.jsonl` et dans le fichier MIDI (`MetaMessage text`).

```bash
uv run bang --seed 77e207b02c0e0801... --mode phase2
```

L'option `--temporal` ajoute un jitter nanoseconde par pas — **non-reproductible** même avec `--seed`.

---

## Structure du projet

```
bang/
├── bang_engine.py      # Moteur central (DNA, Markov, export MIDI, météo, seeds)
├── babka.py            # Parser Babka (subdivision, alternance, euclidien)
├── cli.py              # Interface CLI + MIDI controller
├── web.py              # Interface Web FastAPI+HTMX
├── templates/
│   ├── index.html      # Interface principale + thèmes TUI
│   ├── _voices.html    # Panel voix (DNA coloré + édition inline)
│   ├── _pianoroll.html # Pianoroll SVG
│   ├── _log_entry.html # Entrée de log export
│   ├── _weather.html   # Widget météo
│   └── doc.html        # Documentation (TUI · CLI · API · DNA · Babka)
├── exports/            # Fichiers .mid générés
├── bang_sessions.jsonl # Log de toutes les sessions
└── pyproject.toml
```

---

## BangEngine — API Python

```python
from bang_engine import BangEngine, dark_chain

e = BangEngine(bpm=120, ticks_per_step=120, vel_floor=20, vel_ceiling=110, vel_curve=0.7)

e.add_voice(36, "x---x---")                   # DNA simple
e.add_voice(42, ["x-x-", "x--x"])            # polyrythmie
e.add_markov_voice(dark_chain(), "x-?-")      # mélodie Markov
e.add_babka_voice(38, "x(3,8)")              # euclidien
e.add_babka_voice(36, "<x-[x x]- [x x]-->") # alternance + subdivision
e.add_cc_drone(control=74, breakpoints=[20, 100, 20])

e.export_midi(num_steps=64, filename="out.mid")
```

---

## Contrôleurs MIDI physiques — CLI uniquement

```bash
# Découvrir les CC
uv run bang --learn --controller "Launchpad" --capture 10

# Lancer avec le mapping
uv run bang --mode phase2 --controller "Launchpad" --cc-map "80:chaos,81:bpm" --capture 4
```

**Contrôleurs testés :** Zoom R8 · Novation Launchpad MK3 · Arturia KeyLab Essential MK3 · Arturia MicroFreak · SMC Pad.

---

## Licence

Projet réalisé dans le cadre du méta-univers **Robōtariis**.
