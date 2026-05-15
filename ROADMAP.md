# 🗺️ BANG : Roadmap & Visions
Ce document consigne les évolutions futures du séquenceur algorithmique pour la **Dark Umbrae**.

---

## 🌀 Phase 1 : Sources d'Entropie (En cours)
L'objectif est de remplacer le hasard pur par des données systémiques ou environnementales.
- [ ] **Entropie Temporelle :** Utiliser l'heure système (microsecondes) pour influencer le Jitter.
- [x] **Entropie Cryptographique :** Utiliser des fragments de clés SSH ou de Hash (SHA-256) pour générer des patterns uniques et non-reproductibles.
- [ ] **Lien Local :** Injecter les données météo de Scaër (température, vent) pour moduler la densité des séquences.

## 🎛️ Phase 2 : Moteurs de Génération
- [ ] **Implémentation Markovienne avancée :** Créer des tableaux de probabilités de transition entre les notes (ex: si Do est joué, 70% de chance d'aller vers Ré#).
- [ ] **Mode Drone :** Génération de messages MIDI CC (Control Change) pour piloter des filtres de synthés en continu.
- [ ] **Polyrythmie Dynamique :** Permettre au script de changer la longueur des boucles (ex: passer de 5 à 7 pas) de manière organique.

## 💻 Phase 3 : Interface & Workflow
- [ ] **CLI Interactive :** Pouvoir choisir le "degré de chaos" (0.1 à 1.0) via une commande au lancement.
- [ ] **Mode Live Controller :** Utiliser le Zoom R8 pour modifier certains paramètres d'entropie en temps réel pendant la génération.
- [x] **Système de Logs :** Chaque fichier MIDI exporté contient en méta-donnée la "graine" (seed) utilisée pour pouvoir le régénérer si besoin.

---
*Dernière mise à jour : Mai 2026 - Cadre Robōtariis*