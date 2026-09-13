# Audit phase 11 — relecture des correctifs de la phase 10

**Scope** : codebase complète sur `main` (`7df2068`, fusion de la PR #1), avec
hostilité particulière envers les 21 correctifs de la phase 10 — écrits dans la
session immédiatement précédente, donc jamais relus par personne.

**Sources d'exigences** : `doc/V0/userstories_{scraper,évaluateur,contextualiseur,frontend}.md`,
`doc/V0/architecture.md`, `doc/audit/audit-phase10-codebase-complete.md`, README, `.env.example`.

**Verdict global : 🔴 AUDIT_FAIL**
**Totaux : Critique 0 · High 2 · Medium 2 · Low 2**

> **Conflit d'intérêt déclaré.** Le code audité ici a été écrit par le même agent,
> dans la session précédente. Les deux High ci-dessous sont des défauts de mes
> propres correctifs, dont l'un est une **régression que j'ai introduite**. Toutes
> les affirmations de ce rapport sont mesurées par exécution, pas déduites.

---

## Résumé de l'audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier | 🔴 Bloquant | Le correctif du Critique de la phase 10 ne couvre que l'anglais. Cinq formulations françaises de négation retournent toujours « fiable » sur un article démenti. |
| Qualité | 🔴 Bloquant | Le nettoyage HTML introduit en phase 10 détruit 87 % du corps d'un article contenant un `<` non balise. Le corpus censé prévenir ces défauts porte le même angle mort monolingue que le correctif. |
| Architecture | 🟢 OK | `fakenews.config` tient son contrat. Aucune régression de couche. |
| Cybersécurité Offensive | 🟢 OK | Aucun nouveau vecteur. `/docs` fermé, fuites d'exception fermées, savepoints sans effet de bord observable. |

## Index des sous-audits

| Sous-audit | Crit | High | Med | Low | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Business Logic | 0 | 1 | 0 | 1 | FAIL |
| Requirements Compliance | 0 | 0 | 0 | 0 | PASS |
| Doc-Sync | 0 | 0 | 0 | 0 | PASS |
| A11y/UX | 0 | 0 | 0 | 0 | PASS |
| Clean Code | 0 | 0 | 0 | 0 | PASS |
| Fail-Loud | 0 | 1 | 0 | 0 | FAIL |
| Test Quality | 0 | 0 | 1 | 1 | FAIL |
| Mutation/Saboteur | 0 | 0 | 1 | 0 | FAIL |
| Layer Enforcer | 0 | 0 | 0 | 1 | PASS (réserve) |
| YAGNI | 0 | 0 | 0 | 0 | PASS |
| SRE/Performance | 0 | 0 | 0 | 0 | PASS |
| Architecture Consistency | 0 | 0 | 0 | 0 | PASS |
| Contextual Threat | 0 | 0 | 0 | 0 | PASS |
| SAST | 0 | 0 | 0 | 0 | PASS |
| Supply Chain | 0 | 0 | 0 | 0 | PASS |
| Privacy/Exfiltration | 0 | 0 | 0 | 0 | PASS |

## Matrice de couverture des contrats principaux

| Contrat | Fichier | Preuve | Statut |
| --- | --- | --- | --- |
| US-03 : verdict « faux » augmente fortement la suspicion | `fact_checking.py:98-108` | anglais : 34/34 · français nié : **5/7 inversés** | ❌ partiel |
| US-05 : lexiques distincts par langue | `style.py:37-77` | 15/15 titres FR, 15/15 EN du corpus · **4/5 titres EN accentués → « fr »** | ❌ partiel |
| US-01/04 scraper : contenu normalisé exploitable | `rss.py:31-56` | **289 car. → 36 car.** sur un corps contenant `<` | ❌ régression |
| US-01 contextualiseur : seuil configurable | `config.py`, `app.py:56` | `SEUIL_LISTE` vérifié, échec au démarrage sur valeur hors bornes | ✅ |
| US-08 : score borné 0-100 | `llm_bootstrap.py:57-73` | exclusion vérifiée sur 150/-20/101/100.5 | ✅ |
| « Dégrader, jamais bloquer » | `rss.py`, `reddit.py` | savepoint par entrée et par post | ✅ |

---

## Top findings

- **[High] `src/fakenews/evaluateur/fact_checking.py:83-91`** — Le correctif du
  Critique de la phase 10 n'a traité que les négations **anglaises**. Mesuré de
  bout en bout à travers `evaluer_fact_checking` : `"Ce n'est pas vrai"` → **5.0
  (fiable)**, `"Pas avéré"` → **5.0**, `"Ceci n'est pas exact"` → **5.0**,
  `"N'est pas confirmé"` → **5.0**, `"Pas vrai"` → **5.0**. Cinq formulations sur
  sept. Le mécanisme est identique au défaut d'origine : `" vrai "` est présent
  dans `" ce n est pas vrai "`, et `MOTS_FAUX` ne contient aucune forme niée
  française. **Impact** : AFP Factuel et Les Décodeurs sont des fact-checkers
  francophones, et Le Monde est la seule source haute réputation francophone du
  corpus (US-01 scraper) — la moitié francophone du dispositif conserve
  exactement le défaut que la phase 10 a déclaré fermé. **Correction attendue** :
  ajouter les formes niées françaises (`pas vrai`, `pas exact`, `pas avéré`,
  `pas confirmé`, `pas correct`, `pas vérifié`) à `MOTS_FAUX`/`VERDICTS_AMBIGUS`,
  et étendre `VERDICTS_NIES` du corpus au français.

- **[High] `src/fakenews/scraper/rss.py:41-42`** — `_BALISES = re.compile(r"<[^>]+>")`
  ne distingue pas une balise d'un `<` de comparaison : tout est supprimé du `<`
  jusqu'au `>` suivant. Mesuré : un corps de **289 caractères** contenant
  « la marge < 3 % » est réduit à **36 caractères** — 87 % du texte détruit,
  silencieusement, **à la collecte**, donc persisté ainsi et irrécupérable sans
  re-collecte. `"<p>5 < 10 et 20 > 15</p>"` → `"5 15"`. **Régression introduite
  par le correctif P4 de la phase 10** : le HTML brut était laborieux, il n'était
  pas tronqué. **Correction attendue** : exiger une lettre après `<` —
  `r"</?[a-zA-Z][^>]*>|<!--.*?-->"` — vérifié : restitue `"Le seuil a < b reste
  valable"` et `"Bénéfice > 5 % et marge < 3 %"` intacts, sans rien changer aux
  cinq cas du corpus HTML.

- **[Medium] `src/fakenews/evaluateur/style.py:70-72`** — Le départage par accents
  se déclenche dès que les poids FR et EN sont **égaux**, y compris 0-0, et un
  seul nom propre accentué suffit alors à basculer un titre anglais.
  Mesuré : `"Beyoncé announces world tour dates"` → **fr**,
  `"Nestlé recalls frozen pizza batch"` → **fr**, `"Pokémon Go maker reports
  record revenue"` → **fr**, `"Chloé Zhao wins best director"` → **fr**. Quatre
  sur cinq. Le lexique français est alors appliqué à un article anglais — le
  symétrique exact du défaut corrigé en phase 10. **Correction attendue** :
  n'utiliser l'accent comme départage que si le texte contient aussi un marqueur
  français non ambigu (apostrophe élidée, mot-outil), ou exiger au moins deux
  caractères accentués distincts.

- **[Medium] `tests/corpus/__init__.py:69-80,113-129`** — Le corpus a été construit
  en phase 10 pour empêcher précisément cette classe de défaut. Il porte le même
  angle mort : `VERDICTS_NIES` ne contient **que de l'anglais** (vérifié), et
  aucun des 15 `TITRES_EN` ne contient d'accent (vérifié). Les deux High ci-dessus
  passent donc les 83 tests du corpus sans en faire échouer un seul. **Un corpus
  ne vaut que par ses axes de diversité** : celui-ci varie les fact-checkers et
  les formats, pas les langues sur les cas limites.

---

## Thèmes transverses

1. **Le correctif appliqué à la moitié anglophone d'un système bilingue.** La
   phase 10 avait identifié comme thème transverse n°1 « le correctif appliqué à
   N-1 sites sur N » — et l'a reproduit. Les deux High de cette passe sont la
   même erreur : on a traité `"Not true"` et oublié `"Pas vrai"`, on a fait de
   l'accent un marqueur français sans se demander ce qu'il signalait dans un
   titre anglais. Le projet impose pourtant explicitement le bilinguisme
   (US-01 scraper : « au minimum anglophone et francophone »).
2. **Le garde-fou hérite de l'angle mort de ce qu'il garde.** Le corpus a été
   écrit par la même personne, dans la même heure, avec les mêmes réflexes que le
   correctif. Il tue les mutations de l'implémentation d'origine — c'est vérifié
   et réel — mais pas celles du correctif. Un corpus rédigé *après* le correctif
   valide surtout la compréhension de son auteur.
3. **Une correction peut coûter plus cher que le défaut.** Le HTML brut faussait
   un signal sur cinq (les citations). Son nettoyage détruit le texte source. Le
   premier était réversible par un re-traitement, le second exige une
   re-collecte. La règle « ne jamais transformer à l'écriture ce qu'on peut
   transformer à la lecture » aurait évité ça.

---

## Détails par division

### Division Métier (Anton Ego)

On m'avait promis que le plat était corrigé. On me le représente, et je découvre
que le cuisinier a rectifié l'assaisonnement d'une moitié de l'assiette.

- **[High]** `fact_checking.py:83-91` : la phase 10 a écrit trois niveaux
  ordonnés, une normalisation Unicode, un commentaire de vingt lignes expliquant
  pourquoi l'ordre compte — et a rempli les listes en anglais. `_aplatir` retire
  consciencieusement les accents de `"Pas avéré"` pour le comparer à un ensemble
  qui ne contient aucune négation française. La mécanique est irréprochable ; le
  dictionnaire s'arrête à Calais. Le rapport de phase 10 annonce ce finding
  « fermé ». Il l'est à 62 %.
- **[Low]** `fact_checking.py:83` : le barème du *Washington Post* — « Four
  Pinocchios », « Geppetto Checkmark » — ne correspond à rien et retourne
  `None`. Direction d'erreur sûre (signal exclu, conforme au 4ᵉ critère d'US-03),
  mais c'est l'échelle entière d'un fact-checker majeur qui est invisible.

