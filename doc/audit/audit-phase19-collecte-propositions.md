# Audit phase 19 — Phase 3 du crowdsourcing : correctif F3 et collecteur

Date : 2026-09-13 · Scope : le correctif F3 (`evaluateur/run_evaluateur.py`), le
collecteur `scraper/propositions.py`, le plafond de lecture ajouté à
`scraper/rss.py`, le branchement dans `pipeline_hebdomadaire.yml`,
`tests/test_collecte_propositions.py`.
Base d'exigences : `doc/V3/userstories_crowdsourcing.md` (US-04),
`doc/V3/plan_implementation_crowdsourcing.md` (phase 3),
`doc/V0/architecture.md` (« dégrader, jamais bloquer »),
`doc/audit/audit-phase14-codebase-complete.md` (F3).
État audité : arbre de travail non commité.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🔴 Bloquant | Un échec de collecte n'est **jamais enregistré** : la proposition reste « acceptée » pour l'éternité, le proposant n'apprend rien, et le pipeline retélécharge la même page morte à chaque run. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Douze tests verts sur un comportement que la base ne garde pas. Ils partagent la session du code testé : ils voient une vérité qui n'existe que dans leur tête. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Le correctif F3 déplace le tri sur une colonne non indexée. On a échangé une famine contre un balayage complet. |
| Cybersécurité offensive (Sherlock Holmes) | 🟢 OK | La borne de taille, le timeout, la revalidation de schéma et la collecte hors Vercel tiennent. Rien d'exploitable trouvé. |

**Verdict global : AUDIT_FAIL.** 1 High, 3 Medium, 4 Low.

La fonctionnalité marche de bout en bout sur le chemin nominal — proposition,
collecte, score, vérifié par un test dédié. C'est le **chemin d'échec** qui ne
tient pas, et c'est précisément celui que la docstring du module promet de bien
traiter.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | US-04, cycle de vie d'une proposition | 0 | 1 | 1 | 1 | AUDIT_FAIL |
| Requirements Compliance Auditor | US-04 vs implémentation | 0 | 0 | 0 | 1 | AUDIT_FAIL |
| Doc-Sync Auditor | README, plan V3, `.env.example` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | statuts affichés au proposant | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Clean Code Auditor | `propositions.py` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Fail-Loud Auditor | chemins d'échec du collecteur | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Test Quality Auditor | 13 tests neufs | 0 | 0 | 1 | 1 | AUDIT_FAIL |
| Mutation/Saboteur Auditor | correctif F3, collecteur | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Layer Enforcer | imports du collecteur | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | helpers du collecteur | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | tri F3, requêtes du collecteur | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Architecture Consistency Auditor | plan phase 3 vs code | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | URL fournies par les utilisateurs | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| SAST Scanner | téléchargement, parsing | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | aucune dépendance ajoutée | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | métadonnées de proposition | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte dédupliqué : **8 findings**.

---

## Matrice De Couverture

| Exigence (US-04 / plan phase 3) | Preuve | Statut |
| --- | --- | --- |
| La collecte se fait dans le pipeline, jamais depuis Vercel | `scraper/propositions.py`, step dédié du workflow | ✅ |
| `plateforme = 'proposition'`, hôte en `domaine_source` | test dédié | ✅ |
| Métadonnée renvoyant à la proposition et au proposant | test + lecture | ✅ |
| Succès ⇒ statut `collectee` + `article_id` | test dédié | ✅ |
| **Échec ⇒ statut `echec_collecte` + motif, sans interrompre** | bilan annonce l'échec, **la base garde `acceptee`** | ❌ **F19-01** |
| Plafond par run, configurable | test + `.env.example` | ✅ |
| Schéma `http(s)` revalidé au moment de la connexion | test : aucune connexion ouverte | ✅ |
| Lecture bornée en taille | paramètre transmis (test), **borne réelle non exercée** | ⚠️ F19-07 |
| Repli de date tracé dans la donnée | `date_publication_estimee`, test dédié | ✅ |
| F3 — le reliquat est réellement repris | sonde : l'article dépassé est noté au run suivant | ✅ |
| F3 — le tri reste soutenable | **`date_collecte` non indexée** | ❌ F19-03 |
| L'article proposé suit le parcours normal | test de bout en bout jusqu'au score | ✅ |

