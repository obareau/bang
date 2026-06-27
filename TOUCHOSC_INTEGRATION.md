# TouchOSC Integration — BANG!

## Contexte

Ce document décrit comment générer un layout TouchOSC (`.tosc`) pour contrôler BANG! via OSC,
et les modifications à intégrer dans le code pour automatiser cette génération depuis l'app.

---

## Format .tosc — Ce qu'on a découvert par reverse engineering

### Structure du fichier

Un fichier `.tosc` est du **XML compressé en zlib brut** (pas gzip, pas ZIP).

```python
import zlib
data = zlib.compress(xml.encode('utf-8'))
open('controller.tosc', 'wb').write(data)
```

Pour décoder un `.tosc` existant :

```python
import zlib
xml = zlib.decompress(open('fichier.tosc', 'rb').read()).decode('utf-8')
print(xml)
```

### Élément racine

```xml
<?xml version='1.0' encoding='UTF-8'?>
<lexml version='5'>
  <node ID='...' type='GROUP'>...</node>
</lexml>
```

> **Attention** : l'élément racine est `<lexml version='5'>`, pas `<root>` ni `<TouchOSC>`.

### Types de propriétés

| Type | Usage | Exemple |
|------|-------|---------|
| `b` | booléen | `<property type='b'><key><![CDATA[visible]]></key><value>1</value></property>` |
| `i` | entier | `<property type='i'><key><![CDATA[orientation]]></key><value>0</value></property>` |
| `f` | float | `<property type='f'><key><![CDATA[cornerRadius]]></key><value>3</value></property>` |
| `s` | string | `<property type='s'><key><![CDATA[name]]></key><value><![CDATA[PUNCH]]></value></property>` |
| `c` | couleur RGBA | voir ci-dessous |
| `r` | rect XYWH | voir ci-dessous |

```xml
<!-- Couleur -->
<property type='c'><key><![CDATA[color]]></key>
  <value><r>1.0</r><g>0.3</g><b>0.3</b><a>1.0</a></value>
</property>

<!-- Rectangle position/taille -->
<property type='r'><key><![CDATA[frame]]></key>
  <value><x>10</x><y>42</y><w>280</w><h>55</h></value>
</property>
```

### Propriétés des LABEL

> **Piège** : la propriété `text` n'est **pas reconnue** dans ce format.
> Le texte affiché est uniquement la propriété **`name`**.
> `textSize` est également ignoré.

```xml
<node ID='...' type='LABEL'>
  <properties>
    <property type='s'><key><![CDATA[name]]></key><value><![CDATA[PUNCH]]></value></property>
    <!-- text et textSize ne fonctionnent PAS ici -->
  </properties>
  ...
</node>
```

### Messages OSC

Structure complète d'un message OSC sur un contrôle :

```xml
<messages>
  <osc>
    <enabled>1</enabled>
    <send>1</send>
    <receive>0</receive>
    <feedback>0</feedback>
    <noDuplicates>0</noDuplicates>
    <connections>1111111111</connections>  <!-- Connection 1 activée -->
    <triggers>
      <trigger>
        <var><![CDATA[x]]></var>          <!-- 'x' pour fader, 'touch' pour bouton momentané -->
        <condition>ANY</condition>
      </trigger>
    </triggers>
    <path>
      <partial>
        <type>CONSTANT</type>
        <conversion>STRING</conversion>
        <value><![CDATA[/bang/param/bpm]]></value>
        <scaleMin>0</scaleMin>
        <scaleMax>1</scaleMax>
      </partial>
    </path>
    <arguments>
      <partial>
        <type>VALUE</type>
        <conversion>FLOAT</conversion>
        <value><![CDATA[x]]></value>
        <scaleMin>60</scaleMin>   <!-- valeur min envoyée -->
        <scaleMax>200</scaleMax>  <!-- valeur max envoyée -->
      </partial>
    </arguments>
  </osc>
</messages>
```

Le champ `connections` (`1111111111`) fait référence à la **Connection 1** configurée dans l'app TouchOSC.
Cette connexion doit être créée manuellement dans l'UI TouchOSC (type OSC, host + port).

### Types de nœuds disponibles

| Type | buttonType | Usage |
|------|-----------|-------|
| `FADER` | — | `orientation=1` horizontal, `orientation=0` vertical |
| `BUTTON` | `0` = momentané, `1` = toggle | — |
| `LABEL` | — | texte affiché = propriété `name` |
| `GROUP` | — | conteneur |

---

## Adresses OSC de BANG!

### Sortie BANG! → client (TX)