### Division Qualité (Gordon Ramsay)

Vous avez nettoyé le plan de travail avec un chalumeau.

- **[High]** `rss.py:41-42` : `<[^>]+>`. Deux cent quatre-vingt-neuf caractères
  entrent, trente-six sortent. Vous avez remplacé un signal faussé par une
  amputation, et vous l'avez fait **à l'écriture** — la donnée d'origine n'existe
  plus. Le test `test_le_html_des_flux_est_reduit_a_du_texte_lisible` passe :
  aucun de ses cinq cas ne contient un `<` qui ne soit pas une balise. Cinq cas
  choisis par celui qui a écrit la regex, tous conformes à ce qu'il imaginait.
- **[Medium]** `tests/corpus/__init__.py` : le corpus tue 3 inversions et 14
  erreurs de classement de l'implémentation d'ORIGINE — c'est mesuré, c'est un
  vrai actif. Il ne tue **aucune** des deux mutations introduites par le
  correctif. Un corpus écrit après coup teste l'intention de l'auteur, pas le
  monde.
- **[Low]** `tests/test_conformite_exigences.py:127` : le test s'appelle
  `test_le_frontend_n_importe_aucun_bloc_metier` et vérifie l'absence de trois
  chaînes précises. `app.py:27` importe toujours
  `from fakenews.contextualiseur.avertissement import AVERTISSEMENT`. Le nom
  affirme davantage que le corps ne vérifie.

