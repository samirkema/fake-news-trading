# Audit de suivi — Fin Phase 1 (scraper) + Début Phase 2 (évaluateur)

**Sujet** : delta depuis `audit/audit-phase0-phase1-us01.md` — US-02/US-05/US-06 scraper, US-08/US-01 évaluateur, refactor normalisation/persistance, 31 nouveaux tests.
**Date** : 2026-08-04.
**Scope exclu (délibérément, à ne pas compter comme manquant)** : US-03 scraper (GDELT), US-02 à US-07 évaluateur (sauf US-01), Phases 3/4/5 (contextualiseur, frontend, orchestration bout en bout).

---

## Resume De L'Audit

| Division | Statut | Synthese |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | Un bug de logique métier confirmé et reproduit : la déduplication par hash de contenu détruit silencieusement l'information de republication multi-sources dont le signal de corroboration (Phase 2, US-02 évaluateur) aura besoin. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Les 2 findings High de l'audit précédent sont corrigés et testés — bien joué. Mais la frontière `try/except` du collecteur Reddit est mal placée : elle protège l'appel réseau, pas la boucle de persistance qui suit. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Le code évaluateur (`score.py`) est cohérent avec le schéma DB de Phase 0, mais `architecture.md` documente encore une interface `evaluer(article)` à deux champs (`sous_scores` + `justifications`) que la DB et le code ont déjà fusionnés en un seul. |
| Cybersécurité Offensive (Sherlock Holmes) | 🟡 Avertissement | `.gitignore` manquant de l'audit précédent est corrigé et vérifié. Dépendances toujours non plafonnées (déjà signalé, pas encore traité). |

**Totaux normalisés** : Critical **0** · High **2** · Medium **6** · Low **2**.

**Comparaison avec l'audit précédent** : 2 des 3 High précédents (timeout réseau absent, logique `bozo`/`entries`) sont **corrigés et vérifiés** — l'un par ré-exécution en direct, l'autre par un test de non-régression qui reproduit exactement le bug initial. Le 3e (zéro test) est en grande partie traité : 31 tests réels, pas cosmétiques — mais avec un angle mort précis, qui est justement là où le nouveau bug High a été trouvé.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | persistance.py, reddit.py, score.py | 0 | 1 | 0 | 0 | AUDIT_FAIL (high) |
| Requirements Compliance Auditor | US-02/05/06 scraper, US-08/01 évaluateur vs code | 0 | 0 | 0 | 0 | AUDIT_PASS (voir matrice) |
| Doc-Sync Auditor | architecture.md, plan_implementation.md vs code | 0 | 0 | 2 | 1 | AUDIT_FAIL (medium) |
| A11y/UX Checker | — | — | — | — | — | Non applicable |
| Clean Code Auditor | reddit.py, reputation.py | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Fail-Loud Auditor | reddit.py | 0 | 1 | 0 | 0 | AUDIT_FAIL (high) |
| Test Quality Auditor | tests/ (31 tests) | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium, net progrès) |
| Mutation/Saboteur Auditor | score.py, reputation.py, normalisation.py | 0 | 0 | 0 | 0 | AUDIT_PASS (tests résistent aux mutations testées) |
| Layer Enforcer | evaluateur/, scraper/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | tout le nouveau code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | persistance.py, sources_reddit.py | 0 | 0 | 2 | 0 | AUDIT_FAIL (medium) |
| Architecture Consistency Auditor | architecture.md vs score.py/schéma DB | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Contextual Threat Analyst | contenu Reddit stocké | 0 | 0 | 0 | 0 | Corrobore un finding déjà ouvert (cf. Limites) |
| SAST Scanner | reddit.py, persistance.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | requirements.txt, .gitignore | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium, 1 fix vérifié) |
| Privacy/Exfiltration Auditor | reddit.py (auteur) | 0 | 0 | 0 | 0 | AUDIT_PASS (limite déjà assumée par le projet) |

---

## Matrice De Couverture

