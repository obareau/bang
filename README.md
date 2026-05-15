# BANG — Dark Umbrae Sequencer

Moteur de génération MIDI algorithmique pour le projet **Robōtariis**.  
BANG produit des fichiers `.mid` évolutifs, non-répétitifs, destinés à être sculptés dans Logic Pro ou Ableton Live.

---

![Workflow BANG](workflow.png)

---

## Concept

BANG repose sur une logique de **complexité sous-marine** : des structures simples en surface, des mécanismes chaotiques en profondeur.

- **DNA** — chaque voix est encodée en une chaîne de caractères : `x`(trigger), `-`(silence), `?`(probabiliste), `↺`(ratchet ×3), `░`(jitter de timing). Ces caractères sont compilés en matrices `[trigger, vélocité, probabilité, ratchet, jitter]`.
- **Polyrythmie native** — chaque voix a sa propre longueur de pattern (ex. kick sur 16, basse sur 5). Les cycles se décalent naturellement, le motif ne se répète jamais à l'identique.
- **Entropie multi-sources** — graine cryptographique SHA-256, météo en temps réel (Scaër, Finistère), horloge nanoseconde, fragment de clé SSH.
- **Chaîne de Markov** — voix mélodiques pilotées par une matrice de transitions pondérée sur la gamme pentatonique mineure (A1–G2), avec gravité paramétrable vers les notes graves.

---

## Installation

```bash
git clone git@github.com:obareau/bang.git
cd bang
uv sync
```