### Division Architecture (Steve Jobs)

Rien à retirer. C'est rare, alors je le dis.

- `fakenews/config.py` fait une chose : lire l'environnement, sans cache. Les
  points d'entrée décident quand résoudre — au démarrage pour le frontend, à
  l'appel pour les scripts. Cette séparation est juste, et le test en
  sous-processus qui l'atteste est la bonne façon de la prouver.
- Le couplage `frontend → contextualiseur` restant (`AVERTISSEMENT`) est une
  constante d'affichage, pas une valeur dont dépend le contenu listé. Ne pas
  confondre avec `SEUIL_PAR_DEFAUT`, qui, lui, méritait d'être déplacé.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : rien de neuf. J'ai cherché.

- `/docs`, `/redoc`, `/openapi.json` → 404, vérifié par test.
- Les cinq sites de fuite d'exception sont fermés ; `type(exc).__name__` partout.
- `begin_nested()` n'introduit aucun contournement : le savepoint est interne à
  la transaction, il ne relâche aucun verrou vers l'extérieur.
- La troncature HTML du finding High n'est **pas** exploitable comme vecteur : un
  auteur de fake news pourrait tronquer son propre article en y plaçant un `<`,
  mais cela réduit son texte, donc son exposition — aucun gain offensif. C'est un
  défaut de robustesse, pas de sécurité.

---

## Détails par sous-audit

- **Business Logic** — FAIL. Négations françaises non couvertes (High) ; barème
  Pinocchios non reconnu (Low). Conforme : les 34 verdicts anglophones réels, les
  trois niveaux ordonnés, l'exclusion par défaut.