| Exigence | Fichier(s) requis | Preuve implémentation | Statut |
| --- | --- | --- | --- |
| US-02 scraper : Reddit, champs requis | doc/userstories_scraper.md:25-34 | reddit.py:25-49, testé (test_reddit.py, 5 tests) | ✅ Conforme (non testé en conditions réelles, pas de credentials — cf. Limites) |
| US-05 scraper : dédup URL et/ou hash + MAJ métadonnées volatiles | doc/userstories_scraper.md:71-73 | persistance.py:11-32 | 🔴 Non conforme à l'esprit : le "ou" du hash collapse des republications légitimes multi-domaines (finding MET-1) |
| US-06 scraper : exécution planifiée + journalisation par source | doc/userstories_scraper.md:83-85 | .github/workflows/collecte_hebdomadaire.yml, logs stdout par source (rss.py, reddit.py) | 🟡 Conforme si "journalise" = logs de run GitHub Actions (éphémères) — pas de table de logs persistante (choix d'interprétation, pas un défaut, cf. Limites) |
| US-08 évaluateur : moyenne pondérée, garde-fou non_évaluable | doc/userstories_évaluateur.md:116-120 | score.py:15-45, testé (test_score.py, 6 tests dont le cas somme_poids=0) | ✅ Conforme, vérifié par test direct du cas limite |
| US-01 évaluateur : réputation fiable/douteux/inconnue | doc/userstories_évaluateur.md:7-17 | reputation.py:28-50, testé (test_reputation.py, 5 tests) | ✅ Conforme, y compris le traitement neutre de la satire |
| Interface evaluer(article) : sous_scores + justifications | doc/architecture.md:79-101 | score.py:15-16 | 🟡 Écart de nommage avec la doc (finding ARCH-1), cohérent avec le schéma DB réel |
| Pas de gdelt_event_id factice tant que GDELT n'est pas implémenté | (contrainte d'honnêteté demandée pour cet audit) | Aucune occurrence de "gdelt" dans score.py, reputation.py, reddit.py | ✅ Conforme — vérifié par lecture intégrale, rien d'inventé |

---

## Top Findings

- **High (Confirmé, reproduit)** `src/fakenews/scraper/persistance.py:15-22` — la clause `or_(url_canonique == ..., hash_contenu == ...)` traite deux articles au contenu identique mais publiés sur des **domaines différents** (URLs différentes) comme le même article : le second n'est jamais inséré, seules ses métadonnées écrasent celles du premier. Reproduit en direct : deux insertions avec domaines et URLs distincts → une seule ligne en base. Cela détruit précisément l'information de republication multi-sources ("même dépêche wire republiée telle quelle", `doc/userstories_évaluateur.md:29`) dont le signal de corroboration (US-02 évaluateur, à venir) aura besoin pour compter les sources indépendantes.
- **High (Confirmé sur le code, [RISQUE] sur le déclencheur)** `src/fakenews/scraper/reddit.py:60-73` — le `try/except` ne couvre que `list(client.subreddit(...).new(...))` (ligne 61), pas la boucle de normalisation/persistance qui suit (lignes 67-73, hors du bloc protégé). Une exception dans `normaliser_submission` ou `enregistrer_ou_mettre_a_jour` pour un seul post interromprait la collecte Reddit pour tous les subreddits restants de la boucle — violation du principe "dégrader jamais bloquer" à un grain plus fin que ce que le code protège actuellement.
- **Medium (Écart documentaire)** `doc/architecture.md:79-101` vs `src/fakenews/evaluateur/score.py:15-16` — l'architecture documente deux champs séparés (`sous_scores` valeurs nues, `justifications` dict riche) ; le schéma DB de Phase 0 et maintenant le code évaluateur les ont fusionnés en un seul champ `sous_scores` au format riche. Le code est cohérent avec la DB réelle — c'est `architecture.md` qui n'a jamais été mis à jour après cette décision de Phase 0.
- **Medium (Corroboré)** `doc/plan_implementation.md:100-102` — "Prochaine étape concrète" toujours au niveau Phase 0/US-01 RSS, maintenant deux paliers en retard sur l'état réel (déjà signalé dans l'audit précédent, non corrigé depuis).
- **Medium (Confirmé)** `src/fakenews/scraper/sources_reddit.py:16` — `NB_POSTS_PAR_SUBREDDIT = 100` uniforme pour des subreddits à volume très hétérogène ; r/wallstreetbets peut dépasser 100 posts en quelques jours, risquant de manquer des posts plus anciens dans la fenêtre hebdomadaire. Aucun critère d'acceptation ne discute de cette limite.
- **Medium (Confirmé)** `src/fakenews/evaluateur/reputation.py:11-14` — `reuters.com` (utilisé comme `domaine_source` côté scraper avant repli, `sources_rss.py:28-36`) est absent de la liste `FIABLE`. Impact nul aujourd'hui (flux Reuters mort), mais illustre concrètement que la synchronisation manuelle entre les deux listes (documentée comme condition dans `reputation.py:8`) est déjà en défaut.
- **Medium (Corroboré, portée doublée)** `persistance.py:15-22` — pattern N+1 (une requête `SELECT` par entrée), déjà signalé dans l'audit précédent pour `rss.py` seul, maintenant partagé par `reddit.py` aussi.
- **Medium (Confirmé)** Aucun test n'exerce `enregistrer_ou_mettre_a_jour`, `collecter_rss` ou `collecter_reddit` contre une vraie session/DB. Les 31 tests couvrent bien les fonctions pures, mais le bug High MET-1 ci-dessus vit exactement dans la fonction non testée à cette frontière.
- **Low (Doc-Sync)** `doc/plan_implementation.md:11-24` — tableau des choix techniques n'inclut pas `pytest`, alors que 31 tests réels existent et que `pytest` est dans `requirements.txt`.

