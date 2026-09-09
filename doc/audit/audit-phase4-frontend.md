# Audit de suivi — Phase 4 (Frontend) + glue évaluateur (run_evaluateur.py)

**Sujet** : première surface web du projet (FastAPI + Jinja2 + Vercel), premier passage sécurité web réel, + vérification des corrections du précédent audit.
**Date** : 2026-08-04.
**Scope exclu (délibérément)** : génération LLM réelle (US-02 contextualiseur), US-02 à US-07 évaluateur, US-03 scraper (GDELT), Phase 5.

---

## Resume De L'Audit

| Division | Statut | Synthese |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Le frontend couvre fidèlement US-01 à US-04, mais la toute nouvelle section "État d'avancement" du plan s'est déjà désynchronisée — dans le tour même qui a livré ce qu'elle prétend suivre. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Les corrections du dernier audit (journalisation) sont réelles et vérifiées. Mais un paramètre de requête non validé plante la route en 500, reproduit en direct. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Régression sur le pattern de dégradation des tests : la suite entière refuse de se collecter sans `DATABASE_URL`, plus seulement les tests DB qui "skip" proprement comme avant. |
| Cybersécurité Offensive (Sherlock Holmes) | 🟢 OK | Premier passage sécurité web du projet : XSS testé activement avec 3 payloads différents (titre, domaine, justification) — tous neutralisés par l'échappement Jinja2. Authentification correctement implémentée (comparaison à temps constant). |

**Totaux normalisés** : Critical **0** · High **0** · Medium **4** · Low **2**.

