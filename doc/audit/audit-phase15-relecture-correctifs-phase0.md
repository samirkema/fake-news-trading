# Audit phase 15 — Relecture des correctifs de la phase 0

Date : 2026-09-10 · Scope : les correctifs livrés depuis l'audit phase 14 —
F1 (`evaluateur/fact_checking.py`), F2 et F4 (`frontend/app.py`), leurs tests
(`tests/test_correctifs_audit.py`, `tests/test_fact_checking.py`,
`tests/test_backfill_fact_checking.py`, `tests/conftest.py`).
Base d'exigences : `doc/audit/audit-phase14-codebase-complete.md`,
`doc/V3/plan_implementation_crowdsourcing.md` (phase 0),
`doc/V1/comptes-3-roles.md`, `doc/V0/userstories_frontend.md` US-04.
État audité : arbre de travail non commité.

Nature de cet audit : **relecture de correctifs**, comme les phases 7, 11 et 13.
On ne réaudite pas la codebase — on vérifie que ce qui vient d'être posé tient, et
surtout ce que le correctif a **déplacé** plutôt que supprimé.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Le correctif F1 protège l'avenir et laisse le passé en l'état : les scores déjà corrompus ne sont pas réparables par l'outil de rattrapage existant, dont le filtre saute précisément les lignes à réparer. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Trois tests neufs tuent leur mutation, mais l'un s'appuie sur une assertion temporelle, un autre porte un accent dans son nom, et la fixture qui neutralise le délai couvre toute la suite. |
| Architecture (Steve Jobs) | 🟡 Avertissement | Deux constantes de module là où le projet externalise tout dans `fakenews.config` — dont une inerte, et l'autre impossible à couper en urgence alors que F15-01 rend cette possibilité nécessaire. |
| Cybersécurité offensive (Sherlock Holmes) | 🔴 Bloquant | Le correctif F4 a échangé un déni de service contre un autre : 40 connexions ratées simultanées suffisent à rendre le site injoignable — mesuré, une page publique passe de 4 ms à 4,0 s. |

**Verdict global : AUDIT_FAIL.** 1 High, 3 Medium, 5 Low. Aucun Critique.

Les trois correctifs atteignent leur cible : mesures rejouées, mutations tuées,
**333 tests, 0 skip**. Le défaut bloquant n'est pas un correctif raté — c'est un
effet de bord du remède, et il était prévisible : on a ajouté une attente dans un
processus qui n'a pas de fil à perdre.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | F1, données déjà écrites | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Requirements Compliance Auditor | phase 0 vs plan V3 | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Doc-Sync Auditor | `comptes-3-roles.md`, rapport phase 14 | 0 | 0 | 0 | 2 | AUDIT_PASS (réserves) |
| A11y/UX Checker | message de la page 429 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | `app.py`, `fact_checking.py` | 0 | 0 | 0 | 1 | AUDIT_PASS |
| Fail-Loud Auditor | chemins d'erreur touchés | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Test Quality Auditor | 8 tests neufs + fixture | 0 | 0 | 0 | 3 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | les 3 correctifs | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Layer Enforcer | inchangé par la phase 0 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | constantes du délai | 0 | 0 | 0 | 1 | AUDIT_PASS (réserves) |
| SRE/Performance Auditor | `_ralentir_apres_echec` | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| Architecture Consistency Auditor | configuration externalisée | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Contextual Threat Analyst | scénarios sur `/login` | 0 | 1 | 0 | 0 | AUDIT_FAIL |
| SAST Scanner | comparaisons, validation d'entrée | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Supply Chain & Artifact Auditor | inchangé par la phase 0 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | inchangé par la phase 0 | 0 | 0 | 0 | 0 | AUDIT_PASS |

Décompte global dédupliqué : **9 findings** (un même défaut apparaît sous
plusieurs angles).

---

## Matrice De Couverture

