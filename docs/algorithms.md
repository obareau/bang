# BANG! — Documentation des algorithmes

> Ce document décrit les algorithmes internes de BANG! tels qu'implémentés dans `bang_engine.py` et `babka.py`.

---

## 1. Syntaxe DNA

Le cœur de BANG! est un mini-langage de séquençage par caractères. Chaque symbole encode un vecteur de 5 paramètres :

| Symbole | trigger | vel | prob | ratchet | jitter (ticks) |
|---------|---------|-----|------|---------|----------------|
| `x`     | 1       | 105 | 1.0  | 1       | 0              |
| `-`     | 0       | 0   | 0.0  | 1       | 0              |
| `?`     | 1       | 90  | 0.5  | 1       | 0              |
| `↺`    | 1       | 110 | 1.0  | 3       | 0              |
| `░`     | 1       | 85  | 1.0  | 1       | 25             |

À la lecture, chaque step résout `trigger && random() < prob` — `?` est stochastique (50%), `x` est déterministe. Le **ratchet** divise la durée du step en `n` sous-notes égales. Le **jitter** ajoute un décalage aléatoire `±N ticks` à l'onset de la note.

La compilation DNA → tableau numpy se fait dans `compile_dna()`. Chaque ligne du tableau est `[trigger, velocity, prob, ratchet, jitter]`.

---

## 2. Morphing et mutation DNA

### `morph_dna(p1, p2, mutation_rate)`

Croisement génétique simple à point de coupure unique : les `len//2` premiers caractères viennent de `p1`, la seconde moitié de `p2`. Ensuite chaque position est remplacée par un symbole DNA aléatoire avec probabilité `mutation_rate`.

Analogue à un croisement chromosomique avec erreur de réplication contrôlée.

### `mutate_dna(dna, intensity)`

Corruption progressive : pour chaque caractère, avec probabilité `intensity`, le symbole glisse d'un cran vers un symbole adjacent dans le tableau ordonné `['x', '-', '?', '↺', '░']` (indice ±1). C'est une **marche aléatoire locale** — les mutations restent cohérentes avec l'alphabet DNA, aucun symbole ne surgit ex nihilo.

---

## 3. Chaînes de Markov mélodiques

### Principe

`MarkovChain` stocke une matrice de transition `note → {next_note: poids}`. À chaque step, si le trigger DNA est actif, la note suivante est tirée par `random.choices()` pondéré par la ligne de la note courante.

### Chaînes prédéfinies

**`dark_chain()`** — pentatonique mineure grave (A1–G2, MIDI 33–43). Gravité forte vers A1 (auto-transition 0.40). Conçue pour les lignes de basse sombres du cadre Dark Umbrae.

```
Notes : A1=33, C2=36, D2=38, E2=40, G2=43
        ↑ forte attraction gravitationnelle vers le bas
```

**`bass_chain()`** — Am pentatonique sur 2 octaves (A1–C3, MIDI 33–48). Favorise les sauts de quarte/quinte et le retour à la fondamentale, orienté groove.

### Construction algorithmique : `build_markov_chain(root, intervals, num_octaves)`

Génère une matrice de transition pour n'importe quelle gamme et fondamentale :

1. Construit les notes disponibles à partir des intervalles et du nombre d'octaves (clampées à 21–108)
2. Pour chaque paire source→destination, poids de base par **décroissance exponentielle sur la distance en degrés** :
   ```python
   w = exp(-dist × 0.45)
   ```
3. Bonus ×1.5 sur la tonique, ×1.2 sur la quinte — gravité musicale
4. Pénalité ×0.35 sur la répétition (même note consécutive)
5. Normalisation par ligne (somme = 1.0)

Les gammes disponibles :

