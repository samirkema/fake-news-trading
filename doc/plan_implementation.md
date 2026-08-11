# Plan d'implémentation

Ce plan séquence le développement des 4 blocs définis dans `architecture.md`, en s'appuyant sur les user stories de chaque bloc. L'ordre est piloté par les dépendances réelles entre blocs et par la volonté d'avoir un pipeline testable de bout en bout le plus tôt possible, plutôt que de finir un bloc à 100% avant de commencer le suivant.

---

## Choix technique global

**Python** de bout en bout : c'est le langage qui a le plus de librairies prêtes à l'emploi pour chaque besoin du projet, et c'est cohérent avec la phase ultérieure de fine-tuning (BERT/RoBERTa) déjà actée dans `fiche-projet-fake-news-trading.md`.

| Besoin | Librairie/outil pressenti |
|---|---|
| Flux RSS | `feedparser` |
| Reddit | `praw` (API officielle) |
| GDELT | requêtes HTTP directes sur l'API GDELT |
| Fact Check Tools | requêtes HTTP directes (API Google, gratuite) |
| SEC EDGAR | requêtes HTTP directes (full-text search, gratuit) |
| NER (tickers/entreprises) | `spaCy` |
| Embeddings (clustering US-02 évaluateur) | `sentence-transformers` (modèle léger type `all-MiniLM-L6-v2`, local, gratuit) |
| LLM (US-07 évaluateur, contextualiseur) | **Claude (Anthropic)**, SDK `anthropic` — sortie structurée forcée via tool use plutôt que du parsing de texte libre (cf. `fakenews/llm.py`) |
| Stockage partagé | Supabase (PostgreSQL managé), via `SQLAlchemy` + driver Postgres (`psycopg2`/`asyncpg`) ou le client `supabase-py` |
| Frontend | FastAPI + Jinja2 (pas de SPA, cf. `architecture.md`), déployé sur **Vercel** |
| Code source / CI | **GitHub** (repo + déclencheur des workflows planifiés) |
| Planification hebdomadaire | **GitHub Actions** (workflow `schedule: cron`) ; **Render en repli uniquement** si un job long/persistant s'avère nécessaire (cold start à éviter par défaut) |

---

## Phase 0 — Fondations : stockage partagé

Avant tout bloc métier, définir le schéma Supabase (PostgreSQL) qui sert de contrat entre les 4 blocs (cf. `architecture.md`) :
- table `articles` : id, titre, contenu, domaine_source, date_publication, url, plateforme, métadonnées (JSON)
- table `scores` : article_id, sous-scores US-01 à US-07 (chacun avec `valeur`, `raison`, `preuve_id` — cf. interface `evaluer(article)` dans `architecture.md`), poids appliqués, score composite final (US-08) — un nombre 0-100 ou `non_évaluable` si tous les signaux sont exclus pour cet article
- table `mise_en_contexte` : article_id, explication, sources utilisées, niveau de confiance, avertissement, date de génération

Rien n'est testable de bout en bout sans ce socle — c'est la première chose à coder.

---

## Phase 1 — Scraper

Ordre retenu :

1. **US-01 (RSS)** en premier : aucune authentification requise pour la plupart des flux, résultat immédiatement vérifiable, et ça répond concrètement à la question du volume hebdomadaire réel restée ouverte. Inclut dès le départ les domaines à faible crédibilité anglophones identifiés (infowars.com, naturalnews.com, etc.) et le repli si Reuters RSS est indisponible ; le pendant francophone (à constituer via Décodex, cf. `userstories_scraper.md`) reste à trancher à l'implémentation, pas bloquant pour démarrer avec la liste anglophone existante.
2. **US-02 (Reddit)** ensuite : nécessite l'enregistrement d'une app Reddit (identifiants API), un peu plus de friction que RSS mais toujours gratuit.
3. **US-04 (normalisation/persistance)** en continu au fur et à mesure de 1 et 2, pas comme étape séparée après coup — chaque collecteur écrit directement dans le schéma commun de la Phase 0.
4. **US-05 (déduplication)** une fois qu'il existe au moins deux runs à comparer.
5. **US-03 (GDELT)** ensuite : plus complexe à intégrer, et son utilité dépend surtout des signaux évaluateur les plus complexes (US-02/US-06 évaluateur), qui arrivent plus tard en Phase 2 — pas bloquant pour démarrer.
6. **US-06 (planification hebdomadaire)** en dernier pour ce bloc : n'a de sens qu'une fois les runs manuels fiables.

