# Audit phase 10 — codebase complète

**Scope** : intégralité de la codebase sur la branche `audit/correctifs-codebase`
(commit `be28cb2`) — `src/fakenews/` (2 796 lignes), `tests/` (2 744 lignes),
`api/`, `supabase/migrations/`, `.github/workflows/`, `doc/`, configuration.

**Sources d'exigences** : `doc/V0/userstories_{scraper,évaluateur,contextualiseur,frontend}.md`,
`doc/V0/architecture.md`, `doc/V0/plan_implementation.md`, `doc/V0/fiche-projet-fake-news-trading.md`,
`doc/V1/comptes-3-roles.md`, `README.md`, `.env.example`.

**Verdict global : 🔴 AUDIT_FAIL**
**Totaux : Critique 1 · High 4 · Medium 10 · Low 14**

---

## Résumé de l'audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | Le signal de fact-checking — le plus lourdement pondéré — inverse son verdict sur les formulations les plus courantes. Le premier critère d'acceptation d'US-01 contextualiseur (« seuil configurable sans modification du code ») n'est pas implémenté. Le lexique français d'US-05 est mort à l'exécution. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Une suite de 184 tests intégralement verte qui laisse passer une inversion de score, un lexique inerte et un plafond jamais exercé. Le correctif H2 a laissé un survivant. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Un commit unique en fin de run fait perdre 300 articles pour un seul score hors bornes. Le pool du contextualiseur ne décroît jamais. La règle « les blocs ne s'appellent pas entre eux » est appliquée dans un sens et violée dans l'autre. |
| Cybersécurité offensive (Sherlock) | 🟡 Avertissement | L'authentification elle-même tient — durcie, testée, fail-closed. Mais trois routes échappent à la garde, un message d'exception brut atteint la base et l'écran, et la note de télémétrie sortante omet le plus gros flux. |

---

## Index des sous-audits

| Sous-audit | Scope | Crit | High | Med | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | 5 signaux, agrégateur, déclenchement | 1 | 2 | 1 | 1 | 🔴 FAIL |
| Requirements Compliance | 24 critères d'acceptation | 0 | 1 | 2 | 0 | 🔴 FAIL |
| Doc-Sync Auditor | README, fiche projet, plan, .env.example | 0 | 0 | 3 | 1 | 🟡 |
| A11y/UX Checker | 4 gabarits Jinja2 | 0 | 0 | 0 | 2 | 🟡 |
| Clean Code Auditor | src/ complet | 0 | 0 | 1 | 3 | 🟡 |
| Fail-Loud Auditor | chemins d'erreur | 0 | 1 | 1 | 1 | 🔴 FAIL |
| Test Quality Auditor | 184 tests | 0 | 0 | 1 | 2 | 🟡 |
| Mutation/Saboteur | signaux + pagination + auth | 0 | 0 | 1 | 1 | 🟡 |
| Layer Enforcer | frontières inter-blocs | 0 | 0 | 1 | 0 | 🟡 |
| YAGNI Auditor | points d'entrée, colonnes, barème | 0 | 0 | 0 | 2 | 🟢 |
| SRE/Performance | requêtes, boucles, transactions | 0 | 1 | 1 | 1 | 🔴 FAIL |
| Architecture Consistency | code vs architecture.md / plan | 0 | 0 | 1 | 0 | 🟡 |
| Contextual Threat Analyst | scénarios d'abus métier | 0 | 0 | 0 | 2 | 🟡 |
| SAST Scanner | injections, authz, secrets | 0 | 0 | 1 | 1 | 🟡 |
| Supply Chain & Artifact | deps, lockfile, modèle NER, runtime | 0 | 0 | 0 | 1 | 🟢 |
| Privacy/Exfiltration | flux sortants, logs, champs affichés | 0 | 0 | 2 | 0 | 🟡 |

*(Le total par sous-audit dépasse 29 : plusieurs findings sont corroborés par deux sous-audits et comptés une seule fois dans les totaux globaux.)*

---

## Matrice de couverture des contrats principaux

| Contrat / exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| US-03 évaluateur — verdict « faux » augmente fortement la suspicion | `evaluateur/fact_checking.py:30-36` | mesuré : `"Inaccurate"` → 5.0 | ❌ **inversé** |
| US-05 évaluateur — lexiques distincts par langue (min. FR + EN) | `evaluateur/style.py:34-41` | mesuré : 5/5 textes FR → `"en"` | ❌ inerte |
| US-05 évaluateur — détection présence/absence de citations | `evaluateur/style.py:88` | mesuré : `href="…"` compte comme citation | ❌ neutralisé |
| US-01 contextualiseur — seuil configurable sans modif. du code | `contextualiseur/declenchement.py:8` | constante, aucune lecture d'env | ❌ non implémenté |
| US-01 contextualiseur — plafond LLM configurable | `contextualiseur/declenchement.py:9` | constante, aucune lecture d'env | ❌ non implémenté |
| US-01 contextualiseur — journalise traités vs **total scoré** | `contextualiseur/declenchement.py:37-43` | mesuré : run 2 → « sur 40 » pour 43 scorés | ❌ dénominateur faux |
| US-01 scraper — pendant francophone « douteux » (Décodex) | `scraper/sources_rss.py:15-63` | 0 domaine FR douteux collecté | ❌ absent |
| US-07 évaluateur — plafond d'appels LLM par run | `evaluateur/backfill_llm_bootstrap.py:47` | backfill sans aucune borne | ⚠️ partiel |
| US-08 évaluateur — moyenne pondérée sur signaux applicables | `evaluateur/score.py:32-51` | lecture + `tests/test_score.py` | ✅ |
| US-08 évaluateur — `non_évaluable` si tous signaux exclus | `evaluateur/score.py:42-45` | `test_correctifs_audit.py:378` (bout en bout) | ✅ |
| US-08 évaluateur — trace de contribution par signal | `models.py:74`, `run_evaluateur.py:122` | `test_correctifs_audit.py:440` | ✅ |
| US-02 contextualiseur — post-traitement des `preuve_id` | `contextualiseur/validation.py:17-29` | `tests/test_validation.py` (4 cas) | ✅ |
| US-04 contextualiseur — avertissement porté par la donnée | `models.py:144` vs `frontend/app.py:527,563` | persisté mais jamais relu à l'affichage | ⚠️ partiel |
| US-04 frontend — accès hébergé protégé, défaut fermé | `frontend/app.py:309-329` | `test_correctifs_audit.py:80-101` | ✅ |
| US-04 frontend — lecture seule stricte | `frontend/app.py` (routes) | aucune écriture sur `articles`/`scores`/`mise_en_contexte` | ✅ |
| US-04 frontend — auth sur toute page affichant un score | `frontend/app.py:33` | `/docs`, `/redoc`, `/openapi.json` → 200 sans cookie | ⚠️ surfaces non gardées |
| US-05 scraper — déduplication URL canonique / hash | `scraper/persistance.py:22-41` | `tests/test_persistance.py` | ✅ |
| architecture.md — dégrader, jamais bloquer | `scraper/rss.py:127` vs `scraper/reddit.py:85` | protection au grain de l'entrée absente côté RSS | ⚠️ asymétrique |
| architecture.md — pas d'appel direct entre blocs | `frontend/app.py:26-27` | frontend importe 2 modules du contextualiseur | ❌ violé |
| US-03 scraper — GDELT | — | non implémenté, **documenté** (`plan_implementation.md:105`) | ⏸️ assumé |
| US-02 / US-06 évaluateur — corroboration, décalage viral | — | non implémentés, **documentés** | ⏸️ assumés |