---

## Top Findings

- **[High] F19-01** — ✅ **corrigé le 2026-09-13**, cf. « Suivi des correctifs ».
  `src/fakenews/scraper/propositions.py`, boucle de `collecter_propositions` — chaque branche d'échec se termine par `continue`
  **à l'intérieur** du `with session.begin_nested():`. Or `session.commit()` est
  placé APRÈS le bloc `with` : le `continue` le saute. Le changement de statut ne
  vit donc que dans la transaction courante, et n'est écrit que si une itération
  ULTÉRIEURE réussit à commiter.
  **Mesuré**, une seule proposition injoignable : le bilan annonce
  `{'collectees': 0, 'echecs': 1}` — et la base relue depuis une session neuve
  répond **`acceptee`**.
  **Impact :** trois conséquences, toutes silencieuses. La proposition est
  reprise à **chaque run**, donc la même page morte est retéléchargée
  indéfiniment. Le proposant voit « acceptée — en attente du prochain run
  d'analyse » pour toujours, alors que la collecte a échoué : l'interface lui
  ment. Et le cas `deja_presentes` perd de la même façon son `article_id`, donc
  le rattachement à l'article existant n'est jamais enregistré.
  C'est exactement le contraire de ce que la docstring du module promet —
  « dégrader, jamais bloquer… au grain de l'ENTRÉE » : l'entrée fautive ne dégrade
  pas, elle s'efface.
  **Correction attendue :** commiter dans chaque branche, ou — plus sûr —
  déplacer le `session.commit()` dans un `finally` de l'itération, ou remplacer
  les `continue` par une structure qui retombe sur un point de sortie unique.
- **[Medium] F19-02 · `src/fakenews/scraper/propositions.py`,
  `_construire_article`** — `auteur=None` en dur. Or `evaluer_style` pénalise de
  **+20 points** « aucun auteur identifiable ». **Tout article entré par
  proposition est donc structurellement pénalisé**, indépendamment de son
  contenu, alors que les pages déclarent couramment leur auteur
  (`<meta name="author">`, `article:author`). Le collecteur extrait déjà le titre
  et la date par le même procédé : l'auteur a été oublié, pas écarté.
  Même famille que F9 (phase 14) sur les flux RSS sans byline, en pire : ici
  c'est systématique, et cela touche précisément les articles qu'un humain a
  jugés dignes d'attention.
  **Correction attendue :** extraire `meta[name=author]` / `article:author`, et à
  défaut laisser `None` — mais alors le dire dans la métadonnée, comme pour la
  date.
- **[Medium] F19-03 · `src/fakenews/evaluateur/run_evaluateur.py`, sélection des
  articles** — le correctif F3 trie sur `Article.date_collecte`, colonne **sans
  index** : `pg_indexes` ne liste que `id`, `url_canonique`, `domaine_source`,
  `date_publication` et `hash_contenu`. Le tri précédent portait justement sur
  `date_publication`, qui est indexée. À chaque run, l'évaluateur trie donc
  l'intégralité des articles non scorés sans index.
  Sans conséquence au volume actuel — **[RISQUE]** sur l'ampleur réelle, non
  mesurée — mais c'est une régression de performance introduite en corrigeant une
  famine.
  **Correction attendue :** `create index if not exists idx_articles_date_collecte
  on articles (date_collecte)`, dans une migration.

---

## Thèmes Transverses

1. **Le chemin nominal est testé, le chemin d'échec ne l'est pas vraiment.**
   Douze tests couvrent les échecs de collecte… et aucun ne survit à la question
   « et la base, elle en pense quoi ? ». C'est la faiblesse structurelle d'une
   fixture qui partage la session du code testé.
2. **Corriger une famine peut coûter un index.** F3 est bien corrigé ; le tri qui
   le corrige n'a pas été regardé côté plan d'exécution.
3. **Ce qui est extrait l'est bien, ce qui est oublié l'est en silence.** Titre et
   date sont extraits avec soin, la date manquante est même tracée dans la
   donnée. L'auteur, lui, est câblé à `None` sans qu'aucun commentaire ne dise
   que c'est un choix.

---