**Sur les corrections du dernier audit** : les deux Medium (journalisation `declenchement.py`, `reddit.py`) sont confirmés corrigés — code relu et tests dédiés ré-exécutés indépendamment, 60/60 passent avec la base configurée.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | app.py routes vs US-01/02/03/04 frontend | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | userstories_frontend.md vs app.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | plan_implementation.md "État d'avancement" | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| A11y/UX Checker | templates/*.html | 0 | 0 | 0 | 1 | AUDIT_FAIL (low) |
| Clean Code Auditor | run_evaluateur.py, app.py | 0 | 0 | 0 | 1 | AUDIT_FAIL (low) |
| Fail-Loud Auditor | app.py (date_min/date_max) | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Test Quality Auditor | test_frontend.py, test_run_evaluateur.py | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium — régression) |
| Mutation/Saboteur Auditor | app.py, run_evaluateur.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | frontend/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | frontend/, api/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | app.py (requête liste) | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Architecture Consistency Auditor | requirements.txt, vercel.json | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | contenu RSS/Reddit affiché | 0 | 0 | 0 | 0 | AUDIT_PASS — testé activement, pas seulement lu |
| SAST Scanner | app.py, templates/*.html | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | requirements.txt | 0 | 0 | 0 | 0 | Rien de nouveau (déjà couvert précédemment) |
| Privacy/Exfiltration Auditor | app.py | 0 | 0 | 0 | 0 | AUDIT_PASS |

---

## Matrice De Couverture

| Exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| US-01 frontend : liste filtrable, seuil par défaut, mode "tous" | app.py:45-83 | Testé (6 tests) + curl en direct contre données réelles | ✅ Conforme |
| US-01 frontend : `non_évaluable` n'apparaît jamais | app.py:61 | test_liste_masque_toujours_les_articles_non_evaluables | ✅ Conforme |
| US-02 frontend : sous-scores, poids, justification, signal exclu = "non applicable" | detail.html:16-26 | test_detail_affiche_signal_exclu_comme_non_applicable | ✅ Conforme |
| US-03 frontend : mise en contexte ou message explicite | detail.html:34-47 | 2 tests (avec/sans contexte) | ✅ Conforme |
| US-04 frontend : lecture seule stricte | app.py (aucune route d'écriture) | Vérifié par lecture intégrale : zéro `POST`/`PUT`/`DELETE` | ✅ Conforme |
| US-04 frontend : auth conditionnelle à FRONTEND_PASSWORD | app.py:30-37 | 2 tests + vérification manuelle du timing-safe compare | ✅ Conforme |
| US-04 frontend : avertissement visible sur chaque page | base.html:22 | test_avertissement_visible_sur_la_liste_et_le_detail | ✅ Conforme |
| Pas de gdelt_event_id ni signal fabriqué (US-02-07) | run_evaluateur.py | Lecture intégrale : seul "reputation" apparaît | ✅ Confirmé honnête |
| Section "État d'avancement" à jour | plan_implementation.md:106 | "Phases 4, 5 : non commencées" alors que Phase 4 est livrée | 🔴 Déjà désynchronisée |

---

## Top Findings

- **Medium (Confirmé, reproduit)** `src/fakenews/frontend/app.py:49-50,64-67` — `date_min`/`date_max` sont acceptés en `str` libre et injectés directement dans la clause `WHERE` sans validation. Un paramètre malformé (`?date_min=n-importe-quoi`) fait planter la route en 500 (`sqlalchemy.exc.DataError` / `psycopg2.errors.InvalidDatetimeFormat`), reproduit en direct par une vraie requête HTTP. Pas une faille de sécurité (pas d'injection, la requête paramétrée protège contre ça), mais une entrée utilisateur non fiable qui casse la route au lieu de répondre 400.
- **Medium (Confirmé, régression)** `tests/test_frontend.py`, `tests/test_run_evaluateur.py` — l'un et l'autre importent (transitivement) `fakenews.db`, qui exige `DATABASE_URL` **au chargement du module**. Résultat : sans `DATABASE_URL` (même variable distincte de `TEST_DATABASE_URL`), la collecte pytest échoue entièrement (`Interrupted: 2 errors during collection`), et plus aucun test ne tourne — y compris les tests 100% purs sans DB (`test_normalisation.py`, `test_score.py`...). C'est une régression du pattern établi et validé dans l'audit précédent ("sans TEST_DATABASE_URL, 40 passent + 6 skip proprement") : maintenant, sans `DATABASE_URL`, c'est 0 test qui tourne.
- **Medium (Corroboré)** `src/fakenews/frontend/app.py:61-70` — la requête de la liste n'a ni `LIMIT` ni pagination. Sans impact aujourd'hui (289 articles), mais en tension directe avec l'ambition documentée du projet ("aucune limite de volume n'est imposée arbitrairement", déjà signalé pour la collecte dans un audit précédent — même thème, nouvelle occurrence côté lecture).
- **Medium (Écart documentaire, ironique)** `doc/plan_implementation.md:106` — "Phases 4, 5 : non commencées", écrit pour éviter exactement ce genre de désynchronisation (cf. le titre de la section elle-même, ligne 100), déjà faux : Phase 4 est le sujet même de cet audit.
- **Low** Avertissement de dépréciation `starlette.testclient` sur `httpx` (remplaçant `httpx2` existe réellement sur PyPI, vérifié) — pas urgent, TestClient fonctionne toujours.
- **Low (prospectif)** `src/fakenews/evaluateur/run_evaluateur.py:32` — `POIDS_PAR_DEFAUT[signal]` (accès direct, pas `.get()`) lèvera une `KeyError` si un futur signal ajouté à `sous_scores` n'a pas d'entrée dans `POIDS_PAR_DEFAUT`. Aucun impact aujourd'hui (seul "reputation" y figure, et il est bien dans le barème), mais un piège pour la prochaine personne qui ajoutera US-02 à US-07.

---

## Details Par Division

### Division Métier (Anton Ego)

Les quatre user stories du frontend sont honorées avec une rigueur que je ne peux pas leur reprocher — jusqu'à la dernière ligne du plan d'implémentation, qui, elle, ment déjà.

- **Medium** : DOC-1 (ci-dessus).

### Division Qualité (Gordon Ramsay)

Le service a progressé — les deux plats de la dernière fois (journalisation) reviennent nickel, je les ai vérifiés moi-même. Mais on a laissé un client planter la salle avec une date mal formée, et pire : on a cassé le signal d'alarme lui-même (la suite de tests) pour quiconque n'a pas la base sous la main.

- **Medium** : FAIL-1 (date_min/date_max, 500), TEST-1 (régression skip).

### Division Architecture (Steve Jobs)

- **Medium** : SRE-1 (pas de pagination).
- Rien d'autre — la couche frontend est propre, ne dépend d'aucun module `scraper/`, communique uniquement via le schéma de données. `vercel.json`/`api/index.py` sont cohérents avec la topologie déjà décidée dans `architecture.md`.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : c'est la première fois que ce projet expose une vraie surface web, et c'est la première fois que je peux tester une hypothèse de XSS au lieu de la spéculer. Trois payloads (`<script>`, `<img onerror>`, `<svg onload>`) injectés dans le titre, le domaine et la justification d'un article — les trois ressortent échappés en HTML entities dans la réponse HTTP réelle. L'authentification compare le mot de passe avec `secrets.compare_digest`, la bonne pratique contre les attaques temporelles. Rien à red-teamer de plus sur ce périmètre.

---

## Details Par Sous-Audit

### Business Logic Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : les 4 user stories frontend correspondent trait pour trait à leurs critères d'acceptation, vérifié par test ET par requête HTTP réelle contre les 289 vrais articles collectés.

### Requirements Compliance Auditor
- **Verdict** : AUDIT_PASS — cf. Matrice De Couverture.

### Doc-Sync Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : DOC-1.
- **Points conformes** : le reste de `plan_implementation.md` (choix techniques, séquencement Phase 2/3) reste synchronisé avec le code livré.

### A11y/UX Checker
- **Verdict** : AUDIT_FAIL (Low)
- **Findings** : `liste.html`/`detail.html` n'ont pas d'attributs `aria-*` ni de `<label for="...">` explicitement liés par `id` (liaison implicite par imbrication seulement) — fonctionnel mais fragile pour les lecteurs d'écran. Faible priorité vu le stade du projet (prototype solo), mais réel.
- **Points conformes** : structure sémantique correcte par ailleurs (`<table>`, `<thead>`, vrais boutons, `<label>` imbriqués).

### Clean Code Auditor
- **Verdict** : AUDIT_FAIL (Low)
- **Findings** : run_evaluateur.py:32 (accès direct au lieu de `.get()`, ci-dessus).
- **Points conformes** : `app.py` reste court et lisible malgré deux routes ; pas de duplication entre `liste_articles`/`detail_article`.

### Fail-Loud Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : date_min/date_max non validés → 500 (ci-dessus), reproduit en direct.
- **Points conformes** : la session par requête (`with SessionLocal() as session`) isole bien l'échec — vérifié en direct qu'une requête suivante sur une session fraîche répond normalement (200) après le crash, pas de corruption de pool.

### Test Quality Auditor
- **Verdict** : AUDIT_FAIL (Medium — régression, pas un défaut des tests eux-mêmes)
- **Findings** : TEST-1 (collecte pytest interrompue sans `DATABASE_URL`, ci-dessus).
- **Points conformes** : les tests eux-mêmes, une fois collectés, sont solides — `test_frontend.py` couvre le XSS implicitement (échappement Jinja2 par défaut dans le moteur de rendu utilisé par tous les tests), l'auth, le mode "tous", le 404 ; `test_run_evaluateur.py` vérifie la forme exacte persistée (`sous_scores`, `poids`) contre le schéma réel.

### Mutation/Saboteur Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : raisonnement de mutation sur `liste_articles` (inverser `Score.non_evaluable.is_(False)`, retirer le tri, changer `>=` en `>`) — chaque mutation ferait échouer au moins un test existant.

### Layer Enforcer
- **Verdict** : AUDIT_PASS
- **Points conformes** : `frontend/` ne lit que via SQLAlchemy/le schéma partagé, aucun import direct de `scraper/` ni logique métier dupliquée depuis `evaluateur/`/`contextualiseur/` (réutilise seulement leurs constantes exportées, `SEUIL_PAR_DEFAUT`, `AVERTISSEMENT`).

### YAGNI Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : pas de SPA, pas de framework CSS, pas d'abstraction de templating au-delà de `base.html` — conforme à la décision "commencer simple" de `architecture.md`.

### SRE/Performance Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : SRE-1 (pas de pagination, ci-dessus).
- **Points conformes** : pas de boucle Python coûteuse, la logique de filtrage est entièrement déléguée à la requête SQL (pas de filtrage en mémoire après coup).

### Architecture Consistency Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : `requirements.txt` reflète exactement le choix technique documenté (FastAPI + Jinja2, `plan_implementation.md:22`) ; `vercel.json` + `api/index.py` correspondent à la topologie de déploiement décidée dans `architecture.md`. Note : `.env.example` documente désormais correctement la distinction pooler (frontend serverless) vs connexion directe (jobs batch) — un risque identifié dans un audit antérieur, maintenant traité en documentation (pas encore testable sans vraie instance Supabase, cf. Limites).

### Contextual Threat Analyst
- **Verdict** : AUDIT_PASS
- **Points conformes** : le scénario redouté (contenu adversarial d'une source de désinformation affiché sans échappement) a été testé activement, pas seulement raisonné — payloads XSS dans 3 champs distincts, tous neutralisés.

### SAST Scanner
- **Verdict** : AUDIT_PASS
- **Points conformes** : XSS testé et écarté (ci-dessus). Pas d'injection SQL (ORM paramétré partout, y compris pour `date_min`/`date_max` — le bug de ces derniers est un crash, pas une injection). Comparaison de mot de passe à temps constant.

### Supply Chain & Artifact Auditor
- **Verdict** : rien de nouveau (dépendances toujours non plafonnées, déjà signalé, pas re-décompté ici).

### Privacy/Exfiltration Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : aucune nouvelle fuite de donnée — le frontend n'expose que ce qui est déjà en base, en lecture seule, sans télémétrie ni appel externe.

---

## Points Conformes

- XSS testé activement (3 payloads, 3 champs différents) contre une vraie requête HTTP — aucun ne survit à l'échappement Jinja2 par défaut.
- Authentification HTTP Basic correctement implémentée : `secrets.compare_digest`, gated par `FRONTEND_PASSWORD`, comportement vérifié à la fois par test et par relecture indépendante.
- Isolation de session confirmée : un crash sur une requête ne corrompt pas les requêtes suivantes.
- `run_evaluateur.py` honnête : aucun signal fabriqué pour US-02 à 07, vérifié par lecture intégrale.
- Les deux corrections Medium de l'audit précédent (journalisation `declenchement.py`/`reddit.py`) sont réelles, re-testées indépendamment.
- 60/60 tests passent quand la base est configurée.
- `.env.example` documente maintenant la distinction pooler/connexion directe identifiée dans un audit antérieur.

## Limites De Verification

- Aucune instance Supabase ni compte Vercel réels n'existent — `vercel.json`/`api/index.py` sont syntaxiquement valides et cohérents avec la doc, mais un déploiement réel n'a pas pu être testé (limite déjà documentée dans les audits précédents, toujours vraie).
- Le test XSS a couvert les champs `titre`, `domaine_source` et la `raison` d'un sous-score — pas systématiquement tous les champs texte libre (`contenu` de l'article, `explication`/`sources_utilisees` de `mise_en_contexte`) ; ceux-ci passent par le même mécanisme d'échappement Jinja2 par défaut, donc le risque résiduel est jugé faible mais n'a pas été testé un par un.
- Commandes exécutées : suite `pytest` avec et sans `DATABASE_URL`/`TEST_DATABASE_URL` (régression confirmée) ; script Python autonome injectant 3 payloads XSS et vérifiant leur échappement via `TestClient` réel (données nettoyées après coup par `session.rollback()`, rien persisté) ; requête HTTP réelle avec `date_min` malformé (500 confirmé, reproduit deux fois avec et sans `raise_server_exceptions` pour capturer le type d'exception exact) ; vérification de l'isolation de session (requête suivante toujours fonctionnelle) ; `pip index versions httpx2` pour confirmer que le remplaçant suggéré par l'avertissement de dépréciation existe réellement. Aucune commande destructive ; aucune donnée de test n'a persisté au-delà de la vérification.
