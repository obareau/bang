# BANG — Séquenceur MIDI Algorithmique

Projet de génération MIDI pour le cadre **Robōtariis** (méta-univers musical). Logique "Dark Umbrae" : complexité sous-marine, polyrythmie, entropie progressive.

## Stack

- Python 3.12+ / `uv` (gestionnaire de dépendances)
- `mido` pour la génération MIDI
- `numpy` pour la matrice d'état
- Environnement : serveur distant via Remote-SSH

## Commandes clés

```bash
uv run bang_v2.py          # Génération principale
uv run bang_engine.py      # Test moteur V1.4
python main.py             # Point d'entrée principal
```

## Architecture

- `bang_engine.py` — `BangEngine` : matrice numpy 16x5, DNA syntax (`x-?↺░`), export MIDI
- `bang_v2.py` — Polyrythmie (cycles asymétriques 8/5), corruption progressive (Chaîne de Markov)
- `bang_fork.py` / `bang_multi_fork.mid` — Fork expérimental multi-piste

### DNA Syntax (symboles)
| Char | Déclenchement | Vélocité | Prob | Ratchet | Jitter |
|------|--------------|----------|------|---------|--------|
| `x`  | oui | 105 | 1.0 | 1 | 0 |
| `-`  | non | 0   | 0.0 | 1 | 0 |
| `?`  | oui | 90  | 0.5 | 1 | 0 |
| `↺`  | oui | 110 | 1.0 | 3 | 0 |
| `░`  | oui | 85  | 1.0 | 1 | 25 |

## Roadmap active (Phase 1 en cours)

- Entropie temporelle (microsecondes système)
- Entropie cryptographique (SHA-256 / clés SSH)
- Lien météo local (Scaër) → densité de séquence
- Phase 2 : Markov avancé, Mode Drone (MIDI CC), Polyrythmie dynamique
- Phase 3 : CLI interactive, Mode Live (Zoom R8), Logs avec seed
