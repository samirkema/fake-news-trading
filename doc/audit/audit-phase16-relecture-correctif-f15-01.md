# Audit phase 16 — Relecture du correctif F15-01 et état de la phase 0

Date : 2026-09-10 · Scope : le correctif de F15-01 (borne sur les dormeurs
simultanés, `frontend/app.py`), ses deux tests, et l'état d'ensemble de la
phase 0 du plan V3.
Base d'exigences : `doc/audit/audit-phase15-relecture-correctifs-phase0.md`,
`doc/audit/audit-phase14-codebase-complete.md`,
`doc/V3/plan_implementation_crowdsourcing.md` (phase 0),
`doc/V1/comptes-3-roles.md`, `doc/V0/userstories_frontend.md` US-04.
État audité : arbre de travail non commité.

Troisième relecture consécutive sur le même endroit du code. Ce n'est pas de
l'acharnement : c'est la troisième fois qu'un remède posé sur `/login` produit le
finding suivant, et cette fois le motif est assez net pour être nommé.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Rien de neuf côté métier ; F15-03 reste ouvert — les scores corrompus par F1 attendent toujours un outil capable de les viser. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Le sémaphore est global et rien ne le remet à zéro entre les tests ; la propriété « le site reste joignable » n'est prouvée que par une sonde manuelle. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Troisième constante de réglage en dur dans un projet qui externalise tout — et c'est celle qu'on voudra ajuster en premier. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant | **Le ralentissement est désactivable à la demande par l'attaquant** : quatre requêtes concurrentes suffisent à saturer les places d'attente, après quoi ses essais repartent à pleine vitesse. Mesuré : 20,09 s → 0,01 s. |

**Verdict global : AUDIT_FAIL.** 1 High neuf, 4 Low neufs, plus l'héritage encore
ouvert des phases 14 et 15 (1 High, 2 Medium significatifs).

Le correctif F15-01 fait ce qu'on lui demandait — le site reste joignable, mesuré
et testé — mais il l'obtient en ouvrant une soupape que l'attaquant peut actionner
lui-même. **335 tests, 0 skip.**

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | inchangé par le correctif | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | phase 0 vs plan V3 | 0 | 0 | 0 | 0 | AUDIT_PASS (réserves) |
| Doc-Sync Auditor | `comptes-3-roles.md`, rapports d'audit | 0 | 0 | 0 | 1 | AUDIT_FAIL |
| A11y/UX Checker | aucune surface d'interface touchée | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `_ralentir_apres_echec`, constantes | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Fail-Loud Auditor | repli silencieux du sémaphore | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Test Quality Auditor | 2 tests neufs, hygiène du sémaphore | 0 | 0 | 0 | 2 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | borne et contre-épreuve | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | `LOGIN_DELAI_MAX`, `LOGIN_DORMEURS_MAX` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | occupation résiduelle du pool | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Architecture Consistency Auditor | configuration externalisée | 0 | 0 | 0 | 1 | AUDIT_FAIL |
| Contextual Threat Analyst | scénarios sur `/login` | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| SAST Scanner | contrôle contournable | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Supply Chain & Artifact Auditor | `threading` (stdlib), rien d'autre | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte dédupliqué des findings **neufs** : **5** (F16-01 apparaît sous deux
angles).

---

## Matrice De Couverture

| Ce que le correctif F15-01 devait obtenir | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| Le site reste joignable sous attaque | `frontend/app.py:301` | `GET /login` : 4,006 s → **0,005 s** sous 40 essais concurrents | ✅ |
| Le bruteforce séquentiel reste coûteux | `frontend/app.py:305` | 8 essais : **18,1 s** ; 4 essais : **20,09 s** | ✅ |
| Un mot de passe correct n'est jamais ralenti | `frontend/app.py:511` | **0,016 s**, compteur plein | ✅ |
| La borne ne désactive pas la protection | `tests/test_correctifs_audit.py` (phase 15) | contre-épreuve présente, mutation tuée | ✅ |
| **La protection n'est pas désactivable par l'attaqué…ant** | `frontend/app.py:301` | 4 requêtes concurrentes ⇒ **0,01 s** au lieu de 20,09 s | ❌ **F16-01** |
| Le réglage est ajustable sans redéploiement | `frontend/app.py:299` | constante de module | ❌ F16-04 |
| La propriété est gardée par un test | `tests/` | vérifiée par sonde manuelle uniquement | ❌ F16-05 |