| Clé | Intervalles | Nom |
|-----|-------------|-----|
| `penta_min` | 0,3,5,7,10 | Pentatonique mineure |
| `penta_maj` | 0,2,4,7,9 | Pentatonique majeure |
| `minor` | 0,2,3,5,7,8,10 | Mineur naturel (éolien) |
| `dorian` | 0,2,3,5,7,9,10 | Dorien |
| `phrygian` | 0,1,3,5,7,8,10 | Phrygien |
| `major` | 0,2,4,5,7,9,11 | Majeur (ionien) |
| `mixo` | 0,2,4,5,7,9,10 | Mixolydien |
| `lydian` | 0,2,4,6,7,9,11 | Lydien |

---

## 4. Syntaxe Babka

Babka est un sur-ensemble de DNA qui emprunte la mini-notation de Strudel/TidalCycles. Le parser est une **descente récursive** (`_Parser` dans `babka.py`).

### Structure de données

```python
@dataclass
class BabkaStep:
    trigger:  bool
    velocity: int
    prob:     float
    ratchet:  int
    jitter:   int
    duration: float  # fraction d'un step de base (1.0 = plein)
```

### Subdivision `[a b c]`

Les atomes à l'intérieur partagent la durée d'un step parent. Chaque sous-step reçoit `duration / total_durée_intérieure`. Ex : `[x x x]` → trois hits de durée 1/3 chacun. Fonctionne récursivement — on peut imbriquer des `[...]` dans d'autres `[...]`.

### Alternance `<a b c>`

À chaque cycle, l'alternative sélectionnée est `alternatives[cycle % n]`. Le contenu sélectionné est re-parsé récursivement dans un nouveau `_Parser`. Les alternatives sont séparées par des espaces, et peuvent contenir elles-mêmes des `[...]` ou d'autres `<...>`.

### Euclidien (algorithme de Bresenham) `x(n,k)`

Distribue `n` triggers sur `k` steps avec un espacement maximal :

```python
[atom if (i * n % k) < n else '-' for i in range(k)]
```

C'est l'algorithme de Bjorklund/Euclidean rhythms. `x(3,8)` produit `x--x--x-` — le pattern le plus uniformément espacé possible. En mode **overlay** `[x(n,k)]`, les `k` steps sont compressés dans la durée d'un step via subdivision.

### Exemples

| Pattern | Description |
|---------|-------------|
| `x-[x x]-?` | DNA pur + subdivision |
| `x(3,8)` | Euclidien 3 triggers sur 8 steps |
| `<x-x- ?-?->` | Alternance cycle pair/impair |
| `↺(2,8)` | Ratchet euclidien |
| `[x(3,4)]` | Euclidien overlay (4 steps → durée 1 step) |

---

## 5. Automation CC — Interpolation linéaire par breakpoints

`add_cc_drone()` envoie un message CC à chaque step avec valeur interpolée entre les breakpoints fournis :

```python
t    = i / (num_steps - 1) * (len(bps) - 1)
idx  = int(t)
frac = t - idx
val  = bps[idx] * (1 - frac) + bps[idx+1] * frac   # lerp
```

Les breakpoints sont répartis uniformément sur la durée totale. Ex : `[20, 100, 20]` → sweep filtre monté-descendu. Un seul breakpoint → valeur CC constante.

---

## 6. P-locks (Parameter Locks)

Inspiré du séquenceur Elektron : chaque step peut avoir une valeur CC indépendante. Trois styles de génération algorithmique :

| Style | Algorithme |
|-------|------------|
| `sweep` | `55 + 50 × sin(2πt + phase)` — sinus lent + jitter proportionnel au chaos |
| `texture` | `38 + 52 × |sin(4πt + phase)|` — double fréquence, toujours positif |
| `spike` | Distribution bimodale : 60–127 ou 0–35 selon `random() < chaos × 0.55` |

Un taux de densité détermine la probabilité qu'un step ait effectivement un P-lock (vs `None`). Les P-locks sont émis sur `i × ticks_per_step` indépendamment du trigger note — le CC change même si la note ne sonne pas.

---

## 7. Mode Weather (météo → DNA)

Récupère température et vitesse du vent à Scaër, Bretagne (48.0253°N, -3.6854°E) via l'API Open-Meteo, sans clé.