---

## Top findings

- **[Critique]** `src/fakenews/evaluateur/fact_checking.py:30-36` — `_interpreter_verdict` compare par **sous-chaîne**. `MOTS_VRAI` contient `"true"` et `"accurate"`, donc `"Inaccurate"`, `"Untrue"`, `"Not true"`, `"Barely true"` et `"Half true"` retournent tous **5.0 (fiable)** — mesuré. Un article démonté par un fact-checker reçoit le score le plus rassurant possible sur le signal au poids le plus élevé (1.5), passe sous le seuil 60, ne déclenche pas le contextualiseur et disparaît de la liste par défaut du frontend. **Correction attendue** : comparer sur des verdicts normalisés en jetons entiers (ou une liste de préfixes ancrés), et faire précéder tout test « vrai » d'une détection de négation ; ajouter les verdicts réels au corpus de test.
- **[High]** `src/fakenews/evaluateur/run_evaluateur.py:131` + `evaluateur/llm_bootstrap.py:52` — `float(resultat["score_suspicion"])` n'est pas borné (les `minimum`/`maximum` d'un `input_schema` de tool-use ne sont pas contraignants), et le `session.commit()` unique est **hors** du `try/finally`. Mesuré : un seul article dont `llm_bootstrap` est le seul signal applicable et qui reçoit 150 fait violer `ck_scores_score_final_range` et **annule les scores des 300 articles du run**, appels LLM payés compris. **Correction attendue** : borner la valeur à [0, 100] à la lecture, et commiter par lot plutôt qu'en une transaction unique de fin de run.
- **[High]** `src/fakenews/contextualiseur/declenchement.py:8-9` — `SEUIL_PAR_DEFAUT` et `PLAFOND_APPELS_PAR_DEFAUT` sont des constantes de module, appelées sans argument (`run_contextualiseur.py:39`) et jamais surchargées par l'environnement. Le **premier** critère d'acceptation d'US-01 contextualiseur (« le seuil est configurable sans modification du code ») et le quatrième (« plafonné, valeur configurable ») sont non implémentés — alors que `run_evaluateur._plafond_depuis_env` fait exactement cela pour l'évaluateur. **Correction attendue** : réutiliser `_plafond_depuis_env` (extrait dans un module partagé) pour `CONTEXTUALISEUR_SEUIL` et `LLM_PLAFOND_CONTEXTUALISEUR`.
- **[High]** `src/fakenews/evaluateur/style.py:34-41` — `_MOTS_OUTILS_FR` ne compte que 10 mots et il en faut 2 **distincts** pour conclure « fr ». Mesuré : « Vérité cachée sur les vaccins : ils ne veulent pas que vous sachiez » → `"en"`, comme 4 autres textes français évidents. Le lexique français (`"vérité cachée"`, `"censuré"`, `"ils ne veulent pas que vous sachiez"`) n'est jamais appliqué aux titres et résumés courts — précisément le format putaclic qu'US-05 vise. **Correction attendue** : élargir la liste aux mots-outils réellement fréquents (que, qui, pour, dans, sur, ce, il(s), ne, pas, vous, avec, plus…) et compter les occurrences, pas les types.
- **[High]** `src/fakenews/evaluateur/style.py:88` + `scraper/rss.py:25-28` — `_extraire_contenu` persiste le HTML brut du flux, et `re.search(r'"[^"]{10,}"')` matche n'importe quel attribut. Mesuré : le même résumé en HTML → 10.0 ; en texte nu → 15.0 avec « aucune citation ». Un simple `<a href="https://…">` suffit à annuler le critère. **Correction attendue** : nettoyer le HTML à la collecte (`contenu` doit être du texte), ou exclure les chaînes ressemblant à une URL de la détection de citation.
- **[Medium]** `src/fakenews/frontend/app.py:33` — `FastAPI(title=…)` sans `docs_url=None, redoc_url=None, openapi_url=None`. Mesuré en mode hébergé sans cookie : `/` → 303, mais `/docs`, `/redoc`, `/openapi.json` → **200**. Ces routes divulguent les quatre chemins de l'application et `/docs` charge Swagger UI depuis `cdn.jsdelivr.net`, ce qui contredit `.env.example:93` (« Le frontend, lui, n'appelle aucun service tiers ») et fait exécuter un script tiers non épinglé sur l'origine de l'app.
- **[Medium]** `src/fakenews/evaluateur/source_primaire.py:279` — seul survivant du correctif du finding H2 : `f"…({exc})"` au lieu de `type(exc).__name__`. Mesuré : un message contenant `?token=SECRET-ABC123` atterrit dans `scores.sous_scores` puis dans `templates/detail.html:28`. Les quatre autres sites du même fichier et de `fact_checking.py`/`llm_bootstrap.py` sont corrects ; le test `test_echec_sec_ne_recopie_pas_le_message_d_exception` couvre le chemin SEC, pas le chemin NER.

---

## Thèmes transverses

