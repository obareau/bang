# BANG! — Générateur MIDI algorithmique

> **v0.4.0**

BANG! génère des fichiers `.mid` — c'est tout ce qu'il fait, et c'est tout ce qu'il fera.

Pas de séquenceur temps réel. Pas de timeline. Pas de mixage. BANG produit des patterns MIDI exportés vers Logic, Ableton, ou n'importe quel DAW. Le workflow est clair : générer → écouter → ajuster → exporter.

---

## Ce que BANG! est

- Un **générateur de patterns** selon des modes qui correspondent à des usages prédéfinis : batterie algorithmique, ligne de basse Markov, synths dédiés (Volca Drum, Volca Kick, Volca FM, MicroFreak), ambient, noise, babka euclidien
- Des **presets qui collent au matériel** : notes MIDI et canaux câblés pour Volca Drum (6 canaux split), Volca Kick, Volca FM, MicroFreak, TR-808/909, GM, MPC60, etc.
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
from bang_engine import BangEngine, dark_chain, bass_chain

e = BangEngine(bpm=120, vel_floor=20, vel_ceiling=110, vel_curve=0.7)
e.add_voice(36, "x---x---")
e.add_voice(42, ["x-x-", "x--x"])          # polyrythmie
e.add_markov_voice(dark_chain(), "x-?-")   # mélodie Markov gamme mineure
e.add_markov_voice(bass_chain(), "x---x-") # basse Markov 2 octaves
e.add_babka_voice(38, "x(3,8)")
e.add_cc_drone(control=74, breakpoints=[20, 100, 20])
e.export_midi(num_steps=64, filename="out.mid")
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
