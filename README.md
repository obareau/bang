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
- Une **seed fixe** optionnelle — reproduire exactement un pattern en collant sa seed dans le formulaire
- Une **fonction Play** intégrée dans l'interface — lecture MIDI du pattern courant dans le navigateur, avec pianoroll synchronisé, sans export
- Une **fonction Preview** live — toute modification de pattern DNA met à jour le pianoroll en temps réel, avant d'exporter quoi que ce soit
- Des **P-locks par step** pour les synths hardware (Volca Drum, Volca Kick, Volca FM, MicroFreak) — automation CC générée algorithmiquement

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

### Édition inline

Cliquer sur la représentation DNA d'une voix ouvre un champ d'édition. Le pianoroll se met à jour en temps réel (debounce 350ms). `Enter` valide, `Escape` annule.

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

## Syntaxe DNA

| Symbole | Comportement |
|---------|-------------|
| `x` | Trigger — vélocité 105, 100% |
| `-` | Silence |
| `?` | Probabiliste 50% |
| `↺` | Ratchet ×3 |
| `░` | Ghost — jitter ±25ms |

## Gammes (modes Markov, Phase 2, Bassline)

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
e.add_markov_voice(chain, "x-?-")                          # mélodie Markov D dorian 2 octaves

bass  = build_markov_chain(root_note=26, intervals=SCALE_INTERVALS["penta_min"], num_octaves=2)
e.add_markov_voice(bass, "x---x-")                         # basse pentatonique mineure

e.add_babka_voice(38, "x(3,8)")
e.add_cc_drone(control=74, breakpoints=[20, 100, 20])
e.export_midi(num_steps=64, filename="out.mid", swing=0.3, seed="abc123")
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
