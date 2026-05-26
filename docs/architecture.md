# BANG! — Architecture

## Vue d'ensemble

```
bang-proto/
└── bang/                   # Package principal (service systemd)
    ├── web.py              # Serveur FastAPI + logique métier UI
    ├── bang_engine.py      # BangEngine — moteur de génération MIDI
    ├── babka.py            # Parser syntaxe Babka
    ├── cli.py              # Interface CLI (argparse + rtmidi physique)
    ├── tui.py              # Interface TUI (Textual)
    └── templates/
        ├── index.html      # UI principale HTMX (33KB+)
        ├── _pianoroll.html # Piano-roll SVG
        └── _voices.html    # Liste des voix
```

## Flux de données

```
Formulaire HTMX
      │
      ▼
_read_form()          → valide et normalise les paramètres
      │
      ▼
_build_voices(p)      → sélectionne le mode, génère les patterns DNA/Babka
      │
      ▼
_generate_plocks()    → P-locks CC pour les modes hardware
      │
      ▼
_assemble_engine(p)   → construit BangEngine, ajoute les voix et CC drones
      │
      ▼
engine.export_midi()  → MIDI Type 1 sur disque
      │
      ├─→ _state        → persistance en mémoire + bang_state.json
      ├─→ /pattern       → events JSON pour le player JS
      └─→ pianoroll SVG  → rendu HTMX inline
```

## Composants

### BangEngine (`bang_engine.py`)

Moteur multi-voix. Accumule des voix de trois types :

| Type | Méthode | Hauteur | Rythme |
|------|---------|---------|--------|
| `drum` | `add_voice()` | Note fixe | DNA string ou liste |
| `markov` | `add_markov_voice()` | MarkovChain | DNA trigger |
| `babka` | `add_babka_voice()` | Note fixe | Pattern Babka |
| `cc` | `add_cc_drone()` | — | Interpolation breakpoints |

`export_midi()` est la seule méthode de sortie. Elle :
1. Seed le RNG (déterministe)
2. Résout chaque voix step par step
3. Accumule des tuples `(abs_tick, priority, type, channel, param, value)`
4. Trie par tick + priorité, convertit en deltas MIDI
5. Écrit un fichier MIDI Type 1 et log dans `bang_sessions.jsonl`

### Parser Babka (`babka.py`)

Descente récursive. Produit une liste de `BabkaStep` avec `duration` flottante. Le BangEngine boucle les cycles Babka via `cursor_tick` jusqu'à `num_steps × ticks_per_step`.

Pour le player web, les events Babka ont des `step` flottants (ex : `2.5` = milieu du step 2). Le JS utilise `Math.floor(e.step)` pour le dispatch et `(e.step % 1) × stepDurMs` comme offset sub-step.

### Serveur web (`web.py`)

FastAPI avec HTMX. Toutes les interactions UI retournent des fragments HTML partiels (pas de rechargement de page).

Points d'entrée principaux :

| Route | Méthode | Description |
|-------|---------|-------------|
| `GET /` | — | Page principale |
| `POST /generate` | form | Génère + retourne pianoroll + voix |
| `GET /pattern` | query | Events JSON pour le player JS |
| `POST /vary` | form | Mutation légère du pattern courant |
| `POST /export` | form | Téléchargement du .mid |
| `GET /pianoroll` | query | SVG piano-roll seul |
| `WS /midi-ws` | websocket | Stream MIDI temps réel vers le player |
| `POST /osc/*` | form | Contrôle OSC |

### État global `_state`

```python
_state = {
    "voices":       [(note, dna, vtype), ...],
    "engine":       BangEngine,
    "last_p":       dict,           # derniers paramètres generate
    "plocks":       list,           # P-locks par voix (volca_drum)
    "voice_thin":   {name: factor}, # thinning 1/2/4
    "max_poly":     int,
    "weather":      dict | None,
    "last_seed":    str,
    "voice_swing":  {name: float},
    "seq":          {...},          # séquenceur de presets (8 slots)
    "lfo":          {...},          # LFO par voix
    "ab":           {...},          # morphing A→B
}
```

L'état est persisté dans `bang_state.json` via un autosave middleware à chaque requête modifiante.

## Couches de sortie MIDI

BANG! peut envoyer du MIDI via trois canaux simultanés :

| Canal | Mécanisme | Contexte |
|-------|-----------|----------|
| Export `.mid` | `mido.MidiFile` | Hors-ligne, drag vers DAW |
| MIDI serveur | `python-rtmidi` | Sortie MIDI physique depuis n'importe quel navigateur |
| Web MIDI | WebMIDI API | Chrome/Edge uniquement, nécessite HTTPS |

Le player JS reçoit les events via `/pattern` (JSON) et les dispatche via MIDI ou Web Audio selon la configuration.

## OSC

Émission et réception UDP sur ports configurables. Handlers :

| Adresse OSC | Action |
|-------------|--------|
| `/bang/generate` | Déclenche une génération |
| `/bang/vary` | Variation légère |
| `/bang/param/<name>` | Modifie un paramètre |
| `/bang/density/<voice>` | Ajuste la densité d'une voix |
| `/bang/lock/<voice>` | Verrouille/déverrouille une voix |

## Persistance

| Fichier | Contenu |
|---------|---------|
| `bang_state.json` | État complet de la session (voix, paramètres, SEQ, LFO) |
| `bang_sessions.jsonl` | Log de chaque export MIDI (seed, BPM, voix, météo) |
| `bang_presets.json` | Presets utilisateur |
| `bang_favorites.json` | Seeds favorites |
| `bang_ksp_presets.json` | Presets KeyStep Pro |
| `bang_song.json` | Paramètres de la chanson courante |
| `dna_precieux.npy` | Sessions sauvegardées (matrices numpy) |
