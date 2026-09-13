# Audit phase 13 — relecture des correctifs non commités

**Scope** : l'arbre de travail non commité sur `main` (`7df2068` + 19 fichiers modifiés,
+600/-98), confronté aux findings ouverts de `audit-phase11-relecture-correctifs-phase10.md`
et `audit-phase12-codebase-complete.md`.

**Sources d'exigences** : `doc/V0/userstories_{scraper,évaluateur,contextualiseur,frontend}.md`,
`doc/V0/architecture.md`, `doc/V0/plan_implementation.md`, README, les rapports des phases 11 et 12.

**Verdict global : 🔴 AUDIT_FAIL**
**Totaux : Critique 1 · High 2 · Medium 4 · Low 3**

> **La bonne nouvelle d'abord, parce qu'elle est réelle et vérifiée par mutation.** Le finding
> le plus lourd de la phase 12 — « les cinq plafonds du projet survivent à leur suppression,
> 298 tests verts » — est **fermé**. Chaque plafond a été muté individuellement : chacun tue
> désormais un test nommé. Ce n'est plus une promesse de commentaire, c'est une garantie
> exécutable.
>
> **La mauvaise ensuite.** L'arbre de travail est **rouge** : 7 tests échouent. Et le correctif
> qui ferme le finding « cookie non signé → requête SQL non plafonnée » a rouvert, en plus
> large, le déni de service que la phase 7 avait fermé.

---

## Résumé de l'audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier | 🟡 Avertissement | La mécanisation d'US-04 contextualiseur est un décor : 1 formulation catégorique sur 6 est réellement adoucie. Le garde-fou de pertinence d'US-03 rejette des claims françaises vraies. |
| Qualité | 🔴 Bloquant | 7 tests rouges, `test_comptes.py` en entier. `articles_a_traiter()` est devenu du code mort que six tests continuent de valider pendant que le chemin réel n'est couvert qu'ailleurs. |
| Architecture | 🟡 Avertissement | Les plafonds sont enfin gardés par mutation. Mais un cache d'authentification en mémoire de processus réintroduit le motif que la phase 7 avait nommé. |
| Cybersécurité Offensive | 🔴 Bloquant | Le plafond anti-bruteforce est désormais évalué **avant** la validation de signature et sur un identifiant partagé par tous les visiteurs : un attaquant verrouille le site entier, porteurs de cookies valides compris. |

## Index des sous-audits

| Sous-audit | Scope | Crit | High | Med | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic | `validation.py`, `fact_checking.py`, `score.py` | 0 | 0 | 2 | 0 | FAIL |
| Requirements Compliance | US-03/US-04 évaluateur, US-01/US-04 contextualiseur | 0 | 0 | 1 | 0 | FAIL |
| Doc-Sync | `plan_implementation.md`, README, docstrings `app.py` | 0 | 1 | 1 | 0 | FAIL |
| A11y/UX | `login.html`, `detail.html` | 0 | 0 | 0 | 0 | PASS |
| Clean Code | `style.py:_detecter_langue`, `app.py` | 0 | 0 | 0 | 1 | PASS (réserve) |
| Fail-Loud | commits par article, `except Exception` | 0 | 0 | 0 | 1 | PASS (réserve) |
| Test Quality | `test_correctifs_audit.py` (+293), `test_declenchement.py` | 1 | 0 | 1 | 0 | FAIL |
| Mutation/Saboteur | 5 plafonds + débit SEC | 0 | 0 | 0 | 0 | **PASS** |
| Layer Enforcer | imports inter-blocs | 0 | 0 | 0 | 0 | PASS |
| YAGNI | `declenchement.articles_a_traiter` | 0 | 0 | 1 | 0 | FAIL |
| SRE/Performance | `_recuperer_compte_en_cache` | 0 | 0 | 0 | 1 | PASS (réserve) |
| Architecture Consistency | docs vs code | 0 | 0 | 0 | 0 | PASS |
| Contextual Threat | verrouillage global du frontend | 0 | 1 | 0 | 0 | FAIL |
| SAST | en-têtes HTTP, CSP, cookies | 0 | 0 | 0 | 0 | PASS |
| Supply Chain | `requirements.txt`, modèle NER | 0 | 0 | 0 | 0 | PASS |
| Privacy/Exfiltration | `reputation.DOUTEUX` sur dépôt public | 0 | 0 | 0 | 1 | PASS (réserve) |

