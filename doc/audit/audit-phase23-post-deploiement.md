# Audit phase 23 — Post-déploiement du crowdsourcing V3

Date : 2026-09-13 · Scope : l'état livré en production — commit `8d0c05b` sur
`main`, déployé sur Vercel. Ce que le code exige de la production au démarrage,
ce que le bundle serverless embarque, et ce qui reste ouvert **en ligne**.
Base d'exigences : `README.md` (ordre de déploiement), `doc/V0/architecture.md`
(topologie, décision V3), `doc/V3/`, audits 14 à 22.
Nature : audit de **mise en service**, pas de code. Les défauts de comportement
ont été traités aux phases précédentes ; celui-ci regarde ce qui change quand le
code cesse d'être un fichier pour devenir un service.

---

## Résumé De L'Audit

| Division | Statut | Synthèse |
| --- | --- | --- |
| Métier (Anton Ego) | 🟡 Avertissement | Le module qui porte six routes d'écriture s'annonce, dès sa première ligne, comme n'en ayant aucune. Le mensonge est en tête de fichier. |
| Qualité (Gordon Ramsay) | 🟡 Avertissement | Les instructions de mise en place de la base de test s'arrêtent à la migration `0003`. Qui les suit aujourd'hui obtient une suite qui échoue, pas qui saute. |
| Architecture (Steve Jobs) | 🟢 OK | Le bundle serverless est propre : aucun paquet du pipeline n'a suivi le frontend, toutes ses dépendances réelles sont déclarées. |
| Cybersécurité offensive (Sherlock Holmes) | 🟡 Avertissement | Rien de neuf, mais F16-01 change de statut : le mot de passe partagé ouvre désormais un pouvoir d'écriture, en ligne. |

**Verdict global : AUDIT_PASS avec réserves.** 0 Critique, 0 High, 1 Medium,
1 Low — plus **trois préconditions de production que je ne peux pas vérifier
d'ici**, listées en fin de rapport.

---

## Index Des Sous-Audits

| Sous-audit | Scope | Crit | High | Medium | Low | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Business Logic Auditor | comportement inchangé depuis la phase 22 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Requirements Compliance Auditor | US-04 frontend (déploiement) | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Doc-Sync Auditor | docstrings, README | 0 | 0 | 1 | 1 | AUDIT_FAIL |
| A11y/UX Checker | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Clean Code Auditor | docstring de module | 0 | 0 | 1 | 0 | AUDIT_FAIL |
| Fail-Loud Auditor | démarrage du service | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Test Quality Auditor | trois Low hérités, en production | 0 | 0 | 0 | 0 | AUDIT_PASS (réserves) |
| Mutation/Saboteur Auditor | hors périmètre d'un audit de mise en service | — | — | — | — | n/a |
| Layer Enforcer | bundle Vercel | 0 | 0 | 0 | 0 | AUDIT_PASS |
| YAGNI Auditor | inchangé | 0 | 0 | 0 | 0 | AUDIT_PASS |
| SRE/Performance Auditor | démarrage à froid, état par instance | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Architecture Consistency Auditor | topologie réelle vs `architecture.md` | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Contextual Threat Analyst | surface exposée en ligne | 0 | 0 | 0 | 0 | AUDIT_PASS (réserves) |
| SAST Scanner | inchangé depuis la phase 22 | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Supply Chain & Artifact Auditor | `api/requirements.txt` vs modules chargés | 0 | 0 | 0 | 0 | AUDIT_PASS |
| Privacy/Exfiltration Auditor | données personnelles désormais en ligne | 0 | 0 | 0 | 0 | AUDIT_PASS (réserves) |

Décompte dédupliqué : **2 findings**.

---

## Matrice De Couverture — Ce Que La Production Exige

