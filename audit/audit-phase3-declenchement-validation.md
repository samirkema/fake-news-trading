# Audit de suivi — Corrections MET-1/QUAL-1 + Début Phase 3 (contextualiseur)

**Sujet** : vérification active des 2 corrections High du précédent audit, + nouveau code Phase 3 (déclenchement, validation preuve_id, persistance, avertissement).
**Date** : 2026-08-04.
**Scope exclu (délibérément, à ne pas compter comme manquant)** : génération réelle par LLM (US-02 contextualiseur, cœur du bloc — fournisseur non choisi, hors périmètre documenté) ; US-02 à US-07 évaluateur ; US-03 scraper (GDELT) ; Phases 4/5.

---

## Resume De L'Audit

| Division | Statut | Synthese |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | `declenchement.py` respecte 3 des 4 critères d'acceptation testables de US-01 contextualiseur, mais omet la journalisation explicitement exigée par le 4e. |
| Qualité (Gordon Ramsay) | 🟢 OK | Les deux corrections High du dernier audit (MET-1, QUAL-1) sont réelles, vérifiées indépendamment — pas de la simple déclaration. Nouveaux tests solides, pas cosmétiques. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Incohérence d'observabilité entre les deux collecteurs scraper : `rss.py` élève les entrées ignorées en `warning`, `reddit.py` ne le fait pas pour son équivalent (`ignores`), introduit dans le même correctif que QUAL-1. |
| Cybersécurité Offensive (Sherlock Holmes) | 🟢 OK | Aucun contenu LLM fabriqué, aucune nouvelle surface d'attaque dans le code Phase 3 (fonctions pures + écriture ORM). |

**Totaux normalisés** : Critical **0** · High **0** · Medium **2** · Low **2**.