---

## Details Par Division

### Division Métier (Anton Ego)

Le scraper ne trahit plus la lettre de US-05 — il en trahit l'esprit. "Déduplication par URL canonique et/ou hash du contenu" a été lu comme "n'importe lequel des deux critères suffit à fusionner", sans jamais se demander si une identité de *contenu* entre deux *domaines* différents est une duplication à éliminer ou une corroboration à préserver. Le document voisin, `userstories_évaluateur.md`, répond pourtant explicitement à cette question ligne 29 : une dépêche wire republiée par plusieurs domaines doit être comptée, pas effacée.

- **High** : MET-1, `persistance.py:15-22` (détail ci-dessus).
- **Medium** : DOC-1 (interface `architecture.md`), DOC-2 (plan stale, corroboré).
- **Low** : DOC-3 (pytest absent du tableau technique).

### Division Qualité (Gordon Ramsay)

Les deux plats renvoyés au dernier service sont maintenant corrects — timeout et logique `bozo` fonctionnent et sont couverts par un test qui reproduit le bug d'origine, précisément ce qu'on attend d'une vraie correction plutôt que d'un pansement. Mais la frontière de gestion d'erreur de `reddit.py` a été posée au mauvais endroit.

- **High** : QUAL-1 (`reddit.py:60-73`, frontière try/except trop étroite).
- **Medium** : QUAL-2 (aucun test à la frontière DB, exactement où MET-1 a été trouvé).

### Division Architecture (Steve Jobs)