## Matrice de couverture

| Contrat / exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| US-07 : plafond d'appels LLM par run | `run_evaluateur.py:139` | mutation → `test_audit_phase12_plafond_appels_llm_evaluateur` rouge | ✅ gardé |
| Plafond d'articles par run évaluateur | `run_evaluateur.py:91` | mutation → test dédié rouge | ✅ gardé |
| US-01 ctx. : plafond d'appels du contextualiseur | `run_contextualiseur.py:84` | mutation → test dédié rouge | ✅ gardé |
| Plafond du backfill LLM | `backfill_llm_bootstrap.py:60,70` | test appelle réellement `backfiller_llm_bootstrap(plafond=2)`, assert 2 appels | ✅ gardé |
| Débit SEC EDGAR | `source_primaire.py:44-46` | mutation (`sleep` retiré) → test dédié rouge | ✅ gardé |
| H5 ph.6 : contenu tiers encadré dans les prompts | `generation.py:67-75` | chaque `raison` passe par `encadrer_contenu_non_fiable` | ✅ corrigé |
| US-08 : trace honnête d'un signal hors barème | `score.py:38-47` | `exclu: True` + `raison: "hors barème"` + log | ✅ corrigé |
| Commit par article (ne pas perdre les appels payés) | `run_contextualiseur.py:100`, les 2 backfills | 3 points d'écriture sur 3 convertis | ✅ corrigé |
| Négations françaises de fact-checking | `fact_checking.py:263-276`, `tests/corpus` | corpus réel étendu, tests verts | ✅ corrigé |
| Intégrité HTML à la collecte (`<` isolé) | `rss.py:39` | corpus réel `a < b`, `> 5 %` préservés | ✅ corrigé |
| **Suite de tests verte** | `tests/` | **`7 failed, 318 passed`** | ❌ **rouge** |
| **Le plafond ne ferme jamais la porte à qui a le bon secret** | `app.py:364-366` | cookie valide + plafond atteint → `AccesRefuse`, reproduit | ❌ **violé** |
| US-04 ctx. : formulation jamais catégorique | `validation.py:166-181` | 1 formulation sur 6 adoucie, mesuré | ❌ non mécanisé |
| US-03 : pertinence de la claim | `fact_checking.py:296-307` | claim FR vraie rejetée, mesuré | ❌ faux négatifs |

---

## Top findings