| Précondition | Preuve | Statut |
| --- | --- | --- |
| Les six tables déclarées existent en base | `verifier_schema` les exigera : `articles`, `comptes`, `commentaires`, `mise_en_contexte`, `propositions`, `scores` | ⚠️ **non vérifiable d'ici** |
| Aucun paquet du pipeline dans le bundle serverless | `spacy`, `praw`, `feedparser`, `anthropic`, `pytest` : **aucun chargé** | ✅ |
| Toutes les dépendances réelles déclarées | modules tiers chargés = `fastapi`, `sqlalchemy`, `jinja2`, `pydantic`, `starlette`, `dotenv`, `python_multipart` + transitives — tous couverts | ✅ |
| `CONTEXTUALISEUR_SEUIL` lisible au démarrage | `SEUIL_LISTE = seuil_suspicion()` **au chargement du module** : une valeur illisible fait échouer le déploiement, pas chaque page | ✅ (par conception) |
| `FRONTEND_PASSWORD` définie | absente ⇒ accès refusé, jamais site ouvert | ⚠️ **non vérifiable d'ici** |
| `FAKENEWS_MODE` absente en hébergé | sa présence désactiverait l'authentification | ⚠️ **non vérifiable d'ici** |
| `FAKENEWS_PROXYS_DE_CONFIANCE=1` sur Vercel | sans elle, le plafond de `/login` devient global au lieu d'être par visiteur | ⚠️ **non vérifiable d'ici** |
| Le pipeline reste en pause | `schedule` commenté dans le workflow | ✅ |
| CI verte sur le commit déployé | `8d0c05b`, succès en 1 min 5 s sur la branche | ✅ |
| La documentation décrit le service livré | **docstring du frontend et setup de test périmés** | ❌ F23-01, F23-02 |

---

## Top Findings

- **[Medium] F23-01 · `src/fakenews/frontend/app.py:1-4`** — la docstring du
  module, première chose que lit quiconque ouvre le fichier, affirme :
  > « Frontend de consultation **en lecture seule** […] Ce module ne fait
  > strictement que lire le stockage partagé — **aucune route d'écriture**. »

  Le module compte aujourd'hui **six routes d'écriture** : proposer, décider
  (accepter/refuser), changer son code, promouvoir, rétrograder, commenter,
  retirer un commentaire. La frontière a bien été révisée partout ailleurs —
  `architecture.md` porte une décision V3 complète, `userstories_frontend.md` une
  mise à jour datée, `models.py` deux mentions explicites, le plan V3 un tableau —
  **sauf à l'endroit le plus lu de tous.**
  **Type : Écart documentaire, Confirmé.**
  **Impact :** aucun sur le comportement ; total sur la confiance. Ce dépôt a
  consacré une part considérable de vingt-trois audits à traquer les documents qui
  mentent ; celui-ci ment en quatre lignes, en tête du fichier le plus important.
  **Correction attendue :** remplacer par la frontière réelle — écrit
  `propositions`, `commentaires`, `comptes` ; n'écrit jamais `articles`, `scores`,
  `mise_en_contexte`.
- **[Low] F23-02 · `README.md:108`** — la mise en place de la base de test
  s'arrête à `0001`, avec le commentaire `# + 0002, 0003`. Il existe désormais
  **sept** migrations. Qui suit ces instructions aujourd'hui obtient une base
  incomplète — et la suite n'y **saute** pas, elle **échoue**, sur des erreurs de
  table manquante qui n'accusent pas la bonne cause.
  Le bloc de déploiement, lui, liste correctement les sept (`README.md:88-94`) :
  l'oubli porte sur la seule section qu'un contributeur nouveau suit en premier.
  **Correction attendue :** aligner sur le bloc de déploiement, ou renvoyer vers
  lui plutôt que d'énumérer deux fois.

---

## Thèmes Transverses

1. **Le document le plus lu est celui qu'on oublie.** Quatre fichiers ont été
   amendés avec soin pour décrire la nouvelle frontière d'écriture ; la docstring
   du module concerné ne l'a pas été. Réviser une décision d'architecture ne
   révise pas automatiquement les textes qui la citaient.
2. **Deux sections du même README ont divergé.** Celle qu'on suit pour déployer
   est juste ; celle qu'on suit pour développer ne l'est plus.
3. **Le code livré est conforme ; ce sont ses préconditions qui ne sont pas
   vérifiables d'ici.** Cet audit peut affirmer ce que la production *exigera* ;
   il ne peut pas affirmer qu'elle le fournit.

---

## Détails Par Division

### Division Métier (Anton Ego)

