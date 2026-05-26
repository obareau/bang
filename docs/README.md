# BANG! — Documentation

Bienvenue dans la documentation de BANG!, le générateur MIDI algorithmique pour le cadre **Robōtariis** (Dark Umbrae).

## Index

| Document | Contenu |
|----------|---------|
| [algorithms.md](algorithms.md) | Algorithmes internes — DNA, Markov, Babka, Weather, Seed, Humanisation |
| [dna-syntax.md](dna-syntax.md) | Référence complète de la syntaxe DNA et Babka avec exemples |
| [generation-modes.md](generation-modes.md) | Description de chaque mode de génération (Morph, Noise, Ambient, Babka, Volca…) |
| [api-engine.md](api-engine.md) | API Python BangEngine — utilisation programmatique |
| [architecture.md](architecture.md) | Architecture du projet, flux de données, composants |
| [osc-midi.md](osc-midi.md) | Référence OSC et MIDI — protocoles, canaux, matériel |

## Démarrage rapide

```bash
# Démarrer le serveur de dev
cd bang/
uv run uvicorn web:app --reload --port 7777
# → http://localhost:7777
```

## Utilisation programmatique

```python
from bang_engine import BangEngine, dark_chain, morph_dna

engine = BangEngine(bpm=120)
engine.add_voice(36, morph_dna("x---x---x---x---", "x---?---x↺--░---"))
engine.add_markov_voice(dark_chain(), "x-?-░")
engine.add_cc_drone(74, breakpoints=[20, 100, 20])
engine.export_midi(num_steps=64, filename="out.mid")
```

Voir [api-engine.md](api-engine.md) pour la référence complète.

## Architecture en une phrase

L'interface HTMX envoie des formulaires à FastAPI → `_build_voices()` sélectionne le mode et génère le DNA → `BangEngine.export_midi()` produit le fichier MIDI → le player JS reçoit les events via `/pattern` et les envoie en Web MIDI ou MIDI serveur.