## Détails Par Division

### Division Métier (Anton Ego)

On m'annonce un échec, on l'inscrit au bilan, on le journalise — et on ne le
consigne nulle part. Le convive attend son plat, le registre dit qu'il est
servi, et la cuisine recommence la même préparation ratée chaque semaine.

- **[High] F19-01** — cf. Top Findings. **Type : Confirmé (mesuré).**
- **[Medium] F19-02** — cf. Top Findings. **Type : Confirmé** (lecture) ; l'effet
  de +20 sur le score composite dépend des autres signaux disponibles —
  **[RISQUE]** sur l'ampleur par article.
- **[Low] F19-05** — `templates/compte.html` annonce au proposant « acceptée — en
  attente du prochain run d'analyse ». Or l'article créé entre en **queue** de la
  file FIFO de l'évaluateur (`date_collecte` = maintenant), donc derrière tout le
  reliquat. Avec un backlog supérieur au plafond, l'analyse n'arrive pas « au
  prochain run ». La promesse est optimiste, pas fausse par construction.
  **Correction attendue :** formuler « en attente d'analyse » sans promettre
  d'échéance, ou faire passer les articles proposés devant — ce qui serait un
  choix de priorité à assumer, pas un détail de formulation.

### Division Qualité (Gordon Ramsay)

Douze tests au vert sur un comportement que la base ne conserve pas. Vos tests et
votre code se passent la même assiette sous la table : évidemment qu'ils sont
d'accord.

- **[Medium] F19-04** `tests/test_collecte_propositions.py` — la fixture
  `db_session` est passée directement à `collecter_propositions`, donc les
  assertions lisent **la session qui vient d'écrire**, jamais la base. Un
  changement non commité y est indiscernable d'un changement commité. C'est ce
  qui a laissé passer F19-01, et le test
  `test_une_page_injoignable_ne_bloque_pas_les_suivantes` ne passe que par chance
  — la proposition en échec précède une réussite dont le `commit()` sauve la
  mise.
  **Correction attendue :** au moins un test qui relit l'état depuis une seconde
  session (ou un `expire_all()` après un `commit()` explicite du test), sur le
  chemin d'échec.
- **[Low] F19-07** — `test_la_lecture_est_bornee_en_taille` vérifie que la valeur
  est **transmise** et que la constante est petite ; il ne prouve pas que
  `_telecharger` s'arrête effectivement à cette taille. La fixture `sans_reseau`
  remplace la fonction, donc le `read(taille_max)` ajouté à `rss.py` n'est
  exercé par aucun test.
- **Points conformes :** treize tests dont un parcours de bout en bout jusqu'au
  score — le seul qui vérifie que les deux moitiés du crowdsourcing se
  rejoignent ; les cas de refus (schéma non http, page vide, statut non accepté)
  sont testés autant que les cas nominaux.

### Division Architecture (Steve Jobs)

Un tri sans index. On corrige une famine en payant un balayage, et on ne le
mentionne nulle part.

- **[Medium] F19-03** — cf. Top Findings.
- **[Low] F19-06** `propositions.py`, gestionnaire d'exception externe — le repli
  pose `statut = "echec_collecte"` **sans motif**, là où toutes les autres
  branches en fournissent un. Le proposant lit « collecte impossible » sans
  raison, précisément dans le cas le moins compréhensible (exception
  inattendue).
- **Points conformes :** le collecteur réutilise `_telecharger`, `nettoyer_html`,
  `canonicaliser_url` et `hacher_contenu` au lieu de les réécrire ; le plafond de
  lecture ajouté à `rss.py` profite aussi aux flux ; aucune dépendance nouvelle ;
  aucun franchissement de frontière entre blocs.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : pour une fois, je n'ai rien à redire sur le fond. La
mesure de sécurité principale est structurelle — on va chercher l'URL depuis un
runner jetable, pas depuis la fonction qui sert le site — et elle est
correctement mise en œuvre.

- **[Low] F19-08** `propositions.py`, motifs `_DATE_DECLAREE` — les expressions
  régulières enchaînent des `[^>]+` sur du contenu contrôlé par un tiers. Sur une
  page construite exprès (une balise `<meta` de plusieurs centaines de milliers de
  caractères sans `>`), le moteur peut backtracker longuement. La lecture étant
  bornée à 2 Mo et le travail se faisant dans un runner jetable, l'impact
  plafonne à un run lent. **Type : [RISQUE]**, non mesuré.