Vingt-trois audits à pourchasser les documents qui mentent, et l'on découvre que
le plus effronté d'entre eux tient en quatre lignes au sommet du fichier
principal. Ce n'est pas une négligence de détail : c'est la première phrase que
lira le prochain venu.

- **[Medium] F23-01** — cf. Top Findings.
- **Points conformes :** la décision V3 est documentée là où la règle d'origine
  vivait (`architecture.md`), datée dans les user stories, reflétée dans
  `models.py`, et gardée par un test qui refuse toute écriture du frontend sur les
  trois tables du verdict.

### Division Qualité (Gordon Ramsay)

Votre README explique comment déployer — parfaitement. Il explique aussi comment
monter une base de test, et il s'arrête trois migrations trop tôt. Le nouveau qui
suit vos instructions se prendra quatre tables manquantes dans la figure et
croira que c'est sa faute.

- **[Low] F23-02** — cf. Top Findings.
- **Points conformes :** la CI est verte sur le commit déployé, avec un vrai
  Postgres, les sept migrations appliquées et un budget de skips à zéro. C'est
  précisément ce que la section périmée empêche un humain de reproduire à la main.

### Division Architecture (Steve Jobs)

Le bundle est propre. C'est la seule chose que je voulais vérifier, et elle est
juste.

- **Points conformes :** aucun paquet du pipeline — `spacy`, `praw`,
  `feedparser`, `anthropic`, `pytest` — n'est chargé par le frontend, ce qui
  valide la séparation des deux `requirements.txt` décidée en phase 5 ; toutes les
  dépendances réellement chargées sont couvertes par `api/requirements.txt` ou
  transitives de celles-ci ; le seuil est résolu **au chargement du module**, donc
  une variable mal saisie fait échouer le déploiement de façon visible plutôt que
  de casser page par page.

### Division Cybersécurité Offensive (Sherlock Holmes)

Élémentaire, et pourtant : rien de neuf ne s'est ouvert. C'est le statut de
l'ancien qui a changé.

- **Observation — F16-01 est désormais en ligne.** Le ralentissement de `/login`
  reste désactivable par saturation, et le mot de passe partagé qu'il protège
  n'ouvre plus une consultation mais un **pouvoir d'écriture** : proposer,
  commenter. Reste théorique tant que ce mot de passe est long et aléatoire
  (confirmé par le porteur du projet en phase 16) — mais l'entropie de ce secret
  est maintenant la seule chose qui sépare un inconnu du droit d'écrire sur le
  site.
- **Observation — l'état anti-abus est par instance.** Compteur de tentatives,
  places d'attente et cache de comptes vivent dans la mémoire du process : sur
  Vercel, leur effet est divisé par le nombre d'instances tièdes. Les plafonds de
  propositions et de commentaires, eux, sont comptés **en base** et n'ont pas ce
  défaut — c'était le bon choix.
- **Points conformes :** `/docs`, `/redoc` et `/openapi.json` restent fermés ;
  en-têtes de sécurité et CSP posés par un middleware, donc sur toutes les routes
  neuves sans action supplémentaire ; CSRF exigée sur les six écritures.

---

## Détails Par Sous-Audit

### Business Logic / Requirements Compliance / A11y / SAST / Layer Enforcer / YAGNI / Architecture Consistency
- **Verdict :** AUDIT_PASS. Comportement inchangé depuis la phase 22 ; la
  topologie réelle (Vercel + GitHub Actions + Supabase) correspond à
  `architecture.md`.

### Doc-Sync Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F23-01, F23-02.
- **Points conformes :** `.env.example` couvre les trois variables neuves (vérifié
  par un test) ; le bloc de déploiement du README liste les sept migrations dans
  l'ordre ; l'état d'avancement du plan V3 décrit les quatre phases livrées et les
  sujets restés ouverts.

### Clean Code Auditor
- **Verdict :** AUDIT_FAIL. **Findings :** F23-01 — une docstring qui décrit
  l'inverse du module est un défaut de code, pas de documentation.

