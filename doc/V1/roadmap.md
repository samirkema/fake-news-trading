# Roadmap V1 — axes d'amélioration

La V0 (cf. `doc/V0/`) est validée : scraper RSS multi-sources, 5 signaux
évaluateur (réputation, style, fact-checking, source primaire, LLM bootstrap),
contextualisation LLM ancrée sur preuves, frontend avec authentification par
mot de passe. Ce document liste les axes retenus pour les prochaines versions —
**purement indicatif à ce stade, rien n'est implémenté**.

## 1. Collecte

Élargir les sources et la nature des articles évalués, au-delà du scraping
RSS/Reddit actuel :

- **Soumission d'articles par les utilisateurs** : permettre à un utilisateur de
  proposer lui-même un article/lien à évaluer, en complément de la collecte
  automatique.
- **Évaluation des photos** : ajouter un signal qui analyse les images d'un
  article (pas seulement le texte) — pertinent pour les fake news qui reposent
  sur une image sortie de son contexte ou manipulée.

## 2. Évaluateur

- **Affiner les signaux existants** : améliorer petit à petit la pertinence de
  chaque signal (réputation, style, fact-checking, source primaire, LLM) pour
  rendre le score le plus significatif possible.
- **Interaction utilisateur** : donner aux utilisateurs la possibilité de
  commenter un article évalué et d'influer sur le score (mécanisme à définir —
  pondération d'un retour humain dans le score composite).

## 3. Contextualisation

Aller au-delà de l'explication actuelle du score (ancrée sur les preuve_id) pour
couvrir :

- **L'impact** d'une fake news (portée, conséquences).
- **La propagation** : comment et où elle s'est diffusée.

## Statut

Ces trois axes ont été formulés par l'utilisateur le 2026-08-11 comme direction
pour l'après-V0. Aucun n'est planifié en détail ni commencé — chaque axe sera
scopé (user stories, architecture) séparément, au moment où l'utilisateur
décidera de l'attaquer.
