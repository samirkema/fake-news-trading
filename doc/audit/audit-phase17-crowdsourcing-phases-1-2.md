# Audit phase 17 — Crowdsourcing V3, phases 1 et 2

Date : 2026-09-12 · Scope : les routes d'écriture du frontend et leur support —
`frontend/app.py` (autorisation, CSRF, espace compte, administration des comptes,
propositions, file d'attente), les quatre gabarits neufs, `models.Proposition`,
`fakenews.normalisation`, les migrations `0004` et `0005`,
`tests/test_crowdsourcing.py`.
Base d'exigences : `doc/V3/userstories_crowdsourcing.md`,
`doc/V3/plan_implementation_crowdsourcing.md`, `doc/V0/architecture.md`
(décision V3), `doc/V1/comptes-3-roles.md`, audits phases 14 à 16.
État audité : arbre de travail non commité.

Premier audit d'une fonctionnalité neuve depuis la phase 14. Le frontend cesse
ici d'être en lecture seule : c'est la surface la plus exposée du projet qui
double de taille.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Les huit user stories sont tenues et testées ; mais le code provisoire d'un contributeur voyage dans une URL, et une re-promotion efface sans un mot le code que son titulaire avait choisi. |
| Qualité (Gordon Ramsay) | 🔴 Bloquant | Le jeton CSRF fait tomber le serveur sur une saisie accentuée. Troisième occurrence de la même classe de bug — dans du code écrit **après** l'avoir corrigée deux fois. |
| Architecture (Steve Jobs) | 🟢 OK | Le déménagement de `canonicaliser_url` est la bonne réponse au bon dilemme ; la frontière « intentions humaines vs verdict » tient, et un test la garde enfin. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant | Deux défauts exploitables : un code personnel de plus de 72 octets n'est vérifié qu'en partie, et le jeton CSRF est calculable par tout détenteur du mot de passe partagé — c'est-à-dire par tous les utilisateurs. |

**Verdict global : AUDIT_FAIL.** 2 High, 3 Medium, 4 Low. Aucun Critique.

La fonctionnalité fait ce qu'elle annonce : parcours complet exécuté de bout en
bout, **368 tests, 0 skip**, 33 dédiés. Les défauts sont concentrés sur les
mécanismes transverses ajoutés à la hâte autour d'elle — le jeton CSRF et la
manipulation des codes personnels — pas sur la logique métier.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | propositions, décisions, promotions | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Requirements Compliance Auditor | US-01 à US-07 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | README, `.env.example`, plan V3 | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| A11y/UX Checker | 4 gabarits neufs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `app.py` (+380 lignes) | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Fail-Loud Auditor | chemins d'erreur des écritures | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Test Quality Auditor | `test_crowdsourcing.py` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | gardes d'accès et CSRF | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Layer Enforcer | `fakenews.normalisation` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | helpers ajoutés | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | requêtes des nouvelles routes | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Architecture Consistency Auditor | frontière d'écriture V3 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | scénarios d'abus crowdsourcing | 0 | 1 | 1 | 0 | AUDIT_FAIL |
| SAST Scanner | injections, authz, secrets | 0 | 1 | 2 | 0 | AUDIT_FAIL |
| Supply Chain & Artifact Auditor | dépendances, migrations | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | secrets dans URL et journaux | 0 | 0 | 1 | 0 | AUDIT_FAIL |

Décompte dédupliqué : **9 findings**.

---

## Matrice De Couverture

| Exigence | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| US-01 — tout compte connecté propose | `app.py` `proposer` | test dédié | ✅ |
| US-01 — schéma `http(s)` uniquement | `app.py` `_url_proposable` | 5 schémas refusés (test paramétré) | ✅ |
| US-01 — pas de doublon avec un article existant | `app.py` `proposer` | renvoi vers la fiche, 0 proposition créée | ✅ |
| US-01 — plafond par compte | `app.py` `_propositions_recentes` | compté en base, opposable (test) | ✅ |
| US-02 — file réservée aux contributeurs | `app.py` `exige_role` | 404 sur accès direct (test) | ✅ |
| US-02 — le superadmin est aussi contributeur | `app.py` `ROLES_ORDRE` | comparaison d'ordre (test) | ✅ |
| US-03 — refus motivé obligatoire | `app.py` + `ck_propositions_refus_motive` | route ET schéma | ✅ |
| US-03 — pas de re-décision | `app.py` `_decider` | condition dans l'`UPDATE` (test) | ✅ |
| US-04 — l'acceptation ne collecte pas | `app.py` `accepter_proposition` | `article_id` nul, 0 article (test) | ✅ |
| US-05 — code actuel exigé | `app.py` `changer_code` | test dédié | ✅ |
| US-05 — « tout caractère saisissable » | `app.py` `_normaliser_secret` | NFC/NFD acceptés (test) | ⚠️ **F17-02** |
| US-06 — code personnel imposé au contributeur | migration `0004` | contrainte + test | ✅ |
| US-06 — code provisoire affiché une seule fois | `app.py` `promouvoir` | affiché… **via l'URL** | ❌ **F17-03** |
| US-07 — compte matérialisé à la connexion | `app.py` `_enregistrer_compte` | 2 tests | ✅ |
| Transverse — CSRF sur chaque écriture | `app.py` `exige_csrf` | 403 sans jeton (test) | ❌ **F17-01, F17-04** |
| Transverse — le frontend n'écrit pas le verdict | `tests/test_crowdsourcing.py` | test de source | ✅ (faible, F17-06) |

---

## Top Findings

- **[High] F17-01 · `src/fakenews/frontend/app.py`, `exige_csrf`** — le jeton reçu
  est comparé par `hmac.compare_digest` sur deux `str`. Un jeton non-ASCII fait
  donc lever un `TypeError` : **500 au lieu de 403**. **Mesuré :**
  `csrf='mauvais-jeton-ascii'` → 403, `csrf='café'` → **500**, `csrf='jetön'` →
  **500**.
  C'est la **troisième occurrence de la classe de bug F2** — après `/login`
  (phase 14) et la signature du cookie (phase 0) — et la première écrite *après*
  que la leçon ait été tirée deux fois. Le correctif précédent avait traité deux
  sites d'appel ; il n'a pas empêché le troisième d'être créé une semaine plus
  tard.
  **Correction attendue :** la même qu'au cookie, et pour la même raison — valider
  la FORME à la frontière (un jeton est toujours un hexdigest sha256,
  `^[0-9a-f]{64}$`), ce qui rend la comparaison impossible à faire déborder. Et,
  structurellement : une seule fonction de comparaison de secrets dans le module,
  qui encode, plutôt que trois sites d'appel qui se souviennent chacun de le
  faire.
- **[High] F17-02 · `src/fakenews/frontend/app.py`, `CODE_LONGUEUR_MAX = 200`** —
  bcrypt ne prend en compte que les **72 premiers octets**. Le code accepte 200
  caractères. **Mesuré :** deux codes identiques sur 72 octets et différents
  ensuite ouvrent le **même** hash (`True`). Un contributeur qui choisit une
  phrase de passe longue croit avoir un secret de 200 caractères ; il en a 72, et
  toute variante partageant ce préfixe ouvre son compte.
  **Correction attendue :** refuser au-delà de 72 **octets** (pas caractères — un
  « é » en compte deux), avec un message qui l'explique. La borne actuelle promet
  une sécurité que l'algorithme ne rend pas.
- **[Medium] F17-03 · `src/fakenews/frontend/app.py`, `promouvoir`** — le code
  provisoire est transmis en **query string** :
  `/admin/comptes?pseudo_promu=…&code_provisoire=…`. Il atterrit donc dans les
  journaux d'accès de Vercel, l'historique du navigateur et le cache de la barre
  d'adresse. Le module contient pourtant, quatre fonctions plus haut, une
  docstring qui dit exactement pourquoi on ne met pas de secret dans une URL
  (« une URL se retrouve dans les journaux, l'historique et le `Referer` ») — à
  propos de simples messages d'erreur.
  **Correction attendue :** transporter le code dans un cookie éphémère signé
  (`max_age` court), ou le rendre directement dans la réponse du POST. Un secret
  à usage unique ne doit pas laisser de trace durable dans trois journaux.

---

## Thèmes Transverses

1. **Une classe de bug ne se corrige pas site par site.** F17-01 est la troisième
   apparition du même défaut. Les deux correctifs précédents ont traité *des
   lignes*, pas *la règle* : rien dans le module n'empêche le prochain
   `compare_digest(str, str)` d'être écrit. Une fonction unique de comparaison de
   secrets aurait clos le sujet en phase 0.
2. **Le mot de passe partagé contamine tout ce qui dérive de lui.** Le jeton CSRF
   utilise `FRONTEND_PASSWORD` comme clé : puisque tous les utilisateurs
   connaissent ce secret, tous peuvent calculer le jeton de n'importe qui
   (F17-04). Chaque mécanisme adossé à ce secret hérite de sa faiblesse — le même
   constat qu'en phase 16 sur le bruteforce.
3. **Ce qui est vérifié tient, ce qui est transverse dérape.** Les huit user
   stories sont tenues, testées, et leurs invariants vivent dans le schéma autant
   que dans les routes. Les trois findings sérieux portent tous sur des
   mécanismes ajoutés *autour* de la fonctionnalité.

---

## Détails Par Division

### Division Métier (Anton Ego)

Le service est irréprochable : chaque promesse du menu est tenue, et la maison a
même pris soin de graver ses règles dans le marbre du schéma plutôt que dans le
sable des routes. Je note toutefois qu'on remet au client un code confidentiel
en le criant à travers la salle.

- **[Medium] F17-03** — cf. Top Findings. **Type : Confirmé** (lecture du code,
  motif `code_provisoire=` dans l'URL de redirection).
- **[Low] F17-07** `app.py`, `promouvoir` — la route ne refuse que le rôle
  `superadmin`. Une promotion rejouée sur un compte **déjà contributeur**
  régénère un code provisoire et **écrase silencieusement le code que son
  titulaire avait choisi** (US-05), en invalidant ses sessions. L'interface
  n'offre pas le bouton dans ce cas, donc il faut un POST délibéré — mais une
  opération destructrice ne devrait pas dépendre de l'absence d'un bouton.
  **Correction attendue :** refuser si la cible est déjà contributrice, ou
  l'annoncer explicitement.
- **Points conformes :** l'acceptation n'est pas une collecte (vérifié :
  `article_id` nul et zéro article créé) ; le refus exige un motif côté route ET
  côté base ; la re-décision est impossible par construction (condition dans
  l'`UPDATE`, pas lecture-puis-écriture) ; le doublon renvoie vers la fiche
  existante au lieu d'empiler.

### Division Qualité (Gordon Ramsay)

Vous avez corrigé ce bug en phase 14. Vous l'avez re-corrigé en phase 0, sur un
second site que le premier correctif avait manqué. Et une semaine plus tard vous
en écrivez un troisième, de vos propres mains, dans la fonction censée protéger
les écritures. Ce n'est plus une erreur, c'est une recette.

- **[High] F17-01** — cf. Top Findings. **Type : Confirmé (mesuré).**
- **[Low] F17-06** `tests/test_crowdsourcing.py`,
  `test_le_frontend_n_ecrit_jamais_articles_scores_ni_mise_en_contexte` — le test
  cherche les chaînes `"Article("`, `"Score("`, `"MiseEnContexte("` dans le
  source. Il passerait si le frontend écrivait via `session.execute(insert(Article))`
  ou via une relation. Il garde une *orthographe*, pas une propriété. Il reste
  meilleur que rien — ce contrat n'était couvert par aucun test (F12, phase 14) —
  mais il ne faut pas le croire plus fort qu'il n'est.
- **[Low]** `app.py` dépasse 1200 lignes et porte désormais authentification,
  autorisation, CSRF, consultation, propositions et administration. Le découpage
  en routeurs FastAPI devient dû — la phase 4 (commentaires) ajoutera encore.
- **Points conformes :** 33 tests neufs qui testent **autant les refus que les
  permissions** ; accès direct aux URL réservées vérifié, pas seulement l'absence
  de lien ; une fixture `client` documentée sur le piège `https` (cookie `Secure`
  jamais renvoyé en clair), constat qui a coûté un détour réel.

### Division Architecture (Steve Jobs)

Une seule décision structurante, et elle est juste. Le reste est à sa place.

- **Points conformes :** `canonicaliser_url` déplacé dans un module
  d'infrastructure neutre plutôt que dupliqué ou importé en travers des blocs —
  la duplication aurait fait diverger la déduplication au premier caractère
  d'écart ; `exige_role` compare un ordre et non une égalité, ce qui évite
  d'exclure le superadmin de ses propres écrans ; `_contexte` supprime la
  recopie de dictionnaires que la prochaine route aurait oubliée ; le refus en
  404 plutôt qu'en 403 ne révèle pas l'existence de la file.
- **[Low] F17-08** `models.py`, `Proposition` — le modèle déclare la contrainte de
  statut mais ni l'index unique partiel, ni `ck_propositions_refus_motive`, ni
  `ck_propositions_decision_tracee`. `verifier_schema` ne contrôlant que les
  colonnes, une base à qui manquerait `0005` ne se signalerait qu'à la première
  écriture. Dette connue et déjà documentée, aggravée d'un cran.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : votre jeton anti-CSRF est dérivé d'un secret que vous
avez distribué à tous vos utilisateurs. Il protège donc contre les inconnus, et
contre eux seuls.

- **[High] F17-02** — cf. Top Findings. **Type : Confirmé (mesuré).**
- **[Medium] F17-04** `app.py`, `jeton_csrf` — le jeton vaut
  `HMAC(FRONTEND_PASSWORD, "csrf:" + pseudo)`. Tout utilisateur légitime connaît
  `FRONTEND_PASSWORD` : il peut donc **calculer le jeton de n'importe quel autre
  pseudo** et monter une CSRF visant un contributeur — par exemple lui faire
  accepter une proposition. Le jeton ne dépend ni de la session, ni de son
  expiration, ni du code personnel ; il ne tourne jamais.
  **Type : Confirmé** (par construction) ; l'exploitation complète n'a pas été
  jouée — **[RISQUE]**.
  **Correction attendue :** dériver le jeton de la clé de session déjà en place
  (`_cle_signature`, qui intègre `secret_hash`) et y inclure l'expiration du
  cookie. Le mécanisme existe et est déjà testé pour le cookie.
- **[Medium] F17-05** `app.py`, `_avec_erreur` + gabarits — le message d'erreur
  est lu dans la query string et rendu tel quel. **Mesuré :**
  `/compte?erreur=Votre+compte+est+suspendu+appelez+le+0800` s'affiche
  intégralement dans la page, bandeau d'erreur compris. Jinja échappe le HTML,
  donc pas d'injection de balise — mais un lien envoyé à un utilisateur lui
  affiche un message arbitraire dans une page authentique du site, ce qui est le
  support classique d'un hameçonnage.
  **Correction attendue :** faire voyager un **code** (`?erreur=code_actuel_faux`)
  et laisser le gabarit choisir le texte.
- **Points conformes :** CSRF présent sur les six routes d'écriture, vérifié avant
  tout effet de bord ; schéma d'URL validé à l'entrée (`file://`, `javascript:`,
  `data:` refusés, testé) ; le contrôle d'accès est côté serveur et testé par
  accès direct ; aucune concaténation SQL ; échappement Jinja actif ; le hash des
  codes n'est jamais rendu ; la promotion pose un code aléatoire
  (`secrets.token_urlsafe`).

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F17-07.
- **Points conformes :** les cinq invariants d'US-01 à US-03 sont tenus et testés,
  et trois d'entre eux vivent dans le schéma.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_PASS. Les huit user stories des phases 1 et 2 sont
  implémentées et couvertes. Réserve : US-05 promet « tout caractère
  saisissable » — vrai pour les accents (F15-02 traité), faux au-delà de 72 octets
  (F17-02).

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS avec réserves. `README`, `.env.example`, plan V3 et
  état d'avancement sont à jour, migrations comprises. **[Low]** `comptes-3-roles.md`
  reste désynchronisé sur `/login` (F15-08, ouvert depuis deux audits) et ne
  mentionne pas le changement de code par son titulaire.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS. `label`/`id` appariés partout, `role="alert"` sur les
  erreurs et `role="status"` sur les succès, label masqué mais présent sur le
  champ de motif, `autocomplete` correct sur les champs de code, navigation dans
  un `<nav aria-label>`.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** taille de `app.py`.
- **Points conformes :** revue ponytail passée sur le diff, deux findings
  appliqués (littéraux d'URL encodés à la main, pagination inatteignable) et un
  refus argumenté.

### Fail-Loud Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F17-01 — une saisie hostile produit une
  trace 500 au lieu d'un refus explicite.
- **Points conformes :** `_enregistrer_compte` journalise et laisse passer la
  connexion plutôt que de la faire échouer sur un problème qui n'est pas celui de
  l'utilisateur.

### Test Quality Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F17-06.
- **Points conformes :** 33 tests, dont 11 vérifient un **refus** ; paramétrage
  sur les schémas d'URL et les codes invalides ; les trois tests qui encodaient
  l'ancien contrat ont été mis à jour, pas contournés.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_FAIL. Mutations bien tuées : retirer `exige_csrf` d'une
  route, inverser la comparaison de `ROLES_ORDRE`, supprimer la condition
  `statut == "en_attente"` du `_decider`, accepter un motif vide. **Mutation qui
  survivrait :** remplacer le jeton CSRF par une constante commune à tous les
  comptes — `test_csrf_le_jeton_d_un_autre_compte_ne_vaut_rien` tomberait, mais
  aucun test ne distingue « jeton lié à la session » de « jeton lié au pseudo »
  (F17-04).

### Layer Enforcer
- **Verdict :** AUDIT_PASS. Aucun import de bloc métier ajouté ; le frontend
  importe désormais `fakenews.normalisation`, module d'infrastructure. L'import
  historique de `contextualiseur.avertissement` (F6, phase 14) reste ouvert.

### YAGNI Auditor
- **Verdict :** AUDIT_PASS. Helpers tous utilisés ; `_invalider_compte` conservé
  avec sa justification explicite.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS avec réserves. **[Low]** `/file` charge **toutes** les
  propositions en attente sans pagination — acceptable au volume visé, à revoir
  si la file grossit. Le plafond de propositions est compté en base, donc
  insensible au nombre d'instances : bon choix.

### Architecture Consistency Auditor
- **Verdict :** AUDIT_PASS. La frontière « intentions humaines vs verdict » est
  respectée et, pour la première fois, gardée par un test.

### Contextual Threat Analyst
- **Verdict :** AUDIT_FAIL. **Scénarios :** (1) forge du jeton CSRF d'un
  contributeur par un utilisateur légitime, pour lui faire accepter une
  proposition (F17-04) ; (2) hameçonnage par message reflété (F17-05) ;
  (3) récupération d'un code provisoire dans les journaux ou l'historique
  (F17-03).
- **Points conformes :** le spectateur ne peut ni décider, ni promouvoir, ni
  découvrir que la file existe.

### SAST Scanner
- **Verdict :** AUDIT_FAIL. **Findings :** F17-01 (déni de service applicatif sur
  entrée hostile), F17-02, F17-05.
- **Points conformes :** requêtes paramétrées, échappement actif, validation de
  schéma d'URL à l'entrée.

### Supply Chain & Artifact Auditor
- **Verdict :** AUDIT_PASS. Aucune dépendance ajoutée ; migrations idempotentes
  (`if not exists`, `drop constraint if exists`) et testées à l'application.

### Privacy/Exfiltration Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F17-03 — un secret à usage unique dans
  trois journaux durables.
- **Points conformes :** aucun mot de passe journalisé ; les journaux d'action
  nomment le pseudo et l'identifiant de proposition, jamais un secret.

---

## Points Conformes (Synthèse)

- Les huit user stories des phases 1 et 2 sont implémentées, testées, et leurs
  invariants dupliqués dans le schéma là où ils comptent.
- **368 tests, 0 skip** contre un vrai Postgres avec les cinq migrations.
- Le contrat « le frontend n'écrit jamais le verdict » est enfin gardé par un
  test — il ne l'était par aucun depuis l'origine (F12, phase 14).
- Le contrôle d'accès est côté serveur et vérifié par accès direct aux URL.
- F15-02 (normalisation NFC) traité comme le plan l'exigeait avant d'ouvrir
  l'écran de changement de code.
- `canonicaliser_url` déplacé plutôt que dupliqué : la déduplication ne peut pas
  diverger entre le frontend et le pipeline.

---

## Limites De Vérification

- **F17-04 non exploité de bout en bout** : la forgeabilité du jeton est établie
  par lecture du code (clé = secret partagé, message = pseudo seul), pas par une
  attaque jouée depuis un site tiers.
- **Comportement sur Vercel non observé** : la présence du code provisoire dans
  les journaux d'accès (F17-03) est déduite du fait qu'il voyage en query string,
  non constatée sur la plateforme.
- **Aucun test de charge** sur `/file` sans pagination.
- **Phase 3 non auditée** : le collecteur n'existe pas, donc rien ne va encore
  chercher les URL proposées. C'est la surface la plus sensible de la V3 et elle
  reste à écrire.
- Aucun appel réseau réel ; aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **368 passed, 0 skipped** |
| Sonde CSRF : jetons `'mauvais-jeton-ascii'` / `'café'` / `'jetön'` | 403 / **500** / **500** |
| Sonde bcrypt : deux codes différant après 72 octets | **le même hash les accepte** (`True`) |
| Lecture du site de redirection de `promouvoir` | `code_provisoire=` en query string |
| Sonde message reflété : `/compte?erreur=<texte arbitraire>` | **rendu intégralement** dans la page |
| Parcours V3 complet (9 étapes, connexion → décision → changement de code) | conforme |


---

## Suivi Des Correctifs — 2026-09-12

**Les neuf findings sont traités.** Chacun est gardé par au moins un test, et
chaque test a été vérifié par mutation (réintroduction du défaut, puis
restauration). Suite complète : **379 tests, 0 skip**.

### F17-01 — comparaison de secrets non-ASCII · ✅ traité comme une RÈGLE

Le correctif n'est pas un troisième patch de site. Un point de passage unique,
`_secrets_egaux(attendu, recu)`, encode les deux côtés ; les trois sites de
comparaison y passent (mot de passe partagé, signature du cookie, jeton CSRF).
Un test vérifie qu'il ne reste **qu'un seul** appel direct à
`hmac.compare_digest` dans le module — c'est lui qui empêchera le quatrième
oubli, là où les correctifs des phases 14 et 0 ne traitaient que la ligne du
jour. Vérifié : `csrf='café'` renvoie 403 au lieu de 500, quatre jeux de
caractères testés dont des idéogrammes.

### F17-02 — troncature bcrypt · ✅ corrigé

`CODE_LONGUEUR_MAX = 200` (caractères) devient `CODE_LONGUEUR_MAX_OCTETS = 72`,
la limite réelle de bcrypt, mesurée **en octets** : un « é » en compte deux, donc
borner en caractères aurait laissé passer des codes tronqués malgré tout. Deux
tests : 73 caractères ASCII refusés, 40 caractères accentués (80 octets) refusés.
Le message d'erreur explique la raison plutôt que d'énoncer un nombre.

### F17-03 — code provisoire dans l'URL · ✅ corrigé

Il voyage désormais dans un cookie éphémère (`max_age` 120 s, `HttpOnly`,
`Secure`), lu par la page qui l'affiche puis **effacé**. Le test vérifie les deux
moitiés : l'URL de redirection ne contient plus le code, et un second
rafraîchissement ne le montre plus.

### F17-04 — jeton CSRF forgeable par tout utilisateur · ✅ corrigé

Le jeton dérive maintenant de `_cle_signature`, la clé qui signe déjà le cookie,
et porte l'expiration de la session. Conséquences : incalculable sans le
`secret_hash` pour un compte à code personnel, différent à chaque session, et
invalidé par un changement de code. Le jeton est porté par le contexte commun
(`_contexte`), donc aucune route future ne peut l'oublier.
**Résidu assumé, marqué `ponytail:` dans le code :** pour un spectateur sans code
personnel, la clé reste le mot de passe partagé et seule l'expiration distingue
les sessions — devinable par qui connaît la seconde de connexion. Le remède est
le même que pour le bruteforce : des codes personnels pour tous.

### F17-05 — message arbitraire reflété · ✅ corrigé

Seuls des **codes** voyagent dans la query string ; `_message` les traduit et
ignore tout code inconnu. Un lien forgé n'affiche donc plus rien.

### F17-07 — re-promotion destructrice · ✅ corrigé · F17-06, F17-08 · ✅ atténués

Promouvoir un compte déjà contributeur est refusé avec un message qui dit
pourquoi. Le test de source interdit en plus `insert(`, `delete(` et les `update`
sur les trois tables du verdict — il garde une propriété un peu moins étroite,
sans devenir pour autant une preuve. `models.Proposition` reflète les deux
contraintes de la migration `0005` ; l'index unique partiel reste déclaré dans la
seule migration, comme `uq_comptes_pseudo_lower`.

### F15-08 — doc de référence de l'authentification · ✅ soldé

Ouvert depuis trois audits. `doc/V1/comptes-3-roles.md` décrit désormais le
délai, sa borne de concurrence et son contournement connu (F16-01), la validation
de forme de la signature, la normalisation NFC, les bornes de code, la nouvelle
contrainte `ck_comptes_role_privilegie_a_un_code`, le fait que le frontend écrit
la table, et un tableau des capacités par rôle. La docstring de `models.Compte`
disait encore « jamais écrite par lui » : corrigée.

### Trouvé pendant le correctif — fuite de connexions dans les tests

La suite a refusé de tourner (« sorry, too many clients already ») : la fixture
`db_session` créait un moteur SQLAlchemy par test et ne le libérait jamais, donc
autant de pools laissés ouverts. Un test était sauté au hasard, avec un message
qui accusait la base. `engine.dispose()` ajouté. Ce n'était pas dans le périmètre
de l'audit — la suite ne l'avait jamais atteint avant de dépasser ~370 tests.

### Ce qui reste ouvert

| ID | Sév. | Sujet |
| --- | --- | --- |
| F16-01 | High | Le délai anti-bruteforce est désactivable par saturation — exploitation théorique tant que `FRONTEND_PASSWORD` est long et aléatoire. |
| F3 (ph. 14) | High | Famine du reliquat de l'évaluateur — **à corriger avant la phase 3**. |
| F15-03 | Medium | Scores corrompus par F1, non réparables par le backfill existant. |
| F6 (ph. 14) | Medium | Import inter-blocs `frontend → contextualiseur.avertissement`. |
| F15-04 / F16-04 | Low | Réglages de `/login` non externalisés. |
| — | Low | `app.py` dépasse 1200 lignes ; découpage en routeurs dû avant la phase 4. |