**Sur les corrections demandées** : MET-1 et QUAL-1 sont **confirmées corrigées**, vérifiées deux fois — une fois via la suite de tests existante (lancée indépendamment, avec et sans `TEST_DATABASE_URL`), une fois via une reproduction manuelle écrite pour cet audit, indépendante du code de test déjà présent (pour écarter l'hypothèse d'un test qui passerait à tort). Aucun High cette fois-ci — net progrès sur les deux audits précédents.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | declenchement.py, validation.py | 0 | 0 | 1 | 1 | AUDIT_FAIL (medium) |
| Requirements Compliance Auditor | US-01/02/03/04 contextualiseur vs code | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Doc-Sync Auditor | plan_implementation.md vs état réel | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium, corroboré/aggravé) |
| A11y/UX Checker | — | — | — | — | — | Non applicable |
| Clean Code Auditor | contextualiseur/, persistance.py corrigé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | reddit.py corrigé | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Test Quality Auditor | 15 nouveaux tests | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Mutation/Saboteur Auditor | validation.py, declenchement.py | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | contextualiseur/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | tout le nouveau code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | — | 0 | 0 | 0 | 0 | AUDIT_PASS (rien de nouveau à ce niveau) |
| Architecture Consistency Auditor | rss.py vs reddit.py (observabilité) | 0 | 0 | 1 | 0 | AUDIT_FAIL (medium) |
| Contextual Threat Analyst | contextualiseur/ | 0 | 0 | 0 | 0 | AUDIT_PASS (rien à signaler, pas d'I/O externe) |
| SAST Scanner | contextualiseur/ | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | — | 0 | 0 | 0 | 0 | Rien de nouveau (déjà couvert par l'audit précédent) |
| Privacy/Exfiltration Auditor | contextualiseur/ | 0 | 0 | 0 | 0 | AUDIT_PASS |

---

## Matrice De Couverture

| Exigence | Fichier(s) requis | Preuve implémentation | Statut |
| --- | --- | --- | --- |
| Correction MET-1 (dédup cross-domaine) | scraper/persistance.py | Reproduit indépendamment contre la vraie base : 2 domaines différents, même hash → 2 lignes | ✅ Confirmé corrigé |
| Correction QUAL-1 (frontière try/except) | scraper/reddit.py:70-76 | tests/test_reddit_resilience.py, relu et exécuté | ✅ Confirmé corrigé |
| US-01 contextualiseur : seuil configurable, défaut 60 | declenchement.py:4,8 | test_declenchement.py | ✅ Conforme (avec une nuance `>=` vs "dépasse", cf. finding MET-2) |
| US-01 contextualiseur : non_évaluable = sous le seuil | declenchement.py:19 | test_article_non_evaluable_traite_comme_sous_le_seuil | ✅ Conforme, testé |
| US-01 contextualiseur : plafond + priorisation décroissante | declenchement.py:22-23 | test_plafond_garde_les_scores_les_plus_eleves | ✅ Conforme, testé |
| US-01 contextualiseur : journalisation traités vs total scoré | doc/userstories_contextualiseur.md:18 | Absent de declenchement.py | 🔴 Non couvert (finding MET-1-bis) |
| US-02 contextualiseur : validation preuve_id | validation.py | test_validation.py, 4 tests dont le cas signal exclu | ✅ Conforme, testé, cohérent avec le format réel de reputation.py/score.py |
| US-03 contextualiseur : persistance | contextualiseur/persistance.py | test_contextualiseur_persistance.py, testé contre vraie DB | ✅ Conforme |
| US-04 contextualiseur : avertissement | avertissement.py | Constante statique, formulation non catégorique vérifiée par lecture | ✅ Conforme |
| Pas de contenu LLM fabriqué | contextualiseur/*.py | Lecture intégrale des 5 fichiers : aucun appel LLM, aucun contenu généré en dur | ✅ Confirmé honnête |

---

## Top Findings

- **Medium (Confirmé)** `src/fakenews/contextualiseur/declenchement.py` — le 4e critère d'acceptation de US-01 contextualiseur ("Chaque run journalise le nombre d'articles traités vs. le nombre total scoré par l'évaluateur", `doc/userstories_contextualiseur.md:18`) n'est implémenté nulle part. Pas seulement absent du fichier : aucun `run_contextualiseur.py` n'existe encore pour porter cette responsabilité ailleurs non plus — contrairement au pattern déjà établi dans le scraper, où `collecter_rss`/`collecter_reddit` journalisent eux-mêmes (pas seulement leur `run_*.py`).
- **Medium (Confirmé)** `src/fakenews/scraper/reddit.py:69-84` — le compteur `ignores` introduit par le correctif QUAL-1 n'est jamais élevé en `warning` quand il est non nul, contrairement à l'équivalent RSS (`rss.py`, `ignores_sans_date`, élevé en warning). Incohérence d'observabilité entre les deux collecteurs : un taux d'échec systémique côté Reddit (ex. un bug qui ferait échouer 100% des posts d'un subreddit) resterait noyé en `INFO`, indiscernable d'un run normal dans les logs.
- **Low** `src/fakenews/contextualiseur/declenchement.py:19` vs `doc/userstories_contextualiseur.md:10` — le code retient un article dont `score_final >= seuil` (inclusif), alors que le critère d'acceptation dit "dépasse un seuil" (lecture naturelle : strictement supérieur). Écart mineur, actif uniquement pour un score exactement égal au seuil (60.0 par défaut).
- **Low (Corroboré, aggravé)** `doc/plan_implementation.md:100-102` — "Prochaine étape concrète" toujours ancrée sur Phase 0/US-01 RSS, maintenant trois paliers en retard sur l'état réel (signalé dans les deux audits précédents, jamais corrigé).

---

## Details Par Division

### Division Métier (Anton Ego)

`declenchement.py` fait ce qu'il annonce sur trois critères — mais un contrat n'est pas à moitié honoré. Le quatrième critère de US-01 n'a pas été oublié par accident : c'est un fichier de 25 lignes, entièrement lu, où l'absence est aussi vérifiable qu'une présence l'aurait été.

- **Medium** : MET-1-bis (journalisation manquante, ci-dessus).
- **Low** : MET-2 (`>=` vs "dépasse", ci-dessus).

### Division Qualité (Gordon Ramsay)

Le service se rattrape. Les deux plats renvoyés (MET-1, QUAL-1) reviennent en cuisine corrects — et cette fois je les ai goûtés moi-même, pas seulement lu la fiche. `validation.py` en particulier a un test qui va chercher exactement le genre d'erreur qu'un développeur pressé commettrait (oublier de filtrer les signaux exclus) — c'est le genre de test qui a une raison d'exister.

- Rien à signaler en Medium/High cette division-ci sur le nouveau périmètre.

### Division Architecture (Steve Jobs)

- **Medium** : QUAL-1-bis (incohérence d'observabilité `rss.py` vs `reddit.py`, ci-dessus) — deux collecteurs, même principe déclaré ("dégrader jamais bloquer"), deux niveaux de vigilance différents pour le même type d'événement (entrée ignorée).

### Division Cybersécurité Offensive (Sherlock Holmes)

Rien à instruire. Le nouveau code ne parle à aucun réseau, ne construit aucune requête, ne stocke aucun secret. `avertissement.py` est une constante ; `persistance.py` passe par l'ORM ; `validation.py` et `declenchement.py` sont des fonctions pures sur des dictionnaires. Élémentaire, et pourtant : j'ai quand même lu les cinq fichiers en entier pour m'assurer qu'aucun appel LLM ni contenu fabriqué ne s'était glissé à la place de la vraie génération — rien trouvé.

---

## Details Par Sous-Audit

### Business Logic Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : MET-1-bis, MET-2.
- **Points conformes** : traitement de `non_évaluable`, tri décroissant, plafonnage — les trois testés et corrects.

### Requirements Compliance Auditor
- **Verdict** : AUDIT_FAIL (Medium) — cf. Matrice De Couverture, une ligne rouge sur dix.
- **Points conformes** : `validation.py` (US-02, partie non-LLM), `persistance.py` (US-03) et `avertissement.py` (US-04) couvrent chacun 100% de leurs critères d'acceptation respectifs.

### Doc-Sync Auditor
- **Verdict** : AUDIT_FAIL (Medium, corroboré)
- **Findings** : plan_implementation.md toujours désynchronisé (signalé 3 fois maintenant).
- **Points conformes** : aucune nouvelle promesse fantôme introduite par le code Phase 3 lui-même.

### A11y/UX Checker
- **Verdict** : Non applicable.

### Clean Code Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : les 5 fichiers `contextualiseur/` sont courts, à responsabilité unique, sans nombre magique non documenté (`SEUIL_PAR_DEFAUT`, `PLAFOND_APPELS_PAR_DEFAUT` nommés et commentés).

### Fail-Loud Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : QUAL-1-bis.
- **Points conformes** : le correctif QUAL-1 lui-même journalise correctement chaque post ignoré en `warning` (`reddit.py:74`) — c'est seulement l'agrégat par subreddit qui n'est pas élevé en sévérité quand `ignores > 0`. `contextualiseur/persistance.py` échoue fort (contrainte DB) plutôt que d'écraser silencieusement en cas de double appel — comportement voulu, pas un défaut.

### Test Quality Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : 15 nouveaux tests (5 declenchement, 4 validation, 1 persistance contextualiseur, 4 persistance scraper, 1 résilience reddit), tous exécutés indépendamment pour cet audit — 46/46 passent avec `TEST_DATABASE_URL`, 40 passent + 6 skip proprement sans. Le test `test_item_referencant_un_signal_exclu_est_deplace_vers_deductions` cible précisément une erreur plausible (oublier le filtre `valeur is not None`), pas un cas trivial.

### Mutation/Saboteur Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : raisonnement de mutation sur `valider_faits_traces` (retirer le filtre `is not None`, inverser `in`/`not in`) et sur `articles_a_traiter` (inverser `>=`, retirer le tri, retirer le slice de plafond) — toutes ces mutations feraient échouer au moins un test existant.

### Layer Enforcer
- **Verdict** : AUDIT_PASS
- **Points conformes** : `contextualiseur/` ne dépend d'aucun module `scraper/` ni `evaluateur/` — communique uniquement via les formats de données attendus (`sous_scores`, `scores`), pas par import direct. Cohérent avec le principe déjà vérifié pour `evaluateur/` dans l'audit précédent.

### YAGNI Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : rien de spéculatif — pas de client LLM factice, pas d'abstraction "au cas où" pour un fournisseur non choisi.

### SRE/Performance Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : aucune nouvelle boucle réseau ou I/O coûteuse dans ce périmètre.

### Architecture Consistency Auditor
- **Verdict** : AUDIT_FAIL (Medium)
- **Findings** : QUAL-1-bis (incohérence rss.py/reddit.py).
- **Points conformes** : `validation.py`/`declenchement.py` consomment exactement le format `{valeur, raison, preuve_id}` produit par `evaluateur/reputation.py` et attendu en entrée par `evaluateur/score.py` — vérifié précisément parce qu'un premier examen laissait croire à une incompatibilité avec le `detail` (sortie, pas entrée) de `score.py` ; relecture attentive : pas de défaut, les trois modules sont cohérents entre eux sur le format d'échange réellement utilisé.

### Contextual Threat Analyst
- **Verdict** : AUDIT_PASS
- **Points conformes** : le bloc contextualiseur actuel ne fait aucun appel réseau, ne traite aucune entrée non fiable au sens sécurité (les `sous_scores` viennent de l'évaluateur, pas de l'extérieur) — rien à red-teamer avant que la génération LLM (avec son prompt injection potentiel via le contenu d'article) n'existe.

### SAST Scanner
- **Verdict** : AUDIT_PASS
- **Points conformes** : `contextualiseur/persistance.py` passe par l'ORM SQLAlchemy, aucune construction de requête par chaîne.

### Supply Chain & Artifact Auditor
- **Verdict** : rien de nouveau à ce périmètre (déjà traité dans l'audit précédent — dépendances toujours non plafonnées, non retraité depuis, pas re-décompté ici pour éviter la redondance).

### Privacy/Exfiltration Auditor
- **Verdict** : AUDIT_PASS
- **Points conformes** : aucune nouvelle donnée personnelle introduite par ce périmètre.

---

## Points Conformes

- MET-1 (dédup cross-domaine) confirmé corrigé par une reproduction indépendante, écrite pour cet audit, hors de la suite de tests existante — deux domaines différents avec le même hash de contenu produisent maintenant deux lignes distinctes.
- QUAL-1 (frontière try/except) confirmé corrigé, structure du code relue et test dédié exécuté avec succès.
- Suite de tests complète (46 tests) exécutée deux fois de façon indépendante pour cet audit : avec `TEST_DATABASE_URL` (46 passent) et sans (40 passent, 6 skip proprement — pas d'échec masqué).
- Aucun contenu LLM fabriqué ou appel factice introduit dans le code Phase 3 — vérifié par lecture intégrale.
- Les formats d'échange entre `evaluateur/reputation.py`, `evaluateur/score.py` et `contextualiseur/validation.py` sont mutuellement cohérents (vérifié en détail après une fausse alerte initiale, cf. Architecture Consistency Auditor).
- Le comportement de dépassement de plafond dans `declenchement.py` (articles en trop non traités cette semaine, pas de report) est maintenant une décision explicite et documentée, plutôt qu'une question ouverte comme dans le premier audit.

## Limites De Verification

- La génération réelle par LLM (US-02 contextualiseur) n'existe pas encore — rien à auditer sur ce point au-delà de vérifier son absence honnête (fait, cf. Matrice De Couverture).
- `declenchement.py` n'est appelé par aucun script d'orchestration pour l'instant (pas de `run_contextualiseur.py`) — la journalisation manquante (MET-1-bis) pourrait en théorie être prévue pour cette étape future plutôt qu'oubliée ; le doute est levé en faveur d'un finding réel parce que le pattern équivalent (`collecter_rss`/`collecter_reddit`) journalise déjà lui-même, sans attendre son `run_*.py`.
- Base de test : Postgres local (`fakenews_dev`), pas Supabase — aucune instance Supabase réelle n'existe (limite déjà documentée dans les audits précédents).
- Commandes exécutées : `pytest tests/ -q` sans `TEST_DATABASE_URL` (40 passed, 6 skipped), `pytest tests/ -v` avec `TEST_DATABASE_URL` (46 passed), reproduction manuelle indépendante de MET-1 contre la base locale suivie d'un `DELETE` de nettoyage. Aucune commande destructive sur des données réelles.