Python 3.12+ requis. [uv](https://github.com/astral-sh/uv) pour la gestion des dépendances.

---

## Trois interfaces, un seul moteur

BANG expose le même moteur (`bang_engine.py`) via trois interfaces selon le contexte d'utilisation.

### 1. Interface Web — FastAPI + HTMX

L'interface principale. Tourne sur le serveur, accessible depuis n'importe quel device sur le réseau Tailscale.

```bash
uv run python web.py
# http://100.64.201.127:7777
```

Variable d'environnement pour changer le port :

```bash
BANG_PORT=7800 uv run python web.py
```

**Raccourcis clavier** (hors champ de saisie) :

| Touche | Action |
|--------|--------|
| `G` | Générer les patterns |
| `E` | Exporter le fichier MIDI |
| `W` | Rafraîchir la météo |

Les paramètres (chaos, BPM, gravity, CC depth…) se règlent directement dans les champs de l'interface. **Pas besoin de contrôleur MIDI physique** — l'interface web remplace entièrement cette fonction.

---

### 2. TUI — Terminal (Textual)

Interface visuelle dans le terminal. Utile en SSH sans navigateur.

```bash
uv run python tui.py
```

**Raccourcis :**

| Touche | Action |
|--------|--------|
| `G` | Générer |
| `E` | Exporter |
| `W` | Météo |
| `Q` | Quitter |

Même logique que la web : les paramètres se règlent dans les champs du terminal. **Pas de contrôleur MIDI physique.**

---

### 3. CLI — Ligne de commande

Interface sans UI, pour les scripts et l'automatisation. C'est **la seule interface** qui supporte les contrôleurs MIDI physiques.

```bash
# Génération simple
uv run bang --mode morph --chaos 0.4 --bpm 120 --steps 64 --out session.mid

# Avec entropie météo
uv run bang --mode weather --weather --temporal

# Avec contrôleur MIDI physique (voir section dédiée ci-dessous)
uv run bang --controller "Launchpad" --cc-map "80:chaos,81:bpm" --capture 4
```

**Tous les paramètres CLI :**

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `--mode` | `morph` | `morph`, `random`, `weather`, `markov`, `phase2` |
| `--chaos` | `0.30` | Taux de mutation (0.0 – 1.0) |
| `--bpm` | `110` | Tempo |
| `--steps` | `64` | Nombre de pas MIDI |
| `--gravity` | `0.70` | Attraction vers les graves (Markov) |
| `--cc-depth` | `0.50` | Amplitude des drones CC |
| `--out` | `bang_out.mid` | Fichier de sortie |
| `--weather` | off | Active l'entropie météo |
| `--temporal` | off | Jitter nanoseconde (non-reproductible) |
| `--seed` | auto | Graine fixe pour reproduire une session |
| `--list-ports` | — | Liste les ports MIDI disponibles |
| `--learn` | — | Mode écoute MIDI (voir ci-dessous) |
| `--controller` | — | Nom du port MIDI (sous-chaîne) |
| `--cc-map` | — | Mapping CC→paramètre |
| `--capture` | `4` | Durée de capture en secondes |

---

## Contrôleurs MIDI physiques — CLI uniquement

> **Important :** les contrôleurs MIDI physiques (Launchpad, KeyLab, Zoom R8, MicroFreak…) ne sont disponibles qu'en **mode CLI**. L'interface web et la TUI n'en ont pas besoin — leurs sliders remplissent exactement ce rôle.

Le workflow se fait en deux étapes :

### Étape 1 — Découvrir les CC de ton contrôleur

```bash
uv run bang --list-ports
# → 0: Launchpad MK3
# → 1: KeyLab Essential 49
# → 2: Zoom R8

uv run bang --learn --controller "Launchpad" --capture 10
# Bouge tes knobs pendant 10 secondes
# → CC 80: min=0  max=127  █████████░░░░░░░░░░░
# → CC 81: min=12 max=115  ████████████░░░░░░░░
# → Commande prête : --cc-map "80:chaos,81:bpm"
```

### Étape 2 — Lancer avec le mapping

```bash
uv run bang --mode phase2 --controller "Launchpad" --cc-map "80:chaos,81:bpm" --capture 4 --steps 128 --out live.mid
```

Les valeurs CC sont capturées pendant `--capture` secondes au lancement, puis normalisées (0.0–1.0) et injectées comme paramètres de génération.

**Contrôleurs testés :** Zoom R8, Novation Launchpad MK3, Arturia KeyLab Essential MK3, Arturia MicroFreak, SMC Pad.

---

## DNA et Steps — ce que vous voyez vs ce qui est exporté

L'interface affiche le **pattern DNA de base** de chaque voix — une cellule courte (typiquement 16 caractères = 1 mesure en double-croches). Ce n'est **pas** la séquence complète.

Le paramètre **Steps** définit combien de fois le moteur itère sur toutes les voix. BANG boucle chaque cellule DNA autant de fois que nécessaire pour atteindre ce total :

| Steps | Cellule 16 pas | Résultat dans le .mid |
|-------|----------------|-----------------------|
| 16 | `x---x---x---x---` | 1 boucle — 1 mesure |
| 64 | `x---x---x---x---` | 4 boucles — 4 mesures |
| 128 | `x---x---x---x---` | 8 boucles — 8 mesures |

La **polyrythmie** émerge du fait que chaque voix a une cellule de longueur différente. Exemple en mode `morph` :

- Kick : cellule de 16 pas
- Snare : cellule de 16 pas
- HiHat : cellule de 16 pas
- Basse : cellule de **5 pas**

Sur 64 steps, la basse boucle 12 fois (+ 4 pas) pendant que le kick boucle 4 fois exactement. Le motif ne se répète jamais à l'identique — c'est intentionnel.

> Ce que l'interface affiche = la cellule de base.  
> Ce que le fichier .mid contient = la cellule répétée et entrelacée sur N steps.

---

## Modes de génération

| Mode | Description |
|------|-------------|
| `morph` | Morphing entre deux patterns DNA fixes, mutation proportionnelle au chaos |
| `random` | DNA entièrement aléatoire à chaque génération |
| `weather` | DNA dérivé de la température et du vent (densité, ratchets) |
| `markov` | Voix mélodique pilotée par chaîne de Markov + drone CC74 |
| `phase2` | Markov + kick polyrhythmique + drone CC91 modulé météo |

---

## Entropie et seeds

Chaque export génère une graine SHA-256 composée de :
- `os.urandom(16)` — entropie système
- `time.time_ns()` — horloge nanoseconde
- Fragment de clé SSH locale
- Données météo si disponibles

La graine est embedée dans le fichier MIDI (`MetaMessage text`) et loggée dans `bang_sessions.jsonl`. Pour reproduire exactement une session :

```bash
uv run bang --seed 77e207b02c0e0801... --mode phase2
```

L'option `--temporal` ajoute `time_ns() % 1000` comme jitter par pas — **non-reproductible par définition**, même avec `--seed`.

---

## Structure du projet

```
bang/
├── bang_engine.py     # Moteur central (DNA, Markov, export MIDI, météo, seeds)
├── cli.py             # Interface CLI + MIDI controller
├── tui.py             # Interface TUI Textual
├── web.py             # Interface Web FastAPI+HTMX
├── templates/
│   ├── index.html
│   ├── _voices.html
│   ├── _log_entry.html
│   └── _weather.html
├── exports/           # Fichiers .mid générés
├── bang_sessions.jsonl  # Log de toutes les sessions
└── pyproject.toml
```

---

## Licence

Projet réalisé dans le cadre du méta-univers **Robōtariis**.
