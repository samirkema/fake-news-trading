# Audit phase 14 — Codebase complète (état de travail non commité)

Date : 2026-09-10 · Scope : `src/`, `tests/`, `api/`, `supabase/migrations/`,
`.github/workflows/`, `doc/`, `README.md`, fichiers de configuration.
Base d'exigences : `doc/V0/userstories_*.md`, `doc/V0/architecture.md`,
`doc/V0/plan_implementation.md`, `doc/V1/comptes-3-roles.md`.
État audité : arbre de travail (23 fichiers modifiés non commités, `declenchement.py`
et `test_declenchement.py` supprimés).

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | Un verdict de fact-checking sans rapport avec l'article peut être appliqué à 90/100 ; une partie du corpus collecté n'est jamais notée et disparaît en silence. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Une saisie non-ASCII sur `/login` rend 500 ; un test « garde-fou » ne peut plus échouer ; deux backfills dupliqués ont déjà divergé. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Le frontend importe toujours un bloc métier, exactement ce que `config.py` a servi à éviter pour le seuil. Le plafond d'articles de l'évaluateur n'a pas de mécanisme de rattrapage. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant | Le plafond anti-bruteforce de `/login` n'oppose aucune friction : 60 essais mesurés en 0,10 s, tous évalués, et le bon mot de passe passe compteur plein. |

**Verdict global : AUDIT_FAIL.** 4 High, 7 Medium, 8 Low. Aucun Critique.

Contexte à charge de la codebase : la suite complète passe (**321 tests, 0 skip**)
contre un vrai Postgres avec les trois migrations appliquées, et les correctifs des
phases 6 à 13 tiennent — les défauts ci-dessous sont, pour trois d'entre eux, des
angles morts que la suite ne regarde pas, pas des régressions de correctifs passés.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | évaluateur, contextualiseur | 0 | 2 | 2 | 1 | AUDIT_FAIL |
| Requirements Compliance Auditor | 4 blocs vs user stories | 0 | 1 | 0 | 1 | AUDIT_FAIL |
| Doc-Sync Auditor | README, plan, `.env.example`, commentaires | 0 | 0 | 1 | 1 | AUDIT_PASS (réserves) |
| A11y/UX Checker | templates Jinja | 0 | 0 | 0 | 2 | AUDIT_PASS |
| Clean Code Auditor | `src/` | 0 | 0 | 1 | 1 | AUDIT_PASS (réserves) |
| Fail-Loud Auditor | chemins d'erreur | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Test Quality Auditor | `tests/` | 0 | 0 | 2 | 1 | AUDIT_FAIL |
| Mutation/Saboteur Auditor | invariants critiques | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| Layer Enforcer | frontières entre blocs | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| YAGNI Auditor | `src/`, config | 0 | 0 | 0 | 1 | AUDIT_PASS |
| SRE/Performance Auditor | runs, plafonds, workflows | 0 | 1 | 0 | 2 | AUDIT_FAIL |
| Architecture Consistency Auditor | code vs `architecture.md` | 0 | 0 | 1 | 0 | AUDIT_PASS (réserves) |
| Contextual Threat Analyst | scénarios d'abus | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| SAST Scanner | injections, authz, secrets | 0 | 0 | 1 | 2 | AUDIT_PASS (réserves) |
| Supply Chain & Artifact Auditor | deps, modèle NER, artefacts | 0 | 0 | 0 | 2 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | données sortantes, journaux | 0 | 0 | 1 | 0 | AUDIT_PASS (réserves) |

(Les totaux par sous-audit comptent les findings vus sous cet angle ; un même finding
peut apparaître dans deux sous-audits. Le décompte global dédupliqué est de 19.)

---

## Matrice De Couverture Des Contrats Principaux

