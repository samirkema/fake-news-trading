# User Stories — Scraper

Périmètre : la collecte des articles bruts (RSS, Reddit, GDELT), tous domaines, monde entier, sans filtre thématique a priori, et leur mise à disposition normalisée dans le stockage partagé pour l'évaluateur.

---

## US-01 — Collecte via flux RSS internationaux, tous domaines

**En tant que** scraper automatique,
**je veux** collecter les articles publiés par des flux RSS de presse généraliste et internationale à haute réputation (BBC, Le Monde, et une source wire complémentaire en repli sur Reuters) ainsi que par une sélection de domaines à faible crédibilité,
**afin de** disposer d'un corpus d'actualité mondiale couvrant tout le spectre de fiabilité, et pas seulement des sources déjà réputées fiables, condition nécessaire pour que les signaux de réputation (US-01 évaluateur) et de corroboration croisée (US-02 évaluateur) aient de vrais cas à traiter en usage réel.

**Critères d'acceptation :**
- Les flux RSS retenus couvrent une diversité de zones géographiques et de langues (au minimum anglophone et francophone), sans filtre thématique en amont — tous domaines, pas seulement finance/marché.
- Chaque article collecté conserve : titre, contenu (ou résumé si le flux ne fournit pas le corps complet), domaine source, date de publication, URL d'origine.
- Reuters ayant supprimé ses flux RSS publics en 2020, sa disponibilité est vérifiée à l'implémentation ; en cas d'indisponibilité, le scraper journalise l'échec et bascule sur une source de repli équivalente (autre agence de wire, ou couverture via GDELT) sans interrompre la collecte des autres flux.
- Les domaines à faible crédibilité collectés sont tirés de la même liste de référence que celle utilisée pour la réputation de la source (US-01 évaluateur — dataset OpenSources / Media Bias Fact Check), pour garantir la cohérence entre ce qui est collecté et ce contre quoi c'est évalué. Short-list de départ à vérifier à l'implémentation (disponibilité RSS, domaine toujours actif) :
  - **Conspiration / désinformation, anglophone** ("douteux") : infowars.com, naturalnews.com, beforeitsnews.com, worldnewsdailyreport.com
  - **Conspiration / désinformation, francophone** ("douteux") : liste à constituer à partir du Décodex (Le Monde, décodex.lemonde.fr), qui documente déjà sa propre méthodologie de notation par source — pas de liste figée ici pour éviter de qualifier nommément des sources sans méthodologie vérifiable. Sans ce pendant francophone, le signal de réputation (US-01 évaluateur) n'a aucun cas de test réel côté français, alors que Le Monde en est la seule source "haute réputation" francophone du corpus.
  - **Satire auto-déclarée** (catégorie distincte de la désinformation — intention non trompeuse, bon cas de test pour les signaux stylistiques US-05 évaluateur) : theonion.com, babylonbee.com (anglophone), legorafi.fr (francophone, pendant direct de The Onion)
- Aucune limite de volume n'est imposée arbitrairement — le volume réel dépend de la publication effective de chaque flux sur la semaine, et est journalisé (cf. US-06).

---

## US-02 — Collecte via Reddit (actualité générale + finance)