---

## Top Findings

- **[High] F16-01 · `src/fakenews/frontend/app.py:301`** — le repli « places
  saturées, on répond sans attendre » est **déclenchable par celui-là même qu'il
  ralentit**. Un attaquant maintient `LOGIN_DORMEURS_MAX` (4) requêtes de
  connexion ratées en parallèle — coût nul, aucun identifiant requis — et toutes
  ses autres tentatives passent sans le moindre délai.
  **Mesuré :** quatre essais séquentiels coûtent **20,09 s** places libres, et
  **0,01 s** places saturées par l'attaquant lui-même. Le ralentissement de F4
  redevient exactement ce que l'audit phase 14 lui reprochait : un contrôle
  présent à l'écran, absent dans les faits — à ceci près qu'il est maintenant
  muni d'un interrupteur, et que l'interrupteur est du côté de l'attaquant.
  **Type : Confirmé (mesuré).**
  **Correction attendue :** cesser de payer la friction avec une ressource
  partagée saturable. La marche suivante était déjà écrite dans le `ponytail:` de
  la fonction : **hacher lentement le mot de passe partagé** (bcrypt, comme les
  codes personnels le font déjà via `crypt()`). Un coût en CPU par tentative ne
  se sature pas — il n'y a pas de file d'attente à occuper — il n'immobilise ni
  fil ni connexion pendant qu'il s'exécute, et il ne refuse personne. Il déplace
  la dépense d'un mot de passe partagé en clair dans l'environnement vers un hash
  en base ou en variable, ce qui touche `.env.example`, le README et
  `comptes-3-roles.md` : c'est un changement de phase 1, pas une retouche.
  **Interim honnête :** contre un attaquant séquentiel non averti — le cas
  réaliste sur ce prototype — le délai fonctionne toujours.

---

## Contexte D'Exploitation (précisé après l'audit, 2026-09-11)

Le porteur du projet confirme que `FRONTEND_PASSWORD` est **long et aléatoire**.

Conséquence sur F16-01 : le défaut de mécanisme reste **Confirmé** — la friction
est bien désactivable à volonté par l'attaquant — mais son **exploitation devient
théorique**. Sans limitation de débit, un attaquant reste borné par le réseau et
l'hébergeur (quelques milliers d'essais par seconde au mieux) ; face à un secret
de forte entropie, la recherche exhaustive est hors de portée de plusieurs ordres
de grandeur. La priorité de F16-01 passe donc derrière F3 (phase 14) et F15-02.

**Ce que cela déplace, et qui n'est couvert par rien :** la sécurité de l'accès
repose désormais sur une **propriété opérationnelle que le code ne vérifie pas**.
Aucune contrainte, aucun contrôle au démarrage ne garantit la qualité du mot de
passe partagé — remplacer la variable par une valeur commode dégraderait la seule
protection réelle du site, en silence. C'est le motif exact que le projet a déjà
refermé deux fois : le superadmin semé sans code personnel (phase 6, H3) et la
variable d'environnement absente qui ouvrait l'accès (H4). Un contrôle de
longueur minimale au démarrage, dans le style fail-loud de `fakenews.config`,
fermerait le troisième — **non implémenté, non demandé à ce stade**.

---

## Thèmes Transverses

1. **Trois remèdes, trois déplacements du coût.** Le plafond d'origine ne coûtait
   rien à l'attaquant (F4). Le délai coûtait au serveur ses fils et ses connexions
   (F15-01). La borne rend la friction facultative, et c'est l'attaquant qui
   choisit (F16-01). À chaque tour, la question « qui paie » a reçu une nouvelle
   mauvaise réponse. **La bonne famille de réponses est celle où le coût est
   intrinsèque à la vérification** — du CPU consommé par le calcul lui-même — et
   non un délai adossé à une ressource que quelqu'un peut occuper.
