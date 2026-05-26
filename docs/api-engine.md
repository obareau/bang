# BANG! — API BangEngine

> Référence de l'API Python pour utiliser BangEngine en dehors de l'interface web.

## Import

```python
from bang_engine import (
    BangEngine,
    dark_chain, bass_chain,
    build_markov_chain,
    morph_dna, mutate_dna, random_dna,
    weather_dna, weather_cc_breakpoints, fetch_weather,
    generate_seed,
    SCALE_INTERVALS,
)
```

---

## BangEngine

### Constructeur

```python
engine = BangEngine(
    bpm=124,
    ticks_per_step=120,  # durée d'un step en ticks MIDI (480 ticks = 1 beat)
    vel_floor=0,         # velocity minimale après mapping
    vel_ceiling=127,     # velocity maximale après mapping
    vel_curve=1.0,       # courbe de dynamique (< 1 compression, > 1 expansion)
)
```

**Relation ticks_per_step / temps** : avec `ticks_per_beat=480` (standard BANG!) et `ticks_per_step=120`, un step = 1/4 de beat = une double croche. Pour des noires, utiliser `ticks_per_step=480`.

### Ajouter des voix

```python
# Voix rythmique — note fixe, DNA classique
engine.add_voice(note=36, dna="x---x---x---x---", channel=9)

# Voix rythmique — polyrythmie dynamique (liste de patterns)
engine.add_voice(42, ["x-x-x-x-", "x-x-x-x-x-x-x-x-"])

# Voix mélodique — rythme DNA, hauteur Markov
engine.add_markov_voice(
    chain=dark_chain(),
    trigger_dna="x-?-░",
    velocity=95,
    channel=0,
)

# Voix Babka
engine.add_babka_voice(note=38, pattern="x(3,8)", channel=9)

# Automation CC
engine.add_cc_drone(
    control=74,      # CC MIDI (74 = filtre cutoff)
    channel=0,
    breakpoints=[20, 100, 20],   # sweep filtre
)
```

Toutes les méthodes `add_*` retournent `self` (chaînable).

### Exporter

```python
filename = engine.export_midi(
    num_steps=64,
    filename="output.mid",
    seed=None,             # None = auto-généré, str = reproductible
    weather=None,          # dict {"temperature": float, "wind_speed": float}
    temporal_jitter=False, # ajoute entropie time_ns à chaque note jittée
    swing=0.0,             # 0.0–1.0 (shuffle sur steps impairs)
    plocks=None,           # P-locks per-step par voix
    vel_humanize=0,        # ±N velocity aléatoire par note
    densities=None,        # [float, ...] facteur de densité par voix
    voice_chords=None,     # ["mono"|"power"|"minor"|..., ...] accord par voix Markov
    microtiming=1.0,       # 1.0 = grille, 0.0 = jitter max ±12%
)
# → retourne le chemin absolu du fichier
```

**Types d'accord disponibles** (pour `voice_chords`, sur voix Markov uniquement) :

| Clé | Intervalles |
|-----|-------------|
| `mono` | Monophonique |
| `power` | +7 (quinte) |
| `minor` | +3, +7 |
| `major` | +4, +7 |
| `sus2` | +2, +7 |
| `sus4` | +5, +7 |
| `m7` | +3, +7, +10 |
| `M7` | +4, +7, +11 |
| `dom7` | +4, +7, +10 |
| `dim` | +3, +6 |
| `aug` | +4, +8 |

### Sauvegarder / charger une session

```python
engine.save_session("session.npy")   # sauvegarde les patterns drum en numpy
engine.load_session("session.npy")   # charge et ajoute les voix
```

---

## Chaînes de Markov

### Prédéfinies

```python
chain = dark_chain()    # pentatonique mineure grave, A1–G2
chain = bass_chain()    # Am pentatonique 2 octaves, A1–C3
```

### Algorithmique

```python
chain = build_markov_chain(
    root_note=36,                       # fondamentale (MIDI)
    intervals=SCALE_INTERVALS["minor"], # liste d'intervalles
    num_octaves=1,
)
```

`SCALE_INTERVALS` disponibles : `penta_min`, `penta_maj`, `minor`, `dorian`, `phrygian`, `major`, `mixo`, `lydian`.

### API MarkovChain

```python
chain.generate(length=32, start=36)   # génère une séquence
chain.next_note(current=36)           # une note suivante
```

### Chaîne personnalisée

```python
from bang_engine import MarkovChain

chain = MarkovChain(
    notes=[36, 38, 40, 43, 45],
    transitions={
        36: {36: 0.2, 38: 0.4, 40: 0.3, 43: 0.1, 45: 0.0},
        # ... une entrée par note
    }
)
# Les poids sont normalisés automatiquement (n'ont pas besoin de sommer à 1.0)
```

---

## Helpers DNA

```python
dna = random_dna(length=16)
dna = morph_dna(p1="x---x---", p2="x---?---", mutation_rate=0.2)
dna = mutate_dna("x---x-x-", intensity=0.3)
```

---

## Météo

```python
weather = fetch_weather(timeout=5)
# → {"temperature": 12.5, "wind_speed": 23.0} ou None si hors-ligne

dna = weather_dna(weather, length=16)
bps = weather_cc_breakpoints(weather, num_points=5)
```

---

## Seed

```python
seed = generate_seed(weather=weather)   # SHA-256, 64 chars hex
# Passer seed à export_midi() pour reproductibilité
```

---

## Exemple complet

```python
from bang_engine import (
    BangEngine, dark_chain, build_markov_chain,
    morph_dna, mutate_dna, fetch_weather,
    generate_seed, SCALE_INTERVALS
)

weather = fetch_weather()
seed    = generate_seed(weather=weather)

engine = BangEngine(bpm=110, ticks_per_step=120)

# Batterie
kick = morph_dna("x---x---x---x---", "x---?---x↺--░---", mutation_rate=0.4)
engine.add_voice(36, mutate_dna(kick, 0.15), channel=9)
engine.add_voice(38, "----x-------x---", channel=9)
engine.add_voice(42, ["x-x-x-x-x-x-x-x", "x-x-x-x-x--x--x-"], channel=9)

# Ligne de basse Markov
chain = build_markov_chain(root_note=33, intervals=SCALE_INTERVALS["penta_min"])
engine.add_markov_voice(chain, trigger_dna="x-?-░", velocity=90, channel=0)

# Babka perc
engine.add_babka_voice(48, "<x(3,8) ?(2,8)>", channel=9)

# Automation filtre
engine.add_cc_drone(control=74, breakpoints=[20, 90, 40, 100, 20])

engine.export_midi(
    num_steps=64,
    filename="session.mid",
    seed=seed,
    weather=weather,
    swing=0.15,
    vel_humanize=8,
    microtiming=0.6,
)
```
