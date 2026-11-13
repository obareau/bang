# 🧪 BANG! — Tests & chasse au bug

Documentation du workflow de test automatisé.

> Le serveur de production (`bang.service`, `192.168.1.100` / `bang.lan`) **n'existe plus**. BANG! passe en apps natives : l'app macOS a son propre auto-test (voir ci-dessous) et le webapp Python se teste **en local**.

---

## TL;DR

### App macOS native

```bash
cd macos && swift run bang-check      # moteur : DNA, Babka, 14 modes, export .mid, 808/909, live, connexions
```
Dernière ligne `✓ tout vert` (exit 0) ou `✗ N échec(s)` (exit 1). Les diagnostics
`BANG_SELFTEST_*` pilotent l'app réelle (modes, Song, morph, synchro MIDI clock,
export WAV, OSC, Ableton, MIDI Learn) : voir `macos/README.md`.

### Webapp Python (en local)

```bash
uv run python web.py                  # terminal 1 : lance le webapp sur http://localhost:7777
python3 tests/test_bang.py            # terminal 2 : lance le harnais
```
Dernière ligne de sortie = `BANG_TEST_JSON={...}` (résumé machine-readable).
Exit code `0` = tout vert, `1` = au moins un FAIL.

Depuis Claude Code : taper **`/test-bang`** (lance le harnais + une passe navigateur Puppeteer, et peut filer les bugs dans Todoist avec `--file-bugs`).

---

## ⚠️ À savoir sur le webapp

Le harnais teste un webapp **déjà lancé** : démarrer `uv run python web.py` avant, et le
relancer après une modification du code (sauf avec `uvicorn web:app --reload`).

**`_save_state()` n'est PAS appelé** par `/generate`, `/vary`, `/lock_voice`, `/ctrl`
(seulement par certaines voice-ops). Donc `bang_state.json` sur disque est souvent
**périmé** par rapport à l'état en mémoire. ⇒ Source de vérité = l'endpoint
`GET /session/export`, jamais le fichier sur disque.

---

## Ce que couvre le harnais (`tests/test_bang.py`)

Harnais **stdlib pur** (urllib + json), zéro dépendance — volontaire, le venv n'a ni
pytest ni playwright. ~95 vérifications.

**Sécurité** : au démarrage il fait un *snapshot* de la session via `/session/export`,
et le *restaure* via `/session/import` à la fin. **Le motif de travail de l'utilisateur
n'est jamais détruit.** (`--no-restore` pour désactiver en debug.)

**Oracle de vérité** : `GET /session/export` renvoie
`{params, voices:[{note,pattern,type}], locked_voices}`.
Le champ `locked_voices` a été ajouté exprès pour le harnais (utile aussi au dashboard SSE).

### Catégories

| Catégorie | Vérifie |
|-----------|---------|
| `SMOKE` | tous les endpoints GET répondent 200 (ou <500 pour les tolérés) |
| `R5-frontend` | HTMX/SSE servis **en local** (`/static/js/...`), **zéro** `unpkg.com`, `/live` contient ses contrôles |
| `modes` | les 14 modes génèrent sans erreur et produisent des voix |
| `R1-variety` | `generate` est **non-déterministe** (6/6 signatures distinctes) |
| `R2-allvoices` | **toutes** les voix se régénèrent (≥2 positions varient) — morph/markov/phase2/babka/ambient |
| `R3-vary` | `/vary` et `/voice/vary` modifient réellement le motif |
| `R4-lock` | une voix verrouillée reste figée, les autres mutent |
| `ctrl` | `/ctrl` modifie un param **sans** régénérer, coerce les int, ignore les clés invalides |
| `undo/AB` | `/undo` et le round-trip `/ab/store` ↔ `/ab/load` |
| `voice-ops` | fuzz des 20 opérations par voix : aucun 500, état toujours valide |
| `edge` | bornes de params (steps 8→256, chaos 0/1, bpm 40/240, bassline >128) |
| `seed` | reproductibilité par seed *(informatif)* |

### Les 5 régressions historiques (toutes couvertes, vertes)

1. **R1** — `generate` déterministe à cause de `locked_voices=[0,1,2,3]` figé.
2. **R2** — morph/markov/phase2/babka ne régénéraient que la voix 0 (voix 2-4 hardcodées).
3. **R3** — `/vary` excluait les voix `babka`/`cc` → aucun changement visible.
4. **R4** — verrouillage de voix.
5. **R5** — HTMX chargé depuis le CDN unpkg → bouton mort quand le CDN lag ; désormais servi en local.

---

## Passe E2E navigateur (`/test-bang`, via Puppeteer)

L'API ne peut pas voir les bugs de **câblage DOM/HTMX** (c'est là que vivait le bug
historique « bouton Generate mort »). La passe navigateur :

1. charge `/` → confirme `window.htmx` chargé, `uses_unpkg=false`, `.btn-gen` présent ;
2. clique **Generate** → assert que `#pianoroll` a réellement muté ;
3. charge `/live` → assert SSE connecté (point vert), 9 sliders, 4 voix + locks,
   et qu'un déplacement du slider BPM met à jour l'affichage ;
4. screenshot du dashboard.

---

## Bugs corrigés (2026-05-29)

Les 2 findings de la première passe ont été corrigés ; harnais désormais **95/95**.

| Bug | Cause | Fix appliqué |
|-----|-------|--------------|
| `/voice/vary` no-op intermittent | `mutate_dna(intensity=0.15)` ne garantit pas ≥1 flip sur motif court | boucle de retry (≤8) jusqu'à ce que `new_dna != dna` — `web.py voice_vary()` |
| seed non reproductible | `_build_voices`/`mutate_dna` utilisaient le RNG global non-seedé | `random.seed(_seed_to_int(p['seed']))` en tête de `_build_voices` si seed non vide |

---

## Étendre le harnais

- Source : `tests/test_bang.py`, directement dans le dépôt.
- Ajouter un test = écrire une fonction `t_xxx()` qui appelle `ok(cat, name, cond, ...)`
  puis l'enregistrer dans `main()`.
- Toujours lire l'état via `export()` (helper) et muter via les endpoints — pas d'accès disque.
- Pour un nouveau test de régression : générer N fois, comparer les signatures de voix
  (`voices_sig(export())`).

---

## Cible

`http://localhost:7777` par défaut (webapp lancé en local) — ou passer une autre URL en argument :
`python3 tests/test_bang.py http://hôte:port`.