| Contrat / Exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| US-03 évaluateur — verdict rattaché à l'article | `evaluateur/fact_checking.py:156-171` | garde-fou de pertinence court-circuité quand `text` est absent | ❌ F1 |
| US-03 évaluateur — API indisponible ⇒ signal exclu | `evaluateur/fact_checking.py:172-183` | type d'exception seul, jamais la clé | ✅ |
| US-04 évaluateur — pénalité conditionnée à une claim vérifiable | `evaluateur/source_primaire.py:296-304` | garde-fou avant appel réseau | ✅ |
| US-04 évaluateur — débit SEC respecté | `evaluateur/source_primaire.py:37-47` | 0,15 s entre appels | ✅ |
| US-05 évaluateur — lexiques par langue | `evaluateur/style.py:58-100` | corpus réel, `test_signaux_corpus_reel.py:63-89` | ✅ |
| US-07 évaluateur — plafond d'appels LLM configurable | `run_evaluateur.py:178`, `backfill_llm_bootstrap.py:41-47` | 3 plafonds distincts | ✅ |
| US-08 évaluateur — trace de la contribution par signal | `evaluateur/score.py:35-58`, migration `0003` | `detail_calcul` persisté | ✅ |
| US-08 évaluateur — tout article scoré finit par l'être | `run_evaluateur.py:83-100` | tri `date desc` + plafond ⇒ famine du reliquat | ❌ F3 |
| US-01 contextualiseur — seuil et plafond configurables | `config.py:75-77`, `run_contextualiseur.py:39-40` | lus dans l'environnement | ✅ |
| US-02 contextualiseur — `faits_traces` validés hors prompt | `contextualiseur/validation.py:13-35` | post-traitement mécanique | ✅ |
| US-04 contextualiseur — avertissement porté par la donnée | `frontend/app.py:628`, `models.py` | colonne relue, pas la constante | ✅ |
| US-01 frontend — seuil partagé avec le contextualiseur | `config.py`, `frontend/app.py:70` | même fonction | ✅ |
| US-04 frontend — aucune écriture | `frontend/app.py` (entier) | aucun `add`/`commit`/`delete` | ✅ (non testé, F12) |
| US-04 frontend — auth fail-closed | `frontend/app.py:358-366` | mode local explicite requis | ✅ |
| US-04 frontend — auth réellement opposable | `frontend/app.py:418-452` | plafond sans effet mesuré | ❌ F4 |
| US-04 frontend — connexion robuste aux entrées | `frontend/app.py:436` | 500 sur mot de passe non-ASCII | ❌ F2 |
| `architecture.md` — pas d'appel direct entre blocs | `frontend/app.py:27` | import de `contextualiseur.avertissement` | ⚠️ F6 |
| `architecture.md` — dégrader jamais bloquer | `rss.py:164-191`, `reddit.py:85-97`, `run_evaluateur.py:49-69` | isolation au grain de l'entrée | ✅ |

---

## Top Findings

- **[High] `src/fakenews/evaluateur/fact_checking.py:158`** — ✅ **corrigé le
  2026-09-10**, cf. « Suivi des correctifs » en fin de document. Quand la claim renvoyée
  par Google n'a pas de champ `text` (ou l'a vide), le contrôle de pertinence n'est
  pas appelé du tout : un verdict « False » portant sur un sujet sans aucun rapport
  est appliqué à l'article, valeur 90, poids 1,5 — le plus lourd du barème.
  **Correction attendue :** évaluer la pertinence dans TOUS les cas
  (`if not _claim_est_pertinente(titre, texte_claim or ""): continue`), la fonction
  retournant déjà `False` sur texte vide.
- **[High] `src/fakenews/frontend/app.py:436`** — ✅ **corrigé le 2026-09-10**
  (deux sites, cf. « Suivi des correctifs »). `hmac.compare_digest` refuse deux
  `str` non-ASCII et lève `TypeError`. Un mot de passe saisi avec un accent renvoie
  500 ; surtout, un `FRONTEND_PASSWORD` accentué rend le site **entièrement
  inaccessible**, y compris avec le bon mot de passe, sans le moindre diagnostic.
  **Correction attendue :** comparer des `bytes`
  (`hmac.compare_digest(mot_de_passe.encode(), partage.encode())`).
- **[High] `src/fakenews/evaluateur/run_evaluateur.py:83-100`** — la sélection trie
  par `date_publication desc` puis coupe au plafond. Les articles laissés de côté
  ne sont pas « reportés au prochain run » comme l'affirment le commentaire (l. 36-38)
  et le journal (l. 96-100) : le run suivant reprend les plus récents, c'est-à-dire
  ceux collectés entre-temps. Le reliquat est affamé définitivement.
  **Correction attendue :** traiter le reliquat d'abord (tri `date asc` sur les
  non-scorés, ou deux tranches : reliquat puis nouveautés), ou rendre le plafond
  supérieur à l'ingestion réelle (≥ 500 posts Reddit par run, cf. `sources_reddit.py:16`).
- **[High] `src/fakenews/frontend/app.py:418-452`** — ✅ **traité le 2026-09-10**
  (délai croissant, cf. « Suivi des correctifs »). Le plafond de `/login` ne
  refuse jamais l'ÉVALUATION d'une tentative : il change seulement la page d'erreur.
  Mesuré : 60 essais en 0,10 s, tous vérifiés, puis le bon mot de passe accepté
  compteur plein. Aucun délai, aucun rejet — le contrôle est décoratif, exactement
  le motif que l'audit phase 8 condamnait pour `X-Forwarded-For`.
  **Correction attendue :** refuser la vérification quand le plafond est atteint,
  avec une clé qui ne peut pas devenir un déni de service global (par pseudo, pas par
  identifiant client partagé derrière le proxy), ou à défaut imposer un délai
  croissant sur les échecs.
- **[Medium] `tests/test_conformite_exigences.py:134`** — l'assertion garde contre
  l'import de `fakenews.contextualiseur.declenchement`, module **supprimé** dans cet
  arbre de travail : elle ne peut plus échouer. Pendant ce temps l'import inter-blocs
  réel — `from fakenews.contextualiseur.avertissement import AVERTISSEMENT`
  (`frontend/app.py:27`) — n'est couvert par aucune des trois assertions.