- **Medium** : ARCH-1 (`architecture.md` vs `score.py`, nommage de l'interface).
- **Medium** : ARCH-2 (N+1 corroboré, `persistance.py`, maintenant 2 appelants).

### Division Cybersécurité Offensive (Sherlock Holmes)

- **Résolu, vérifié** : `.gitignore` (SEC-1 de l'audit précédent) existe désormais et couvre `.env`, les venvs et les caches — vérifié par lecture directe.
- **Toujours ouvert** : dépendances non plafonnées dans `requirements.txt` (SEC-2 de l'audit précédent, non retraité depuis).
- Rien de nouveau côté injection/secrets : `reddit.py` et `persistance.py` passent tous deux par l'ORM paramétré ; credentials Reddit lus depuis l'environnement, jamais en dur.

---

## Details Par Sous-Audit

### Business Logic Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : MET-1.
- **Points conformes** : US-08 (`score.py`) et US-01 réputation (`reputation.py`) implémentent fidèlement leurs critères d'acceptation respectifs, y compris les cas limites (`somme_poids == 0`, domaine `None`, satire neutre).

### Requirements Compliance Auditor
- **Verdict** : AUDIT_PASS pour la lettre des critères testables (cf. Matrice De Couverture), avec une réserve forte sur MET-1 qui est un défaut de cohérence *inter*-user-stories (US-05 scraper vs US-02 évaluateur) plutôt qu'une violation d'un critère d'acceptation pris isolément — ce type d'écart est précisément ce qu'une revue user-story-par-user-story seule ne peut pas voir.
- **Points conformes** : GDELT (US-03 scraper) honnêtement absent, aucun `gdelt_event_id` inventé nulle part dans le code Phase 2.

### Doc-Sync Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : DOC-1, DOC-2 (corroboré), DOC-3.
- **Points conformes** : l'ordre d'implémentation de Phase 2 dans `plan_implementation.md:54-63` (US-08 puis US-01) correspond exactement à ce qui a été livré.

### A11y/UX Checker
- **Verdict** : Non applicable — aucun front-end dans ce delta.

### Clean Code Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : ARCH-3 (reputation.py:11-14, dérive `reuters.com`/`FIABLE`, classé ici plutôt qu'en doublon car c'est un défaut de duplication de données, pas de documentation).
- **Points conformes** : `reddit.py` et `rss.py` partagent maintenant `normalisation.py`/`persistance.py` sans duplication de logique — bon réflexe DRY suite au refactor.

### Fail-Loud Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : QUAL-1.
- **Points conformes** : `rss.py` journalise maintenant en `warning` (visible par défaut) le nombre d'entrées ignorées faute de date exploitable — corrige le finding Medium de l'audit précédent, vérifié en direct (NaturalNews : 31 ignorées, loggées).

### Test Quality Auditor
- **Verdict** : AUDIT_FAIL (Medium — net progrès depuis le High précédent)
- **Findings** : QUAL-2 (zéro test à la frontière DB).
- **Points conformes** : les 31 tests sont substantiels, pas cosmétiques — vérifié par raisonnement de mutation manuel sur `calculer_score_composite` (inversion d'opérateur, inversion de garde) et par une reproduction directe du bug `bozo`/`entries` de l'audit précédent comme test de non-régression (`test_rss.py:33-38`).

### Mutation/Saboteur Auditor
- **Verdict** : AUDIT_PASS pour les fonctions testées
- **Findings** : aucun pour `score.py`/`reputation.py`/`normalisation.py` — les mutations raisonnées (inversion d'opérateur `+=`→`-=`, inversion de garde `== 0`→`!= 0`, inversion d'appartenance de liste) sont toutes détectées par au moins un test existant.
- **Points conformes** : voir ci-dessus. Pour `persistance.py`, `collecter_rss`, `collecter_reddit` : sans objet, aucun test à muter (cf. Test Quality Auditor).

### Layer Enforcer
- **Verdict** : AUDIT_PASS
- **Points conformes** : `src/fakenews/evaluateur/` ne dépend d'aucun module de `src/fakenews/scraper/` (et vice versa) — la duplication volontaire de `reputation.py` (plutôt qu'un import) respecte le principe "pas d'appel direct entre les blocs".

### YAGNI Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : `run_scraper.py` regroupe RSS+Reddit sans introduire de framework d'orchestration prématuré ; pas d'abstraction spéculative dans `score.py`/`reputation.py`.

### SRE/Performance Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : ARCH-2 (N+1 corroboré), DOC-4 (`NB_POSTS_PAR_SUBREDDIT` non validé contre le volume réel).
- **Points conformes** : le timeout réseau (10s) de l'audit précédent est maintenant en place et vérifié en direct sur les 8 flux RSS réels.

### Architecture Consistency Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : ARCH-1.
- **Points conformes** : `reputation.py` et `score.py` sont mutuellement cohérents entre eux (le format de sortie de l'un correspond exactement à ce que l'autre attend en entrée), même s'ils divergent tous deux du diagramme `architecture.md`.

### Contextual Threat Analyst
- **Verdict** : corrobore un finding déjà ouvert, pas de nouveau scénario.
- **Findings** : le contenu Reddit (`selftext`, potentiellement du texte formaté Markdown/HTML échappé) est stocké brut par `reddit.py:29`, même limite déjà signalée pour le contenu RSS dans l'audit précédent (SEC-3, vecteur XSS stocké prospectif pour la Phase 4) — élargie à une deuxième source, pas un nouveau défaut.

### SAST Scanner
- **Verdict** : AUDIT_PASS
- **Points conformes** : `persistance.py` et `reddit.py` passent exclusivement par l'ORM SQLAlchemy paramétré ; aucune construction de requête par concaténation de chaîne trouvée dans le nouveau code.

### Supply Chain & Artifact Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : dépendances `requirements.txt` toujours non plafonnées/non verrouillées (SEC-2 de l'audit précédent, non retraité).
- **Points conformes** : `.gitignore` désormais présent et correct (SEC-1 résolu, vérifié par lecture).

### Privacy/Exfiltration Auditor
- **Verdict** : AUDIT_PASS (limite déjà assumée par le projet)
- **Findings** : aucun nouveau — `reddit.py:32` stocke le nom d'auteur Reddit (`auteur`), même catégorie de donnée déjà couverte par la limite de rétention documentée dans `architecture.md`.

---

## Points Conformes

- Les 2 findings High de l'audit précédent (timeout réseau, logique `bozo`/`entries`) sont corrigés et vérifiés — l'un en ré-exécutant le collecteur en direct contre les 8 flux RSS réels, l'autre par un test de non-régression qui reproduit le bug exact.
- Le finding Medium "drop silencieux d'entrées sans date" est corrigé — vérifié en direct, NaturalNews journalise maintenant `31 entrée(s) ignorée(s)` en `warning`.
- `.gitignore` (SEC-1) résolu, vérifié.
- 31 tests réels et substantiels, pas cosmétiques (vérifié par raisonnement de mutation).
- Aucun `gdelt_event_id` factice — le projet reste honnête sur ce qui n'est pas implémenté.
- `score.py` et `reputation.py` mutuellement cohérents, séparation de couches respectée entre scraper et évaluateur.
- Pas d'injection, pas de secret en dur dans le nouveau code.

## Limites De Verification

- US-02 Reddit (`reddit.py`) n'a pas pu être testée en conditions réelles — aucun credential Reddit (`REDDIT_CLIENT_ID`/`SECRET`) disponible dans cet environnement. Seule la logique pure de normalisation (`normaliser_submission`) a été testée, via un objet factice imitant l'interface PRAW.
- Le finding QUAL-1 (frontière try/except trop étroite dans `reddit.py`) est confirmé sur la structure du code, mais le scénario déclencheur exact (une soumission Reddit qui ferait planter `normaliser_submission`) n'a pas été reproduit — classé `[RISQUE]` pour cette partie.
- L'interprétation de "journalise le nombre d'articles collectés par source" (US-06 scraper) comme satisfaite par les logs stdout de GitHub Actions (éphémères, pas de table de logs persistante) est un choix d'interprétation documenté ici, pas un défaut confirmé — à trancher explicitement si une traçabilité à plus long terme est souhaitée.
- Le finding MET-1 a été reproduit contre la base de test locale (Postgres local, pas Supabase — aucune instance Supabase réelle n'existe, cf. audit précédent) ; la donnée de test insérée a été supprimée après vérification.
- Commandes exécutées : `pytest tests/ -q` (31 passed), reproduction directe de MET-1 par insertion de deux articles via `enregistrer_ou_mettre_a_jour` contre la base locale `fakenews_dev`, suivi d'un nettoyage (`DELETE`). Aucune commande destructive sur des données réelles (la base locale ne contient que des données de test collectées par ce projet lui-même).
