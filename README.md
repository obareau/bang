# ⚡ BANG (V2)
> **MIDI Algorithmic Sequencer for the Robōtariis Universe.**

BANG est un moteur de génération MIDI conçu pour le cadre **Robōtariis**. Il privilégie le workflow "Audio First / Jam" en générant des structures complexes et évolutives destinées à être sculptées en studio.

---

## 🌌 Concept : Dark Umbrae Logic
Sous une apparence minimaliste, BANG déploie une logique de "complexité sous-marine" basée sur :

*   **Polyrythmie Native :** Superposition de cycles asymétriques (ex: 8/5) créant un décalage infini.
*   **Corruption Progressive :** Algorithme de mutation qui dégrade les notes et les vélocités au fil de la séquence.
*   **Audio-First :** Conçu pour générer de la matière première (fichiers `.mid`) prête pour Logic Pro ou Ableton Live.

Le moteur de BANG V2 repose sur une Chaîne de Markov à état simple avec pondération probabiliste.L'Algo derrière BANG :Stochastique (Hasard calculé) : Chaque pas du pattern ne contient pas une instruction binaire (on/off), mais une valeur de probabilité ($P$).Modulo asymétrique : C'est ce qui crée la polyrythmie. En utilisant des longueurs de boucles différentes pour chaque instrument, on crée un motif qui ne se répète jamais à l'identique sur une courte période.Entropie Linéaire : La fonction mutate injecte du désordre (entropie) de manière proportionnelle à l'avancement du temps ($t$), transformant une structure stable en un système chaotique.

![Workflow BANG V2](./workflow.png)

## 🚀 Installation & Usage

Ce projet utilise [uv](https://github.com/astral-sh/uv) pour une gestion rapide des dépendances.

```bash
# Cloner le projet
git clone [https://github.com/obareau/bang.git](https://github.com/obareau/bang.git)
cd bang

# Lancer la génération
uv run bang_v2.py

🛠️ Spécifications Techniques
Langage : Python 3.12+

Librairie : mido pour la manipulation des flux MIDI.

Architecture : Multi-pistes (Drums / Bass / Chaos).

Environnement : Optimisé pour serveur distant via Remote-SSH.

📜 Licence
Projet réalisé dans le cadre du méta-univers Robōtariis