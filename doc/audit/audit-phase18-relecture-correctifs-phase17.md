# Audit phase 18 — Relecture des correctifs de la phase 17

Date : 2026-09-12 · Scope : les neuf correctifs livrés après l'audit phase 17 —
`_secrets_egaux`, borne bcrypt, cookie du code provisoire, jeton CSRF lié à la
session, codes d'erreur, refus de re-promotion, test de source renforcé,
contraintes du modèle, `doc/V1/comptes-3-roles.md` — plus la correction de fuite
de connexions dans `tests/conftest.py`.
Base d'exigences : `doc/audit/audit-phase17-crowdsourcing-phases-1-2.md`,
`doc/V3/userstories_crowdsourcing.md`, `doc/V1/comptes-3-roles.md`.
État audité : arbre de travail non commité.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟢 OK | Aucune règle métier touchée par ces correctifs, aucune régression fonctionnelle. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Un test certifie qu'une porte s'ouvre sans jamais vérifier qu'on peut franchir le seuil — c'est précisément ce qui a laissé passer le défaut ci-dessous. |
| Architecture (Steve Jobs) | 🟢 OK | Le point de passage unique pour les secrets est la bonne réponse ; il manque un demi-pas pour être complet. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant | Le correctif de normalisation n'a été appliqué qu'à **un** des deux chemins qui lisent le mot de passe partagé : avec une variable en forme NFD, la connexion réussit puis chaque page renvoie au formulaire. Boucle infinie, silencieuse. |

**Verdict global : AUDIT_FAIL.** 1 High, 1 Medium, 2 Low.

Les neuf correctifs de la phase 17 tiennent, et deux hypothèses de récidive ont
été testées puis écartées. Le seul défaut trouvé est une **régression introduite
par le correctif F15-02 lui-même**, restée invisible deux audits durant parce que
le test qui la couvrait s'arrête une requête trop tôt.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | inchangé par les correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | US-05, US-06 après correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | `comptes-3-roles.md`, `models.py` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| A11y/UX Checker | aucune surface touchée | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `_secrets_egaux`, `_message` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Fail-Loud Auditor | échec silencieux de session | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Test Quality Auditor | tests phase 14 et 17 | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Mutation/Saboteur Auditor | les 6 correctifs testables | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | helpers ajoutés | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | `conftest`, `_message` | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| Architecture Consistency Auditor | point de passage des secrets | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | récidives de la classe F2 | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| SAST Scanner | entrées hostiles sur les écritures | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | cookie du code provisoire | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte dédupliqué : **4 findings**.

---

## Matrice De Couverture

| Ce que la phase 17 devait obtenir | Preuve | Statut |
| --- | --- | --- |
| F17-01 — un jeton CSRF hostile est refusé, pas 500 | `'café'`, `'jetön'`, idéogrammes → **403** | ✅ |
| F17-01 — la règle, pas la ligne | un seul `hmac.compare_digest` dans le module, vérifié par un test | ✅ |
| **Récidive ailleurs — octets UTF-8 invalides** | `%ED%A0%80`, `%FF%FE`, `%C3%28` en `csrf` → **403** ; en mot de passe → **401** | ✅ |
| F17-02 — un code que bcrypt tronquerait est refusé | 73 caractères ASCII et 40 caractères accentués refusés | ✅ |
| F17-03 — le code provisoire quitte l'URL | redirection nue, affiché une fois, cookie consommé | ✅ |
| F17-04 — jeton lié à la session | dépend du pseudo, du code personnel et de l'expiration | ✅ |
| F17-05 — plus de message arbitraire | texte injecté absent de la page, code connu traduit | ✅ |
| F17-07 — re-promotion refusée | hash inchangé après tentative | ✅ |
| **F15-02 — un mot de passe partagé accentué reste utilisable** | connexion 303 **puis chaque page renvoie à /login** | ❌ **F18-01** |
| Fuite de connexions dans les tests | suite complète sans « too many clients » | ✅ |

---

## Top Findings

