# Audit de suivi — Phase 5 (Automatisation bout en bout)

**Sujet** : orchestration scraper → évaluateur → contextualiseur en un job GitHub Actions unique, + vérification des 4 corrections du précédent audit.
**Date** : 2026-08-05.
**Scope exclu (délibérément)** : génération LLM réelle (US-02 contextualiseur), US-02 à US-07 évaluateur, US-03 scraper (GDELT) — inchangés depuis les audits précédents.

---

## Resume De L'Audit

| Division | Statut | Synthese |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | Le job hebdomadaire tel qu'écrit ne survivra probablement pas à sa première exécution réelle : la collecte Reddit plante tout le script si les identifiants ne sont pas configurés, et rien n'indique qu'ils le sont. |
| Qualité (Gordon Ramsay) | 🟢 OK | Les 4 corrections du dernier audit sont réelles, vérifiées indépendamment — connexion paresseuse, validation de dates, pagination, base de test dédiée propre. |
| Architecture (Steve Jobs) | 🔴 Bloquant | Même défaut que ci-dessus, vu sous l'angle architecture : le principe "dégrader, jamais bloquer" que le projet s'impose lui-même est violé exactement au point de couture que Phase 5 vient de créer (un step qui plante arrête tout le job GitHub Actions). |
| Cybersécurité Offensive (Sherlock Holmes) | 🟢 OK | Rien de nouveau à signaler — pas de nouvelle surface exposée par l'orchestration elle-même. |

**Totaux normalisés** : Critical **0** · High **1** · Medium **0** · Low **1**.

**Sur les 4 corrections du dernier audit** : toutes confirmées réelles par exécution indépendante — connexion DB paresseuse (import sans `DATABASE_URL` réussi, échec propre au premier appel), suite de tests complète (41 passent + 26 skip sans DB configurée ; 67 passent avec `TEST_DATABASE_URL=fakenews_test`), séparation `fakenews_test`/`fakenews_dev` vérifiée propre (0 ligne dans les 3 tables de `fakenews_test` avant les tests), section "État d'avancement" à jour.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | run_scraper.py / reddit.py, pipeline_hebdomadaire.yml | 0 | 1 | 0 | 0 | AUDIT_FAIL (high) |
| Requirements Compliance Auditor | Phase 5 vs plan_implementation.md | 0 | 0 | 0 | 0 | AUDIT_PASS (avec réserve, cf. ci-dessous) |
| Doc-Sync Auditor | plan_implementation.md Phase 5 + État d'avancement | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | — | — | — | — | — | Non applicable (pas de nouveau front-end) |
| Clean Code Auditor | run_contextualiseur.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | reddit.py:59 (via run_scraper.py) | 0 | 1 | 0 | 0 | AUDIT_FAIL (high — même défaut que Business Logic) |
| Test Quality Auditor | test_run_contextualiseur.py, tests date/pagination | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Mutation/Saboteur Auditor | run_contextualiseur.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | contextualiseur/run_contextualiseur.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | pipeline_hebdomadaire.yml | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | pipeline_hebdomadaire.yml (env au niveau job) | 0 | 0 | 0 | 1 | AUDIT_FAIL (low) |
| Architecture Consistency Auditor | "dégrader jamais bloquer" vs comportement réel | 0 | 1 | 0 | 0 | AUDIT_FAIL (high — même défaut, angle architecture) |
| Contextual Threat Analyst | run_contextualiseur.py | 0 | 0 | 0 | 0 | AUDIT_PASS — aucun contenu fabriqué, vérifié |
| SAST Scanner | run_contextualiseur.py, pipeline_hebdomadaire.yml | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | .github/workflows/ | 0 | 0 | 0 | 0 | AUDIT_PASS — un seul fichier de workflow, pas de doublon de cron |
| Privacy/Exfiltration Auditor | — | 0 | 0 | 0 | 0 | AUDIT_PASS |

---

## Matrice De Couverture

| Exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| Un seul workflow planifié (pas de doublon de cron) | .github/workflows/ | `ls` confirme un seul fichier (`pipeline_hebdomadaire.yml`), `collecte_hebdomadaire.yml` absent | ✅ Conforme |
| Orchestration scraper → évaluateur → contextualiseur en un job | pipeline_hebdomadaire.yml:26-36 | Lecture + reproduction locale des 3 commandes en séquence | 🔴 Le job tel qu'écrit ne va pas au bout si Reddit n'est pas configuré (cf. Top Findings) |
| run_contextualiseur.py n'invente rien (US-02 hors périmètre honnête) | run_contextualiseur.py | Lecture intégrale : aucun appel LLM, journalise l'absence de génération | ✅ Confirmé honnête |
| Correction 1 : date_min/date_max → 422 | app.py:70-71 | Test + reproduction indépendante | ✅ Confirmé |
| Correction 2 : tests sans DATABASE_URL | db.py | Import + premier appel testés indépendamment | ✅ Confirmé |
| Correction 3 : pagination | app.py:93-97, liste.html:38-44 | Test dédié, 67/67 passent | ✅ Confirmé |
| Correction 4 : doc à jour | plan_implementation.md:108-109 | Phase 4 et 5 correctement reflétées | ✅ Confirmé |
| Séparation fakenews_test / fakenews_dev | conftest.py, base locale | `fakenews_test` vérifiée à 0 ligne dans les 3 tables avant exécution | ✅ Confirmé propre |

---

## Top Findings

- **High (Confirmé, reproduit deux fois)** `src/fakenews/scraper/reddit.py:59` (via `run_scraper.py:20`) — `creer_client()` lit `os.environ["REDDIT_CLIENT_ID"]` sans filet, **en dehors** du `try/except` par subreddit qui protège le reste de la collecte Reddit. Si les identifiants Reddit ne sont pas configurés (aucune preuve dans ce projet qu'ils le soient — l'agent qui a construit ce pipeline ne peut pas créer de compte Reddit à la place de l'utilisateur), `run_scraper.py` plante avec une trace Python brute et un code de sortie 1, **après** que la collecte RSS a réussi. Reproduit deux fois en local (avec et sans le problème SSL de l'environnement de vérification, cf. Limites) : même `KeyError: 'REDDIT_CLIENT_ID'` à chaque fois. Dans le vrai workflow GitHub Actions, un step qui échoue arrête le job par défaut (pas de `continue-on-error` configuré) — l'évaluateur et le contextualiseur ne s'exécuteraient donc jamais. C'est exactement le scénario que "dégrader, jamais bloquer" (`doc/architecture.md`) est censé empêcher, et Phase 5 vient d'en élargir la portée : avant, un plantage Reddit n'affectait que la collecte Reddit ; maintenant, il emporte tout le pipeline hebdomadaire avec lui.
- **Low** `pipeline_hebdomadaire.yml:11-16` — les secrets Reddit sont déclarés au niveau du job (`env:` du job, pas du step), donc exposés aux étapes évaluateur et contextualiseur qui n'en ont pas besoin. Sans risque de sécurité concret (même job, même runner), mais imprécis — les scoper au step scraper uniquement documenterait mieux les dépendances réelles de chaque étape.

---

## Details Par Division

### Division Métier (Anton Ego)

Le contrat de Phase 5 — "orchestrer les blocs disponibles aujourd'hui" — est honoré dans l'intention et dans le code de chaque étape prise isolément. Mais un menu qui s'arrête au plat principal parce que l'entrée a mis le feu à la cuisine n'est pas un menu complet, et personne n'a vérifié que la cuisine ne prendrait pas feu.

