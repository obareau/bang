# BANG! — Séquenceur MIDI Algorithmique

Générateur MIDI algorithmique pour le cadre **Robōtariis** (Dark Umbrae). Syntaxe DNA propriétaire + syntaxe Babka (fusion DNA + Strudel). Interface web FastAPI + HTMX, export MIDI, player Web MIDI temps réel.

## Stack

- Python 3.12+ / `uv` · FastAPI + uvicorn + HTMX + Jinja2
- `mido` (MIDI) · `numpy` (matrices DNA)
- Service systemd `bang.service` — port `7777`
- HTTPS via Caddy + cert auto-signé → `https://bang.lan`
- Web MIDI API (Chrome, nécessite HTTPS)

## Repo & service

```
Repo  : /home/olivier/DEV/bang-proto/bang/
Branch: dev/* pour les features, main = prod stable
```

**⚠️ Le service tourne depuis `bang-proto/bang/`, pas `bang-proto/`.**

```bash
sudo systemctl restart bang
sudo journalctl -u bang -f --no-pager
```

**Toujours créer un branch `dev/<feature>` avant de coder — ne jamais commit sur main directement.**

## Architecture fichiers

| Fichier | Rôle |
|---------|------|
| `web.py` | FastAPI — routes, state, pianoroll, player JSON |
| `bang_engine.py` | `BangEngine` — DNA, Markov, CC drone, export MIDI |
| `babka.py` | Parser syntaxe Babka (DNA + Strudel) |
| `cli.py` | Interface CLI (argparse + MIDI physique) |
| `tui.py` | Interface TUI (Textual) |
| `templates/index.html` | UI principale HTMX (33KB+) |
| `templates/_pianoroll.html` | Piano-roll SVG |
| `templates/_voices.html` | Liste voix |

## Commandes de dev

```bash
# Démarrer en dev (hot-reload)
uv run uvicorn web:app --reload --port 7777

# Tester le parser Babka
uv run python babka.py

# Tester l'engine
uv run python bang_engine.py

# Lancer les tests (si pytest ajouté)
uv run pytest
```

## Syntaxe DNA

| Sym | trigger | vel | prob | ratchet | jitter |
|-----|---------|-----|------|---------|--------|
| `x` | oui | 105 | 1.0 | 1 | 0 |
| `-` | non | 0 | 0.0 | 1 | 0 |
| `?` | oui | 90 | 0.5 | 1 | 0 |
| `↺` | oui | 110 | 1.0 | 3 | 0 |
| `░` | oui | 85 | 1.0 | 1 | 25 |

## Syntaxe Babka (DNA + Strudel)

Fusion DNA + mini-notation Strudel. DNA pur reste valide.

| Opérateur | Comportement |
|-----------|-------------|
| `[a b c]` | Subdivision : n atomes dans 1 step (durées divisées) |
| `<a b c>` | Alternance cycle par cycle (séparés par espaces) |
| `x(n,k)` | Euclidien inline → k steps durée 1.0 |
| `[x(n,k)]` | Euclidien overlay → k steps dans 1 step |

Exemples : `x-[x x]-?` · `x(3,8)` · `<x-x- ?-?->` · `↺(2,8)` · `<[x x]- x-->`

## Modes de génération

| Mode | Description |
|------|-------------|
| Morph | DNA morphé + mutation selon chaos |
| Random | Aléatoire pur |
| Weather | Densité/texture selon météo Scaër |
| Markov | Ligne mélodique via chaîne de Markov |
| Phase 2 | Markov + CC drone + polyrythmie |
| Noise ◼ | 8 voix cycles asymétriques, haute entropie |
| Ambient ◌ | 3 voix ultra-sparse |
| Babka ⚗ | Syntaxe Babka — 3 niveaux selon chaos |
| Volca Drum ★ | 6 parts sur canaux 1–6, P-locks CC |

## BangEngine API