1. **Le correctif appliqué à N-1 sites sur N.** H2 (fuite d'exception) fermé quatre fois sur cinq. La règle « les blocs ne s'appellent pas entre eux » respectée par duplication volontaire dans `reputation.py:5-8` et violée sans commentaire dans `frontend/app.py:26-27`. La protection au grain de l'élément longuement justifiée dans `reddit.py:52-63` et absente de `rss.py`. Le plafond configurable par environnement implémenté dans l'évaluateur et pas dans le contextualiseur. Le schéma de défaut est constant : une bonne décision, appliquée là où l'audit précédent regardait.
2. **La correspondance par sous-chaîne est le défaut récurrent du domaine.** L'audit de phase 6 (finding H6) a corrigé `nom_connu in nom_normalise` dans `source_primaire.py` en passant aux jetons entiers, avec un commentaire de dix lignes expliquant pourquoi. `fact_checking.py:32-35` fait exactement la même erreur, sur un signal plus lourd, et n'a pas été revisité.
3. **Le vert de la CI mesure la non-régression des correctifs, pas la conformité aux exigences.** 184 tests, 0 skip, une discipline exemplaire sur les findings passés (`test_correctifs_audit.py` porte le numéro du finding qu'il verrouille). Mais aucun test ne part d'un critère d'acceptation non encore corrigé : le seuil non configurable, le lexique FR inerte, les citations HTML et l'inversion des verdicts traversent la suite sans la faire broncher.
4. **Les commentaires décrivent l'intention, pas toujours l'état.** `style.py:104-118` documente longuement une exclusion « étroite et atteignable » — elle l'est. `fact_checking.py:16-19` affirme que les verdicts type « mixture » restent non traités — `"Half true"` est traité, et à l'envers. Le premier commentaire est un actif, le second un passif.

---

## Détails par division

### Division Métier (Anton Ego)

On m'a servi un plat dont la carte promet sept signaux, dont cinq sont annoncés cuisinés. Je découpe.

- **[Critique]** `evaluateur/fact_checking.py:30-36` : le signal censé être le plus factuel du dispositif — celui qui s'appuie sur le travail d'un fact-checker humain, celui qu'US-03 pondère à 1,5 précisément *parce qu'il a un ancrage externe vérifiable* — retourne « fiable » quand le fact-checker a écrit « Inaccurate ». Ce n'est pas une nuance perdue en traduction. C'est le contraire du verdict. Le module s'en défend par un commentaire qui promet de ne trancher que sur « les formulations non ambiguës » ; « Not true » lui paraît apparemment ambigu, et il tranche pour « vrai ». La carte ment.
- **[High]** `contextualiseur/declenchement.py:8` : US-01 contextualiseur ouvre par « Le seuil est configurable sans modification du code. » C'est le premier critère, celui qu'on lit avant tous les autres. Il est faux. Le seuil est une constante ; le recalibrer sur le corpus labellisé que la user story appelle de ses vœux exige un commit, une revue, un déploiement. Et comme `frontend/app.py:496` importe la même constante, il faudra penser à ce que les deux blocs restent d'accord — un couplage qu'un `os.environ` aurait épargné.
- **[High]** `evaluateur/style.py:34-41` : US-05 exige des lexiques « distincts par langue, au minimum anglais et français, pas une règle unique appliquée telle quelle à tout le corpus ». Le lexique français existe, il est soigné, il contient les formules exactes de la désinformation francophone. Il n'est jamais consulté. Cinq phrases françaises sur cinq sont réputées anglaises. Le Monde est la seule source haute réputation francophone du corpus ; Le Gorafi son seul pendant satirique. Pour eux, US-05 applique le lexique anglais. On a écrit le bon dictionnaire et posé la serrure sur l'autre porte.
- **[Medium]** `contextualiseur/declenchement.py:37-43` : « Chaque run journalise le nombre d'articles traités vs. le nombre **total** scoré par l'évaluateur — donne une mesure réelle du taux de suspicion. » Mesuré : run 1 annonce « 3 sur 43 », run 2 annonce « 0 sur 40 » alors que 43 articles sont scorés. Le dénominateur est le pool restant, pas le total. La mesure dérive à chaque exécution, et le mot « cette semaine » subsiste dans le message alors que la docstring des lignes 25-27 se félicite de l'avoir corrigé.
- **[Low]** `scraper/sources_rss.py:59-63` : Le Gorafi est collecté, `reputation.py` ne le connaît pas, ce qui est correct (satire ≠ désinformation, la docstring le dit). Reuters, en revanche, est collecté sous `reuters.com` et absent des deux listes — la seule agence de presse du corpus est en « réputation inconnue ». Sans effet aujourd'hui, le flux étant mort et le repli Guardian étant, lui, listé fiable.

### Division Qualité (Gordon Ramsay)

184 tests. Zéro skip. Une CI qui refuse le vert facile. Et là-dedans, un test qui s'appelle `test_valeur_plafonnee_a_100` et qui n'a **jamais vu** le chiffre 100 de sa vie.

- **[High]** `evaluateur/run_evaluateur.py:131` : le `commit()` est en dehors du `try/finally`. Trois cents articles, jusqu'à cinquante appels LLM facturés, et tout ça repose sur une seule transaction qu'un unique score à 150 fait exploser. Mesuré : `IntegrityError` sur `ck_scores_score_final_range`, zéro ligne persistée, les deux articles parfaitement sains du lot partis avec. On ne met pas trois cents assiettes sur le même plateau.
- **[Medium]** `scraper/rss.py:127-141` : dans `reddit.py`, douze lignes de commentaire expliquent pourquoi la protection est **au grain du post** et pas du subreddit, « appliqué au grain du post, pas seulement du subreddit ». Excellent. Puis on ouvre `rss.py` et il n'y a rien. Pas un `try`. Une entrée qui pose problème et c'est `collecter_rss`, puis `run_scraper`, puis les steps évaluateur et contextualiseur du workflow qui tombent. Vous avez écrit la leçon et ne l'avez pas relue.
- **[Low]** `tests/test_style.py:65-71` — mesuré : le cas de test atteint **45.0**. L'assertion `valeur <= 100.0` passe avec ou sans le `min(100.0, penalite)`. Retirez le plafond, la suite reste verte. Un test qui ne tue aucune mutation n'est pas un test, c'est une ligne de couverture.
- **[Low]** `tests/test_fact_checking.py:25-47` : trois verdicts testés — « False », « True », « Unproven ». Les trois seuls sur lesquels la sous-chaîne tombe juste par accident. « Unproven » est justement le verdict ambigu qui ne contient ni `true` ni `false`. On a choisi le seul exemple qui ne révèle rien.
- **[Low]** `evaluateur/backfill_{fact_checking,llm_bootstrap}.py:72/80` : `nb_traites += 1` s'incrémente même quand le nouvel appel échoue et rend `valeur: None`, puis le log annonce « N score(s) mis à jour avec un signal **valide** ». L'outil de rattrapage ment sur son propre rattrapage.
- **[Low]** `db.py:26` : `os.environ["DATABASE_URL"]` lève un `KeyError` nu. À côté, `_plafond_depuis_env` et `_proxys_de_confiance` nomment la variable, rappellent la valeur par défaut et disent quoi faire. Le même soin pour la variable sans laquelle rien ne démarre : non.

### Division Architecture (Steve Jobs)

- **[High]** `evaluateur/run_evaluateur.py:131` : une transaction pour trois cents articles n'est pas une décision d'architecture, c'est l'absence de décision. Le module applique « dégrader, jamais bloquer » à chaque signal, à chaque appel réseau, à chaque client — puis remet le résultat de tout ce soin dans un seul panier.
- **[Medium]** `contextualiseur/run_contextualiseur.py:26-34` : `select(Score)` sans borne, sans filtre de seuil, colonnes JSONB comprises, matérialisé intégralement en Python. Le filtrage, le tri et le plafonnement se font **après**. Et comme un article sous le seuil n'obtient jamais de `MiseEnContexte`, il reste dans le pool pour toujours : le coût de sélection croît linéairement avec l'historique complet du projet, pour ne jamais rien sélectionner de plus. La bonne requête est un `WHERE score_final >= seuil ORDER BY score_final DESC LIMIT plafond`, et elle tient sur une ligne.
- **[Medium]** `frontend/app.py:26-27` : le frontend importe `AVERTISSEMENT` et `SEUIL_PAR_DEFAUT` du contextualiseur. `architecture.md` : « Les blocs ne s'appellent pas entre eux directement. » `reputation.py:5-8` duplique une liste entière plutôt que de l'importer du scraper, en citant cette règle. Une règle qu'on applique quand elle coûte et qu'on oublie quand elle arrange n'est pas une règle. Conséquence concrète, pas théorique : `models.py:144` persiste `mise_en_contexte.avertissement` — non nullable, exigé par US-04 contextualiseur « portée par la donnée elle-même, pas uniquement ajoutée a posteriori par le frontend » — et `app.py:527,563` affiche la **constante importée**. La colonne est écrite, jamais lue. Le jour où la formulation change, toutes les anciennes mises en contexte s'affichent avec le nouveau texte. C'est exactement ce que le critère interdisait.
- **[Low]** `scraper/run_reddit.py`, `scraper/run_rss.py` : `run_reddit` n'est référencé **nulle part** dans le dépôt ; `run_rss` seulement dans un rapport d'audit de phase 0. `run_scraper.py` les remplace tous deux, et c'est lui que le workflow appelle. Deux points d'entrée morts. Supprimez-les.
- **[Low]** `models.py:49,119` : `CheckConstraint(f"plateforme in {PLATEFORMES}")` dépend du `repr` d'un tuple Python pour produire du SQL. Ça marche à trois éléments, ça produit `in ('rss',)` — invalide — à un seul. Une contrainte de schéma ne doit pas dépendre d'un détail de formatage.
- **[Low]** `.github/workflows/pipeline_hebdomadaire.yml` : aucun `timeout-minutes`, alors que `run_evaluateur.py:32-37` justifie son plafond d'articles précisément par « exposé au timeout GitHub Actions ». Le raisonnement est fait, la borne explicite manque.

### Division Cybersécurité Offensive (Sherlock Holmes)

- **[Medium]** `frontend/app.py:33` — Élémentaire, et pourtant : on a soigneusement fait de `compte_courant` une dépendance de `/` et de `/articles/{id}`, on a rendu le défaut fermé, on a testé le cookie expiré, le cookie rallongé, le cookie forgé. Et FastAPI, lui, a discrètement ajouté trois routes que personne n'a inventoriées. Mesuré en mode hébergé, sans cookie : `/docs` 200, `/redoc` 200, `/openapi.json` 200. Le butin est modeste — les quatre chemins et les noms de champs du formulaire, pas de données d'article. Mais deux conséquences comptent : la docstring du module affirme un inventaire de routes qui est incomplet, et `/docs` envoie le navigateur du visiteur chercher Swagger UI sur `cdn.jsdelivr.net`, ce que `.env.example:93` déclare impossible (« Le frontend, lui, n'appelle aucun service tiers ») et qui fait exécuter un script tiers non épinglé sur l'origine de l'application.
- **[Medium]** `evaluateur/source_primaire.py:279` — Le finding H2 avait été traité avec méthode : `type(exc).__name__` partout, un commentaire à chaque site expliquant que `raison` est persistée puis rendue. Quatre sites sur cinq. Celui-ci interpole l'exception entière. Mesuré : un message contenant `?token=SECRET-ABC123` traverse `scores.sous_scores` et ressort dans `templates/detail.html:28`. L'exception vient de spaCy, dont les messages citent volontiers des chemins et des URL de modèles.
- **[Medium]** `.env.example:88-93` — La section « Données sortantes » est méritoire : elle documente que le **titre** part chez Google Fact Check et SEC EDGAR. Elle omet Anthropic, qui reçoit le titre **et** jusqu'à 4 000 caractères de contenu (`llm_bootstrap.py:48`) plus 2 000 en contextualisation (`generation.py:80`) — de très loin le plus gros flux sortant du système, et le seul qui transporte du texte rédigé par des personnes identifiables (corps de posts Reddit, dont l'auteur est par ailleurs stocké en base, `reddit.py:32`). Une note de télémétrie qui documente les deux petits flux et tait le grand oriente mal la lecture.
- **[Low] [RISQUE]** `frontend/app.py:378-382` — Le mot de passe en clair est transmis à Postgres comme paramètre de `select(func.crypt(mot_de_passe, secret_hash))`. La requête est paramétrée, donc pas d'injection ; mais un `log_min_duration_statement` ou un `log_statement` bavard sur l'instance Supabase enregistrerait la valeur liée. Non prouvé — dépend d'une configuration serveur non observable d'ici. À vérifier avant d'ouvrir l'accès.
- **[Low] [RISQUE]** `frontend/app.py:376-384` — Un pseudo doté d'un `secret_hash` fait passer par bcrypt (dizaines de millisecondes) ; un pseudo sans code passe par `hmac.compare_digest` (microsecondes). L'écart est mesurable à distance et permet d'énumérer quels pseudos ont un code personnel — c'est-à-dire de localiser le superadmin, seule vraie frontière du modèle (`doc/V1/comptes-3-roles.md:108-114`). Coût d'exploitation faible, gain limité (le code lui-même reste à trouver).
- **[Low]** `llm.py:41` — `encadrer_contenu_non_fiable` ne neutralise que la chaîne exacte `</contenu_non_fiable>`. Un article contenant `</contenu_non_fiable >` ou `</CONTENU_NON_FIABLE>` sort du cadre. Le modèle traitera vraisemblablement la suite comme du contenu quand même — la consigne système est explicite et répétée — mais le garde-fou annoncé comme mécanique redevient une affaire de discipline du modèle.
- **[Low]** `normalisation.py:5-9` — `canonicaliser_url` supprime la query string. Sur un domaine dont les articles s'identifient par `?id=123`, tous les articles s'effondrent sur une même URL canonique et la déduplication d'US-05 scraper les confond. Aucun des huit flux actuels n'est dans ce cas ; c'est une fragilité à l'ajout d'une source, pas un défaut actif.

---

## Détails par sous-audit

### Business Logic Auditor
- **Verdict** : 🔴 AUDIT_FAIL
- **Findings** : inversion `_interpreter_verdict` (Critique) ; détection de langue FR (High) ; citations HTML (High) ; dénominateur du taux de suspicion (Medium) ; Reuters hors listes de réputation (Low).
- **Points conformes** : `score.py` implémente exactement US-08 (exclusion des `valeur: None`, renormalisation par `Σpoids`, `non_evaluable` sur dénominateur nul) ; `valider_faits_traces` applique le post-traitement `preuve_id` sans faire confiance au prompt, et rejette aussi les items citant un signal **exclu** — nuance correcte que la user story n'imposait pas explicitement ; `evaluer_source_primaire` conditionne bien la pénalité à une claim vérifiable et distingue « aucun dépôt » de « dépôts sans correspondance », les deux critères les plus délicats d'US-04.

### Requirements Compliance Auditor
- **Verdict** : 🔴 AUDIT_FAIL
- **Findings** : seuil et plafond du contextualiseur non configurables (High, US-01 contextualiseur critères 1 et 4) ; pendant francophone absent alors que la Phase 1 est déclarée terminée (Medium, US-01 scraper) ; backfill LLM sans plafond (Medium, US-07).
- **Points conformes** : la matrice ci-dessus recense 9 critères pleinement satisfaits et prouvés par test ; les trois user stories non implémentées (US-03 scraper, US-02/US-06 évaluateur) sont explicitement documentées comme telles dans `plan_implementation.md:105-106`, avec la raison — c'est de la dette déclarée, pas de la dette cachée.

### Doc-Sync Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** :
  - `doc/V0/fiche-projet-fake-news-trading.md:18` — « ## État actuel du code / on part de zéro », alors que cinq blocs sont livrés, testés et déployés. Même fichier : ligne 26 « Reddit API | À intégrer » (intégré), ligne 24 « Flux RSS (Reuters…) | Intégré » (Reuters est mort, remplacé par un repli Guardian), ligne 40 « Prochaines étapes : 1. Ajouter un module Reddit » (fait). C'est la fiche d'entrée du projet. (Medium)
  - `.env.example:88-93` — note « Données sortantes » omettant Anthropic. (Medium, cf. Privacy)
  - `evaluateur/fact_checking.py:16-19` — le commentaire affirme que les verdicts type « mixture » restent non traités ; `"Half true"` est traité, et à l'envers. (Medium, corrobore le finding Critique)
  - `plan_implementation.md:105` — « l'évaluateur a un repli par similarité prévu pour ce cas » : le repli n'existe pas non plus, US-02 évaluateur n'étant pas implémentée. La formulation laisse croire à une mitigation active. (Low)
- **Points conformes** : `README.md` est exact sur l'état réel, y compris l'avertissement sur le `schedule` commenté et sur les skips de tests ; `plan_implementation.md` tient sa section « État d'avancement » et porte même une note d'auto-discipline (ligne 115) ; `doc/V1/comptes-3-roles.md` décrit fidèlement la mécanique implémentée, formule de cookie comprise.

### A11y/UX Checker
- **Verdict** : 🟡 Avertissement
- **Findings** :
  - `templates/base.html` — aucun lien de déconnexion, alors que `POST /logout` existe et est testé (`test_correctifs_audit.py:476`). L'utilisateur ne peut pas se déconnecter depuis l'interface. (Low)
  - `templates/login.html:22-25` — pas d'`autocomplete="username"` / `autocomplete="current-password"`, ce qui gêne les gestionnaires de mots de passe sur un formulaire dont le mot de passe est justement long et partagé. Pas de `<label>` associé : les champs ne portent qu'un `placeholder`, qui disparaît à la saisie et n'est pas un substitut d'étiquette pour un lecteur d'écran. (Low)
- **Points conformes** : titres de page distincts par vue, verrouillés par test ; `rel="noopener noreferrer"` sur le lien sortant ; états vides explicites sur la liste comme sur le détail (« Aucun article ne correspond… », « Aucune mise en contexte n'a encore été générée ») ; un signal exclu s'affiche « non applicable » et non « 50 », exactement comme US-02 frontend l'exige ; `<html lang="fr">` ; échappement Jinja2 actif partout (aucun `|safe`).

### Clean Code Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** : `nb_traites` incrémenté sur un signal resté exclu dans les deux backfills (Medium) ; `CheckConstraint` par f-string sur un tuple (Low) ; `run_reddit.py`/`run_rss.py` morts (Low) ; `MODELE_PAR_DEFAUT` lu à l'import du module (`llm.py:13`) donc insensible à un `monkeypatch.setenv` postérieur — piège de test latent (Low).
- **Points conformes** : nommage français cohérent de bout en bout ; aucune fonction dépassant 60 lignes ; aucun `except: pass` ; les constantes magiques sont nommées et commentées avec leur justification mesurée (`LONGUEUR_MIN_POUR_CITATION`, `TERMES_RECHERCHE_MAX`, `INTERVALLE_MIN_SEC`) ; les commentaires expliquent le *pourquoi* et citent la mesure qui l'a établi, ce qui est très au-dessus de la moyenne.

### Fail-Loud Auditor
- **Verdict** : 🔴 AUDIT_FAIL
- **Findings** : perte du run entier sur un score hors bornes, sans clamp ni commit par lot (High) ; `rss.py` sans protection au grain de l'entrée, asymétrique avec `reddit.py` (Medium) ; `KeyError` nu sur `DATABASE_URL` (Low).
- **Points conformes** : `schema.verifier_schema` est un excellent garde-fou — il transforme une panne totale opaque en un message nommant la table, la colonne et l'action attendue, et il refuse explicitement de devenir lui-même un mode de panne quand l'introspection échoue (`schema.py:58-65`, testé aux trois branches) ; `_plafond_depuis_env` échoue avec un `SystemExit` qui nomme la variable, la valeur reçue et la valeur par défaut ; les cinq intégrations externes dégradent en `valeur: None` avec une `raison` traçable au lieu de propager.

### Test Quality Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** :
  - Aucun test ne part d'un critère d'acceptation non encore corrigé : les quatre findings High/Critique ci-dessus traversent 184 tests sans en faire échouer un seul. La suite verrouille les régressions des audits passés, elle ne vérifie pas la conformité initiale. (Medium)
  - `test_style.py:65-71` — le plafond n'est jamais atteint (mesuré : 45.0). (Low)
  - `test_fact_checking.py:25-47` — trois verdicts, tous des cas où la sous-chaîne tombe juste par accident. (Low)
  - `test_source_primaire.py:277` — couvre la fuite d'exception sur le chemin SEC, pas sur le chemin NER, qui est le seul encore fautif. (Low)
  - `test_frontend.py:213` — `test_pas_d_authentification_en_mode_local` repose une variable que la fixture `client` a déjà posée ; le test ne peut pas échouer autrement que par une panne générale. (Low)
- **Points conformes** : 184 tests, **0 skip**, exécutés ici contre un vrai Postgres avec les trois migrations — la CI ne ment pas ; un seul test sans assertion, et c'est un « ne doit rien lever » assumé et documenté ; `test_correctifs_audit.py` fait porter à chaque test le numéro du finding qu'il verrouille, discipline rare et précieuse ; `test_pagination_ne_duplique_ni_n_omet_d_article_a_scores_ex_aequo` vérifie la propriété (l'union des pages = l'ensemble) et non le symptôme, en expliquant en docstring pourquoi le test précédent était insuffisant ; `_pas_de_reseau` est une garde autouse dont la docstring énonce honnêtement ce qu'elle **ne** couvre pas (psycopg2/libpq).

### Mutation/Saboteur Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** :
  - Retirer `min(100.0, penalite)` de `style.py:121` : **suite verte** (mesuré). (Medium)
  - Inverser `VALEUR_FAUX` et `VALEUR_VRAI` dans `fact_checking.py:26-27` : les deux tests concernés (`"False"`, `"True"`) échouent — mutation tuée. En revanche, remplacer `any(mot in note …)` par une correspondance exacte : **suite verte**, alors que c'est le correctif attendu. Les tests certifient le comportement fautif. (Low)
  - Remplacer `_MOTS_OUTILS_FR` par l'ensemble vide (donc « tout est anglais ») : `test_vocabulaire_charge_francais_detecte` échoue — mutation tuée. Mais le test ne passe aujourd'hui que parce que sa fixture contient « un/et/une » ; il valide l'implémentation, pas l'exigence. (Low)
- **Points conformes** : les mutations sur l'authentification sont bien tuées — retirer l'expiration de la charge signée, accepter un cookie expiré, ignorer `FAKENEWS_MODE`, plafonner une connexion réussie, faire confiance à `X-Forwarded-For` sans déclaration : chacune fait échouer au moins un test nommé ; supprimer le tri secondaire par `Article.id` fait échouer le test de pagination ex æquo ; supprimer la branche d'exclusion de `style` fait échouer `test_non_evaluable_est_atteignable_depuis_le_pipeline`.

### Layer Enforcer
- **Verdict** : 🟡 Avertissement
- **Findings** : `frontend/app.py:26-27` importe deux modules du bloc contextualiseur, en contradiction avec `architecture.md` (« Les blocs ne s'appellent pas entre eux directement ») et avec le traitement inverse retenu dans `reputation.py:5-8`. Conséquence matérielle : `mise_en_contexte.avertissement` est persisté et jamais relu, ce qui vide de sa substance le critère US-04 contextualiseur « portée par la donnée elle-même, pas uniquement ajoutée a posteriori par le frontend ». (Medium)
- **Points conformes** : aucun bloc n'appelle un autre bloc *à l'exécution* — le contrat « la base est le seul point de contact » tient pour le pipeline ; `fakenews.llm` et `fakenews.db` sont correctement posés comme infrastructure neutre, pas comme dépendances inter-blocs ; `api/index.py` reste un adaptateur de trois lignes ; `api/requirements.txt` isole réellement la lambda de lecture des dépendances lourdes du batch.

### YAGNI Auditor
- **Verdict** : 🟢 OK
- **Findings** : `run_reddit.py` (0 référence) et `run_rss.py` (1 référence, dans un rapport d'audit archivé) sont deux points d'entrée morts remplacés par `run_scraper.py`. (Low) — `MiseEnContexte.faits_traces` et `deductions_llm` sont persistés et jamais affichés, mais US-03 contextualiseur exige la persistance et non l'affichage : conservation légitime, pas de finding.
- **Points conformes** : `corroboration` et `decalage_viral` restent au barème `POIDS_PAR_DEFAUT` alors qu'aucun code ne les produit — et le commentaire de `score.py:4-9` explique que c'est délibéré (US-08 fixe les sept poids, un signal absent ne contribue à rien) en citant le finding d'audit qui l'avait relevé. C'est la bonne façon de conserver quelque chose. `pyproject.toml` a été réduit à sa seule fonction réelle, avec le raisonnement en commentaire. Aucune abstraction spéculative, aucune interface à un seul implémenteur, aucun paramètre inutilisé.

### SRE/Performance Auditor
- **Verdict** : 🔴 AUDIT_FAIL
- **Findings** : commit unique pour 300 articles (High) ; pool du contextualiseur non borné et croissant à vie, filtrage seuil/tri/plafond faits en Python après chargement intégral (Medium) ; absence de `timeout-minutes` sur le workflow hebdomadaire (Low).
- **Points conformes** : `_respecter_le_debit_sec` respecte la politique d'accès équitable SEC (0,15 s ≈ 6,7 req/s contre 10 autorisées), avec un commentaire qui explique pourquoi le verrou précédent était inutile ; clients HTTP créés une fois par run et fermés en `finally` ; `EVALUATEUR_PLAFOND_ARTICLES` borne le run avec report explicite du reliquat et journalisation du nombre reporté ; pagination du frontend en `LIMIT n+1` sans `COUNT(*)` ; index posés sur `domaine_source`, `date_publication`, `hash_contenu`, `score_final` ; `pool_pre_ping` activé ; les backfills itèrent par lots de 200.

### Architecture Consistency Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** : la règle « pas d'appel direct entre blocs » est violée par le frontend et appliquée par duplication ailleurs, sans qu'aucun document n'arbitre entre les deux traitements. (Medium, cf. Layer Enforcer)
- **Points conformes** : aucun module fantôme — tous les fichiers annoncés par `README.md`, `plan_implementation.md` et les workflows existent et sont exécutables ; la topologie décrite dans `architecture.md` (Vercel + GitHub Actions + Supabase) correspond exactement à `vercel.json`, `api/index.py` et aux cinq workflows ; le principe « pas de rescoring en v1 » est tenu, et les deux exceptions (backfills) sont documentées en tête de fichier avec leur périmètre strict et leur raison ; `keepalive_supabase.yml` documente correctement pourquoi une visite non authentifiée ne réveille pas la base — vérifié : `compte_courant` lève `AccesRefuse` avant tout `session.execute`.

### Contextual Threat Analyst
- **Verdict** : 🟡 Avertissement
- **Scénarios examinés** :
  - *Un émetteur de désinformation veut faire baisser son propre score.* Voie la plus efficace : faire produire par un fact-checker complaisant, ou simplement faire indexer, un `textualRating` contenant « true » ou « accurate » sous une forme négative — « Not true », « Inaccurate ». Le signal le plus lourd bascule alors de 90 à 5. Aucune fabrication n'est même nécessaire : les verdicts réels suffisent (Critique, cf. Business Logic).
  - *Le même veut échapper au signal stylistique.* Publier en français : le lexique FR n'est pas appliqué (High). Ou inclure un lien dans le résumé RSS : la pénalité « aucune citation » disparaît (High).
  - *Le même veut manipuler le LLM de scoring.* `encadrer_contenu_non_fiable` + `CONSIGNE_CONTENU_NON_FIABLE` traitent le cas frontal ; une balise fermante variante sort du cadre mécanique mais reste couverte par la consigne système (Low, [RISQUE]).
  - *Un visiteur non authentifié cartographie l'application.* `/openapi.json` livre les quatre chemins et les noms de champs (Medium, cf. SAST).
  - *Un attaquant veut identifier le superadmin.* Écart de temps bcrypt vs `compare_digest` sur `/login` (Low, [RISQUE]).
- **Points conformes** : le plafond de `/login` a été conçu contre les deux échecs réels — le contournement par `X-Forwarded-For` tournant et le déni de service par saturation du compteur — et les deux propriétés sont verrouillées par des tests qui rejouent la mesure d'origine ; la contrainte `ck_comptes_superadmin_a_un_code` rend l'état dangereux impossible en base plutôt que de compter sur une procédure ; le placeholder aléatoire du superadmin est le bon défaut (inaccessible plutôt qu'accessible au mot de passe partagé).

### SAST Scanner
- **Verdict** : 🟡 Avertissement
- **Findings** : `/docs`, `/redoc`, `/openapi.json` non gardés (Medium) ; mot de passe en clair transmis en paramètre à Postgres, exposé si le serveur journalise les paramètres liés (Low, [RISQUE]).
- **Points conformes** : aucune injection SQL — tout passe par SQLAlchemy Core/ORM avec paramètres liés, y compris `func.crypt(mot_de_passe, secret_hash)` ; aucun XSS — Jinja2 autoescape actif, zéro `|safe`, zéro `Markup` ; aucun path traversal (pas de service de fichiers) ; aucune désérialisation non sûre (JSON uniquement) ; aucun secret en dur dans les fichiers suivis — la seule occurrence trouvée est une clé factice de test (`test_correctifs_audit.py:64`) et des identifiants `postgres/postgres` de service CI local ; `.env` et `.env.local` non suivis, `.gitignore` correct avec exception explicite pour `.env.example` ; HMAC-SHA256 avec `hmac.compare_digest` (comparaison à temps constant), bcrypt côté base pour le code personnel ; cookie `httponly` + `secure` + `samesite=lax`, avec attributs symétriques à la suppression ; `article_id` typé `uuid.UUID` dans la signature de route, donc validé avant d'atteindre SQL.

### Supply Chain & Artifact Auditor
- **Verdict** : 🟢 OK
- **Findings** : pas de lockfile — deux exécutions du même commit peuvent résoudre des versions différentes. Le risque est **connu, documenté et compensé** par l'archivage d'un `pip freeze` en artefact CI (`ci.yml:73-83`), ce qui rend l'écart diagnosticable a posteriori. Reste une compensation, pas une prévention. (Low)
- **Points conformes** : bornes hautes explicites sur les 12 dépendances du batch et les 6 du frontend, avec la raison en commentaire ; le modèle NER `en_core_web_sm` est **épinglé à 3.8.0** par URL de release dans la CI, le pipeline et le README — les trois cohérents, ce qui est précisément ce qu'exige un artefact dont la version change la sortie d'un signal ; `api/requirements.txt` est séparé et réduit, avec la justification (bundle Vercel) ; toutes les actions GitHub sont épinglées à une majeure (`@v4`, `@v5`) ; aucun asset vendored, aucun script d'installation distant hors la roue spaCy épinglée.

### Privacy/Exfiltration Auditor
- **Verdict** : 🟡 Avertissement
- **Findings** :
  - `.env.example:88-93` — note « Données sortantes » omettant Anthropic, qui reçoit titre + jusqu'à 4 000 caractères de contenu par article scoré et 2 000 par mise en contexte, corps de posts Reddit inclus. (Medium)
  - `evaluateur/source_primaire.py:279` — message d'exception brut persisté puis affiché. (Medium, cf. division Sherlock)
  - `evaluateur/fact_checking.py:76` — `logger.warning(…, exc)` conserve volontairement le détail complet dans le log, ce qui inclut l'URL avec `?key=…` en cas de `HTTPStatusError`. Le commentaire l'assume (« GitHub masque les secrets »), ce qui est exact pour les runs GitHub Actions où la clé est un secret déclaré. Vrai dans le contexte d'exécution réel du module ; à ne pas généraliser à une exécution locale. Pas de finding, mais la nuance mérite d'être écrite dans le commentaire.
- **Points conformes** : le frontend n'exfiltre rien — aucun appel réseau sortant depuis le code applicatif, aucune télémétrie, aucun asset distant dans les gabarits (le CSS est inline, cf. cependant `/docs`) ; le rôle et le pseudo ne sont jamais rendus aux gabarits, propriété vérifiée par test sur les deux pages ; les `raison` persistées ne portent que le type d'exception sur quatre des cinq chemins ; `reddit.py:32` stocke l'auteur mais aucun gabarit ne l'affiche ; `architecture.md:139` déclare explicitement le RGPD et le droit de republication comme non traités en phase prototype et en fait une condition bloquante à toute ouverture publique — la limite est assumée, pas ignorée.

---

## Points conformes majeurs (à ne pas casser)

1. **La CI ne ment plus.** 184 tests, budget de skips à zéro, vrai Postgres avec les trois migrations appliquées, échec si un test est skippé, déclenchement sur toutes les branches. Vérifié ici par exécution : `184 passed` en 134 s, 0 skip.
2. **L'authentification est fail-closed et sérieusement testée.** `FRONTEND_PASSWORD` absente ⇒ accès refusé, pas accès libre ; mode local explicite ; expiration dans la charge signée ; clé HMAC liée au `secret_hash` ; plafond qui ne s'applique qu'aux échecs ; `X-Forwarded-For` ignoré sans déclaration explicite. Chacune de ces propriétés a un test nommé qui rejoue le scénario d'attaque mesuré.
3. **La base défend ses invariants.** `ck_scores_non_evaluable_coherent`, `ck_scores_score_final_range`, `ck_comptes_superadmin_a_un_code`, unicité sur `url_canonique` et sur `lower(pseudo)`. Le schéma refuse les états incohérents plutôt que de compter sur le code — et c'est ce qui a permis de *prouver* le finding High sur le commit unique.
4. **`fakenews.schema` transforme une panne opaque en diagnostic.** Le meilleur module du dépôt : il traite un problème réel (deux canaux de déploiement non synchronisés), il refuse de créer un nouveau mode de panne, et ses trois branches sont testées.
5. **Les commentaires portent des mesures, pas des opinions.** « mesuré : 50 tentatives avec un en-tête tournant, zéro refus », « `q="announces fourth quarter"` → 0 hit sur un dépôt qui existe ». Cette discipline rend l'audit possible et doit survivre à toute refonte.

---

## Limites de vérification

- **Commandes exécutées** : `pytest --collect-only` (184 tests) ; création d'une base Postgres locale **dédiée et vide** (`fakenews_audit_tmp`), application des trois migrations, `pytest -q` complet → `184 passed, 0 skipped, 1 warning` en 133,9 s ; huit sondes Python ciblées (`_interpreter_verdict`, `_detecter_langue`, `evaluer_style` sur HTML, `evaluer_source_primaire` avec NER en échec, `selectionner_articles_a_traiter` sur deux runs simulés, `evaluer_articles_non_scores` avec LLM factice hors bornes, énumération des routes FastAPI, requêtes non authentifiées en mode hébergé) ; base temporaire supprimée en fin d'audit. Aucun fichier de production modifié.
- **Commandes bloquées** : `git log --all --name-only` et `git grep` sur l'historique complet ont échoué (`fatal: mmap failed`, `short read: Operation timed out`) — le volume hébergeant le dépôt renvoie des erreurs d'E/S intermittentes. **Conséquence : la recherche de secrets dans l'historique Git n'a pas pu être menée.** Elle n'a porté que sur les fichiers suivis à l'état actuel (aucun secret réel trouvé). À rejouer sur une copie locale du dépôt.
- **Non vérifiable depuis ici** : le comportement réel des API Google Fact Check Tools et SEC EDGAR (garde `_pas_de_reseau` active, et aucun appel sortant n'a été tenté) ; la configuration de journalisation de l'instance Supabase (d'où le classement `[RISQUE]` du mot de passe transmis à `crypt()`) ; le comportement du runtime Vercel (nombre d'instances tièdes, donc plafond `/login` réel ; réécriture effective de `X-Forwarded-For`) ; les variables d'environnement effectivement posées sur Vercel et dans les secrets GitHub ; l'écart de temps bcrypt/`compare_digest` n'a pas été chronométré, il est déduit de la lecture.
- **Hors périmètre de vérification** : US-03 scraper (GDELT), US-02 et US-06 évaluateur — non implémentés et documentés comme tels ; aucun finding n'est ouvert à leur sujet.

---

# Correctifs appliqués (2026-09-09)

Tous les correctifs ci-dessous sont sur la branche `audit/correctifs-codebase`,
au-dessus de `be28cb2`. **Suite : 298 tests, 0 skip** (184 avant), contre un
Postgres neuf avec les trois migrations — le budget `SKIPS_MAX=0` de la CI tient.

## Findings fermés

| # | Sévérité | Finding | Correctif | Preuve |
| --- | --- | --- | --- | --- |
| 1 | **Critique** | Verdict de fact-checking inversé | `_interpreter_verdict` compare des jetons entiers bornés d'espaces, sur **trois niveaux ordonnés** (ambigu → faux → vrai) ; défaut à `None` | `fact_checking.py:40-108` · 34 verdicts réels + 7 formes niées testés |
| 2 | High | Score LLM non borné + commit tout-ou-rien | Score hors [0,100] **exclu** (pas écrêté) ; commit par lots de 25 avec rollback isolé et articles perdus nommés | `llm_bootstrap.py:57-73`, `run_evaluateur.py:40-64` |
| 3 | High | Seuil et plafond non configurables (US-01) | Module `fakenews/config.py` : `CONTEXTUALISEUR_SEUIL`, `LLM_PLAFOND_CONTEXTUALISEUR`, `LLM_PLAFOND_BACKFILL`, bornes validées | `config.py` · `test_conformite_exigences.py` |
| 4 | High | Lexique français jamais appliqué | Comparaison des poids FR/EN sur les **occurrences**, listes élargies, départage par accents | `style.py:34-77` · 30 titres réels |
| 5 | High | `href="…"` compté comme citation | Nettoyage HTML **à la collecte** ; URL retirées avant analyse | `rss.py:31-56`, `style.py:127-136` |
| 6 | Medium | `/docs`, `/redoc`, `/openapi.json` publics | Désactivées | `app.py:33` · 3 tests → 404 |
| 7 | Medium | Fuite d'exception NER | `type(exc).__name__`, 5ᵉ site du finding H2 | `source_primaire.py:279` |
| 8 | Medium | `select(Score)` intégral en mémoire | `WHERE … ORDER BY … LIMIT` en SQL | `run_contextualiseur.py:23-70` |
| 9 | Medium | `rss.py` sans protection au grain de l'entrée | `begin_nested()` par entrée, **et** par post côté Reddit | `rss.py:139-163`, `reddit.py:85-93` |
| 10 | Medium | Backfill LLM sans plafond | `LLM_PLAFOND_BACKFILL` (défaut 100) | `backfill_llm_bootstrap.py:35-46` |
| 11 | Medium | Avertissement persisté jamais relu (US-04) | La page de détail affiche la valeur en base, repli sur la constante | `app.py:576-590` |
| 12 | Medium | Import inter-blocs `frontend → contextualiseur` | Le seuil vit dans `fakenews.config` | `app.py:26` |
| 13 | Medium | Ratio du taux de suspicion faux (US-01) | Dénominateur = total scoré, calculé en SQL | `run_contextualiseur.py:57-63` |
| 14 | Medium | Anthropic absent des données sortantes | Section réécrite : titre **et** corps, 4 000 / 2 000 caractères | `.env.example:104-119` |
| 15 | Low | Compteurs de backfill mensongers | `nb_valides` distinct de `nb_traites` | les deux backfills |
| 16 | Low | `KeyError` nu sur `DATABASE_URL` | `SystemExit` nommant les trois endroits où la poser | `db.py:26-39` |
| 17 | Low | Balise fermante neutralisée à la casse exacte | Regex insensible casse/espaces | `llm.py:37-42` |
| 18 | Low | Contrainte SQL dépendant du `repr` d'un tuple | `_liste_sql()` | `models.py:21-28` |
| 19 | Low | Pipeline sans `timeout-minutes` | `timeout-minutes: 60` | `pipeline_hebdomadaire.yml:14` |
| 20 | Low | `reuters.com` en réputation inconnue | Ajouté à `FIABLE` | `reputation.py:11-22` |
| 21 | Low | `test_valeur_plafonnee_a_100` ne tue aucune mutation | Voir finding **N1** ci-dessous | `test_style.py:65-89` |

## Trouvé pendant la correction

- **N1 — Low — Le plafond à 100 du signal de style est inatteignable.** En
  cherchant un cas qui sature, on constate que le maximum structurel est **80**
  (20 + 15 + 15 + 30). `min(100.0, penalite)` est donc du code mort aujourd'hui.
  Conservé comme garde-fou en cas de futur réglage des pénalités, mais le test
  l'énonce désormais : il asserte `== 80.0`, ce qui le rend sensible aux quatre
  constantes. Preuve : `style.py:141-171`, `test_style.py:65`.
- **N2 — Medium — `SystemExit` levé dans un gestionnaire de requête ASGI.**
  Première version du correctif 3 : le frontend résolvait le seuil à chaque
  requête, donc une valeur hors bornes cassait le groupe de tâches du serveur au
  lieu de produire une erreur lisible — **constaté en exécutant l'application**,
  pas déduit. Le seuil est désormais résolu **au chargement du module**
  (`app.py:35-50`) : une valeur invalide fait échouer le démarrage, donc le
  déploiement, ce qui se voit. Un test en sous-processus le verrouille.
- **N3 — Low — La fixture `db_session` ne survivait pas à un rollback applicatif.**
  Le correctif 2 (rollback par lot) faisait annuler la transaction du test
  elle-même (`SAWarning: transaction already deassociated`). Passage à
  `join_transaction_mode="create_savepoint"` (`conftest.py:96-107`).

## Vérification

- **Corpus adverse** : rejoué contre l'implémentation d'ORIGINE, le nouveau corpus
  détecte **3 verdicts inversés** (`Inaccurate`, `This is not true`,
  `Not accurate`), **14/34 verdicts mal classés**, **4/7 formes niées lues comme
  vrai** et **7/15 titres français traités en anglais**. Il ne s'agit donc pas de
  tests qui décrivent le correctif après coup.
- **Test de mutation** : `begin_nested()` remplacé par `if True` → la 3ᵉ entrée
  échoue en `PendingRollbackError`, le test tombe. La protection est bien exercée.
- **Bout en bout** : trois articles réels insérés puis évalués par le vrai
  `run_evaluateur` — l'article putaclic francophone obtient 78,3 (style 55,0 :
  le lexique FR s'applique enfin), Le Monde 6,7 (citation reconnue), BBC 8,3.
  Frontend vérifié sur base réelle : `/docs` → 404, seuil relu, seuil hors bornes
  → échec au démarrage avec message. Bases temporaires supprimées.
- **Faux positif corrigé** : un premier test « écriture refusée par la base »
  passait sans rien exercer — `canonicaliser_url` retire la query string, donc la
  déduplication applicative interceptait le doublon avant la contrainte SQL.
  Remplacé par une violation `NOT NULL` que le code applicatif ne peut pas voir.

## Restant ouvert

| Finding | Pourquoi |
| --- | --- |
| Sources francophones douteuses (US-01 scraper) | **Décision produit** : choisir les sources dans le Décodex et vérifier leurs flux. Pas un correctif de code. |
| `main` 8 commits derrière | C'est `a620c27` qui tourne sur Vercel : dix phases d'audit, dont trois correctifs de sécurité, ne sont pas déployées. **Action d'exploitation.** |
| Recherche de secrets dans l'historique Git | Toujours bloquée par les erreurs d'E/S du volume (`mmap failed`). À rejouer sur une copie. |
| `[RISQUE]` mot de passe transmis à `crypt()` · écart de temps bcrypt | Dépendent d'une configuration Supabase non observable d'ici. |
| `run_reddit.py` / `run_rss.py` | **Conservés délibérément** malgré la recommandation de suppression : 17 lignes chacun, utiles pour rejouer une seule source en débogage. |
| `canonicaliser_url` retire la query string | Fragilité à l'ajout d'une source, pas un défaut actif sur les huit flux courants. |