```
/bang/clock   INT32(step)  INT32(total_steps)
/bang/Punch   INT32(step)  INT32(velocity)  INT32(bpm)
/bang/Snap    INT32(step)  INT32(velocity)  INT32(bpm)
/bang/HH      INT32(step)  INT32(velocity)  INT32(bpm)
/bang/OH      INT32(step)  INT32(velocity)  INT32(bpm)
/bang/Perc    INT32(step)  INT32(velocity)  INT32(bpm)
/bang/Acc     INT32(step)  INT32(velocity)  INT32(bpm)
```

### Entrée client → BANG! (RX sur port 57120)

```
/bang/param/bpm       FLOAT (60–200)
/bang/param/swing     FLOAT (0–100)
/bang/param/chaos     FLOAT (0–1)
/bang/param/gravity   FLOAT (0–1)
/bang/param/density   FLOAT (0–1)   ← densité globale
/bang/generate        FLOAT (1.0)   ← trigger
/bang/vary            FLOAT (1.0)   ← trigger
/bang/stop            FLOAT (1.0)   ← trigger
/bang/slot/{0-7}      FLOAT (0|1)   ← toggle slot mémoire
/bang/density/Punch   FLOAT (0–1)
/bang/density/Snap    FLOAT (0–1)
/bang/density/HH      FLOAT (0–1)
/bang/density/OH      FLOAT (0–1)
/bang/density/Perc    FLOAT (0–1)
/bang/density/Acc     FLOAT (0–1)
/bang/lock/{0-5}      FLOAT (0|1)   ← toggle lock voix
```

---

## Générateur Python actuel

Le script `gen_bang.py` génère le `.tosc` depuis Windows/WSL.
Layout iPad Pro 12.9" (1366×1024) :

- **Row 1** : faders globaux horizontaux (BPM, Swing, Chaos, Gravity, Density)
- **Row 2** : transport (GENERATE · VARY · STOP) + 8 slots mémoire (toggle)
- **Row 3+** : 6 voix verticales (Punch/Snap/HH/OH/Perc/Acc) avec fader density + bouton LOCK

```
C:\Users\obare\Desktop\gen_bang.py          ← générateur
C:\Users\obare\Desktop\bang_controller.tosc ← fichier généré
```

---

## Intégration dans BANG! — À faire

L'endpoint `/touchosc` existe déjà dans l'API et retourne un `.tosc` au format ZIP (`lexml version='3.0.0'`).
Le format utilisé par notre générateur est différent : zlib brut, `lexml version='5'`.

**Les deux formats sont valides** dans TouchOSC — `version='5'` (zlib) est l'ancien format,
`version='3.0.0'` (ZIP) est le nouveau. TouchOSC accepte les deux.

### Option A — Améliorer `/touchosc` existant

Modifier le générateur interne de BANG! pour produire le layout complet (params globaux + transport + voix)
au lieu du layout minimal actuel. Le format ZIP est déjà en place.

### Option B — Ajouter `/touchosc/full`

Nouvel endpoint qui génère le layout complet en zlib (format `version='5'`), en se basant sur
les voix du pattern courant (`/pattern` → `voices[].name`).

```python
# Pseudo-code endpoint
@app.get('/touchosc/full')
def export_touchosc_full():
    pattern = get_current_pattern()
    voices = [(v['name'], *voice_color(v['name'])) for v in pattern['voices']]
    tosc_bytes = generate_tosc(voices)  # voir gen_bang.py
    return Response(tosc_bytes, media_type='application/octet-stream',
                    headers={'Content-Disposition': 'attachment; filename="bang_controller.tosc"'})
```

### Voix et couleurs

Les noms de voix viennent directement de `/pattern` → `voices[].name`.
Ils sont identiques pour tous les presets builtin : `Punch, Snap, HH, OH, Perc, Acc`.

Couleurs suggérées par voix :

```python
VOICE_COLORS = {
    'Punch': (1.0, 0.3,  0.3 ),
    'Snap':  (1.0, 0.6,  0.2 ),
    'HH':    (0.2, 0.85, 0.85),
    'OH':    (0.1, 0.7,  0.7 ),
    'Perc':  (0.8, 0.3,  1.0 ),
    'Acc':   (1.0, 0.85, 0.1 ),
}
```

---

## Config TouchOSC côté app

Dans TouchOSC → Connections → Connection 1 :

| Champ | Valeur (LAN) | Valeur (Tailscale) |
|-------|-------------|-------------------|
| Type | OSC | OSC |
| Host | `192.168.1.100` | `100.64.201.127` |
| Send Port | `57120` | `57120` |
| Receive Port | (optionnel) | (optionnel) |

---

## Références

- Générateur complet : `gen_bang.py` (Windows Desktop)
- Reverse engineering réalisé le 2026-05-26 en session avec Claude Code
- Format découvert par décompression zlib d'un fichier test créé dans l'éditeur TouchOSC