```python
from bang_engine import BangEngine, dark_chain

e = BangEngine(bpm=120, ticks_per_step=120)

e.add_voice(36, "x---x---")              # voix DNA simple
e.add_voice(42, ["x-x-", "x--x"])       # polyrythmie dynamique
e.add_markov_voice(dark_chain(), "x-?-") # mélodie Markov
e.add_babka_voice(38, "x(3,8)")         # voix Babka
e.add_cc_drone(control=74, breakpoints=[20, 100, 20])

e.export_midi(num_steps=64, filename="out.mid")
```

## State web (`_state`)

```python
_state = {
    "voices":    [(note, dna, vtype), ...],   # vtype: drum/markov/babka/cc/vd0-5
    "engine":    BangEngine instance,
    "last_p":    dict params du dernier generate,
    "plocks":    list CC per-step (volca_drum),
    "voice_thin": {name: factor},             # thinning 1/2/4
    "max_poly":  int,
    "weather":   dict | None,
    "last_seed": str,
}
```

## /pattern endpoint (Web MIDI player)

Retourne les events pour le player JS. Les voix Babka ont des `step` flottants (ex: `2.5` = milieu du step 2). Le player JS utilise `Math.floor(e.step)` pour le dispatch et `(e.step % 1) * stepDurMs` comme offset sub-step.

## App desktop Qt6 (branche `qt6-native`)

Rebuild natif PySide6 de l'app (indépendant de `web.py`, mêmes fondations
via `pattern_lib.py` extrait du webapp). Génération, édition DNA interactive
(grille cliquable), lecture MIDI temps réel (port réel ou synthé intégré
FluidSynth), séquenceur 8 slots, song mode, presets, Ableton OSC, export
MIDI type 0/1.

**Pas d'export Strudel dans la version Qt6.** Tenté puis abandonné : la
syntaxe DNA/Babka (probabilités, ratchets, jitter) ne se traduit pas
proprement en mini-notation Strudel réelle — les patterns générés ne
jouaient pas (voix mélodiques sans synthé attaché, échantillons percussion
inventés sans garantie d'exister, opérateur `?` avec argument numérique
non-standard). Le webapp garde son `/export/strudel` tel quel (fonctionnalité
existante, non touchée). La seule filiation Strudel qui reste pertinente
côté Qt6 est historique : la syntaxe Babka (`babka.py`) s'est inspirée de la
mini-notation Strudel/TidalCycles pour ses opérateurs `[ ]` / `< >` / `(n,k)`.

## Préfixes de commit

`Feat:` · `Fix:` · `Refactor:` · `Chore:` · `Docs:`

<!-- argus:convention-session -->
## Session de travail — convention d'écosystème

**En ouvrant ce projet**, lire `ROADMAP.md` avant toute chose : il porte ce
qui reste à faire, ce qui est en cours, et — sous « Demandes externes
(Argus) » — ce que d'autres projets attendent d'ici. Commencer sans l'avoir lu
revient à redécouvrir ou refaire.

**Avant de finir**, le mettre à jour dans le même commit que le code :

- cocher `- [x]` ce qui est fait, y compris dans le bloc des demandes externes
  (cocher une demande suffit à la marquer résolue, Argus le voit au scan) ;
- ajouter ce qui a été découvert en chemin, même mal formulé — une ligne
  imprécise vaut mieux qu'un savoir perdu ;
- retirer ou requalifier ce qui n'a plus de sens.

Un roadmap qui ne suit pas le code ment deux fois : il fait croire qu'il reste
à faire ce qui est fait, et il perd ce qui a été appris. Toute la progression
mesurée par [Argus](http://argus.lan) en dépend.

⚠️ Le bloc entre `<!-- argus:begin -->` et `<!-- argus:end -->` du ROADMAP
appartient à Argus, qui le régénère depuis sa base. On y coche des cases, on
n'y écrit pas à la main.
<!-- argus:convention-session:end -->