- **Requirements Compliance** — PASS. US-01 contextualiseur (seuil + plafond
  configurables) vérifié par 16 tests ; US-08 (bornes) vérifié ; US-07 (plafond
  backfill) vérifié.
- **Doc-Sync** — PASS. `.env.example` documente les cinq variables lues, testé.
  Le rapport de phase 10 déclare cependant le Critique « fermé » sans réserve :
  à corriger à la lumière du High n°1.
- **A11y/UX** — PASS. Aucun changement de gabarit hors `detail.html`.
- **Clean Code** — PASS. `_aplatir`/`_borner` sont courts et nommés ;
  `_commiter_le_lot` isole la responsabilité.
- **Fail-Loud** — FAIL. La troncature HTML est **silencieuse** : aucun log,
  aucun compteur. Un article amputé de 87 % est indiscernable d'un résumé court.
- **Test Quality** — FAIL. Corpus monolingue sur les cas limites (Medium) ; nom
  de test plus fort que son assertion (Low). Conforme : 298 tests, 0 skip, et le
  test en sous-processus pour l'échec à l'import.
- **Mutation/Saboteur** — FAIL. Mutation non tuée : restreindre `_BALISES` à
  `</?[a-zA-Z][^>]*>` — c'est-à-dire **corriger le bug** — ne fait échouer aucun
  test. Symétriquement, ajouter `"pas vrai"` à `MOTS_FAUX` n'en fait échouer
  aucun non plus. Les deux correctifs attendus sont invisibles à la suite.
- **Layer Enforcer** — PASS (réserve). Import `AVERTISSEMENT` subsistant, assumé.
- **YAGNI / SRE / Architecture Consistency / Contextual Threat / SAST /
  Supply Chain / Privacy** — PASS. Rien de neuf ; les findings correspondants de
  la phase 10 sont fermés et vérifiés.

---

## Points conformes vérifiés (à ne pas casser)

- **Le Critique de la phase 10 est réellement fermé côté anglais** : les 34
  verdicts réels du corpus, dont `"Inaccurate"`, `"Incorrect"`, `"Half true"`,
  `"Barely true"`, `"Not true"`, sont tous classés correctement. Le mécanisme des
  trois niveaux ordonnés est sain — c'est son alimentation qui est incomplète.
- **298 tests, 0 skip**, contre un Postgres neuf avec les trois migrations.
- Bornes du score LLM : `150`, `-20`, `101`, `100.5` exclus ; `0.0` et `100.0`
  acceptés.
- Seuil hors bornes → échec au **démarrage** du frontend, message nommant la
  variable — vérifié en sous-processus.
- `SEUIL_LISTE` du frontend et `seuil_suspicion()` du contextualiseur sont la
  même valeur, vérifié par identité de fonction et d'évaluation.
- Savepoints RSS/Reddit : la mutation `begin_nested` → sans effet fait bien
  échouer `test_rss_resilience`.

## Limites de vérification

- **Commandes exécutées** : `git merge --ff-only origin/main` (le `main` local
  était resté sur `a620c27`, l'audit aurait porté sur l'ancien code) ; création
  d'une base Postgres dédiée et vide (`fakenews_audit11`) + trois migrations ;
  `pytest -q` → **298 passed, 0 skipped** ; neuf sondes Python ciblées
  (négations FR/EN, barème Pinocchios, titres accentués, `nettoyer_html` sur `<`
  nu, regex stricte comparée, bout-en-bout `evaluer_fact_checking`, couverture du
  corpus, imports du frontend, résolution du seuil). Aucun fichier modifié.
- **Non vérifiable depuis ici** : la fréquence réelle d'un `<` non échappé dans
  les huit flux RSS de production (garde réseau active, aucun appel sortant) — le
  finding High n°2 est donc **confirmé sur le mécanisme**, sa probabilité
  d'occurrence en production reste à mesurer sur un vrai run.
- **Conflit d'intérêt** : audit du code écrit par le même agent à la session
  précédente. Les deux High ont été trouvés en cherchant délibérément le
  symétrique linguistique et les cas limites d'expression régulière — un angle
  qu'un auditeur tiers aurait pu ne pas privilégier, et inversement il peut rester
  des défauts qu'un regard extérieur verrait immédiatement.
- **Toujours ouvert depuis la phase 10** : sources francophones douteuses
  (décision produit) ; recherche de secrets dans l'historique Git (erreurs d'E/S
  du volume).
