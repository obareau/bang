# BANG! — Modes de génération

> Ce document décrit chaque mode de génération disponible dans BANG!, sa logique algorithmique et son usage musical.

Le paramètre **chaos** (0.0–1.0) est transversal à tous les modes — il contrôle l'intensité des mutations, la densité des patterns et la complexité des structures générées.

---

## Modes batterie / percussions

### Random
Génération pure : `random.choices(DNA_SYMBOLS, k=16)` sur chaque voix. Aucune contrainte musicale. Utile pour l'exploration ou comme point de départ.

4 voix : kick (36), snare (38), hi-hat (42), clap (48).

### Morph
Croisement génétique entre deux patterns kick archétypaux :
- `p1 = "x---x---x---x---"` (four-on-the-floor)
- `p2 = "x---?---x↺--░---"` (avec probabilisme et ratchet)

Le morph est effectué avec `mutation_rate = chaos × 0.5`, suivi d'une `mutate_dna` supplémentaire `intensity = chaos × 0.6`. Chaos faible → kick proche de la four-on-the-floor. Chaos élevé → ruptures rythmiques, ratchets, silences.

Le snare et le hi-hat sont fixes (`----x-------x---` et `x-x-x-x-x-x-x-x`).

### Noise ◼
8 voix avec longueurs asymétriques (5, 7, 9, 11, 13 steps) — les décalages de cycle créent de la polymétrie naturelle.

| Note | Longueur | Usage |
|------|----------|-------|
| 36 (kick) | 11 | Basse |
| 38 (snare) | 7 | Médium |
| 42 (hi-hat) | 13 | Haute densité |
| 48 | 5 | Court, répétitif |
| 40, 43, 24, 33 | 9, 11, 7, 13 | Texture |

Le hi-hat a un profil de poids biaisé vers `-` (silences fréquents, pas de ratchet/jitter). Les autres voix ont un profil modulé par le chaos : `[2 + chaos×3, max(0.1, 2-chaos×1.5), 1+chaos, chaos×1.5, chaos]` pour `[x, -, ?, ↺, ░]`.

### Ambient ◌
3 voix ultra-sparse (kick 36, sub 24, bass 33) avec poids DNA fortement biaisés vers le silence :
```
[x=0.3+chaos×0.3, -=9.0, ?=0.5+chaos×0.2, ↺=0, ░=0]
```
Mutation très faible (`intensity = chaos × 0.05`). Conçu pour des textures de fond longues et aléatoires.

---

## Modes mélodiques

### Markov
Batterie DNA (kick muté, snare, hi-hat fixes) + une voix mélodique Markov.

La voix Markov utilise `dark_chain()` (pentatonique mineure grave A1–G2) avec le pattern trigger `"x-?-░"`. Le rythme est défini par le DNA, la hauteur par la chaîne de Markov. La gamme et la fondamentale sont configurables via le formulaire (12 toniques × 8 modes).

### Phase 2
Markov + automation CC drone :
- CC 74 (filtre cutoff) : sweep `[20, cc_peak, 20]` où `cc_peak = 20 + cc_depth × 100`
- CC 91 (réverb) : breakpoints modulés par la météo si disponible

### Bassline
2 voix Markov sur la même note racine (ligne principale + contre-rythme) + CC drone filtre. Les patterns trigger varient selon le chaos :

| Chaos | Style |
|-------|-------|
| < 0.30 | `"x---x---"` / `"x-------x-------"` — régulier |
| 0.30–0.55 | Mutés légèrement — syncopes douces |
| > 0.55 | Mutés fortement — groove tendu |

Si `chaos > 0.35`, un CC5 (portamento) est ajouté avec pic `= chaos × 60`.

---

## Modes matériel dédié

### Volca Drum ★
6 voix sur canaux MIDI 1–6 (index 0–5). Note = 60/C3 indifféremment — seul le canal compte pour le Volca Drum. DNA 16 steps max.

| Part | Rôle | Profil DNA |
|------|------|------------|
| P1 Punch | Kick-ish | Four-on-the-floor |
| P2 Snap | Snare-ish | 2 et 4 |
| P3 HH | Closed hi-hat | Doubles croches |
| P4 OH | Open/cymbal | Sparse probabiliste |
| P5 Perc | Synth perc | Jitter et ratchet |
| P6 Acc | Layer/accent | Contre-rythme |

Chaque part : `morph_dna(base_a, base_b, chaos×0.4)` + `mutate_dna(chaos×0.3)`.

P-locks CC générés algorithmiquement par voix (sweep/texture/spike selon le profil du part).

### Volca Kick
1 voix (note 60/C3). 3 paires de patterns archétypaux (four-on-the-floor, syncopé, swing). La paire est sélectionnée par `int(chaos × 3) % 3`, puis morphée et mutée.

### Volca FM
3 voix polyphoniques (grave C1=36, quinte G1=43, octave C2=48) sur un canal unique. Morph + mutate avec taux modéré.

### MicroFreak
3 voix paraphoniques (lead A2=45, contre E2=40, pédale C2=36) sur canal 1. Le lead est plus dense, la pédale ultra-sparse. Morph chaos×0.45 + mutate chaos×0.30.

### KeyStep Pro
3 drums sur canal 10 (kick, snare, hi-hat) + 4 pistes mélodiques Markov sur canaux 1–4 (lead, bass, chord, arp). Chaque piste mélodique a son propre pattern trigger muté et sa propre chaîne Markov issue de la gamme configurée.

---

## Mode Babka ⚗

3 niveaux sélectionnés par seuils de chaos :

| Chaos | Niveau | Caractéristiques |
|-------|--------|-----------------|
| < 0.4 | Simple | DNA pur + euclidien statique `x(3,8)` |
| 0.4–0.7 | Moyen | Alternances `<...>`, euclidien probabiliste `?(3,8)`, ratchet `↺(2,8)` |
| > 0.7 | Dense | Subdivisions imbriquées, euclidien dynamique `?(n,8)` avec `n = int(chaos×8)`, alternances complexes |

Le paramètre chaos influe aussi sur le nombre de triggers du snare euclidien (`n_snare = clamp(int(chaos×8), 2, 7)`).

---

## Weather (météo)

Chaque voix reçoit un pattern DNA généré par `weather_dna()` (voir [algorithms.md](algorithms.md#6-mode-weather-météo--dna)) puis muté par `mutate_dna(intensity=chaos×0.4)`. La densité et le type de symboles sont directement contrôlés par la température et le vent à Scaër.

---

## Polyrythmie (tous modes)

Via l'interface, chaque voix peut avoir un **cycle indépendant** (bouton `Ns`) qui détermine la longueur de son pattern. Des longueurs incommensurables (ex: 7 et 11) produisent des super-cycles de LCM(7,11)=77 steps avant répétition.