- **High** : le plantage Reddit non isolé (ci-dessus), qui empêche le contrat même de Phase 5 (un pipeline qui va jusqu'au bout chaque semaine) de tenir.

### Division Qualité (Gordon Ramsay)

Les quatre correctifs du dernier service sont bons — je les ai goûtés moi-même, indépendamment, base de test propre à l'appui. Mais on vient d'assembler trois plats sur un seul plateau sans vérifier qu'un des trois ne renverse pas les deux autres en tombant.

- Rien à signaler en propre ici au-delà du finding déjà classé Fail-Loud/Business Logic.

### Division Architecture (Steve Jobs)

Le principe que ce projet s'est donné lui-même — dégrader, jamais bloquer — n'est pas juste une bonne idée écrite dans un fichier `architecture.md` : c'est un contrat que le code doit honorer à chaque frontière. `reddit.py:59` est exactement une de ces frontières, et Phase 5 vient d'augmenter le prix de la violer : ce n'était qu'une dégradation locale hier, c'est un blocage du pipeline entier aujourd'hui.

- **High** : même défaut, vu comme une violation de principe architectural plutôt qu'un bug isolé.
- **Low** : portée des secrets au niveau job plutôt que step.

### Division Cybersécurité Offensive (Sherlock Holmes)

Rien à instruire. L'orchestration n'introduit aucune nouvelle entrée non fiable, aucun nouvel appel réseau non déjà audité, aucun secret nouveau. Élémentaire : trois scripts déjà audités, enchaînés, ne créent pas de nouvelle surface d'attaque du simple fait d'être enchaînés.

---

## Details Par Sous-Audit

### Business Logic Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : plantage Reddit non isolé (ci-dessus).
- **Points conformes** : la collecte RSS, elle, dégrade correctement par source (vérifié dans la même exécution : Onion et Babylon Bee collectés avec succès malgré Reuters/Legorafi en échec, avant que Reddit ne fasse tout planter).

### Requirements Compliance Auditor
- **Verdict** : AUDIT_PASS avec réserve — chaque étape individuelle respecte ses propres critères d'acceptation déjà audités ; c'est la composition des trois en un seul job qui introduit un nouveau mode d'échec non couvert par aucune user story existante (aucune ne dit explicitement "un step ne doit pas empêcher les suivants").
- **Points conformes** : `run_contextualiseur.py` respecte fidèlement US-01 contextualiseur (déclenchement) réutilisé tel quel, sans dupliquer sa logique.

### Doc-Sync Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : la nouvelle section Phase 5 de `plan_implementation.md` décrit fidèlement ce qui a été livré (orchestration réelle, contextualiseur limité à la sélection) — pas d'écart trouvé, y compris sur le remplacement de l'ancien workflow.

### A11y/UX Checker
- **Verdict** : Non applicable.

### Clean Code Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : `run_contextualiseur.py` est court, sa docstring explique honnêtement sa propre limite (pas de génération), pas de duplication avec `declenchement.py`.

### Fail-Loud Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : le plantage n'est pas le problème ici (planter fort sur une config manquante est en général une bonne pratique Fail-Loud) — le problème est que ce plantage fort n'est **pas isolé** de la suite du pipeline. Fail-loud au bon endroit (le module Reddit) mais avec un rayon d'explosion qui déborde sur des blocs qui n'ont rien à voir.
- **Points conformes** : `run_evaluateur.py` et `run_contextualiseur.py` n'ont aucune dépendance externe non gérée — testé en isolant leur exécution, aucun des deux n'a planté.

### Test Quality Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : `test_run_contextualiseur.py` (3 tests) couvre les trois cas utiles (au-dessus du seuil, en-dessous, déjà traité) sans être cosmétique. Les nouveaux tests `test_frontend.py` (date malformée, date valide, pagination) sont substantiels — vérifié par ré-exécution indépendante, 67/67 passent.
- **Limite notée** : aucun test n'exerce le scénario exact trouvé ici (`run_scraper.py` avec Reddit non configuré) — logique, puisque les tests de `reddit.py` utilisent un client factice injecté (`client=...`), qui contourne justement `creer_client()` et donc ce chemin de code précis.

### Mutation/Saboteur Auditor
- **Verdict** : AUDIT_PASS pour ce qui est testé
- **Points conformes** : raisonnement de mutation sur `selectionner_articles_a_traiter` (inverser la condition `MiseEnContexte.id.is_(None)`, retirer l'appel à `articles_a_traiter`) — chaque mutation ferait échouer un test existant.

### Layer Enforcer
- **Verdict** : AUDIT_PASS
- **Points conformes** : `run_contextualiseur.py` importe `declenchement.py` (même bloc) mais rien de `scraper/` ni `evaluateur/` au-delà du schéma de données partagé — cohérent avec le reste du projet.

### YAGNI Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : le workflow reste un seul job simple, pas de matrice de jobs ni d'abstraction d'orchestration prématurée pour un pipeline de 3 étapes.

### SRE/Performance Auditor
- **Verdict** : AUDIT_FAIL (Low)
- **Findings** : secrets Reddit exposés à tous les steps du job (ci-dessus) — hygiène, pas un risque réel dans ce contexte.
- **Points conformes** : pas de step redondant, pas de ré-installation inutile des dépendances.

### Architecture Consistency Auditor
- **Verdict** : AUDIT_FAIL (High)
- **Findings** : violation du principe "dégrader jamais bloquer" au point de couture introduit par Phase 5 (ci-dessus, détaillé dans Business Logic Auditor).
- **Points conformes** : la topologie du job (checkout → setup Python → install → 3 steps séquentiels) correspond exactement à ce que `plan_implementation.md` et `architecture.md` décrivent.

### Contextual Threat Analyst
- **Verdict** : AUDIT_PASS
- **Points conformes** : scénario envisagé (le contextualiseur invente une mise en contexte plausible mais fausse pour combler l'absence de LLM) — testé par lecture intégrale du code, ne se produit pas. Le script journalise honnêtement son inaction plutôt que de fabriquer un résultat.

### SAST Scanner
- **Verdict** : AUDIT_PASS
- **Points conformes** : rien de nouveau à ce niveau — `run_contextualiseur.py` ne fait que des lectures ORM paramétrées.

### Supply Chain & Artifact Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : vérifié qu'un seul fichier de workflow existe (`ls .github/workflows/`) — pas de risque de double exécution planifiée qui doublonnerait la collecte ou userait le quota Actions pour rien.

### Privacy/Exfiltration Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : aucune nouvelle donnée personnelle introduite par l'orchestration elle-même.

---

## Points Conformes

- Les 4 corrections de l'audit précédent sont réelles, vérifiées indépendamment (connexion paresseuse, validation de date, pagination, doc à jour).
- Séparation `fakenews_test`/`fakenews_dev` vérifiée propre (0 ligne dans les 3 tables de `fakenews_test` avant exécution des tests).
- Un seul fichier de workflow planifié — pas de doublon de cron.
- `run_contextualiseur.py` honnête : aucun contenu fabriqué, journalise clairement son inaction.
- La collecte RSS dégrade correctement par source, même en situation réelle dégradée (SSL local, flux bloqués) — vérifié en direct.
- 67/67 tests passent contre la base de test dédiée.

## Limites De Verification

- Le job GitHub Actions réel n'a pas pu être exécuté (pas de dépôt GitHub ni de secrets configurés dans cet environnement) — le comportement "un step qui échoue arrête le job" est un fait documenté et standard de GitHub Actions (pas de `continue-on-error` dans le fichier), pas quelque chose que j'ai pu observer en conditions réelles CI.
- La reproduction du plantage Reddit a d'abord été polluée par un problème sans rapport : l'environnement Python de vérification (fraîchement créé pour cet audit) n'avait pas de certificats SSL configurés (artefact connu des installations python.org sur macOS, déjà rencontré et documenté plus tôt dans ce projet), faisant échouer tous les flux RSS pour une raison différente. Isolé et corrigé (`SSL_CERT_FILE` pointé vers `certifi`) avant de confirmer que le `KeyError: 'REDDIT_CLIENT_ID'` est bien la cause réelle et unique du code de sortie 1, indépendante de cet artefact.
- Aucune instance Supabase réelle n'existe (limite déjà documentée dans tous les audits précédents) — tout testé contre Postgres local.
- Commandes exécutées : `ls .github/workflows/` (un seul fichier confirmé) ; import de `fakenews.db` sans `DATABASE_URL` puis premier appel (échec propre confirmé) ; suite `pytest` complète sans variable DB (41 passed, 26 skipped) puis avec `TEST_DATABASE_URL=fakenews_test` (67 passed) ; requête SQL directe confirmant `fakenews_test` vide avant tests ; exécution séquentielle réelle des 3 commandes du workflow contre `fakenews_dev`, deux fois (avec puis sans l'artefact SSL local), reproduisant à chaque fois le plantage Reddit avec la même trace. Aucune commande destructive ; les articles RSS réellement collectés pendant cette vérification (Onion, Babylon Bee) sont des données légitimes, pas nettoyées (cohérent avec l'usage établi de `fakenews_dev` comme base d'exploration manuelle).
