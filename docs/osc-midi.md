# BANG! — Référence OSC & MIDI

## OSC (Open Sound Control)

### Configuration

Le panneau OSC est accessible via le bouton **OSC** dans l'interface. Ports configurables séparément pour émission (TX) et réception (RX).

Par défaut :
- TX : `localhost:57120` (port SuperCollider)
- RX : `localhost:9000`

### Messages émis par BANG! (TX)

À chaque génération, BANG! émet les paramètres courants :

```
/bang/bpm            i   tempo en BPM
/bang/chaos          f   valeur chaos (0.0–1.0)
/bang/steps          i   nombre de steps
/bang/mode           s   nom du mode de génération
/bang/seed           s   seed hex (16 premiers caractères)
/bang/voice/<n>/dna  s   pattern DNA de la voix n
/bang/voice/<n>/note i   note MIDI de la voix n
```

### Messages reçus par BANG! (RX)

| Adresse | Args | Action |
|---------|------|--------|
| `/bang/generate` | — | Déclenche une génération |
| `/bang/vary` | — | Variation légère du pattern |
| `/bang/param/bpm` | `i` | Change le BPM |
| `/bang/param/chaos` | `f` | Change le chaos (0.0–1.0) |
| `/bang/param/steps` | `i` | Change le nombre de steps |
| `/bang/density/<voice>` | `f` | Ajuste la densité d'une voix |
| `/bang/lock/<voice>` | `i` | Verrouille (1) / déverrouille (0) une voix |

### Exemples SuperCollider

```supercollider
// Écouter les paramètres BANG!
OSCdef(\bangBpm, {|msg| ("BPM: " ++ msg[1]).postln}, '/bang/bpm');
OSCdef(\bangSeed, {|msg| ("Seed: " ++ msg[1]).postln}, '/bang/seed');

// Envoyer un generate depuis SC
NetAddr("localhost", 9000).sendMsg('/bang/generate');

// Changer le chaos
NetAddr("localhost", 9000).sendMsg('/bang/param/chaos', 0.7);
```

### Exemples Max/MSP

```
[udpsend 127.0.0.1 9000]
    ^
[prepend /bang/generate]
    ^
[bang]       → déclenche une génération
```

---

## MIDI

### Canaux par mode

| Mode | Canal(aux) | Notes |
|------|-----------|-------|
| Batterie (tous modes drum) | 10 (index 9) | GM standard |
| Markov / Phase 2 | Configurable (défaut ch10) | |
| Bassline | ch1 | |
| Volca Drum | ch 1–6 (index 0–5) | 1 canal par part |
| Volca Kick | ch1 | Note C3=60 |
| Volca FM | ch1 | 3 notes simultanées |
| MicroFreak | ch1 | 3 voix paraphoniques |
| KeyStep Pro drums | ch10 | |
| KeyStep Pro mélo | ch 1–4 | 4 pistes |

### MIDI Serveur (python-rtmidi)

Sortie MIDI physique sans dépendance Chrome. Fonctionne depuis n'importe quel navigateur sur le LAN.

**Activer** : panneau Setup → MIDI Server → choisir port → Start.

Le serveur reçoit les events du player JS via WebSocket (`/midi-ws`) et les envoie au port MIDI physique en temps réel.

### MIDI Clock

**TAP** : calcule le BPM par médiane sur 5 taps consécutifs.

**SYNC** : synchronisation sur horloge MIDI entrante (24 PPQN). Le BPM est calculé en temps réel depuis les messages `timing_clock`. Les messages `start` et `stop` contrôlent le transport automatiquement.

### Web MIDI API

Nécessite Chrome ou Edge + HTTPS (`https://bang.lan`). Permet :
- Sortie MIDI directe vers un périphérique connecté
- **MIDI Learn** : capture d'un pattern depuis un clavier/pad physique

---

## Sync avec Ableton Live (AbletonOSC)

Si AbletonOSC est installé dans Ableton :

- **Sync BPM** : BANG! lit `/live/song/get/tempo` et synchronise son tempo
- **Push clip** : chaque voix peut être envoyée comme clip MIDI directement dans la session view d'Ableton

Configuration dans le panneau Setup → Ableton.

---

## Presets matériel

BANG! inclut des presets de mapping MIDI pour des synthétiseurs et boîtes à rythme courants :

| Preset | Notes |
|--------|-------|
| GM Standard | Kick=36, Snare=38, HH=42, etc. |
| TR-808 | Mapping original Roland |
| TR-909 | Mapping original Roland |
| MPC60 | Mapping MPC classique |
| Volca Drum | 6 canaux 1–6, note C3 |
| Volca Kick | Canal 1, note C3 |
| Volca FM | Canal 1, 3 voix C1/G1/C2 |
| MicroFreak | Canal 1, 3 voix paraphoniques |
| KeyStep Pro | Drums ch10, mélo ch1–4 |

Les presets remappent automatiquement les notes MIDI des voix générées.
