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

## 4. Frontend

Le frontend actuel (liste filtrable + détail par article, cf. `doc/V0/`) reste
minimal et doit être amélioré — portée précise à définir, mais candidats
identifiés au fil de la V0 : ergonomie des filtres, accueil des nouvelles
fonctionnalités des axes ci-dessus (soumission d'articles, commentaires,
photos), lisibilité de la mise en contexte.

### Comptes à 3 rôles — fondation posée (2026-08-26)

La connexion distingue désormais trois rôles (`spectateur`, `contributeur`,
`superadmin`) via un pseudo saisi en plus du mot de passe partagé. Aucune
capacité n'y est encore conditionnée — c'est la brique de base pour les axes
ci-dessus (interaction utilisateur, modération, soumission). Détail et limite de
sécurité connue : `doc/V1/comptes-3-roles.md`.

## Scopé depuis — Crowdsourcing (V3, 2026-09-10)

Trois des points listés ci-dessus ne sont plus « indicatifs » : ils sont scopés
dans `doc/V3/` (user stories + plan d'implémentation), sans être implémentés.

- axe 1, « soumission d'articles par les utilisateurs » → proposition d'un
  article par tout compte connecté, file d'attente décidée par les contributeurs,
  entrée dans le pipeline par le même chemin que la collecte automatique ;
- axe 2, « interaction utilisateur » → commentaires sur l'analyse d'un article.
  **La moitié « influer sur le score » n'est pas retenue** : un vote humain non
  authentifié rendrait le score composite manipulable et lui retirerait son
  explicabilité (cf. `doc/V3/userstories_crowdsourcing.md`, US-08) ;
- axe 4, frontend → écrans d'accueil de ces fonctionnalités, plus un espace
  compte et un écran de gestion des contributeurs.

C'est aussi la version où la fondation « comptes à 3 rôles » ci-dessous cesse
d'être décorative : le rôle `contributeur` reçoit sa première capacité, et donc
son premier code personnel obligatoire.

## Statut

Ces quatre axes ont été formulés par l'utilisateur le 2026-08-11 comme direction
pour l'après-V0. Aucun n'est planifié en détail ni commencé — chaque axe sera
scopé (user stories, architecture) séparément, au moment où l'utilisateur
décidera de l'attaquer.