- **[Critique] `src/fakenews/frontend/app.py:364-366` — la suite de tests est rouge.**
  `compte_courant` appelle désormais `_identifiant_client(request)`, qui lit
  `request.client` (`app.py:301`). Les sept tests de `tests/test_comptes.py`
  construisent leur requête comme un `types.SimpleNamespace` sans attribut
  `client` : chacun casse sur `AttributeError: 'types.SimpleNamespace' object has
  no attribute 'client'`. Mesuré : `7 failed, 318 passed` contre un vrai Postgres
  avec les trois migrations appliquées. La CI échoue le job dès qu'un test est
  rouge (`ci.yml`, budget de skips à zéro) : en l'état, ce travail ne peut pas
  être fusionné. Le fait que le correctif n'ait jamais été exécuté contre
  `test_comptes.py` est le vrai signal — c'est le fichier qui couvre exactement la
  fonction modifiée. **Correction attendue** : donner à la fixture un
  `client=SimpleNamespace(host=...)`, ou faire de `_identifiant_client` une
  fonction tolérante à une requête sans `client` (elle l'est déjà pour `None`,
  pas pour l'attribut absent).

- **[High] `src/fakenews/frontend/app.py:364-366` — un cookie parfaitement valide est refusé.**
  Le plafond est évalué **avant** la validation de signature :
  `if _trop_de_tentatives(identifiant): raise AccesRefuse()` précède
  `_decomposer_cookie`. Reproduit de bout en bout : cookie correctement signé
  (`_signature_valide` → `True`), 10 échecs enregistrés sur le même identifiant,
  puis `compte_courant` → `AccesRefuse`. Le projet avait pourtant codifié
  l'invariant inverse dans un test nommé
  `test_le_plafond_ne_ferme_jamais_la_porte_a_qui_a_le_bon_mot_de_passe` — il
  reste vert parce qu'il ne couvre que `/login`, pas `compte_courant`. Le
  garde-fou hérite de l'angle mort de ce qu'il garde, exactement comme en phase 11.
  **Amplification** : `_proxys_de_confiance()` vaut `0` par défaut, donc
  `_identifiant_client` retombe sur `request.client.host` — derrière Vercel, l'IP
  du proxy, **partagée par tous les visiteurs**. Un seul attaquant qui envoie
  10 cookies mal signés verrouille le site entier pendant toute la fenêtre, pour
  tout le monde, sur **toutes** les routes et plus seulement `/login`. C'est le
  finding N1 de la phase 7 (déni de service par IP de proxy) ressuscité et élargi.
  **Correction attendue** : ne consulter le plafond qu'**après** l'échec de
  signature, jamais avant — un cookie valide ne doit traverser aucun compteur.

- **[High] `src/fakenews/frontend/app.py:288-301` — le commentaire affirme la propriété que le correctif vient de supprimer.**
  Le docstring de `_identifiant_client` soutient toujours que le partage
  d'identifiant est sans danger « puisqu'une authentification RÉUSSIE n'est jamais
  plafonnée (cf. `connexion`) : le partage ne prive personne d'accès ». Depuis ce
  correctif, c'est faux : `compte_courant` plafonne les porteurs de cookie valide.
  Le raisonnement qui justifiait de ne pas se soucier du partage d'IP est donc
  caduc, et le commentaire le masque. Thème transverse 2 de la phase 12 —
  « le commentaire qui affirme la propriété tient lieu de propriété » — reproduit
  à l'identique, dans la fonction voisine de celle qu'il décrivait.

- **[Medium] `src/fakenews/contextualiseur/validation.py:166-181` — `valider_formulation_prudente` adoucit 1 formulation sur 6.**
  Mesuré, sortie brute : `"Cet article est une fake news."` → adouci ; `"Cet
  article est faux."`, `"Le Monde ment sur ce sujet."`, `"Cette information est
  mensongère et fabriquée de toutes pièces."`, `"L'auteur a délibérément menti à
  ses lecteurs."`, `"Ce site publie de la propagande."` → **inchangés**. Trois
  expressions régulières codées en dur sont présentées comme la mécanisation
  d'US-04 (« la formulation n'est jamais catégorique »), alors qu'elles forment
  une liste de six tournures exactes qu'un modèle n'a aucune raison de produire
  littéralement. La phase 12 demandait un post-traitement ; ceci en a la forme et
  pas l'effet. Second défaut : la réécriture est **silencieuse** — aucun journal,
  aucune trace que la sortie du LLM a été modifiée, ce qui contredit l'esprit de
  traçabilité d'US-08. **Correction attendue** : soit assumer que la garantie
  repose sur le prompt et le documenter comme tel, soit détecter par classe
  lexicale (verbes d'accusation + désignation de source) et **journaliser** chaque
  réécriture.

- **[Medium] `src/fakenews/evaluateur/fact_checking.py:296-307` — `_claim_est_pertinente` rejette des claims françaises vraies.**
  Le recouvrement est purement lexical, sans lemmatisation. Mesuré : titre
  `"Le vaccin modifie l'ADN"` contre la claim `"Les vaccins ARN modifient le
  génome humain"` → **`False`**, donc verdict de fact-checker ignoré et signal
  `fact_checking` exclu. « vaccin »/« vaccins » et « modifie »/« modifient » ne
  se croisent pas. L'anglais, bien moins fléchi, en souffre nettement moins : le
  garde-fou est plus sévère en français qu'en anglais. C'est le quatrième angle
  mort bilingue relevé en quatre audits (phases 10, 11, 12, et ici). Second point :
  `if not texte_claim: return True` laisse passer sans aucun contrôle toute claim
  dont l'API ne renvoie pas de texte. **Correction attendue** : comparer sur des
  préfixes de mots (troncature à 5-6 caractères) ou sur les lemmes spaCy déjà
  chargés par `source_primaire`, et couvrir le cas français par un test de corpus réel.

- **[Medium] `src/fakenews/contextualiseur/declenchement.py:18` — `articles_a_traiter()` est du code mort validé par six tests.**
  `run_contextualiseur.py:12` a retiré l'import ; plus aucun appelant en
  production. La logique (seuil `>=`, exclusion des `non_evaluable`, tri
  décroissant, plafond) a été portée en SQL dans
  `selectionner_articles_a_traiter` — correctement, les deux sémantiques
  concordent. Mais `tests/test_declenchement.py` continue d'exercer les six
  comportements sur la fonction morte. Un lecteur voit six tests verts sur le
  déclenchement et en conclut que le déclenchement est couvert ; ce qui tourne en
  production est une requête SQL dont seul `test_run_contextualiseur.py` répond.
  **Correction attendue** : supprimer `articles_a_traiter` et `test_declenchement.py`
  (la fonction n'a plus de raison d'exister), ou la remettre sur le chemin réel.

- **[Medium] `doc/V0/plan_implementation.md:111` — la ligne d'avancement est écrite au futur antérieur.**
  « Phases 7 à 12 (relectures d'audit et consolidations) : passages successifs
  traitant **l'ensemble des findings** ». Au moment où cette phrase est écrite,
  sept tests sont rouges et la mécanisation d'US-04 couvre une tournure sur six.
  La section « État d'avancement » porte explicitement la promesse de ne pas se
  désynchroniser silencieusement — c'est précisément ce qu'elle fait ici.
  **Correction attendue** : décrire l'état après passage au vert, pas avant.

- **[Low] `src/fakenews/frontend/app.py:321-338` — cache d'authentification sans invalidation.**
  `_cache_comptes` retient `(role, secret_hash)` par pseudo pendant 60 s, dans un
  dictionnaire de module. Un changement de rôle, une rotation de `secret_hash` ou
  une suppression de compte reste sans effet jusqu'à 60 s ; les résultats négatifs
  étant cachés aussi, un compte créé après une première consultation n'existe pas
  pendant 60 s. Sur Vercel (processus éphémères) l'impact est faible, mais c'est
  de l'état en mémoire de processus dans le chemin d'authentification — le motif
  que la phase 7 avait nommé « le durcissement qui ouvre une autre porte ».
  **Correction attendue** : purger l'entrée du pseudo concerné à chaque connexion
  réussie, ou accepter et documenter la fenêtre de 60 s.

- **[Low] `src/fakenews/scraper/rss.py:39` — `_BALISES` ne couvre ni doctype ni instruction de traitement.**
  Le motif `</?[a-zA-Z][^>]*>|<!--.*?-->` corrige bien la régression du `<`
  isolé (vérifié sur le corpus réel), mais `<!DOCTYPE html>` et `<?xml ... ?>`
  commencent par `!` et `?` : ils survivent désormais littéralement dans le texte
  stocké. Aucun flux RSS observé ne les place dans un `description`, d'où la
  sévérité basse. **Correction attendue** : ajouter `<![^>]*>|<\?.*?\?>` à
  l'alternative, avec une entrée de corpus.

- **[Low] `src/fakenews/evaluateur/reputation.py:335-339` — quatre publications francophones nommées sur un dépôt public.**
  L'ajout ferme bien le finding « pendant francophone d'US-01 absent », mais il
  inscrit dans un dépôt public et attribuable quatre noms de domaines de
  publications en activité, classés « douteux ». `doc/V0/architecture.md` pose le
  risque de diffamation comme condition bloquante à l'ouverture publique, et
  l'audit post-push de la phase 5 avait déjà relevé l'exposition des listes
  anglophones. Ce n'est pas un défaut de code : c'est une décision éditoriale qui
  n'est tracée nulle part. **Correction attendue** : citer la source de
  classement (Décodex, date de consultation) dans le fichier, comme le fait déjà
  le commentaire pour les sources anglophones.

---

## Thèmes transverses

1. **Le correctif qui n'a pas été exécuté contre le test de sa propre fonction.**
   `compte_courant` est modifiée ; `test_comptes.py` la couvre entièrement ; les
   sept tests cassent. Variante nouvelle du « correctif qui se croit sur parole »
   de la phase 7 : ici le correctif ne se croit pas sur parole, il n'a simplement
   jamais été lancé.

2. **Le garde-fou plus sévère en français qu'en anglais.** Quatrième occurrence
   consécutive (`_detecter_langue` ph.11, lexique français ph.10, négations ph.11,
   `_claim_est_pertinente` ici). À chaque fois le correctif est écrit et testé
   sur l'anglais, puis étendu au français par ajout de chaînes littérales. La
   cause commune est l'absence de normalisation morphologique, pas l'oubli d'une
   liste.

3. **La mécanisation décorative.** `valider_formulation_prudente` a la forme
   d'un post-traitement mécanique et la couverture d'un exemple. Un test vert
   (`test_audit_phase12_formulation_prudente_adoucit_affirmations_categoriques`)
   certifie la seule tournure qui fonctionne.

4. **Ce qui a réellement progressé.** Les cinq plafonds sont passés de zéro
   couverture comportementale à cinq mutations tuées. C'est le seul finding de la
   phase 12 dont la fermeture résiste à une vérification adverse, et c'est le plus
   coûteux des cinq.

---

## Détails par division

### Division Métier (Anton Ego)

- **[Medium]** `validation.py:166-181` : on m'annonce une garantie mécanique
  contre l'affirmation catégorique. On me sert trois expressions régulières qui
  reconnaissent « est une fake news » et laissent passer « est faux ». Le plat
  porte le nom du plat ; il n'en a pas la substance. US-04 exige que la
  formulation ne soit *jamais* catégorique — pas qu'elle évite six tournures.
- **[Medium]** `fact_checking.py:296-307` : le filtre de pertinence protège
  honorablement l'anglais et pénalise le français. Une claim vraie, sur le même
  sujet, dans la langue que le projet dit couvrir, est écartée pour cause de
  pluriel.
- **Conforme** : `score.py:38-47` trace enfin un signal hors barème comme exclu
  et le journalise. La trace ne ment plus.

### Division Qualité (Gordon Ramsay)

- **[Critique]** Sept tests rouges. Sept. Sur le fichier qui couvre exactement la
  fonction qu'on vient de toucher. Personne n'a lancé `pytest tests/test_comptes.py`
  avant de déclarer la phase 12 traitée dans le plan d'implémentation.
- **[Medium]** `test_declenchement.py` : six tests verts qui valident une
  fonction que le pipeline n'appelle plus. Du vert qui ne mesure rien.
- **Conforme, et c'est rare** : les cinq tests de plafond sont de vrais mutation
  killers. `test_audit_phase12_plafond_backfill_llm` appelle réellement
  `backfiller_llm_bootstrap` avec `plafond=2` et compte les appels — exactement
  ce que la phase 12 réclamait quand elle constatait que l'ancien test ne faisait
  que lire une variable d'environnement.

### Division Architecture (Steve Jobs)

- **[Medium]** `declenchement.articles_a_traiter` n'a plus de raison d'exister.
  Une fonction publique sans appelant est une dette qu'on paie en lisibilité à
  chaque relecture. Supprimez-la.
- **[Low]** `_recuperer_compte_en_cache` place de l'état mutable de processus
  dans le chemin d'authentification pour économiser une requête indexée sur une
  table de quelques lignes. L'optimisation n'a pas été mesurée ; le coût en
  invalidation, si.
- **Conforme** : les frontières entre blocs tiennent, `fakenews.config` reste le
  point unique des réglages, aucun import inter-blocs nouveau.

### Division Cybersécurité Offensive (Sherlock Holmes)

- **[High]** Élémentaire, et pourtant : pour fermer une requête SQL non plafonnée,
  on a placé le compteur d'échecs devant la vérification de signature. Capacité de
  l'attaquant : envoyer dix requêtes portant un cookie syntaxiquement correct et
  mal signé. Chemin : `compte_courant` → `_identifiant_client` → IP du proxy
  Vercel, commune à tous → `_trop_de_tentatives` → `AccesRefuse` pour quiconque se
  présente ensuite, cookie valide compris. Impact : indisponibilité totale du
  frontend pour tous les utilisateurs, à coût nul pour l'attaquant, sur toutes les
  routes. La mitigation est d'inverser deux lignes.
- **Conforme** : en-têtes de sécurité HTTP posés par middleware, CSP cohérente
  avec les gabarits (`style-src 'unsafe-inline'` nécessaire, `frame-ancestors
  'none'`), `/docs` toujours fermé, aucun secret suivi par git.

---

## Détails par sous-audit

**Business Logic** — FAIL (2 Medium). `valider_formulation_prudente` 1/6 ;
`_claim_est_pertinente` faux négatifs FR. Conforme : `score.py` hors barème.

**Requirements Compliance** — FAIL (1 Medium). US-04 contextualiseur annoncée
mécanisée, mesurée à 1 tournure sur 6. US-01 scraper francophone : `DOUTEUX`
enrichi, mais aucun flux RSS francophone douteux collecté — le plan le dit
désormais explicitement, ce qui est honnête.

**Doc-Sync** — FAIL (1 High, 1 Medium). Docstring `_identifiant_client` caduc ;
`plan_implementation.md:111` en avance sur la réalité. Conforme : README
redescend `test_conformite_exigences.py` de « les critères d'acceptation » à
« une sélection de critères critiques », ce qui correspond enfin au fichier.

**A11y/UX** — PASS. `login.html` gagne des `<label for>` explicites,
`role="alert"` sur l'erreur et `aria-describedby` conditionnel. `detail.html`
expose désormais `faits_traces` et `deductions_llm` séparément, ce qui sert
directement US-02/US-03 frontend. Jinja2 autoéchappe : aucune injection.

**Clean Code** — PASS (réserve, 1 Low). `_detecter_langue` compte maintenant cinq
branches successives pour départager une égalité de mots-outils. C'est correct
(vérifié sur le corpus réel), mais chaque branche est une règle empirique de plus
sans mesure. À surveiller.

**Fail-Loud** — PASS (réserve, 1 Low). Les trois `except Exception` ajoutés autour
des commits journalisent, rollbackent et continuent — comportement voulu
(« dégrader jamais bloquer »). Réserve : `Exception` avale aussi les erreurs de
programmation, qui seront lues comme des refus de base.

**Test Quality** — FAIL (1 Critique, 1 Medium). Voir Top findings. Les 14
nouveaux tests sont dans l'ensemble de bonne facture : ils nomment le finding
qu'ils gardent et assertent un comportement, pas une existence.

**Mutation/Saboteur** — **PASS**. Cinq mutations appliquées sur une copie de
l'arbre, suite relancée à chaque fois : plafond LLM évaluateur → 1 test rouge ;
plafond d'articles par run → 1 test rouge ; plafond contextualiseur → 1 test
rouge ; `time.sleep` du débit SEC → 1 test rouge ; plafond du backfill → la
boucle ne termine plus (le test ne peut plus passer). Aucune mutation survivante.

**Layer Enforcer** — PASS. Aucun import inter-blocs nouveau ; le seuil transite
toujours par `fakenews.config`.

**YAGNI** — FAIL (1 Medium). `articles_a_traiter` sans appelant.

**SRE/Performance** — PASS (réserve, 1 Low). Le cache d'authentification économise
une requête indexée par requête HTTP ; le gain n'est pas mesuré. Le passage du
plafond du contextualiseur en SQL (`LIMIT`) est en revanche un vrai gain, mesuré
par la phase 10 et conservé ici.

**Architecture Consistency** — PASS. Le retrait de la double application du
plafond (SQL puis Python), demandé par la phase 12, est effectif et sémantiquement
équivalent : les deux chemins utilisaient `>=` sur le seuil.

**Contextual Threat** — FAIL (1 High). Verrouillage global du frontend, cf. Top
findings.

**SAST** — PASS. En-têtes de sécurité, CSP, pas d'injection SQL (requêtes
paramétrées SQLAlchemy), pas de XSS (autoéchappement Jinja2 sur les nouveaux
champs `fait.texte` et `item.texte`).

**Supply Chain** — PASS. `spacy>=3.8.0,<3.9.0` remplace `>=3.7,<4.0` : l'épinglage
du modèle NER `en_core_web_sm` (figé hors `requirements.txt`) redevient cohérent
avec la bibliothèque qui le charge. C'était le finding « épinglage à moitié » de
la phase 12.

**Privacy/Exfiltration** — PASS (réserve, 1 Low). Aucune sortie réseau nouvelle,
aucun secret journalisé. Réserve sur les quatre domaines francophones nommés.

---

## Corrections restant à faire, par ordre

1. **Bloquant** — réparer les 7 tests de `tests/test_comptes.py` (`app.py:301`,
   requête sans attribut `client`).
2. **Bloquant** — déplacer `if _trop_de_tentatives(...)` **après** l'échec de
   `_signature_valide` dans `compte_courant` (`app.py:364-366`), et ajouter le
   test manquant : « un cookie valide reste accepté quand le plafond est atteint ».
3. Corriger le docstring de `_identifiant_client` (`app.py:288-301`), devenu faux.
4. Rendre `_claim_est_pertinente` insensible à la flexion française, avec une
   entrée de corpus réel FR.
5. Décider pour `valider_formulation_prudente` : élargir et journaliser, ou
   assumer la garantie par prompt et le documenter.
6. Supprimer `articles_a_traiter` et `tests/test_declenchement.py`.
7. Réécrire `plan_implementation.md:111` une fois la suite verte.
8. Low : invalidation du cache de comptes ; doctype/PI dans `_BALISES` ; source de
   classement des domaines francophones.

---

## Correctifs appliqués après cet audit

Suite complète : **321 passés, 0 skippé** contre un vrai Postgres, migrations appliquées.

| # | Finding | Correctif | Vérification |
| ---: | --- | --- | --- |
| 1 | Critique — 7 tests rouges | Le plafond retiré de `compte_courant` supprime l'appel à `_identifiant_client` qui cassait les fixtures | 6/7 verts immédiatement ; le 7e était une pollution de cache (ligne suivante) |
| — | Pollution du cache entre tests | `_cache_comptes.clear()` dans la fixture autouse `_environnement_neutre` | `test_cookie_superadmin_lie_au_secret_hash` passait seul, échouait en suite ; vert dans les deux cas |
| 2 | High — cookie valide refusé | **Suppression** du couple `_trop_de_tentatives` / `_enregistrer_tentative_ratee` de `compte_courant` ; la charge base reste absorbée par le cache | Nouveau test `test_audit_phase13_plafond_ne_ferme_jamais_la_porte_a_un_cookie_valide`, **mutation killer vérifié** (plafond réintroduit → rouge) |
| 3 | High — docstring caduc | Sans objet : le retrait du plafond rend de nouveau vraie l'affirmation « une authentification réussie n'est jamais plafonnée » | Relecture |
| 4 | Medium — faux négatifs FR du fact-checking | Mots tronqués à 5 caractères dans `_mots_significatifs` ; claim sans texte désormais rejetée | `test_audit_phase13_claim_francaise_flechie_reste_pertinente` |
| 5 | Medium — US-04 décorative | Motif recomposé en désignation × accusation (produit croisé au lieu de 6 phrases), fin de proposition consommée, chaque réécriture journalisée | 6 tournures catégoriques adoucies contre 1 avant ; 2 formulations prudentes laissées intactes |
| 6 | Medium — code mort | `articles_a_traiter` et `SEUIL_PAR_DEFAUT` supprimés, `declenchement.py` et `test_declenchement.py` supprimés, `PLAFOND_APPELS_PAR_DEFAUT` déplacé dans `fakenews.config` | Suite verte, un module et un fichier de tests en moins |
| 7 | Medium — plan en avance sur la réalité | Ligne « Phases 7 à 13 » réécrite : acquis vérifiés par mutation, et mention explicite du plafond annulé | Relecture |
| 8a | Low — cache sans invalidation | Purge du pseudo à chaque connexion réussie | Couvert par la suite |
| 8b | Low — doctype/PI dans `_BALISES` | `<![^>]*>|<\?.*?\?>` ajoutés à l'alternative | Corpus réel `a < b` toujours vert |
| 8c | Low — domaines francophones | Source de classement citée (Décodex, date de consultation) et raison du besoin d'attribution | Relecture |

**Choix de conception à retenir** : le finding High a été fermé par une *suppression*, pas
par un réordonnancement. Un plafond posé sur un identifiant que tous les visiteurs
partagent derrière le proxy ne peut pas protéger la base sans pouvoir fermer le site ;
le cache de comptes, ajouté dans le même lot, couvre déjà la charge que ce plafond
prétendait couvrir. Le plafond de `/login` — lui légitime, puisqu'il ne plafonne que les
échecs sur une route qui n'en a pas d'autre usage — est inchangé.

**Reste ouvert, assumé** : `valider_formulation_prudente` reste un garde-fou lexical.
Une accusation portée par un nom propre (« Le Monde ment ») y échappe : la couvrir
demanderait de la reconnaissance d'entités, hors de proportion avec le gain. La première
ligne de défense reste la consigne de prompt, ce que le docstring dit désormais.

---

## Limites de vérification

- **Commandes exécutées** : `pytest -q` complet contre un Postgres 16 local
  (`fakenews_test`, migrations `0001`/`0002`/`0003` appliquées) → `7 failed,
  318 passed` ; cinq mutations de plafond sur une copie de l'arbre dans un
  répertoire temporaire ; deux scripts de vérification ciblés (refus d'un cookie
  valide sous plafond ; couverture réelle de `valider_formulation_prudente` sur
  six formulations).
- **Non exécuté** : aucun appel réseau réel (SEC EDGAR, Google Fact Check Tools,
  Anthropic, Reddit, flux RSS) — le `conftest.py` interdit les connexions
  sortantes non locales, et cet audit ne l'a pas contourné. Les comportements de
  ces intégrations sont donc jugés sur le code et les corpus enregistrés, pas sur
  l'API vivante.
- **Non exécuté** : aucun déploiement Vercel, donc le partage d'IP de proxy
  derrière Vercel est établi par lecture de `_identifiant_client` et de la valeur
  documentée `FAKENEWS_PROXYS_DE_CONFIANCE=1`, pas par observation en production.
  Le verrouillage lui-même est en revanche reproduit localement.
- **Environnement** : `psycopg2-binary` (le driver du projet) ; une première
  tentative avec `psycopg` v3 a produit 89 erreurs de collecte — artefact de
  l'auditeur, sans rapport avec le code audité, corrigé avant toute conclusion.
- **Périmètre exclu** : les fichiers non modifiés par l'arbre de travail n'ont pas
  été réaudités. Les findings des phases 11 et 12 qui ne sont pas touchés par ces
  correctifs restent ouverts et ne sont pas repris ici.
- **Hooks actifs** : `.claude/settings.json` injecte des consignes `PreToolUse`
  sur `Read`/`Glob`/grep depuis l'installation de graphify ; elles n'ont pas
  restreint la lecture des fichiers audités.