---

## Phase 2 — Évaluateur

Ordre retenu, du signal le plus simple/autonome au plus complexe/dépendant :

1. **US-08 (squelette du score composite)** dès que 1 seul signal existe, pas en dernier : implémenter l'agrégateur et sa logique d'exclusion des signaux neutres/non-applicables tôt, pour avoir un score de sortie testable dès le premier signal réel plutôt que d'attendre que les 7 soient prêts.
2. **US-01 (réputation)** : simple lookup sur la liste de référence déjà nécessaire côté scraper (OpenSources/MBFC) — pas de nouvelle dépendance externe.
3. **US-05 (signaux stylistiques)** : aucune dépendance externe (byline, citations, marqueurs de sensationnalisme) — bon second signal pour enrichir US-08 rapidement.
4. **US-07 (LLM bootstrap)** : un seul appel LLM par article, prompt structuré. Le journaliser dès maintenant commence à constituer le futur dataset d'entraînement, conformément à la stratégie hybride du projet.
5. **US-03 (fact-checking)** : API Google Fact Check Tools, gratuite, intégration directe.
6. **US-02 (corroboration croisée)** : dépend du clustering GDELT (Phase 1, étape 5) ou d'un repli par similarité de titre/contenu — plus complexe, à faire une fois GDELT disponible.
7. **US-04 (source primaire finance)** : nécessite NER + requêtes SEC EDGAR — signal le plus spécialisé, le moins souvent applicable (uniquement claims financières précises).
8. **US-06 (décalage d'apparition)** : dépend du clustering d'événements (US-02) et du timestamp de première détection Reddit (scraper US-02) — signal le plus complexe, en dernier.

---

## Phase 3 — Contextualiseur

Séquentiel, chaque étape dépendant de la précédente :

1. **US-01 (déclenchement conditionnel)** : nécessite que US-08 évaluateur soit fonctionnel pour avoir un seuil de suspicion à tester.
2. **US-02 (génération ancrée sur les preuves)** : le cœur du bloc — d'autant plus fiable que les signaux US-03/US-04 évaluateur (Phase 2) sont déjà implémentés, sinon le contextualiseur aura peu de preuves externes à citer.
3. **US-03 (persistance/traçabilité)** en parallèle de 2, même logique que le stockage des scores.
4. **US-04 (avertissement automatisé)** : ajout simple une fois 2 et 3 en place, à ne pas oublier avant toute mise en avant publique des résultats.

---

## Phase 4 — Frontend

1. **US-01 (liste des articles suspects)** : premier écran utile dès que Phase 2 produit des scores.
2. **US-02 (détail des scores/justifications)** : consomme directement les données déjà tracées, pas de nouvelle logique métier.
3. **US-03 (mise en contexte affichée)** : n'apporte de valeur qu'une fois Phase 3 en place ; gérer explicitement le cas "pas encore traité".
4. **US-04 (lecture seule, hébergé sur Vercel — le local ne sert qu'au dev/test)** : contrainte à respecter dès le début du bloc plutôt qu'une fonctionnalité ajoutée à la fin (connexion Supabase externalisée dès la première ligne de code, déploiement Vercel mis en place tôt puisque c'est la version de référence, pas une cible secondaire).

---

## Phase 5 — Automatisation bout en bout

Une fois les 4 blocs individuellement fonctionnels : orchestrer scraper → évaluateur → contextualiseur en un unique workflow GitHub Actions planifié hebdomadairement (le frontend reste consulté à la demande sur Vercel, pas dans cette tâche). Correspond au point "automatiser le rapport hebdomadaire via GitHub Actions" de `fiche-projet-fake-news-trading.md`.

**Réalisé avec les blocs disponibles aujourd'hui**, pas d'attente de leur complétude totale : `.github/workflows/pipeline_hebdomadaire.yml` enchaîne scraper (US-06) → évaluateur (`run_evaluateur.py`) → contextualiseur (`run_contextualiseur.py`, génération réelle branchée sur Claude). Remplace l'ancien workflow `collecte_hebdomadaire.yml` (scraper seul), pour éviter deux jobs planifiés qui se chevaucheraient.

---

## Hors de ce plan (pour rappel)

- Le fine-tuning du modèle maison (BERT/RoBERTa/DistilBERT) sur les datasets publics (LIAR, FakeNewsNet, ISOT) + les labels US-07 accumulés : peut démarrer en parallèle dès que suffisamment de labels existent, mais c'est un chantier indépendant de ce plan.
- Le module de scoring d'impact marché (yfinance) et les stratégies de trading (backtrader/vectorbt) : étapes 4 et 5 de la feuille de route du projet, hors du périmètre "détection fake news" couvert ici.

---

## État d'avancement (mis à jour à chaque étape livrée, pour éviter que cette section ne se désynchronise silencieusement — cf. audits de suivi)

- **Phase 0** : terminée.
- **Phase 1 (scraper)** : US-01 (RSS), US-02 (Reddit), US-04 (normalisation), US-05 (déduplication), US-06 (GitHub Actions) terminées. US-03 (GDELT) non implémentée, décision assumée (cf. `doc/userstories_scraper.md` US-03 et les audits de suivi) — l'évaluateur a un repli par similarité prévu pour ce cas.
- **Phase 2 (évaluateur)** : US-08 (squelette du score composite), US-01 (réputation), US-03 (fact-checking, API Google Fact Check Tools), US-04 (source primaire, NER spaCy + SEC EDGAR full-text search), US-05 (style), US-07 (LLM bootstrap, Claude) terminées. US-02 (corroboration) et US-06 (décalage viral) restent à faire — tous deux bloqués sur la même brique de clustering (embeddings/GDELT), non implémentée.
- **Phase 3 (contextualiseur)** : US-01 (déclenchement), US-02 (génération réelle, Claude, ancrée sur les signaux évaluateur disponibles et validée par `validation.py`), US-03 (persistance) et US-04 (avertissement) terminées.
- **Phase 4 (frontend)** : US-01 (liste filtrable, paginée), US-02 (détail scores/justifications), US-03 (mise en contexte ou message explicite) et US-04 (lecture seule, auth conditionnelle, déploiement Vercel) terminées.
- **Phase 5 (automatisation)** : orchestration hebdomadaire scraper → évaluateur → contextualiseur en place (`pipeline_hebdomadaire.yml`), génération de mise en contexte réellement branchée.

**Prochaine étape concrète** : les 2 signaux évaluateur restants (US-02 corroboration, US-06 décalage viral) nécessitent tous deux la même brique de clustering (embeddings, cosinus sur titre+texte, seuil 0.8/0.85 cf. `userstories_évaluateur.md` US-02) — à construire une fois, puis brancher aux deux signaux. Avec 5 signaux désormais actifs (réputation, fact-checking, source primaire, style, LLM bootstrap), la génération de mise en contexte (déjà branchée) a davantage de matière factuelle vérifiable à citer (`preuve_id` fact-checking/source primaire notamment) qu'avec réputation/style seuls.

**Note pour la prochaine mise à jour de cette section** : elle s'est déjà désynchronisée une fois, dans le tour même qui a livré la Phase 4 (cf. audit de suivi `audit/audit-phase4-frontend.md`) — la mettre à jour fait partie de "finir" une phase, pas une étape séparée qu'on peut oublier.