- **Points conformes :** schéma revalidé au point de connexion, et vérifié par un
  test qui s'assure qu'**aucune connexion n'est ouverte** ; lecture bornée à 2 Mo
  quoi qu'annonce le serveur ; timeout explicite hérité de `_telecharger` ; le
  contenu collecté est échappé à l'affichage comme tout autre article ; les
  métadonnées n'enregistrent que des pseudos déjà publics dans la file.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F19-01, F19-02, F19-05.
- **Points conformes :** seuls les statuts `acceptee` sont collectés ; un article
  déjà présent est rattaché plutôt que dupliqué ; l'ordre de traitement est stable
  et favorise les plus anciennement acceptées.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_FAIL. Le 4ᵉ critère d'US-04 — « un échec de collecte fait
  passer la proposition à `echec_collecte` avec un motif » — n'est pas tenu en
  base (F19-01), alors qu'il l'est en apparence dans le bilan et les journaux.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS. README, `.env.example`, plan V3 et état d'avancement
  décrivent exactement ce qui est livré, y compris la pause du `schedule`.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F19-05 (promesse
  d'échéance). Les statuts sont rendus en texte, pas en code, et le motif de refus
  est affiché au proposant.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F19-06.
- **Points conformes :** fonctions courtes, `_marquer` évite quatre répétitions,
  chaque constante porte la raison de sa valeur.

### Fail-Loud Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F19-01 — l'échec est journalisé et
  compté, mais pas persisté : la forme la plus trompeuse d'échec silencieux,
  puisque tous les signaux visibles disent le contraire.

### Test Quality Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F19-04, F19-07.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_FAIL. **Mutation qui survivrait :** supprimer entièrement
  le `session.commit()` du collecteur — aucun test ne tombe, puisque aucun ne lit
  la base depuis une autre session. C'est F19-01 sous un autre angle.
  **Mutations bien tuées :** tri F3 inversé, plafond ignoré, revalidation de
  schéma retirée, repli de date non tracé.

### Layer Enforcer / YAGNI / Architecture Consistency
- **Verdict :** AUDIT_PASS. Le collecteur vit dans `fakenews.scraper`, n'importe
  que de l'infrastructure et son propre bloc, et le plan phase 3 décrit
  exactement ce qui a été fait.

### SRE/Performance Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F19-03 (tri non indexé).
- **Points conformes :** plafond par run, lecture bornée, une requête par
  proposition et non par champ.

### Contextual Threat Analyst
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F19-08.
- **Scénario écarté :** faire collecter une ressource interne — la collecte a lieu
  dans un runner GitHub Actions sans réseau privé intéressant, et c'est la raison
  documentée de ce placement.

### SAST Scanner / Supply Chain / Privacy
- **Verdict :** AUDIT_PASS. Aucune injection, aucune dépendance ajoutée, aucune
  donnée personnelle nouvelle hors pseudos déjà visibles dans la file.

---

## Points Conformes (Synthèse)

- **F3 est réellement corrigé** : sonde rejouée, l'article autrefois affamé est
  noté au run suivant, et le journal nomme désormais le cas qu'aucun tri ne règle.
- Le parcours complet proposition → acceptation → collecte → score est vérifié
  par un test unique et explicite.
- La mesure de sécurité principale est structurelle et correctement placée :
  l'URL utilisateur est tirée depuis le runner, jamais depuis Vercel.
- Le repli de date est tracé **dans la donnée** (`date_publication_estimee`), pas
  seulement dans un commentaire.
- **395 tests, 0 skip** contre un vrai Postgres avec les cinq migrations.

---

## Limites De Vérification

- **F19-02 :** l'effet réel du +20 sur le score composite d'un article proposé
  dépend des autres signaux disponibles ; non mesuré sur un corpus.
- **F19-03 :** aucun `EXPLAIN` exécuté, aucun volume réaliste chargé — le défaut
  est structurel (colonne non indexée), son coût ne l'est pas.
- **F19-08 :** aucune page adverse construite pour mesurer le backtracking.
- **Aucun téléchargement réel** : la fixture remplace `_telecharger`, donc le
  comportement face à une redirection, un certificat invalide ou un serveur lent
  n'est pas observé.
- Aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **395 passed, 0 skipped** |
| Sonde : une seule proposition injoignable, relecture en session neuve | bilan `echecs: 1`, base : **`acceptee`** |
| Lecture de `_construire_article` | `auteur=None,` en dur |
| `select indexdef from pg_indexes where tablename='articles'` | 5 index, **aucun sur `date_collecte`** |
| Sonde F3 rejouée | le reliquat passe devant, plus de famine |


---

## Suivi Des Correctifs — 2026-09-13

**Les huit findings sont traités.** Suite : **402 tests, 0 skip**.

### F19-01 — l'échec n'était pas commité · ✅ corrigé par SUPPRESSION du motif

Plutôt que d'ajouter un `commit()` dans chaque branche — ce qui aurait laissé le
piège en place pour la prochaine —, les sorties anticipées ont disparu :
`_collecter_une` traite une proposition et **retourne** sa clé de bilan ; la
boucle fait `with begin_nested(): cle = _collecter_une(...)` puis commite
**inconditionnellement**. Il n'existe plus de chemin qui saute le commit.

**Vérification, sonde de l'audit rejouée :** une seule proposition injoignable,
relecture depuis une session neuve → **`echec_collecte`** (contre `acceptee`
avant). Mutation : rendre le commit conditionnel fait tomber trois cas de test
sur trois.

### F19-02 — auteur câblé à `None` · ✅ corrigé

`_extraire_auteur` lit `meta[name=author]`, `article:author` et `byl`, dans les
deux ordres d'attributs. Un `_meta(noms)` partagé avec l'extraction de date
supprime la duplication au passage. Une page qui ne signe pas reste sans auteur —
la pénalité d'US-05 est alors méritée, et une contre-épreuve l'exige (sans quoi
retourner une valeur bidon passerait).

### F19-03 — tri non indexé · ✅ corrigé

Migration `0006_index_date_collecte.sql`. Vérifié : `pg_indexes` liste désormais
`idx_articles_date_collecte`. « Premier collecté, premier servi » était le bon
ordre ; il est maintenant soutenable.

### F19-04, F19-07 — tests · ✅ corrigés

Trois formes d'issue sont vérifiées par un test paramétré qui compte les commits
— la propriété qui manquait. Sa docstring dit explicitement ce que la fixture
partagée **ne peut pas** prouver, plutôt que de laisser croire le contraire. Le
plafond de lecture est désormais exercé sur la **vraie** `_telecharger`, avec une
réponse factice qui prétend livrer 50 Mo : `read(1000)` en rend 1000.

### F19-05, F19-06, F19-08 — ✅ corrigés

L'interface n'annonce plus « au prochain run » mais « en attente d'analyse » — la
file d'attente ne garantissait pas cette échéance. Le repli d'exception pose
désormais un motif, comme toutes les autres branches. Les motifs d'extraction
bornent leurs quantificateurs (`[^>]{0,300}`), ce qui referme le backtracking
possible sur une balise démesurée.

### Incident pendant la correction — `git checkout` sur un fichier non commité

Une commande de restauration après mutation a utilisé `git checkout
src/fakenews/scraper/rss.py`, qui a **écrasé trois modifications non commitées** :
l'import de `fakenews.normalisation` (phase 2 V3), le correctif `_BALISES` de
l'audit phase 11 — celui qui empêchait `<[^>]+>` de détruire le texte autour d'un
« < » isolé — et le plafond de lecture ajouté la veille.

Les trois ont été reconstruites et la suite repasse au vert, le test de la phase 11
compris. La leçon vaut d'être écrite : **restaurer après mutation doit se faire
depuis une copie, jamais depuis `git`**, tant que l'arbre de travail porte des
modifications non commitées — ce qui est le cas de ce dépôt depuis vingt audits.

### Revue ponytail

Deux findings appliqués sur mes propres correctifs : deux tests couvraient la
même propriété (fusionnés, −14 lignes), et le paramétrage passait la page HTML
entière en identifiant de test (remplacé par une clé lisible).