| Ce que la phase 0 devait obtenir | Fichier(s) | Preuve | Statut |
| --- | --- | --- | --- |
| F1 — un verdict non rattachable n'est jamais utilisé | `evaluateur/fact_checking.py:162` | sonde : `None` sur claim sans `text` (90.0 avant) | ✅ |
| F1 — une claim rattachable reste exploitée | `tests/test_correctifs_audit.py` (phase 14) | contre-épreuve présente | ✅ |
| F1 — les scores déjà calculés sont réparables | `evaluateur/backfill_fact_checking.py:27` | le filtre saute les lignes corrompues | ❌ F15-03 |
| F2 — un mot de passe accentué est refusé, pas 500 | `frontend/app.py:487` | sonde : 401 (500 avant) | ✅ |
| F2 — un `FRONTEND_PASSWORD` accentué reste utilisable | `frontend/app.py:487` | sonde : 303 | ✅ |
| F2 — un cookie non-ASCII ne casse pas les pages | `frontend/app.py:198` | 5 formes invalides redirigées | ✅ |
| F2 — le même mot de passe fonctionne quel que soit le clavier | `frontend/app.py:487` | NFC accepté, NFD refusé (mesuré) | ❌ F15-02 |
| F4 — une tentative ratée coûte du temps | `frontend/app.py:284` | 60 essais : 0,10 s → 278 s | ✅ |
| F4 — un mot de passe correct n'est jamais ralenti | `frontend/app.py:493` | 303 instantané, compteur plein | ✅ |
| F4 — le remède n'enferme personne | `frontend/app.py:284` | 40 essais concurrents ⇒ site à 4,0 s | ❌ F15-01 |
| Phase 0 débloque la phase 1 | `doc/V3/plan_implementation_crowdsourcing.md` | F15-02 rouvre le préalable d'US-05 | ⚠️ F15-04 |

---

## Top Findings

