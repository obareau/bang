# BANG! — Référence syntaxe DNA & Babka

## Syntaxe DNA

Le DNA BANG! est une séquence de caractères où chaque symbole encode directement les paramètres d'un step rhythmique.

### Table des symboles

| Symbole | Nom | trigger | velocity | prob | ratchet | jitter |
|---------|-----|---------|----------|------|---------|--------|
| `x` | Hit fort | oui | 105 | 100% | 1 | 0 |
| `-` | Silence | non | — | 0% | — | — |
| `?` | Hit probabiliste | oui | 90 | 50% | 1 | 0 |
| `↺` | Ratchet ×3 | oui | 110 | 100% | 3 | 0 |
| `░` | Hit avec jitter | oui | 85 | 100% | 1 | ±25 ticks |

### Paramètres

- **trigger** : si 0, le step est toujours silencieux
- **velocity** : vélocité MIDI avant mapping (0–127)
- **prob** : probabilité de déclenchement — `?` se joue une fois sur deux
- **ratchet** : nombre de sous-notes dans le step. `↺` = 3 notes sur la durée d'un step
- **jitter** : décalage aléatoire de l'onset en ticks MIDI (±N)

### Exemples de patterns

```
x---x---x---x---    four-on-the-floor (kick)
----x-------x---    backbeat (snare)
x-x-x-x-x-x-x-x    doubles croches (hi-hat)
x---x-x-?---x---    syncope avec probabilisme
x-?-░               5 steps : hit, silence, probabiliste, silence, jitter
↺---x---↺---x---   ratchets sur les 1 et 3
```

### Polyrythmie par liste

Passer une liste de patterns crée un séquenceur de patterns : chaque cycle consomme le pattern suivant dans la liste.

```python
engine.add_voice(42, ["x-x-x-x-", "x---x---x---"])
# Cycle 1 : pattern 8 steps, Cycle 2 : pattern 12 steps → déphasage
```

---

## Syntaxe Babka

Babka est un sur-ensemble de DNA. Tout pattern DNA pur est un pattern Babka valide.

### Subdivision `[a b c]`

Compress plusieurs atomes dans la durée d'un step. Les durées sont divisées proportionnellement à leur durée relative dans le groupe.

```
[x x]       → 2 hits dans 1 step, durée 0.5 chacun
[x x x]     → 3 hits dans 1 step, durée 0.333 chacun
[x - x]     → hit, silence, hit — durée 0.333 chacun
[x(2,4)]    → euclidien 2/4 compressé dans 1 step
```

Les groupes peuvent être imbriqués :

```
[[x x] x]   → (hit, hit) dans la première moitié + hit dans la seconde
```

### Alternance `<a b c>`

Sélectionne un pattern différent à chaque cycle. Séparation par espaces.

```
<x- -x>         cycle 0: "x-", cycle 1: "-x", cycle 2: "x-", ...
<x---x--- ?-?-> cycle pair: 4-on-floor, cycle impair: probabiliste
<[x x]- x-->    cycle 0: subdivision + silence, cycle 1: hit + 2 silences
```

Les alternatives peuvent contenir des `[...]` et d'autres `<...>`.

### Euclidien inline `x(n,k)`

Génère un pattern euclidien de `n` triggers sur `k` steps. Remplace l'atome par le résultat développé — le pattern occupe `k` steps dans la séquence.

```
x(3,8)   → x--x--x-    (3 triggers sur 8 steps)
x(2,5)   → x--x-        (2 triggers sur 5 steps)
?(3,8)   → ?--?--?-     (same mais probabiliste)
↺(2,8)  → ↺------↺-   (ratchet euclidien)
```

L'algorithme de Bresenham garantit le placement le plus uniformément espacé possible.

### Euclidien overlay `[x(n,k)]`

Euclidien compressé dans la durée d'un step (combinaison subdivision + euclidien).

```
[x(3,4)]   → hit, silence, hit, hit dans 1 step (durée 0.25 chacun)
[x(2,4)]   → hit, silence, hit, silence dans 1 step
```

### Combinaisons

```
x-[x x]-?              DNA + subdivision + probabiliste
<x---x--- x-[x-]x-->   alternance avec subdivision imbriquée
↺-[x ?]-░(2,4)        ratchet + groupe + euclidien overlay
x(3,8)-<x- [x x]>     euclidien inline + alternance
```

### Durées flottantes

Contrairement au DNA classique (steps entiers), Babka produit des durées flottantes. Un step `[x x x]` dure exactement 1 step de base mais contient 3 onsets à `t=0`, `t=1/3` et `t=2/3`. Le player JS utilise ces offsets sub-step pour un rendu précis.

---

## Notation musicale → DNA

Quelques équivalences entre notation musicale et DNA (pattern 16 steps = 1 mesure 4/4 en doubles croches) :

| Rythme | DNA |
|--------|-----|
| Noire sur chaque temps | `x---x---x---x---` |
| Backbeat (2 et 4) | `----x-------x---` |
| Triolet de noires | `x----x----x-----` (15 steps) |
| Charleston (1 et 2e double croche de chaque temps) | `x-x-x-x-x-x-x-x-` |
| Clave 3-2 | `x--x--x---x-x---` |
| Euclidien 3/8 (Tresillo) | `x(3,8)` = `x--x--x-` |
| Euclidien 5/8 (Cinquillo) | `x(5,8)` = `x-xx-xx-` |
| Euclidien 4/12 (Bossa) | `x(4,12)` |