- **[Medium] `src/fakenews/evaluateur/backfill_fact_checking.py:35-96` vs
  `backfill_llm_bootstrap.py:45-120`** — même boucle dupliquée à ~80 %, et la
  divergence est déjà là : le backfill LLM est plafonné, celui du fact-checking ne
  l'est pas.

---

## Thèmes Transverses

1. **Le garde-fou existe, mais le site d'appel le contourne.** F1 (pertinence non
   appelée) et F4 (plafond qui n'empêche rien) partagent la même forme : la fonction
   défensive est correcte et testée EN ISOLATION, l'appelant la rend inopérante. Les
   tests unitaires du helper passent, l'exigence n'est pas tenue.
2. **Une promesse écrite dans un commentaire ne remplace pas un mécanisme.** F3 est
   documenté à l'envers dans le code lui-même (« repris au prochain run »), et le
   journal l'affirme à chaque run.
3. **Ce qui n'est pas ASCII n'a jamais été essayé.** F2 sur un projet dont toute
   l'interface, la documentation et les mots de passe probables sont francophones.
4. **La suite de tests vérifie des codes de statut, pas des propriétés de sécurité.**
   Aucun test ne mesure la friction opposée à un attaquant ; ils vérifient qu'un 429
   apparaît.

---

## Détails Par Division

### Division Métier (Anton Ego)

Ah, le fact-checking. On m'avait vendu une machine à confronter les affirmations aux
verdicts des vérificateurs, et l'on découvre qu'elle sert le verdict d'un autre plat
dès que l'assiette arrive sans étiquette.

- **[High] F1** `evaluateur/fact_checking.py:158` — le filtre de pertinence, ajouté en
  phase 12 précisément parce qu'une recherche floue associe un verdict à un article
  sans rapport, n'est consulté que si `claim["text"]` est non vide. La docstring de
  `_claim_est_pertinente` (l. 118-121) déclare pourtant que l'absence de texte rend la
  pertinence *invérifiable* et que le verdict ne doit pas être utilisé. Le site
  d'appel dit le contraire de la fonction qu'il appelle. **Type : Confirmé** (mesuré,
  cf. Commandes) ; la fréquence réelle des claims sans `text` dans l'API Google est,
  elle, **[RISQUE]**.
- **[High] F3** `run_evaluateur.py:83-100` — famine du reliquat, cf. Top Findings.
  **Type : Confirmé** (reproduit : un article dépassé par la collecte suivante n'est
  jamais noté). Un article jamais noté n'existe pas pour le frontend, qui joint
  `Score` en `inner join` (`frontend/app.py:553`).
- **[Medium] F7** `contextualiseur/run_contextualiseur.py:52` — même forme, effet
  atténué : le tri par score décroissant plafonné à 20 par run affame les articles
  juste au-dessus du seuil dès que plus de 20 articles suspects arrivent par semaine.
  Contrairement à F3, un article traité quitte le vivier, donc l'avancement existe ;
  il n'est simplement pas garanti. `.env.example` promet « repris aux runs suivants,
  du score le plus élevé au plus faible » — la deuxième moitié de la phrase est
  exacte, la première est optimiste.
- **[Medium] F8** `evaluateur/fact_checking.py:107-111` — la troncature des mots à
  5 caractères, introduite en phase 13 pour la flexion française, élargit aussi le
  recouvrement : « vaccination », « vaccins », « vaccinés » se réduisent au même
  jeton. Avec un seuil de 2 jetons communs, deux sujets d'actualité voisins peuvent
  se croiser. **Type : [RISQUE]** — mécanisme confirmé par lecture, taux de faux
  positifs non mesuré faute de corpus étiqueté.
- **[Low] F9** `evaluateur/style.py:141-143` — la pénalité « aucun auteur
  identifiable » (+20) tombe sur tout flux RSS ne publiant pas de byline dans son
  XML (cas courant, notamment BBC World, `sources_rss.py:18-21`). Le signal mesure
  alors le format du flux, pas la pratique éditoriale de la source. **Type :
  [RISQUE]** — l'effet dépend des flux réellement collectés.

### Division Qualité (Gordon Ramsay)

Un `TypeError` sur un accent. Sur un projet écrit intégralement en français. Vous
avez blindé le seuil hors bornes, blindé la variable illisible, blindé la clé absente
— et personne n'a jamais tapé « café » dans le champ mot de passe.

- **[High] F2** `frontend/app.py:436` — cf. Top Findings. **Type : Confirmé** (mesuré :
  401 en ASCII, 500 sur `'mötdepasse'` ; et 500 sur le BON mot de passe si le partagé
  est accentué). Le contraste est saignant : `config.py:47-56` prend la peine de
  nommer la variable, la valeur et la marche à suivre pour un entier mal saisi, et la
  seule porte d'entrée du site rend une trace 500 nue.
- **[Medium] F5** `backfill_fact_checking.py` / `backfill_llm_bootstrap.py` —
  duplication et divergence, cf. Top Findings. Le backfill fact-checking parcourt
  toute la table `scores` sans plafond d'appels (l. 42-86) ; l'API est gratuite, mais
  elle a un quota journalier, et l'argument « ces correctifs appellent la même API sur
  TOUTE la table » (`backfill_llm_bootstrap.py:36-41`) vaut identiquement pour lui.
- **[Low] F10** `frontend/app.py:507`, `:520` — `HTTPException(422)` produit une
  réponse JSON là où tout le reste du site rend du HTML. Un filtre malformé sort
  l'utilisateur de l'interface.

### Division Architecture (Steve Jobs)

Vous avez déplacé le seuil dans un module neutre en écrivant trois paragraphes pour
justifier que le frontend ne devait pas importer un bloc métier. Puis vous avez laissé
l'import juste au-dessus.

- **[Medium] F6** `frontend/app.py:27` — `from fakenews.contextualiseur.avertissement
  import AVERTISSEMENT`. `architecture.md` (« les blocs ne s'appellent pas entre eux
  directement ») et `config.py:13-27` (qui applique la règle au seuil, et rappelle que
  `reputation.py` va jusqu'à DUPLIQUER une liste pour l'éviter) sont sans ambiguïté.
  Deux issues cohérentes : déplacer la constante dans `fakenews.config` (une chaîne
  partagée entre deux blocs, exactement le cas d'usage du module), ou écrire dans
  `architecture.md` que la règle ne vise que le comportement et pas les constantes.
  L'état actuel est le seul qui ne soit pas défendable. **Type : Écart documentaire +
  Confirmé.**
- **[Low] F11** `evaluateur/score.py:14-22` — `corroboration` et `decalage_viral` au
  barème sans producteur. Conservé en connaissance de cause et sans effet de calcul :
  **non retenu comme défaut**, mentionné pour clore la question posée à chaque audit.
- Le reste tient : `api/requirements.txt` réduit, blocs sans appel croisé (hors F6),
  contrat de base de données respecté, `verifier_schema` au bon endroit.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : vous comptez les tentatives, vous journalisez le refus,
vous rendez un 429 — et vous vérifiez le mot de passe quand même, à chaque fois, sans
la moindre milliseconde d'attente. Le compteur n'est pas une serrure, c'est un
carnet de notes.

- **[High] F4** `frontend/app.py:418-452` — cf. Top Findings. Scénario d'attaque :
  l'attaquant connaît l'existence du site (URL Vercel), poste des couples
  pseudo/mot de passe en boucle ; à 600 essais/seconde mesurés en local, un mot de
  passe partagé faible tombe. Le 429 ne lui coûte rien — il ne le lit même pas. La
  seule protection réelle reste l'entropie de `FRONTEND_PASSWORD`.
  **Type : Confirmé (mesuré).**
- **[Medium] F13** `frontend/app.py:324-345` — le cache `(role, secret_hash)` de 60 s
  retarde d'autant la révocation d'un code personnel : changer le `secret_hash` de
  `samirkema` en base laisse l'ancien cookie valide jusqu'à 60 s **par instance
  Vercel tiède**. Effet secondaire non documenté d'un correctif de performance de la
  phase 12. **Type : Confirmé** (lecture ; la fenêtre par instance est **[RISQUE]**,
  elle dépend du parc d'instances).
- **[Medium] F14** `frontend/app.py:430-434` — le mot de passe en clair est transmis
  comme paramètre SQL à `crypt()`. Si Supabase active `log_statement='all'` ou un
  `log_min_duration_statement` bas, les paramètres liés apparaissent en clair dans les
  journaux du serveur. Une vérification bcrypt côté Python garderait le secret dans le
  process. **Type : [RISQUE]** — dépend d'une configuration Supabase non vérifiable
  d'ici.
- **[Medium] F15** `contextualiseur/generation.py:75` — la `raison` d'un signal est
  encadrée par `encadrer_contenu_non_fiable` (l. 73), mais le `preuve_id` interpolé
  juste à côté ne l'est pas ; or il contient l'URL renvoyée par l'API tierce
  (`fact_checking.py:170`). Surface d'injection étroite (une URL), mais c'est le seul
  fragment d'origine externe qui atteint le prompt hors du cadre. **Type : [RISQUE].**
- **[Low] F16** `templates/detail.html:11` — `href="{{ article.url }}"` sans
  validation de schéma ; l'URL vient d'un flux tiers. La CSP `default-src 'self'`
  (`app.py:48-50`) neutralise `javascript:`, l'échappement Jinja empêche la sortie
  d'attribut. **Type : [RISQUE] mitigé** — une liste blanche `http/https` reste la
  défense au bon endroit.
- **[Low] F17** `frontend/app.py:48-50` — CSP sans `form-action` ni `base-uri`. Sur un
  site à un seul formulaire, c'est peu, mais ce sont les deux directives qui bloquent
  le détournement d'un POST de connexion.
- Points tenus, et ils comptent : cookie signé avec l'expiration DANS la charge,
  clé dérivée du `secret_hash` pour les comptes à code personnel, superadmin
  contraint par le schéma (`0002_comptes.sql:57-59`), `/docs` fermé, en-têtes de
  sécurité posés, secrets jamais recopiés dans `raison`, `.env*` ignoré (`.env.local`
  vérifié non suivi).

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_FAIL.
- **Findings :** F1 (High), F3 (High), F7 (Medium), F8 (Medium), F9 (Low).
- **Points conformes :** exclusion des signaux non applicables et `non_evaluable`
  cohérents de bout en bout (`score.py:62-65`, `run_contextualiseur.py:50`,
  `app.py:553`) ; bornes de date inclusives côté haut ; pas de rescoring hors des deux
  backfills explicitement scopés.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_FAIL.
- **Findings :** F1 casse le 2e critère d'US-03 évaluateur (le verdict doit porter sur
  la claim de l'article) ; F12 (Low) — le 1er critère d'US-04 frontend (« aucune
  écriture ») est respecté dans le code mais **aucun test ne le verrouille** ; une
  route d'écriture ajoutée par erreur passerait la CI.
- **Points conformes :** matrice ci-dessus — 15 contrats sur 19 tenus et prouvés.
  US-02/US-06 évaluateur et US-03 scraper non implémentés, mais **déclarés comme tels**
  dans `plan_implementation.md` et le README : absence assumée, pas écart.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** F3 (Medium sous cet angle) — le commentaire `run_evaluateur.py:36-38`
  et le message de journal l. 96-100 affirment un rattrapage qui n'existe pas ; c'est
  une documentation qui MENT, pas seulement absente. F18 (Low) — `README.md:72` et
  `plan_implementation.md:110` présentent le « plafond sur `/login` » comme un
  durcissement acquis parmi les 33 correctifs, ce que F4 contredit.
- **Points conformes :** `.env.example` documente les 15 variables lues (verrouillé
  par `test_conformite_exigences.py:171-194`) ; l'« État d'avancement » du plan est à
  jour, y compris pour les phases 11-13 ; le README dit explicitement que le
  `schedule` est en pause.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS.
- **Findings :** F10 (Low, 422 JSON hors charte) ; F19 (Low) — `liste.html:6` fixe
  `step="1"` sur `score_min` alors que les scores sont des `numeric(5,2)` : un filtre
  à 60,5 est refusé par le navigateur, jamais par le serveur.
- **Points conformes :** `login.html` a `label for`/`id` appariés, `role="alert"` sur
  l'erreur, `aria-describedby` conditionnel, `autocapitalize`/`pattern` cohérents avec
  `_PSEUDO_RE` ; titres de page distincts ; tableaux avec `thead`.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** F5 (Medium, duplication des backfills) ; F20 (Low) — `app.py` fait
  630 lignes et mélange quatre responsabilités (session, plafond, cache, routes) ;
  acceptable à cette taille, à surveiller.
- **Points conformes :** aucun `except` silencieux, aucune valeur magique non nommée
  dans les chemins de décision, commentaires qui expliquent le POURQUOI et citent la
  mesure qui a motivé le choix. La densité de commentaires est élevée mais chaque
  bloc porte une information non déductible du code.

### Fail-Loud Auditor
- **Verdict :** AUDIT_FAIL.
- **Findings :** F2 (High) — le seul chemin de configuration qui échoue sans
  diagnostic, dans un projet qui en fournit un partout ailleurs.
- **Points conformes :** `config.py` (SystemExit nommant variable, valeur, remède),
  `db.py:29-38`, `schema.py:57-77`, `_commiter_le_lot`, isolation par `begin_nested`
  dans les deux collecteurs.

### Test Quality Auditor
- **Verdict :** AUDIT_FAIL.
- **Findings :**
  - **[Medium] F21** `tests/test_conformite_exigences.py:134` — assertion qui ne peut
    plus échouer (module supprimé), et qui laisse passer l'import inter-blocs réel.
  - **[Medium] F22** `tests/test_fact_checking.py:26-47` — les quatre cas du module qui
    fournissent une claim la construisent SANS champ `text`, c'est-à-dire exactement le
    chemin où le garde-fou de pertinence est court-circuité (F1). Le module de test le
    plus proche du défaut l'emprunte à chaque cas sans jamais le voir. Symétriquement,
    `test_correctifs_audit.py:851` affirme `not _claim_est_pertinente(titre, "")` —
    vrai pour le helper, faux pour le comportement observable.
  - **[Low] F12** — le contrat « lecture seule » d'US-04 frontend n'est pas testé.
- **Points conformes :** `_pas_de_reseau` (conftest:47-81) avec sa limite psycopg2
  honnêtement documentée ; `db_session` en `create_savepoint` ; `_environnement_neutre`
  purge le cache de comptes ; budget de skips à 0 vérifié en CI ; corpus réel séparé
  des fixtures synthétiques (`tests/corpus/`), la meilleure décision de test du dépôt.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_FAIL.
- **Mutations qui survivraient :**
  - **[High]** supprimer entièrement le compteur de `/login` (`app.py:419`, `:439`,
    `:454`) : deux tests tombent sur le code 429, **aucun** ne constate une perte de
    protection — parce qu'il n'y en avait pas. Le test
    `test_le_plafond_ne_ferme_jamais_la_porte_a_qui_a_le_bon_mot_de_passe`
    (`test_correctifs_audit.py:146`) CERTIFIE la propriété qui neutralise le contrôle,
    même figure que le test de la phase 8 qui certifiait la rotation de
    `X-Forwarded-For`.
  - **[Medium]** remplacer `_claim_est_pertinente(...)` par `True`
    (`fact_checking.py:158`) : seuls les tests du helper tombent, aucun test de bout
    en bout de `evaluer_fact_checking`.
  - Inverser `Article.date_publication.desc()` en `.asc()` (`run_evaluateur.py:90`) :
    aucun test ne tombe — l'ordre de traitement n'est vérifié nulle part, alors que
    c'est lui qui décide quels articles existent pour le reste du système.
- **Mutations bien tuées :** les cinq plafonds, le débit SEC, l'ordre des niveaux de
  verdict, la borne haute de date, le départage de pagination, l'expiration dans le
  cookie, le fail-closed de l'authentification.

### Layer Enforcer
- **Verdict :** AUDIT_FAIL (Medium unique).
- **Findings :** F6 — import inter-blocs frontend → contextualiseur, non couvert par
  le test censé garder la règle (F21).
- **Points conformes :** `reputation.py` duplique la liste plutôt que d'importer le
  scraper ; `config.py` héberge le seuil partagé ; `pythonpath` déclaré dans
  `pyproject.toml` au lieu de trois mécanismes concurrents.

### YAGNI Auditor
- **Verdict :** AUDIT_PASS.
- **Findings :** F11 (Low, poids morts assumés).
- **Points conformes :** `pyproject.toml` réduit à la configuration pytest, pas de
  `build-system` décoratif ; pas d'interface à implémentation unique ; le cache de
  comptes et la purge du compteur sont bornés et justifiés par des mesures. Le
  `ponytail:` de `app.py:375` documente correctement le plafond non posé et sa
  condition de déclenchement.

### SRE/Performance Auditor
- **Verdict :** AUDIT_FAIL.
- **Findings :** F3 (High) ; **[Low] F23** — `backfill_fact_checking.yml` et
  `backfill_llm_bootstrap.yml` n'ont pas de `timeout-minutes`, alors que
  `pipeline_hebdomadaire.yml:12-15` a justement corrigé cet oubli (défaut plateforme :
  6 h) ; **[Low] F24** — `keepalive_supabase.yml:22` installe des dépendances sans
  borne haute, seule commande `pip` du dépôt à ne pas être bornée.
- **Points conformes :** commits par tranches de 25, plafonds articles/LLM, clients
  HTTP créés une fois par run et fermés en `finally`, débit SEC, `pool_pre_ping`,
  pagination SQL `limit+1`, sélection du contextualiseur poussée en SQL.

### Architecture Consistency Auditor
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** F6 (Medium).
- **Points conformes :** le schéma, les quatre blocs, la topologie Vercel/GitHub/
  Supabase, la stratégie « dégrader jamais bloquer » et l'interface `evaluer(article)`
  correspondent au code, y compris les formats de `preuve_id`. Aucun module fantôme :
  tous les scripts cités par le README et les workflows existent.

### Contextual Threat Analyst
- **Verdict :** AUDIT_FAIL.
- **Scénarios :**
  1. **Bruteforce du mot de passe partagé** (F4, High) — mesuré, aucune friction.
  2. **Empoisonnement du score par un tiers** (F1, High sous cet angle) — un acteur
     qui parvient à faire indexer une ClaimReview sans `text` fait attribuer 90/100 à
     des articles sans rapport ; **[RISQUE]**, dépend de l'API Google.
  3. **Injection de prompt via le contenu collecté** — traitée : cadre
     `<contenu_non_fiable>`, balise fermante neutralisée quelle que soit la casse,
     `raison` encadrée. Reste F15 (`preuve_id` non encadré).
  4. **Révocation retardée d'un accès** (F13) — 60 s par instance.
- **Points conformes :** le frontend n'écrit jamais ; le rôle n'est jamais affiché ;
  aucune énumération de comptes possible (message d'erreur unique).

### SAST Scanner
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** F14 (Medium, mot de passe en paramètre SQL) ; F16, F17 (Low).
- **Points conformes :** aucune concaténation SQL (tout en SQLAlchemy paramétré, y
  compris `func.crypt`) ; autoescape Jinja actif ; pas de désérialisation non sûre ;
  pas de `subprocess`/`eval` ; pas de secret en dur ; `.env*` ignoré avec exception
  explicite pour le gabarit ; en-têtes `nosniff`, `DENY`, `Referrer-Policy`, CSP ;
  cookie `httponly`/`secure`/`samesite=lax` posé ET supprimé avec les mêmes attributs.

### Supply Chain & Artifact Auditor
- **Verdict :** AUDIT_PASS.
- **Findings :** F24 (Low) ; **[Low] F25** — `graphify-out/` (5,3 Mo d'artefact généré)
  n'est ni suivi ni ignoré : un `git add .` l'embarquera. À ajouter au `.gitignore`.
- **Points conformes :** bornes hautes sur toutes les dépendances des deux
  `requirements.txt` ; modèle spaCy épinglé par URL exacte dans la CI ET le pipeline ;
  `pip freeze` archivé en artefact à chaque run CI pour rendre observable l'absence de
  lockfile ; `actions/*@v4`/`v5` figés au majeur.
- **Limite :** absence de lockfile — décision tracée et compensée, pas un défaut neuf.

### Privacy/Exfiltration Auditor
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** F14 (Medium, sous l'angle des journaux serveur).
- **Points conformes :** `.env.example` documente les trois flux sortants et nomme le
  plus volumineux (corps d'article vers Anthropic, jusqu'à 4 000 caractères) ; les
  messages d'exception ne recopient jamais l'URL d'appel dans `raison` (quatre sites
  traités, y compris le chemin spaCy) ; le RGPD est explicitement déclaré hors
  périmètre prototype dans `architecture.md`.

---

## Points Conformes (Synthèse)

- **321 tests, 0 skip** contre un vrai Postgres avec les trois migrations : le
  « faux vert » de la phase 6 est bien refermé, et vérifié ici par exécution.
- Authentification **fail-closed** : `FRONTEND_PASSWORD` absente ⇒ accès refusé, mode
  local explicite requis.
- Superadmin structurellement protégé : contrainte SQL imposant un `secret_hash`,
  placeholder aléatoire inconnu, clé de signature du cookie dérivée de ce hash.
- Prompts LLM : contenu tiers encadré, balise fermante neutralisée toutes casses,
  `faits_traces` validés mécaniquement contre les `preuve_id` réels.
- « Dégrader, jamais bloquer » appliqué au **grain de l'entrée** dans les deux
  collecteurs, avec `begin_nested` — et non seulement au grain de la source.
- Traçabilité US-08 complète et persistée (`detail_calcul`), poids fusionnés et non
  écrasés par les backfills.
- Corpus de tests réels séparé des fixtures synthétiques — la pratique qui a mis fin
  à la série d'inversions de verdicts.

---

## Limites De Vérification

- **Aucun appel réseau réel** : les API Google Fact Check, SEC EDGAR et Anthropic
  n'ont pas été interrogées. La fréquence réelle des claims sans champ `text` (F1),
  le taux de faux positifs de la troncature à 5 caractères (F8) et la présence de
  bylines dans les flux RSS collectés (F9) restent donc non mesurés.
- **Pas d'accès à la configuration Supabase de production** : le niveau de
  journalisation SQL (F14) et le nombre d'instances Vercel tièdes (F13, F4) n'ont pas
  pu être constatés.
- **Le modèle spaCy `en_core_web_sm` n'est pas installé localement** : le chemin NER
  de `source_primaire.py` a été audité par lecture, dégradation vérifiée par les
  tests existants, mais non exécuté ici.
- Base de test locale (`fakenews_audit14`) créée, migrée, utilisée, puis supprimée —
  aucune écriture sur une base réelle du projet.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `python3 -m pytest -q` (sans `TEST_DATABASE_URL`) | 232 passed, **89 skipped** |
| `createdb fakenews_audit14` + 3 migrations `psql -v ON_ERROR_STOP=1` | appliquées (2 NOTICE d'idempotence attendues) |
| `TEST_DATABASE_URL=… python3 -m pytest -q` | **321 passed, 0 skipped** |
| Sonde F1 : claim avec texte hors sujet / sans champ `text` / texte vide | `None` / **90.0** / **90.0** — garde-fou contourné |
| Sonde F4 : 60 POST `/login` erronés puis 1 correct | 10×401 + 50×429 en **0,10 s**, puis **303 + cookie posé** |
| Sonde F2 : mots de passe `'mauvais-ascii'` / `'mötdepasse'` / `'café'` | 401 / **500** / **500** ; avec `FRONTEND_PASSWORD` accentué : **500 même sur le bon mot de passe** |
| Sonde F3 : 2 runs `evaluer_articles_non_scores(plafond_articles=2)` avec arrivée d'articles récents entre les deux | l'article dépassé n'est **jamais** noté |
| `grep` écritures dans `frontend/app.py` | aucune (`add`/`commit`/`delete`/`insert`) |

Aucune commande bloquée. Aucun code de production modifié — audit strictement en
lecture.

---

## Suivi Des Correctifs

### F1 — verdict de fact-checking non rattachable · ✅ corrigé le 2026-09-10

- **Correctif :** `evaluateur/fact_checking.py` — la garde `if texte_claim and ...`
  est supprimée du site d'appel : `_claim_est_pertinente(titre, claim.get("text") or "")`
  est désormais consultée dans TOUS les cas. La fonction traitait déjà le texte vide
  comme non pertinent ; elle n'était simplement jamais interrogée là-dessus.
- **Tests ajoutés** (`tests/test_correctifs_audit.py`, section « Audit phase 14 ») :
  champ `text` absent et champ `text` vide (paramétrés), claim hors sujet avec texte
  (contre-épreuve du garde-fou existant), claim rattachable réellement exploitée
  (contre-épreuve du correctif — sans elle, neutraliser le signal entier passerait).
- **Dette de test soldée (F22) :** les quatre fixtures qui empruntaient le chemin
  fautif sans le voir portent maintenant un `text` rattachable au titre
  (`tests/test_fact_checking.py:26,33,45`, `tests/test_backfill_fact_checking.py:56`).
- **Vérification :** sonde de l'audit rejouée — claim sans `text` et claim à `text`
  vide renvoient désormais `None` / `preuve_id: "fact_checking"` là où elles
  renvoyaient `90.0` / `fact_checking:<url>`. Suite complète : **325 passed, 0 skip**
  contre un vrai Postgres migré (321 avant, +4 tests).

### F2 — chaîne non-ASCII dans l'authentification · ✅ corrigé le 2026-09-10

- **Correctif 1/2 — `/login` :** comparaison sur des octets
  (`mot_de_passe.encode("utf-8")`), car `hmac.compare_digest` refuse deux `str`
  non-ASCII.
- **Correctif 2/2 — un second site, non relevé par l'audit initial :**
  `_decomposer_cookie` validait la forme du pseudo et de l'expiration, mais
  laissait passer n'importe quoi comme signature. Un serveur ASGI décodant ses
  en-têtes en latin-1, un octet non-ASCII dans le cookie atteignait
  `compare_digest` sous forme de `str` non-ASCII — même `TypeError`, mais sur
  **chaque page** et non plus seulement sur `/login`. La signature étant toujours
  un hexdigest sha256, elle se valide désormais à la frontière (`_SIGNATURE_RE`),
  comme le pseudo. Découvert en préparant le correctif, pas pendant l'audit :
  celui-ci n'avait examiné qu'un seul des deux appels à `compare_digest`.
- **Vérification :** sonde rejouée — `'mötdepasse'` et `'café'` renvoient 401 là
  où ils renvoyaient 500 ; un `FRONTEND_PASSWORD` accentué ouvre de nouveau la
  session. Cinq formes de signature invalide (accentuée, non hexadécimale, trop
  courte, majuscules, vide) sont refusées par une redirection, pas par une 500.

### F4 — plafond `/login` sans friction · ✅ traité le 2026-09-10 · ⚠️ effet de bord

> **Amendé par l'audit phase 15 (F15-01, High) :** le remède immobilise un fil du
> pool et une connexion Postgres pendant l'attente. Mesuré : 40 connexions ratées
> simultanées font passer une page publique de 4 ms à 4,0 s. Le déni de service
> par verrouillage a été échangé contre un déni de service par épuisement de
> ressources. Correction attendue dans `audit-phase15-relecture-correctifs-phase0.md`.

- **Décision de conception :** **ralentir, pas refuser.** Refuser l'évaluation
  au-delà du plafond le rendrait opposable, mais permettrait de fermer la porte à
  autrui — derrière un proxy non déclaré l'identifiant client est partagé par tous
  les visiteurs (phase 7, N1), et une clé par pseudo laisserait un attaquant
  verrouiller le compte qu'il vise, superadmin compris. Un délai n'enferme
  personne.
- **Correctif :** `_ralentir_apres_echec` — délai proportionnel aux échecs récents
  du client (0,5 s par échec, plafonné à 5 s), appliqué **après** un échec et
  seulement sur un échec. Le message de la page 429 dit maintenant ce qui se passe
  réellement (« chaque nouvel essai est ralenti ») au lieu d'annoncer une attente
  de plusieurs minutes qui n'existait pas.
- **Vérification, même sonde qu'à l'audit :** 60 essais erronés passent de
  **0,10 s à 278 s** (×2800), et le 61ᵉ essai, correct, ouvre toujours la session
  **instantanément** compteur plein — la propriété imposée par N1 tient.
- **Plafond connu, marqué `ponytail:` dans le code :** le délai est par requête,
  donc un attaquant qui parallélise n'est ralenti que d'un facteur borné par la
  concurrence qu'il obtient. Marche suivante si nécessaire : hacher lentement le
  mot de passe partagé (bcrypt, comme les codes personnels), ce qui rend chaque
  essai coûteux quelle que soit la parallélisation — pas un refus, qui rouvrirait
  N1.
- **Note de test :** le délai est neutralisé pour la suite par une fixture
  `autouse` (sans quoi les tests qui martèlent `/login` prendraient des minutes) et
  rétabli par trois tests dédiés. C'est un compromis assumé : la disparition pure
  et simple du mécanisme n'est tuée que par ces trois tests-là.

### F3 — famine du reliquat de l'évaluateur · ouvert

Seul finding High encore ouvert. Correctif mécanique (traiter le reliquat avant
les nouveautés), mais il touche l'ordre de sélection du pipeline : à faire avant
que la file d'attente des propositions (`doc/V3/`) n'alimente réellement la base,
sous peine de faire passer les articles proposés après les plus récents collectés
automatiquement.