### Fail-Loud Auditor
- **Verdict :** AUDIT_PASS. Trois échecs de configuration produisent un
  diagnostic nommé plutôt qu'une panne muette : seuil illisible (échec au
  démarrage), `DATABASE_URL` absente (message nommant les trois endroits où la
  poser), schéma en retard (message nommant la table manquante).

### Test Quality Auditor
- **Verdict :** AUDIT_PASS avec réserves. Les trois Low de la phase 22 sont
  désormais **en production** : le cloisonnement des commentaires entre articles
  n'est gardé par aucun test, leur tri n'a pas de clé de départage, et un
  commentaire multiligne s'affiche aplati. Aucun n'est bloquant ; le premier reste
  le plus gênant, puisqu'une régression y serait invisible à la suite.

### SRE/Performance Auditor
- **Verdict :** AUDIT_PASS. Démarrage à froid : une seule résolution de
  configuration, une seule vérification de schéma par instance. L'état anti-abus
  par instance est documenté et assumé.

### Contextual Threat Analyst / Privacy
- **Verdict :** AUDIT_PASS avec réserves. **Le RGPD n'est plus théorique** :
  le site en ligne peut désormais recevoir des textes rédigés par des personnes
  identifiables par leur pseudo, conservés sans durée définie.
  `architecture.md` classe le sujet hors périmètre prototype et fait de
  l'authentification la condition qui tient lieu de garde-fou. Le mécanisme de
  retrait (masquage avec trace) est le premier élément concret ; ce n'est pas une
  politique de conservation.

### Supply Chain & Artifact Auditor
- **Verdict :** AUDIT_PASS. Aucune dépendance ajoutée par la V3 ; bundle
  serverless vérifié par inspection des modules réellement chargés.

---

## Points Conformes (Synthèse)

- **Le bundle serverless est propre** : aucun paquet du pipeline n'a suivi le
  frontend, et toutes ses dépendances réelles sont déclarées.
- **CI verte** sur le commit déployé, avec un vrai Postgres et les sept
  migrations.
- **Le pipeline est resté en pause** : aucune collecte, aucune notation, aucun
  appel LLM ne partira sans déclenchement manuel.
- Les trois échecs de configuration les plus probables produisent un diagnostic
  nommé, pas une panne muette.
- Les plafonds d'écriture sont comptés **en base**, donc insensibles au nombre
  d'instances — contrairement à l'état anti-bruteforce, dont la limite est
  documentée.

---

## Limites De Vérification — À Contrôler Toi-Même

Cet audit est fait depuis une machine sans accès à la production. **Trois choses
que je ne peux ni vérifier ni garantir**, et qui décident si le déploiement est un
succès :

1. **Les sept migrations sont-elles appliquées sur Supabase ?** Sinon,
   `verifier_schema` lèvera une erreur nommant la table manquante, sur **toutes**
   les pages. La requête de contrôle donnée précédemment (les sept `OK`) répond à
   la question en une exécution.
2. **Les variables Vercel sont-elles justes ?** `DATABASE_URL` et
   `FRONTEND_PASSWORD` présentes, `FAKENEWS_PROXYS_DE_CONFIANCE=1`, et surtout
   **`FAKENEWS_MODE` absente** — sa présence désactiverait l'authentification sur
   le site public.
3. **Le déploiement Vercel a-t-il abouti ?** Un échec de build laisse l'ancienne
   version en ligne, ce qui est un état sûr mais silencieux.

Autres limites : aucun navigateur ici, donc le rendu réel n'est pas observé ;
aucun test de charge ; aucun code de production modifié pendant cet audit.

### Commandes Exécutées

| Commande | Résultat |
| --- | --- |
| `git merge v3-crowdsourcing && git push origin main` | `7df2068..8d0c05b`, déclencheur Vercel envoyé |
| `gh run list --branch v3-crowdsourcing` | **succès**, 1 min 5 s, même commit |
| Inspection des modules tiers chargés par le frontend | 7 paquets directs + transitives, **aucun paquet du pipeline** |
| Tables exigées par `verifier_schema` | six, dont `propositions` et `commentaires` |
| `grep` sur « lecture seule stricte » | trois mentions correctes, **une docstring fausse** |
| `grep` sur les migrations listées dans le README | déploiement : 7 ✅ · base de test : **s'arrête à 0003** |