- **[High] F18-01 · `src/fakenews/frontend/app.py`, `compte_courant`** — ✅ **corrigé
  le 2026-09-13**, cf. « Suivi des correctifs ». Le
  correctif de normalisation Unicode (F15-02) a été appliqué à la **route de
  connexion** et **pas** à la garde d'accès. `connexion` normalise le mot de
  passe partagé avant de signer le cookie ; `compte_courant` relit
  `FRONTEND_PASSWORD` **brute** pour valider cette signature. Les deux clés
  diffèrent dès que la variable d'environnement n'est pas en forme NFC.
  **Mesuré**, avec `FRONTEND_PASSWORD` posée en NFD : la connexion réussit
  (**303**, cookie posé), puis `GET /` renvoie **303 vers /login**. L'utilisateur
  boucle entre le formulaire et la redirection, **sans aucun message**, avec le
  bon mot de passe entre les mains.
  C'est le mode de panne exact que F2 devait supprimer — « site entièrement
  inaccessible avec un mot de passe accentué » — réintroduit sous une forme plus
  discrète : il ne produit plus de 500 dans les journaux, il ne produit rien du
  tout.
  **Type : Confirmé (mesuré).** Sans effet tant que `FRONTEND_PASSWORD` est en
  ASCII, ce qui est le cas aujourd'hui.
  **Correction attendue :** normaliser au **point de lecture** et non au point
  d'usage — une fonction unique qui lit la variable et rend sa forme NFC, appelée
  par les deux chemins. Même remède que F17-01 : la règle, pas la ligne.
- **[Medium] F18-02 · `tests/test_correctifs_audit.py`,
  `test_audit_phase14_un_mot_de_passe_partage_accentue_reste_utilisable`** — le
  test pose un mot de passe accentué, poste `/login`, et s'arrête sur
  `status_code == 303` et la présence du cookie. Il ne suit **jamais** la
  redirection. Il certifie donc que la porte s'ouvre, sans jamais vérifier qu'on
  peut franchir le seuil — exactement l'angle mort de F18-01, resté ouvert deux
  audits durant.
  Second facteur : le littéral accentué du fichier de test est en NFC (les
  sources Python le sont), donc le cas NFD n'existait dans aucun test.
  **Correction attendue :** faire suivre chaque test de connexion d'un accès à
  une page protégée, et paramétrer le cas accentué sur les deux formes Unicode.

---

## Thèmes Transverses

1. **Un correctif de forme doit s'appliquer au point de LECTURE.** F17-01 a été
   traité correctement (un point de passage pour comparer) ; F15-02 ne l'a pas
   été (deux points de lecture, un seul normalisé). Le même raisonnement, appliqué
   une fois sur deux.
2. **Un test d'authentification qui s'arrête au 303 ne prouve rien.** Une session
   se juge à la requête suivante. Trois tests de la suite s'arrêtent au code de
   redirection.
3. **Les récidives testées n'ont pas eu lieu.** Octets UTF-8 invalides sur le
   jeton CSRF et sur le mot de passe : refusés proprement, 403 et 401. Le point de
   passage unique fait son travail sur ce qu'il couvre.

---

## Détails Par Division

### Division Métier (Anton Ego)

Rien à redire : aucun de ces correctifs n'a touché à une règle de gestion, et la
maison a eu la courtoisie de vérifier que les neuf promesses précédentes tenaient
encore.

### Division Qualité (Gordon Ramsay)

Votre test vérifie que la clé entre dans la serrure. Il ne vérifie pas que la
porte s'ouvre. Deux audits ont défilé pendant que ce test affichait du vert sur
un site qui, dans la bonne configuration, ne laisse entrer personne.

- **[Medium] F18-02** — cf. Top Findings.
- **[Low]** `app.py`, `_message` — le dictionnaire est reconstruit à chaque appel
  et relit l'environnement pour une seule entrée. Sans conséquence mesurable ;
  à noter si la table grossit.
- **Points conformes :** les six correctifs testables ont été vérifiés par
  mutation, un par un, avec restauration ; le test « un seul `compare_digest` »
  garde la règle et pas seulement son application du jour.

### Division Architecture (Steve Jobs)

Le point de passage unique est la bonne idée. Il lui manque son pendant en
lecture. On a réglé la moitié du problème et on a appelé ça une règle.

- **Points conformes :** `_secrets_egaux` centralise la comparaison ; le jeton
  CSRF réutilise `_cle_signature` au lieu d'inventer une seconde dérivation ;
  `_contexte` porte le jeton, donc aucune route future ne peut l'oublier.