### `weather_dna(weather, length)`

```
density     = clamp((temp + 10) / 40, 0.15, 0.85)
wind_factor = min(1.0, wind / 60)
```

Pour chaque step :
- Si `random() > density` → silence `-`
- Sinon, tirage parmi `↺`, `░`, `?`, `x` avec poids proportionnels à `wind_factor`

**Froid → sparse, chaud → dense. Vent fort → ratchets et jitter.**

### `weather_cc_breakpoints(weather, num_points)`

```python
base  = clamp((temp + 10) / 40 × 110, 10, 100)   # cutoff MIDI
depth = min(60, wind / 60 × 80)                   # amplitude modulation
val_i = base + sin(i / (n-1) × π) × depth
```

Courbe sinusoïdale sur la durée de la séquence. Froid = filtre fermé, chaud = filtre ouvert. Vent fort = oscillation ample.

---

## 8. Seed déterministe et reproductibilité

### `generate_seed(weather)`

Entropie composée :
- `os.urandom(16)` — 128 bits CSPRNG système
- `time.time_ns()` — timestamp nanoseconde
- 64 octets du milieu de la clé SSH locale (ed25519 ou rsa)
- Données météo encodées si disponibles

Le tout haché en SHA-256 → 64 chars hex.

À l'export, `random.seed()` et `np.random.seed()` sont initialisés avec les 16 premiers hex → **reproductibilité totale à seed identique**.

### Temporal jitter

Option `temporal_jitter=True` : pour chaque note avec `jitter > 0`, un offset supplémentaire basé sur `time_ns() % 1000` est ajouté. Casse la reproductibilité de façon contrôlée — chaque performance est unique même à seed identique.

---

## 9. Humanisation

### Velocity mapping `vel_map(vel, floor, ceiling, curve)`

```python
t   = (vel / 127) ** curve
out = floor + t × (ceiling - floor)
```

- `curve < 1` → compression dynamique (velocities rapprochées, style hip-hop)
- `curve = 1` → rescaling linéaire
- `curve > 1` → expansion dynamique (contrastes exagérés, style classique)

### Vel humanize

`random.randint(-n, n)` ajouté à chaque velocity avant le mapping. Simule l'imperfection d'un interprète humain.

### Micro-timing

Jitter d'onset `±12% × ticks_per_step`, pondéré par `(1.0 - microtiming)` :
- `microtiming = 1.0` → grille parfaite, pas de micro-timing
- `microtiming = 0.0` → jitter maximal ±12%

### Swing

Décalage `+swing × ticks_per_step × 0.5` sur les steps impairs (index 1, 3, 5…). Swing à 0.0 = grille, 1.0 = shuffle maximal (triplet). Appliqué à l'export MIDI et au player JS.

---

## 10. Polyrythmie dynamique

Quand une voix reçoit une **liste de patterns DNA** au lieu d'une string, le moteur avance au pattern suivant à chaque épuisement du pattern courant :

```python
pattern_idx = (pattern_idx + 1) % len(patterns)
```

Des patterns de longueurs différentes produisent des cycles qui se décalent progressivement — polyrythmie par déphasage de grille. Ex : `["x-x-", "x--x--x-"]` (4 vs 8 steps) crée un cycle de LCM(4,8) = 8 steps avant répétition.

---

## 11. Assemblage MIDI multi-piste (Type 1)

L'export produit un fichier **MIDI Type 1** (multi-piste) avec `ticks_per_beat = 480` :

- **Track 0** : tempo + métadonnées (seed encodée dans un champ `BANG_SEED:...`)
- **Une track par voix note** (drum, markov, babka) nommée `drum-36`, `markov-ch10`, etc.
- **Une track par drone CC** nommée `CC74`, `CC91`, etc.

Les événements sont accumulés sous forme de tuples `(abs_tick, priority, type, channel, param, value)`, triés par tick absolu, puis convertis en deltas MIDI en une passe. Le `priority` (0 ou 1) assure que les `note_off` s'écrivent avant les `note_on` au même tick.