- **[High] F15-01 · `src/fakenews/frontend/app.py:284`** — ✅ **corrigé le
  2026-09-10**, cf. « Suivi des correctifs » en fin de document. `time.sleep` dans une
  route synchrone : le délai **immobilise un fil du pool et une connexion
  Postgres** pendant toute sa durée. Toutes les routes de l'application sont
  `def`, donc toutes partagent le même limiteur anyio (40 jetons, valeur lue à
  l'exécution) ; et la session ouverte par `Depends(get_session)` a déjà consommé
  une connexion du pool SQLAlchemy (défauts : 5 + 10 de débordement) avant
  l'attente. **Mesuré :** 40 connexions ratées simultanées, compteur plein, font
  passer un simple `GET /login` de **4 ms à 4,006 s**. Le correctif F4 a donc
  supprimé un déni de service par verrouillage et en a introduit un par épuisement
  de ressources — celui-là ne demande même pas de connaître un pseudo.
  **Correction attendue :** borner le nombre de dormeurs simultanés bien en
  dessous du pool (un sémaphore non bloquant à 4-8 places ; au-delà, on répond
  sans attendre — l'attaquant ne gagne rien de plus qu'avant le correctif, et le
  trafic légitime continue de passer). Corollaire : `LOGIN_DELAI_MAX` doit
  redescendre à une valeur qui ait un sens avec cette borne.
- **[Medium] F15-02 · `src/fakenews/frontend/app.py:487`** — aucune normalisation
  Unicode avant comparaison. **Mesuré :** `"sécrété"` en NFC ouvre la session
  (303), le **même mot de passe visuellement**, saisi en NFD — la forme que macOS
  produit couramment — est refusé (401). Le correctif F2 rend donc les accents
  utilisables *seulement dans la forme où ils ont été posés*. Sans conséquence
  tant qu'un seul opérateur pose la variable ; **bloquant pour US-05 de la V3**,
  où chacun choisira son code depuis son navigateur et pourra se retrouver enfermé
  dehors avec le bon mot de passe entre les mains. **Correction attendue :**
  `unicodedata.normalize("NFC", ...)` des deux côtés, aux deux endroits — la
  comparaison partagée **et** le chemin `crypt()` des codes personnels, qui a
  exactement le même défaut et que le correctif n'a pas touché.
- **[Medium] F15-03 · `src/fakenews/evaluateur/backfill_fact_checking.py:27`** —
  le correctif F1 empêche de nouvelles corruptions, il ne répare rien. Or l'outil
  de rattrapage existe… et ne peut pas servir : `_sans_fact_checking_valide` ne
  retient que les scores dont le signal est **exclu** (`valeur is None`), alors
  qu'un score corrompu porte précisément une valeur — 90.0. Les lignes à réparer
  sont exactement celles que le filtre saute. **Correction attendue :** un critère
  de sélection qui vise les scores dont le `preuve_id` cite une URL de
  ClaimReview, puis un nouveau passage. Combien de lignes sont concernées en base
  est **[RISQUE]** : cela dépend de la fréquence des claims sans `text` chez
  Google, non mesurée.

---

## Thèmes Transverses

1. **Un correctif de sécurité déplace le coût, il ne l'annule pas.** F4 a
   transféré la charge du verrouillage vers l'occupation de ressources. La
   question à se poser systématiquement après ce type de correctif n'est pas
   « est-ce que ça marche », mais « qui paie maintenant ».
2. **Faire fonctionner l'Unicode n'est pas le supporter.** F2 a supprimé le
   `TypeError` ; il reste la question, plus difficile, de savoir quand deux
   chaînes différentes désignent le même mot de passe.
3. **Réparer le code ne répare pas les données.** Le projet applique « pas de
   rescoring en v1 », mais s'est doté de deux scripts de backfill précisément pour
   les exceptions. F1 en est une, et l'outil ne sait pas la traiter.
4. **La phase 0 est fonctionnellement atteinte.** Les trois défauts visés sont
   morts et gardés par des tests qui tombent quand on retire le correctif. Ce
   sont les effets de bord qui ouvrent des findings, pas les cibles manquées.

---

## Détails Par Division

### Division Métier (Anton Ego)

Un cuisinier qui cesse de servir un plat avarié mérite un mot aimable. On lui en
adressera un le jour où il aura débarrassé les assiettes déjà posées sur les
tables.

- **[Medium] F15-03** — cf. Top Findings. **Type : Confirmé** (lecture du filtre)
  pour l'incapacité de l'outil ; **[RISQUE]** pour le volume réellement affecté.
- **Point conforme :** le correctif ne fabrique pas de faux négatif. La
  contre-épreuve `test_audit_phase14_une_claim_rattachable_reste_exploitee`
  vérifie qu'une claim pertinente produit toujours 90 et son `preuve_id` complet —
  sans elle, neutraliser le signal entier aurait passé la CI.

### Division Qualité (Gordon Ramsay)

Trois tests qui tuent leur mutation, très bien. Maintenant expliquez-moi pourquoi
l'un d'eux vérifie la sécurité avec un chronomètre, et pourquoi un nom de fonction
porte un accent alors que les 340 autres n'en portent aucun.

- **[Low] F15-06** `tests/test_correctifs_audit.py` —
  `test_audit_phase14_un_mot_de_passe_correct_n_est_jamais_ralenti` assied sa
  garantie sur `ecoule < 0.5`. La propriété testée est juste et importante (N1),
  mais une CI chargée peut faire échouer un test qui ne décrit aucune régression.
  **Correction attendue :** vérifier la propriété plutôt que sa conséquence
  temporelle — par exemple en observant que `_ralentir_apres_echec` n'est pas
  appelé sur un succès (espion), la mesure restant en appoint.
- **[Low] F15-07** — `test_audit_phase14_un_mot_de_passe_non_ascii_est_refuse_pas_planté` :
  seul identifiant non-ASCII du dépôt. Python l'accepte ; `grep` sur un clavier
  sans accent, moins.
- **[Low] F15-09** `tests/conftest.py` — la fixture `autouse`
  `_sans_ralentissement_login` désactive le mécanisme pour **toute** la suite.
  C'est assumé et écrit, y compris dans la fixture elle-même, et trois tests le
  rétablissent. Le résidu reste : la suppression pure et simple du mécanisme n'est
  tuée que par ces trois-là — vérifié, la mutation « retirer l'appel à
  `_ralentir_apres_echec` » fait tomber 2 tests sur 333.
- **Points conformes :** les huit tests neufs portent chacun le défaut qu'ils
  gardent en docstring, avec la mesure d'origine ; les fixtures qui empruntaient
  le chemin fautif de F1 sans le voir ont été corrigées plutôt que contournées.

### Division Architecture (Steve Jobs)

Deux constantes en dur dans un projet qui a écrit trois paragraphes pour
expliquer pourquoi un seuil devait vivre dans l'environnement. L'une ne sert à
rien. L'autre, on voudra l'éteindre à distance le jour où elle posera problème —
c'est-à-dire aujourd'hui.

- **[Medium] F15-04** `src/fakenews/frontend/app.py:114` —
  `LOGIN_DELAI_PAR_ECHEC` est une constante de module. Tout le reste du projet
  passe par `fakenews.config` et l'environnement : seuil, cinq plafonds, proxys de
  confiance, modèle LLM. Ici, changer la valeur — ou couper le mécanisme, ce que
  F15-01 peut rendre urgent — exige un commit et un redéploiement.
  **Correction attendue :** `reel_depuis_env` existe déjà, avec ses bornes et son
  diagnostic ; et `.env.example` devra suivre, sans quoi
  `test_conformite_exigences.py:171` échouera — ce qui est exactement son rôle.
- **[Low] F15-05** `src/fakenews/frontend/app.py:284` — `LOGIN_DELAI_MAX` est
  inerte : la file est bornée à `LOGIN_TENTATIVES_MAX = 10` (`deque(maxlen=…)`) et
  0,5 × 10 = 5,0, soit exactement le plafond. Le `min()` ne réduit jamais rien. Ce
  n'est pas un défaut — c'est un garde-fou de couplage entre trois constantes —
  mais il mérite le commentaire qui le dit, sinon le prochain lecteur croira que
  le plafond agit.
- **Point conforme :** aucun nouveau franchissement de frontière entre blocs ;
  `fact_checking.py` n'a gagné aucune dépendance.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : vous avez retiré la serrure qui pouvait enfermer les
gens dehors, et vous l'avez remplacée par un tourniquet dans lequel quarante
personnes suffisent à bloquer le hall.

- **[High] F15-01** — cf. Top Findings. **Scénario d'attaque :** l'attaquant n'a
  besoin ni d'un pseudo valide, ni du mot de passe, ni même de viser quelqu'un —
  quarante requêtes `POST /login` concurrentes avec n'importe quel mot de passe
  faux, entretenues, et le site ne répond plus pour personne. C'est moins cher que
  l'attaque que le correctif visait à rendre chère. **Type : Confirmé (mesuré).**
  À noter : la borne réellement atteinte en premier est probablement le pool
  SQLAlchemy (5 + 10) et non les 40 jetons du threadpool, la session étant ouverte
  avant l'attente — **[RISQUE]**, non isolé par une mesure séparée.
- **[Medium] F15-02** — cf. Top Findings. Sous l'angle sécurité : deux
  représentations d'un même secret, dont une seule ouvre. Direction d'erreur sûre
  (on refuse plutôt qu'on accepte), mais elle transforme un mot de passe correct
  en mot de passe rejeté, ce qui est un mode de panne à part entière.
- **Points conformes :** la validation de la signature du cookie ferme un second
  site de F2 que l'audit phase 14 n'avait pas vu, et le fait à la **frontière**
  (forme attendue exigée) plutôt qu'en rattrapant l'exception plus loin ; la
  comparaison reste à temps constant ; le message de la page 429 décrit désormais
  le comportement réel, ce qui referme l'écart écran/code que la phase 8 avait
  érigé en principe.

---

## Détails Par Sous-Audit

### Business Logic Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F15-03.
- **Points conformes :** F1 traite les trois formes (`text` absent, vide, hors
  sujet) ; direction d'erreur sûre conservée (neutre plutôt que pari).

### Requirements Compliance Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F15-04 sous l'angle du plan V3 — la
  phase 0 déclare débloquer la phase 1, mais F15-02 rouvre le préalable qu'elle
  était censée fermer : US-05 exige que le nouveau code « accepte tout caractère
  saisissable », ce qui n'est vrai que dans une seule forme de normalisation.
- **Points conformes :** les deux cibles de phase 0 (F2, F4) sont atteintes au
  sens où le plan les décrivait ; F3 est correctement laissé ouvert et daté.

### Doc-Sync Auditor
- **Verdict :** AUDIT_PASS avec réserves.
- **Findings :** **[Low] F15-08** — `doc/V1/comptes-3-roles.md` décrit le plafond
  de `/login` (« ralentisseur, pas barrière », deux propriétés à ne pas casser)
  sans mentionner le délai qui, désormais, est le mécanisme réel. C'est le
  document de référence de l'authentification : il doit porter le comportement,
  pas seulement le compteur. **[Low]** le rapport de phase 14 marque F4
  « traité » sans réserve — à amender par le présent rapport.
- **Points conformes :** le suivi des correctifs de la phase 14 est daté, mesuré,
  et distingue ce qui est corrigé de ce qui reste ouvert.

### A11y/UX Checker
- **Verdict :** AUDIT_PASS. Le seul changement d'interface est le message du 429,
  qui gagne en exactitude. Structure du formulaire inchangée, `role="alert"` et
  `aria-describedby` conservés.

### Clean Code Auditor
- **Verdict :** AUDIT_PASS. **Findings :** F15-05 (constante inerte).
- **Points conformes :** `_ralentir_apres_echec` est court, nommé pour ce qu'il
  fait, et porte son plafond connu en `ponytail:` avec la marche suivante ; le
  correctif F1 supprime une condition au lieu d'en ajouter une.

### Fail-Loud Auditor
- **Verdict :** AUDIT_PASS. Aucun chemin d'erreur nouveau, aucune exception
  avalée. Un cookie malformé redirige, il ne plante plus.

### Test Quality Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F15-06, F15-07, F15-09.
- **Points conformes :** 333 tests, 0 skip contre un vrai Postgres migré ;
  contre-épreuves systématiques (une claim pertinente reste exploitée, un mot de
  passe correct passe compteur plein) ; les fixtures de `test_fact_checking.py`
  ont été corrigées à la source.

### Mutation/Saboteur Auditor
- **Verdict :** AUDIT_PASS. Les trois mutations ont été réintroduites une à une et
  toutes tuées : comparaison sur des `str` (4 tests tombent), signature de cookie
  non validée (1), appel au ralentissement retiré (2). La mutation « remplacer
  `min(LOGIN_DELAI_MAX, …)` par le seul produit » ne tuerait rien — cf. F15-05,
  elle est inerte par construction.

### Layer Enforcer
- **Verdict :** AUDIT_PASS. Périmètre inchangé par la phase 0. L'import
  inter-blocs `frontend → contextualiseur.avertissement` (F6, phase 14) reste
  ouvert.

### YAGNI Auditor
- **Verdict :** AUDIT_PASS avec réserves. **Findings :** F15-05.
- **Points conformes :** aucune abstraction spéculative ; le délai réutilise le
  compteur existant au lieu d'ouvrir une seconde structure.

### SRE/Performance Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F15-01.
- **Points conformes :** le délai n'est jamais appliqué à un succès, donc jamais
  sur le chemin nominal ; aucune régression sur les autres routes en l'absence
  d'attaque (4 ms mesurés au repos).

### Architecture Consistency Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F15-04 — configuration non externalisée
  là où le projet en a fait une règle.

### Contextual Threat Analyst
- **Verdict :** AUDIT_FAIL. **Findings :** F15-01 (déni de service à quarante
  requêtes, sans identifiant ni cible).
- **Points conformes :** le scénario de bruteforce visé par F4 est effectivement
  devenu coûteux (×2800 sur 60 essais) ; le scénario de verrouillage d'un compte
  visé reste impossible.

### SAST Scanner
- **Verdict :** AUDIT_FAIL. **Findings :** F15-02 (validation/normalisation
  d'entrée incomplète sur un chemin d'authentification).
- **Points conformes :** validation de forme du cookie à la frontière ;
  comparaison à temps constant ; pas de nouvelle surface d'injection.

### Supply Chain & Artifact Auditor
- **Verdict :** AUDIT_PASS. Aucune dépendance ajoutée, aucun artefact nouveau.

### Privacy/Exfiltration Auditor
- **Verdict :** AUDIT_PASS. Aucun mot de passe journalisé — le message de refus ne
  cite que l'identifiant client, comme avant.

---

## Points Conformes (Synthèse)

- Les trois défauts visés par la phase 0 sont morts, mesurés avant/après, et
  gardés par des tests qui tombent quand on retire le correctif.
- Un **second site de F2** a été trouvé et fermé pendant le correctif — la
  signature du cookie —, ce que l'audit phase 14 avait manqué en n'examinant qu'un
  des deux appels à `compare_digest`.
- La propriété imposée par la phase 7 (N1) tient sans exception : un mot de passe
  correct n'est ni refusé ni ralenti, compteur plein.
- L'écran ne ment plus : le message du 429 décrit le mécanisme réellement exercé.
- **333 tests, 0 skip** contre un vrai Postgres avec les trois migrations.

---

## Limites De Vérification

- **La borne réellement atteinte en premier sous F15-01** (pool SQLAlchemy à 15
  connexions, ou limiteur anyio à 40 jetons) n'a pas été isolée par une mesure
  séparée : la sonde établit l'effet, pas lequel des deux plafonds cède d'abord.
- **Comportement sur Vercel non mesuré** : la répartition entre instances
  serverless peut atténuer F15-01 sans le supprimer, chaque instance restant
  vulnérable pour les requêtes qu'elle sert. Non vérifiable depuis ici.
- **Volume de scores corrompus par F1** non mesuré : aucune interrogation de la
  base de production, et la fréquence des claims sans `text` chez Google n'est pas
  connue.
- Aucun appel réseau réel ; aucune modification du code audité.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `TEST_DATABASE_URL=… pytest -q` | **333 passed, 0 skipped** |
| Mutation ×3 (str, signature, ralentissement) puis restauration | 4 / 1 / 2 tests tombent — les trois correctifs sont gardés |
| Sonde NFC/NFD sur `/login` | NFC → **303**, NFD (même mot de passe) → **401** |
| Sonde threadpool : 40 `POST /login` concurrents, compteur plein | `GET /login` : **4 ms au repos → 4,006 s** sous charge |
| Lecture du limiteur anyio à l'exécution | **40 jetons**, partagés par toutes les routes (toutes `def`) |
| Sondes F1/F2/F4 de la phase 14 rejouées | conformes au suivi consigné |


---

## Suivi Des Correctifs

### F15-01 — le ralentissement pouvait fermer le site · ✅ corrigé le 2026-09-10 · ⚠️ effet de bord

> **Amendé par l'audit phase 16 (F16-01, High) :** la borne referme bien le déni
> de service, mais son repli « places saturées, on répond sans attendre » est
> déclenchable par l'attaquant lui-même — quatre requêtes concurrentes suffisent,
> et ses essais repartent à pleine vitesse (20,09 s → 0,01 s, mesuré). Le
> ralentissement redevient optionnel, à sa main. Cf.
> `audit-phase16-relecture-correctif-f15-01.md`.

- **Correctif :** `LOGIN_DORMEURS_MAX = 4` et un `threading.BoundedSemaphore`
  acquis en non-bloquant dans `_ralentir_apres_echec`. Au-delà de quatre dormeurs
  simultanés, la tentative repart sans attendre : l'attaquant n'obtient rien de
  plus qu'avant le ralentissement, et il reste toujours des fils et des
  connexions pour le trafic légitime. Stdlib, six lignes ajoutées à la fonction.
- **Pourquoi pas une route `async` :** libérer le fil demanderait `await` sur le
  sommeil, mais le corps de la route interroge la base en synchrone
  (`Depends(get_session)`, SQLAlchemy sync) — sur une route asynchrone, ces appels
  bloqueraient la boucle d'événements, c'est-à-dire pire que le défaut soigné.
- **Vérification, sonde identique à celle de l'audit :** sous 40 tentatives ratées
  concurrentes, compteur plein, `GET /login` passe de **4,006 s à 0,005 s** — soit
  la latence au repos.
- **Contre-épreuve :** le bruteforce séquentiel reste ralenti — 8 essais erronés
  d'affilée coûtent **18,1 s**, et un mot de passe correct passe en **0,016 s**.
- **Mutations tuées :** retirer la borne fait tomber le test de F15-01 ; supprimer
  les places libres (borne à 0) fait tomber la contre-épreuve, donc la protection
  F4 ne peut pas disparaître en douce.
- **Revue ponytail appliquée :** commentaire de la borne raccourci de 7 lignes (le
  récit vit dans ce rapport, pas dans le code) ; `LOGIN_DELAI_MAX` conservé —
  plafonner la durée d'occupation d'une place rare a désormais un sens — mais
  documenté comme inerte aux valeurs actuelles, ce que demandait F15-05.
- **Suite :** 335 tests, 0 skip contre un vrai Postgres migré. Graphe de
  connaissance régénéré (`graphify update .`) : 1397 nœuds, 2075 arêtes.

### F15-02 à F15-09 — non traités

F15-02 (normalisation Unicode) reste le préalable à rouvrir avant US-05 de la V3.
Les autres sont inchangés. F15-05 est partiellement soldé : la constante reste,
son inertie est désormais écrite.