2. **Un repli silencieux est une décision, pas un détail.** `return` sans attendre
   quand le sémaphore est plein est du fail-open : correct pour la disponibilité,
   et c'est précisément ce que l'attaquant provoque. Tout repli devrait être
   journalisé — celui-ci ne l'est pas, donc rien dans les logs ne dira jamais que
   la protection a été neutralisée.
3. **Le reste de la phase 0 n'a pas bougé.** Deux relectures consécutives ont été
   absorbées par un seul mécanisme, pendant que F3 (famine du reliquat, High,
   phase 14) et F15-02 (normalisation Unicode, bloquant pour US-05) attendent.

---

## Détails Par Division

### Division Métier (Anton Ego)

Rien de neuf à me mettre sous la dent : ce correctif ne touche aucune règle
métier. Je note simplement que les assiettes de la phase 14 sont toujours sur les
tables — les scores corrompus par F1 n'ont ni été réparés, ni rendus réparables
(F15-03, ouvert).

### Division Qualité (Gordon Ramsay)

Le sémaphore est global, et rien dans les fixtures ne le remet à zéro. Aujourd'hui
un seul test y touche et il rend ses places dans un `finally`. Le jour où un test
oubliera, vous chercherez pendant deux heures pourquoi la suite ralentit d'un
quart.

- **[Low] F16-03** `tests/test_correctifs_audit.py` — `_dormeurs` n'est réinitialisé
  par aucune fixture, contrairement à `_tentatives_login` et `_cache_comptes` qui
  ont chacun la leur (`_reinitialiser_le_compteur_de_tentatives`,
  `_environnement_neutre`). Un `release()` manquant retirerait silencieusement une
  place à toute la suite, sans faire échouer le test fautif. **Correction
  attendue :** une fixture `autouse` qui recrée le sémaphore, sur le modèle des
  deux autres.
- **[Low] F16-05** — la propriété centrale du correctif (« le site reste
  joignable ») est prouvée par une sonde exécutée à la main, jamais par la suite.
  Les deux tests neufs vérifient le comportement de `_ralentir_apres_echec` en
  isolation, pas l'effet sur une autre route. **Correction attendue :** un test
  à quelques fils qui mesure la latence de `GET /login` pendant que les places
  sont prises — coûteux mais borné, ou à défaut assumer explicitement que cette
  propriété n'est pas gardée.
- **Points conformes :** les deux tests neufs tuent leur mutation (borne retirée,
  places supprimées) ; la contre-épreuve empêche la protection de disparaître en
  douce ; 335 tests, 0 skip contre un vrai Postgres migré.

### Division Architecture (Steve Jobs)

Trois constantes de réglage en dur dans un fichier, pour un projet qui a écrit
trois paragraphes sur l'externalisation d'un seuil. Celle-ci est la plus mal
placée des trois : c'est le premier bouton qu'on voudra tourner en production.

- **[Low] F16-04** `src/fakenews/frontend/app.py:299` — `LOGIN_DORMEURS_MAX`
  rejoint `LOGIN_DELAI_PAR_ECHEC` et `LOGIN_DELAI_MAX` hors de `fakenews.config`.
  F15-04 signalait déjà le problème ; le correctif l'a aggravé d'un cran.
  `entier_depuis_env` existe, avec son diagnostic et ses bornes.
- **Points conformes :** aucune dépendance ajoutée (`threading` est stdlib) ;
  `LOGIN_DELAI_MAX` porte désormais la mention d'inertie que réclamait F15-05 ;
  le choix de rester en route synchrone est justifié dans le code — passer la
  route en `async` aurait libéré le fil mais bloqué la boucle d'événements sur les
  appels SQLAlchemy synchrones, soit pire que le défaut soigné.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : vous avez mis un tourniquet, constaté qu'il bloquait le
hall, puis décidé qu'il s'effacerait dès que quatre personnes y patientent. Il ne
restait plus à l'attaquant qu'à y poster quatre complices.

- **[High] F16-01** — cf. Top Findings. **Scénario complet :** quatre connexions
  persistantes envoyant des `POST /login` erronés en boucle occupent les places
  d'attente en permanence ; sur une cinquième connexion, l'attaquant déroule son
  dictionnaire à pleine vitesse. Il n'a besoin ni de pseudo valide, ni de compte,
  ni de contourner quoi que ce soit — il utilise le mécanisme de protection
  exactement comme il est écrit. **Type : Confirmé (mesuré, 20,09 s → 0,01 s).**