**En tant que** scraper automatique,
**je veux** collecter les posts des subreddits r/worldnews et r/news (actualité générale) ainsi que r/wallstreetbets, r/stocks et r/investing (finance),
**afin de** capturer à la fois l'actualité mondiale généraliste et le signal spécifique finance déjà requis par l'évaluateur (US-06 évaluateur, décalage d'apparition).

**Critères d'acceptation :**
- Chaque post collecté conserve : titre, corps du texte, subreddit d'origine, date de publication, score/upvotes, nombre de commentaires, URL du post.
- Le biais de couverture principalement anglophone de Reddit est documenté comme limite connue (ne remplace pas la diversité linguistique des flux RSS, la complète).
- La liste des subreddits suivis est configurable (ajout/retrait) sans modification du code de collecte.

---

## US-03 — Collecte via GDELT (support du clustering d'événements)

**En tant que** scraper automatique,
**je veux** interroger l'API GDELT sur la fenêtre de la semaine écoulée,
**afin de** fournir à l'évaluateur les données d'événements nécessaires au regroupement par claim (US-02 évaluateur, corroboration croisée) et à la comparaison d'ordre d'apparition (US-06 évaluateur).

Le scraper ne calcule pas lui-même de clusters : il se contente d'attacher l'identifiant d'événement GDELT (`gdelt_event_id`) à chaque article/post quand une correspondance existe. C'est l'évaluateur (US-02 évaluateur) qui construit les clusters réellement utilisés pour le scoring, en s'appuyant en priorité sur ce `gdelt_event_id` et en repli sur la similarité de titre/contenu — pour qu'il n'y ait qu'un seul endroit où "cluster" est défini.

**Critères d'acceptation :**
- Chaque article RSS et chaque post Reddit collecté se voit attacher le `gdelt_event_id` correspondant en métadonnée, quand une correspondance GDELT existe pour la semaine.
- Cette mise en correspondance couvre aussi bien les articles RSS que les posts Reddit, pas seulement les articles — condition nécessaire pour que le signal de décalage d'apparition (US-06 évaluateur) puisse rattacher un post Reddit à un événement.
- En l'absence de correspondance GDELT pour un article ou un post donné, `gdelt_event_id` est absent (pas une erreur) ; l'évaluateur retombe alors sur un regroupement par similarité de titre/contenu (cf. US-02 évaluateur).

---

## US-04 — Normalisation et persistance dans le stockage partagé

**En tant que** scraper automatique,
**je veux** normaliser tous les articles et posts collectés (RSS, Reddit) dans un schéma commun et les écrire dans le stockage partagé,
**afin que** l'évaluateur puisse les consommer sans connaître leur source de collecte d'origine.

**Critères d'acceptation :**
- Schéma commun minimal : identifiant, titre, contenu, domaine source, date de publication, URL, plateforme d'origine (rss / reddit — GDELT n'est pas une plateforme d'origine, cf. US-03 : c'est un enrichissement de métadonnée sur des articles/posts déjà collectés via RSS ou Reddit), métadonnées spécifiques à la plateforme (ex. upvotes Reddit, `gdelt_event_id` quand une correspondance existe).
- L'écriture dans le stockage est le seul point de contact entre le scraper et l'évaluateur (conforme au contrat défini dans `architecture.md` — pas d'appel direct entre les deux blocs).

---

## US-05 — Déduplication inter-runs

**En tant que** scraper automatique,
**je veux** détecter si un article déjà collecté lors d'un run précédent réapparaît,
**afin d'**éviter de dupliquer les entrées dans le stockage partagé et de fausser le comptage de sources corroborantes (US-02 évaluateur).

**Critères d'acceptation :**
- Déduplication par URL canonique et/ou hash du contenu.
- Un article déjà présent n'est pas réinséré, mais ses métadonnées volatiles (ex. upvotes Reddit) peuvent être mises à jour si republiées avec des valeurs différentes.

---

## US-06 — Exécution hebdomadaire planifiée

**En tant que** scraper automatique,
**je veux** m'exécuter automatiquement une fois par semaine sur une fenêtre de temps définie,
**afin d'**alimenter le pipeline sans intervention manuelle.

**Critères d'acceptation :**
- Le scraper est déclenché via une tâche planifiée (cf. "Prochaines étapes" de `fiche-projet-fake-news-trading.md`).
- Chaque run journalise le nombre d'articles collectés par source (RSS par flux, Reddit par subreddit, GDELT) — ce comptage réel remplace toute estimation a priori du volume hebdomadaire.

---

## Hors périmètre (pour rappel)

- Le filtrage thématique ou la classification "pertinent pour la finance" d'un article n'est pas fait par le scraper — il collecte tous domaines sans distinction ; c'est l'évaluateur qui traite ensuite chaque signal, y compris ceux spécifiques à la finance (US-04 évaluateur).
- Le choix et l'évolution du stockage partagé (Supabase) relèvent de `architecture.md`, pas de ces user stories.