- **Observation :** la symétrie manquante de F18-01 est structurelle, pas
  accidentelle — il n'existe pas de fonction « lire le mot de passe partagé »,
  seulement deux `os.environ.get` séparés par six cents lignes.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : vous avez fermé la fenêtre par laquelle le bug était
entré, et laissé la porte de service ouverte — la même pièce, le même courant
d'air, un autre battant.

- **[High] F18-01** — cf. Top Findings. **Impact :** déni de service total et
  silencieux, déclenché par une configuration légitime (coller un mot de passe
  accentué depuis un gestionnaire sur macOS). Aucun journal ne le signale : ni
  500, ni message d'erreur, ni entrée de log — seulement des 303 en boucle.
- **[Low]** `app.py`, `NOM_COOKIE_CODE` — le cookie du code provisoire porte
  `Secure`, donc il n'est pas renvoyé en `http://`. En développement local, le
  code provisoire ne s'affiche jamais. Conséquence assumée du bon réglage, à
  connaître avant de chercher un bug ailleurs.
- **Points conformes :** trois formes d'octets UTF-8 invalides refusées
  proprement sur le jeton CSRF (403) et sur le mot de passe (401) ; le cookie du
  code provisoire est `HttpOnly`, `Secure`, `SameSite=Lax`, borné à 120 s et
  consommé à la première lecture.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_PASS. Aucune règle métier modifiée ; les neuf correctifs
  sont des changements de mécanisme.

### Requirements Compliance Auditor
- **Verdict :** AUDIT_PASS. US-05 (« tout caractère saisissable ») est tenue pour
  les **codes personnels**, qui sont normalisés des deux côtés. F18-01 ne touche
  que le mot de passe **partagé**, dont US-05 ne parle pas.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS. `comptes-3-roles.md` est à jour de trois correctifs
  (F15-08 soldé) ; la docstring de `models.Compte` ne prétend plus que le
  frontend n'écrit jamais la table.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS. Aucune surface d'interface touchée.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** `_message` reconstruit.

### Fail-Loud Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F18-01 — le pire des échecs : muet.
  Aucun diagnostic n'est produit, alors que le projet fait de l'erreur nommée
  une règle (`config.py`, `db.py`, `schema.py`).

### Test Quality Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F18-02.
- **Points conformes :** 379 tests, 0 skip ; les tests de la phase 17 vérifient
  les deux moitiés de chaque propriété (le code provisoire est affiché **et**
  consommé ; un code connu est traduit **et** un code inconnu ignoré).

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_PASS. Six mutations réintroduites et toutes tuées :
  comparaison sur `str`, borne à 200 caractères, code provisoire remis dans
  l'URL, jeton indépendant de la session, message repris de la query string,
  re-promotion autorisée.

### Layer Enforcer / YAGNI / Architecture Consistency
- **Verdict :** AUDIT_PASS. Périmètre inchangé ; aucun helper mort.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS avec réserves. La fuite de moteurs SQLAlchemy dans
  `conftest` est corrigée (`engine.dispose()`), ce qui referme un défaut qui
  faisait sauter des tests au hasard en accusant la base.

### Contextual Threat Analyst
- **Verdict :** AUDIT_FAIL. **Scénario :** le porteur du projet fait tourner son
  mot de passe partagé, colle depuis un gestionnaire une valeur contenant un
  accent en forme décomposée, et perd l'accès à son propre site sans qu'aucun
  message n'explique pourquoi.

### SAST Scanner
- **Verdict :** AUDIT_PASS. Entrées hostiles testées (UTF-8 invalide, jetons
  étrangers, longueurs extrêmes) : toutes refusées par un statut approprié.

### Supply Chain & Artifact Auditor / Privacy
- **Verdict :** AUDIT_PASS. Aucune dépendance ajoutée ; plus aucun secret dans
  une URL.

---

## Points Conformes (Synthèse)

- Les **neuf findings** de la phase 17 sont effectivement corrigés, chacun vérifié
  par sonde et par mutation.
- La classe de bug F2 ne récidive pas sur les entrées hostiles testées : le point
  de passage unique tient pour ce qu'il couvre.
- **379 tests, 0 skip**, et la suite ne sature plus le serveur de connexions.
- Le jeton CSRF réutilise la clé de session existante plutôt qu'une seconde
  dérivation maison.