- **[Low] F16-02** `src/fakenews/frontend/app.py:301` — coût résiduel : les quatre
  places occupées en permanence retiennent quatre des quinze connexions du pool
  SQLAlchemy (défauts constatés à l'exécution : `QueuePool`, size 5,
  max_overflow 10). Le site reste joignable — mesuré à 0,005 s — mais 27 % du pool
  est immobilisable gratuitement et indéfiniment. Impact réel sur Vercel
  **[RISQUE]** : chaque instance ayant son propre pool et son propre sémaphore, le
  rapport 4/15 se conserve par instance, ce qui est cohérent, mais n'a pas été
  mesuré en conditions réelles.
- **[Low]** repli non journalisé (cf. thème transverse 2) — aucune trace ne
  signalera que le ralentissement a cessé de s'appliquer. Sur un mécanisme de
  sécurité, l'absence d'observabilité du mode dégradé est en soi une lacune.
- **Points conformes :** le déni de service de F15-01 est bien fermé, mesuré sur
  la sonde d'origine ; la propriété N1 (un mot de passe correct n'est jamais
  refusé ni ralenti) tient toujours ; aucune nouvelle surface d'attaque.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS. Aucune règle métier touchée. F15-03 reste ouvert.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_PASS avec réserves. Le correctif tient l'exigence qu'il
  visait (disponibilité) ; mais US-04 frontend fait de l'authentification une
  « condition bloquante », et F16-01 rend sa seule friction optionnelle au gré de
  l'attaquant. La phase 0 ne peut pas être déclarée close.

### Doc-Sync Auditor
- **Verdict :** AUDIT_FAIL. **[Low] F15-08, toujours ouvert et aggravé** —
  `doc/V1/comptes-3-roles.md` décrit le plafond de `/login` (« ralentisseur, pas
  barrière », deux propriétés à ne pas casser) sans mentionner ni le délai ni la
  borne de concurrence. C'est le document de référence de l'authentification, et
  il décrit désormais un mécanisme vieux de deux correctifs.
- **Points conformes :** les rapports de phase 14 et 15 portent leur suivi daté et
  mesuré ; le plan V3 distingue ce qui est clos de ce qui reste ouvert.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS. Aucune surface d'interface touchée par ce correctif.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS. `_ralentir_apres_echec` reste courte, le sémaphore est
  acquis en non-bloquant et rendu dans un `finally`. Commentaire raccourci de sept
  lignes à la suite de la revue ponytail, sans perte de la mesure qui justifie la
  valeur 4.

### Fail-Loud Auditor
- **Verdict :** AUDIT_PASS avec réserves. Le repli du sémaphore est silencieux :
  aucun journal ne distingue « ralenti » de « pas ralenti faute de place ».

### Test Quality Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F16-03, F16-05.
- **Points conformes :** contre-épreuve présente et efficace ; assertions portant
  sur la propriété, pas sur l'implémentation.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_PASS. Deux mutations réintroduites et tuées : borne retirée
  (le test F15-01 tombe), places supprimées (la contre-épreuve tombe). En
  revanche, **aucune mutation ne modélise F16-01** : le défaut n'est pas dans le
  code, il est dans la stratégie — un test ne peut le tuer qu'en mesurant le débit
  d'essais sous saturation.

### Layer Enforcer
- **Verdict :** AUDIT_PASS. Périmètre inchangé ; l'import inter-blocs F6 (phase 14)
  reste ouvert.

### YAGNI Auditor
- **Verdict :** AUDIT_PASS. Aucune abstraction spéculative ; `LOGIN_DELAI_MAX`
  conservé avec sa mention d'inertie, ce qui est le bon compromis entre suppression
  et garde-fou de couplage.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F16-02.
- **Points conformes :** la borne 4/15 laisse toujours onze connexions au trafic
  légitime ; latence au repos inchangée (4 ms).

### Architecture Consistency Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F16-04 — troisième réglage non
  externalisé, contraire à la règle que le projet s'est donnée.