- `doc/V1/comptes-3-roles.md` est à jour, F15-08 soldé après trois audits.

---

## Limites De Vérification

- **F18-01 mesuré en local uniquement.** Sur Vercel, la variable
  d'environnement passe par l'interface de la plateforme ; sa forme Unicode à
  l'arrivée n'a pas été observée.
- **Aucun mot de passe non-ASCII n'est en service aujourd'hui** (confirmé par le
  porteur du projet en phase 16) : l'impact est réel mais non déclenché.
- **Les trois autres tests qui s'arrêtent à un 303** n'ont pas été audités un par
  un ; F18-02 nomme le motif, pas son inventaire complet.
- Aucun appel réseau réel ; aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **379 passed, 0 skipped** |
| Sonde NFD : `FRONTEND_PASSWORD` en forme décomposée | connexion **303**, puis `GET /` → **303 vers /login** (boucle) |
| Sonde UTF-8 invalide sur `csrf` (3 formes) | **403** à chaque fois |
| Sonde UTF-8 invalide sur `mot_de_passe` | **401** |
| Sondes F17-01 à F17-07 rejouées | conformes au suivi consigné |
| Lecture de `compte_courant` | ne normalise pas `FRONTEND_PASSWORD` |


---

## Suivi Des Correctifs — 2026-09-13

### F18-01 — deux points de lecture du mot de passe partagé · ✅ corrigé

`_mot_de_passe_partage()` lit `FRONTEND_PASSWORD` **et** rend sa forme NFC. Les
deux chemins — la route de connexion qui signe le cookie, la garde d'accès qui le
valide — passent par elle. La divergence de clés devient impossible : il n'existe
plus deux façons d'obtenir cette valeur.

Même remède que `_secrets_egaux` pour la comparaison, appliqué cette fois à la
**lecture** : c'est la moitié qui manquait, et c'est elle que le nouveau test
`test_audit_phase18_le_mot_de_passe_partage_est_lu_en_un_seul_endroit` garde —
il compte les lectures brutes et exige qu'il n'y en ait qu'une.

**Vérification, sonde de l'audit rejouée** avec `FRONTEND_PASSWORD` en NFD :
connexion **303**, puis `GET /` → **200**. La boucle est fermée.

### F18-02 — le test qui s'arrêtait au 303 · ✅ corrigé, et plus grave que décrit

Le test est désormais paramétré sur les deux formes Unicode et **suit la
connexion d'un accès à une page protégée**. Mais en le corrigeant, il est apparu
que le défaut dépassait ce seul test.

**Le cookie de session porte `Secure`.** Un client HTTP correct refuse donc de le
renvoyer en clair — et les fixtures `client` de `test_frontend.py` et
`test_correctifs_audit.py` parlaient en `http://`. Conséquence, mesurée :

| Client | `GET /` après connexion, sans suivi | avec suivi | page réellement rendue |
| --- | --- | --- | --- |
| `http://testserver` | **303** | 200 | **le formulaire de connexion** |
| `https://testserver` | **200** | 200 | la liste des articles |

Toutes les assertions de la forme `assert client.get("/").status_code == 200`
après une connexion passaient donc **sur la page de login**, sans jamais exercer
un accès authentifié. Un faux vert de la même famille que celui de la phase 6
(55 tests skippés), sur un périmètre plus étroit mais sur le chemin
d'authentification.

Les deux fixtures sont passées en `https://testserver`, comme
`test_crowdsourcing.py` le faisait déjà — sa docstring signalait le piège depuis
la phase 2, sans que personne n'aille voir si les autres fixtures l'avaient
évité.

**Mutation :** remettre la fixture en `http://` fait tomber le test accentué.
Remettre la lecture brute de la variable fait tomber les deux tests de F18-01.

### Résultat

**382 tests, 0 skip** (379 avant). Aucun test n'a été perdu au passage en `https`,
ce qui signifie qu'aucun ne dépendait du faux vert pour passer — la protection
était inutile, pas trompeuse sur le fond.

### Non traités — les deux Low

- `_message` reconstruit son dictionnaire à chaque appel : sans conséquence
  mesurable.
- Le cookie du code provisoire porte `Secure`, donc invisible en développement
  local sur `http://` : conséquence assumée du bon réglage.