### Contextual Threat Analyst
- **Verdict :** AUDIT_FAIL. **Findings :** F16-01.
- **Points conformes :** le scénario de verrouillage (N1) reste impossible ; celui
  d'épuisement de ressources (F15-01) est fermé.

### SAST Scanner
- **Verdict :** AUDIT_FAIL. **Findings :** F16-01, sous l'angle « contrôle de
  sécurité contournable par une condition que l'attaquant maîtrise ».
- **Points conformes :** validation de la signature du cookie en place ;
  comparaison à temps constant ; aucune injection.

### Supply Chain & Artifact Auditor
- **Verdict :** AUDIT_PASS. `threading` est stdlib ; `api/requirements.txt`
  inchangé.

### Privacy/Exfiltration Auditor
- **Verdict :** AUDIT_PASS. Aucun secret journalisé ; le repli, faute d'être
  journalisé, n'expose rien non plus.

---

## Findings Hérités Encore Ouverts

| ID | Sév. | Sujet | Conséquence pour la suite |
| --- | --- | --- | --- |
| F3 (ph. 14) | High | Famine du reliquat de l'évaluateur | À corriger **avant la phase 3** : un article proposé et accepté passerait après les plus récents de la collecte automatique. |
| F15-02 | Medium | Normalisation Unicode des mots de passe | **Bloquant pour US-05** (espace compte). Le vrai préalable restant de la phase 0. |
| F15-03 | Medium | Scores corrompus non réparables par le backfill | Données faussées tant qu'aucun outil ne sait les viser. |
| F15-04 / F16-04 | Low | Réglages non externalisés | Aucun ajustement possible sans redéploiement. |
| F15-06 / F15-07 / F15-09 / F16-03 / F16-05 | Low | Hygiène de tests | Aucune conséquence fonctionnelle. |
| F15-08 | Low | `comptes-3-roles.md` désynchronisé | Document de référence de l'authentification, périmé de deux correctifs. |
| F6 (ph. 14) | Medium | Import inter-blocs frontend → contextualiseur | Contredit `architecture.md`. |

---

## Points Conformes (Synthèse)

- **F15-01 est bien fermé** : la sonde d'origine passe de 4,006 s à 0,005 s.
- Le bruteforce **séquentiel** — le cas réaliste sur ce prototype — reste ralenti
  d'un facteur d'environ 2800 sur 60 essais.
- La propriété imposée par la phase 7 (N1) tient à travers les trois correctifs
  successifs : un mot de passe correct n'est jamais refusé ni ralenti.
- Le refus de passer la route en `async` est correctement justifié dans le code,
  avec la raison technique exacte.
- La revue ponytail a été appliquée et son refus argumenté (`LOGIN_DELAI_MAX`).
- **335 tests, 0 skip** contre un vrai Postgres migré ; graphe de connaissance
  régénéré après modification, conformément au `CLAUDE.md` du projet.

---

## Limites De Vérification

- **Comportement sur Vercel non mesuré.** Le sémaphore et le pool étant par
  instance, le raisonnement se conserve en théorie ; le nombre d'instances tièdes
  et leur répartition n'ont pas été observés.
- **F16-01 mesuré en local, en process unique.** Le scénario réel (connexions
  distantes maintenues) n'a pas été rejoué contre un déploiement.
- **Le coût CPU d'un bcrypt sur le mot de passe partagé** — la correction
  attendue — n'a pas été mesuré : son acceptabilité sur une fonction serverless
  reste à établir avant de s'engager.
- Aucun appel réseau réel ; aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **335 passed, 0 skipped** |
| Sonde F15-01 rejouée (40 essais concurrents) | `GET /login` : **0,005 s** (4,006 s avant correctif) |
| Sonde F16-01 : 4 essais séquentiels, places libres | **20,09 s** |
| Sonde F16-01 : mêmes essais, places saturées par l'attaquant | **0,01 s** |
| Lecture des défauts du pool SQLAlchemy à l'exécution | `QueuePool`, size 5, max_overflow 10 → **15** |
| `grep` sur la réinitialisation de `_dormeurs` dans les fixtures | aucune |
