# Plan d'implémentation — Crowdsourcing (V3)

Séquence les user stories de `doc/V3/userstories_crowdsourcing.md`. Même principe
que `doc/V0/plan_implementation.md` : l'ordre est piloté par les dépendances
réelles, pas par la visibilité des fonctionnalités — et chaque phase doit être
testable de bout en bout avant la suivante.

> **Statut : plan, rien n'est implémenté.** La section « État d'avancement » en
> fin de document est à tenir à jour à chaque phase livrée, comme celle du plan
> V0 — qui s'est déjà désynchronisée une fois.

---

## Principe directeur : ce que le frontend a le droit d'écrire

La règle « frontend en lecture seule stricte » tombe (cf. `architecture.md`,
décision V3). Elle est remplacée par une frontière plus précise, qui doit tenir
dans chaque phase :

| Table | Frontend | Pipeline |
|---|---|---|
| `propositions` | **écrit** (création, décision) | lit, met à jour le statut de collecte |
| `commentaires` | **écrit** (création, retrait) | — |
| `comptes` | **écrit** (enregistrement à la connexion, code personnel, rôle) | — |
| `articles` | lit | écrit |
| `scores` | lit | écrit |
| `mise_en_contexte` | lit | écrit |

**Le frontend n'écrit jamais le verdict.** Il enregistre des intentions humaines ;
le pipeline seul produit les articles, les scores et les mises en contexte. C'est
cette ligne-là qui remplace « lecture seule », et c'est elle qu'un test doit
verrouiller : aucune route du frontend ne doit toucher les trois tables du bas.

---

## Phase 0 — Préalables bloquants

Ces deux correctifs ne relèvent pas du crowdsourcing, mais le crowdsourcing les
rend bloquants. Les traiter d'abord, séparément, avec leurs propres tests.

1. **F2 — comparaison de mots de passe non-ASCII** (`frontend/app.py`, une ligne :
   comparer des `bytes`). US-05 ouvre un écran où l'utilisateur **choisit** son
   mot de passe : livrer cet écran avant le correctif, c'est lui fournir un moyen
   de verrouiller son compte avec un accent. Détail et mesure dans
   `doc/audit/audit-phase14-codebase-complete.md`.
2. **F4 — plafond `/login` sans effet.** Le mot de passe partagé ne donnait accès
   qu'à une consultation ; il va donner un pouvoir d'écriture. Décision de
   conception à prendre ici (refuser la vérification au-delà du plafond, avec une
   clé de comptage qui ne redevienne pas un déni de service global), pas au
   moment où la file d'attente sera déjà ouverte.

**Taille :** F2 minuscule, F4 petite mais avec une décision à trancher.

---

## Phase 1 — Identité et rôles opposables

**Pourquoi en premier :** tout le reste en dépend. `doc/V1/comptes-3-roles.md` le
dit déjà — « avant de donner à `contributeur` une action que `spectateur` ne peut
pas faire, il faudra un `secret_hash` par contributeur ». Livrer la file d'attente
avant cette phase donnerait le pouvoir de décision à quiconque connaît le mot de
passe partagé, sous le pseudo de son choix.

**Contenu : US-06, US-07, US-05 (partie code personnel), + exigences transverses
autorisation et CSRF.**

1. **Migration `0004_comptes_contributeur_code.sql`** — étendre la contrainte
   existante :
   ```sql
   alter table comptes drop constraint if exists ck_comptes_superadmin_a_un_code;
   alter table comptes add constraint ck_comptes_role_privilegie_a_un_code
       check (role = 'spectateur' or secret_hash is not null);
   ```
   Rattrapage préalable pour les contributeurs déjà semés sans code (même figure
   que la migration `0002` pour le superadmin) : poser un code aléatoire inconnu
   plutôt que laisser la contrainte échouer — fail-closed, le contributeur
   redemande un code.
2. **Garde d'autorisation** (`frontend/app.py`) : une dépendance FastAPI par
   capacité, construite sur `compte_courant`, avec une **hiérarchie** —
   `superadmin` ⊇ `contributeur` ⊇ `spectateur`. Jamais d'égalité stricte de
   rôle : l'utilisateur est superadmin **et** contributeur.
3. **Jeton anti-CSRF** sur tous les formulaires d'écriture. Dérivable du secret de
   session déjà en place (même clé HMAC que le cookie, charge différente) — pas de
   nouvelle dépendance, pas de stockage serveur.
4. **US-07 — enregistrement à la première connexion** : à l'issue d'un `POST
   /login` réussi, insérer le pseudo en `spectateur` s'il est absent. Attention au
   cache de comptes (`_cache_comptes`, TTL 60 s) : la connexion le purge déjà pour
   ce pseudo, à conserver.
5. **US-06 — écran superadmin** : liste des comptes, promouvoir / rétrograder,
   affichage unique du code provisoire.
6. **US-05 — changement de code personnel** : formulaire code actuel + nouveau
   code ×2, vérification par `crypt()` côté Postgres (mécanisme existant),
   écriture du nouveau hash, invalidation implicite des sessions du pseudo.

**Tests attendus :** un spectateur reçoit un refus sur chaque route réservée, en
accès direct à l'URL ; un contributeur sans code personnel ne peut pas exister
(la base le refuse) ; un changement de code invalide le cookie précédent ; un
POST sans jeton CSRF est refusé ; un mot de passe accentué fonctionne
(régression F2).

**Taille :** la plus grosse phase. C'est la fondation, et c'est là que se
concentre le risque de sécurité.

---

## Phase 2 — Propositions et file d'attente

**Contenu : US-01, US-02, US-03, US-05 (partie « mes propositions »).**

1. **Migration `0005_propositions.sql`** :
   ```sql
   create table if not exists propositions (
       id uuid primary key default gen_random_uuid(),
       url text not null,
       url_canonique text not null,
       note text,
       propose_par text not null,
       date_proposition timestamptz not null default now(),
       statut text not null default 'en_attente',
       decide_par text,
       date_decision timestamptz,
       motif text,
       article_id uuid references articles (id) on delete set null,

       constraint ck_propositions_statut check (statut in
           ('en_attente', 'acceptee', 'refusee', 'collectee', 'echec_collecte')),
       -- Un refus sans motif est un mur, pas une décision (US-03).
       constraint ck_propositions_refus_motive check (
           statut <> 'refusee' or (motif is not null and length(trim(motif)) > 0)),
       -- Une décision trace toujours son auteur et sa date.
       constraint ck_propositions_decision_tracee check (
           statut = 'en_attente' or (decide_par is not null and date_decision is not null))
   );
   -- Empêche deux propositions vivantes pour la même URL (US-01), sans gêner
   -- l'historique des refus.
   create unique index if not exists uq_propositions_en_cours
       on propositions (url_canonique)
       where statut in ('en_attente', 'acceptee');
   ```
   Les invariants d'US-03 vivent dans la base, pas seulement dans la route : c'est
   la leçon de `ck_comptes_superadmin_a_un_code`.
2. **Modèle SQLAlchemy** `Proposition` dans `models.py` — miroir exact, sous peine
   de faire mentir `verifier_schema`.
3. **Routes** : `GET/POST /propositions` (proposer), `GET /file` (file d'attente,
   garde contributeur), `POST /file/{id}/accepter`, `POST /file/{id}/refuser`.
4. **Déduplication à la proposition** : rechercher `url_canonique` dans `articles`
   puis dans `propositions` vivantes, avant insertion.
5. **Plafond par compte et par fenêtre**, lu dans l'environnement via
   `fakenews.config` (les helpers `entier_depuis_env` existent).

**Point d'attention :** `fakenews.schema.verifier_schema` ne contrôle que les
**colonnes manquantes**, pas les contraintes ni les index. Une base en retard sur
`0005` ne fera pas échouer le démarrage : elle échouera à la première écriture.
L'ordre « migrations d'abord » (`README.md`) reste la seule protection réelle.

**Tests attendus :** proposition d'une URL déjà analysée → pas de doublon, renvoi
vers la fiche ; refus sans motif → rejeté (par la route ET par la base) ; un
spectateur ne peut ni accéder à la file ni décider ; plafond de propositions
opposable ; ordre et pagination stables.

**Taille :** moyenne.

---

## Phase 3 — Entrée dans le pipeline

**Contenu : US-04.**

1. **Migration `0006_articles_plateforme_proposition.sql`** — la contrainte
   actuelle n'autorise que `rss` et `reddit`, donc l'insertion échouerait :
   ```sql
   alter table articles drop constraint if exists ck_articles_plateforme;
   alter table articles add constraint ck_articles_plateforme
       check (plateforme in ('rss', 'reddit', 'proposition'));
   ```
   Et `PLATEFORMES` dans `models.py`, dans le même commit.
2. **Nouveau collecteur** `scraper/propositions.py`, court par construction : tout
   ce dont il a besoin existe déjà dans le dépôt —
   `rss._telecharger` (timeout, User-Agent), `rss.nettoyer_html`,
   `normalisation.canonicaliser_url`, `normalisation.hacher_contenu`,
   `persistance.enregistrer_ou_mettre_a_jour`. Il ne reste à écrire que
   l'extraction du titre et de la date depuis le HTML, et la mise à jour du
   statut.
3. **Date de publication** : `articles.date_publication` est `not null`. Si la
   page ne porte pas de date exploitable, retomber sur la date de proposition
   **et le consigner dans `metadonnees`**. Limite à assumer et à écrire : un
   article daté par défaut du jour décale la fenêtre ±5 jours ouvrés d'US-04
   évaluateur (source primaire) et fausse le filtre par date du frontend.
4. **Branchement dans le pipeline** : un step avant l'évaluateur dans
   `pipeline_hebdomadaire.yml`. Le `schedule` **reste commenté** — décision de
   l'utilisateur du 2026-09-10 : on ne réactive pas encore le scraping
   hebdomadaire. Les propositions acceptées attendent donc un déclenchement
   manuel, et l'interface doit le dire (US-04).
5. **Plafond de collecte par run**, configurable, documenté dans `.env.example`.

**Sécurité :** la collecte se fait dans le runner GitHub Actions, jamais depuis
Vercel. Reste à borner ce que le runner accepte : schéma `http`/`https`
uniquement (déjà validé à la proposition, à revalider ici — la validation d'entrée
ne se délègue pas), taille de réponse plafonnée, redirections limitées, timeout
explicite.

**Tests attendus :** une proposition acceptée devient un article `plateforme =
'proposition'` puis reçoit un score ; un échec de collecte marque
`echec_collecte` sans interrompre les suivantes ; le plafond est opposable ; une
URL non `http(s)` est refusée par le collecteur même si elle a franchi le
formulaire.

**Taille :** petite à moyenne — l'essentiel est de la réutilisation.

---

## Phase 4 — Commentaires

**Contenu : US-08.** En dernier parce que c'est la seule fonctionnalité qui ne
conditionne rien d'autre — et la première à retirer si le périmètre doit se
réduire.

1. **Migration `0007_commentaires.sql`** : `id`, `article_id` (FK cascade),
   `pseudo`, `texte`, `date_creation`, `retire_le`, `retire_par`.
   Retrait = masquage, pas suppression : `retire_le is null` est la condition
   d'affichage public. Un contenu retiré pour raison juridique doit rester
   consultable par le superadmin.
2. **Route de publication** + affichage sur la page de détail, **sous** l'analyse
   et la mise en contexte, visuellement distincts.
3. **Route de retrait**, réservée au superadmin.
4. **Plafond par compte et par fenêtre.**

**Tests attendus :** un commentaire retiré n'apparaît plus publiquement mais
existe toujours en base ; un spectateur peut commenter ; seul le superadmin
retire ; la longueur est bornée ; le contenu est échappé à l'affichage (Jinja
autoescape est actif, un test le verrouille) ; l'avertissement automatisé reste
présent sur la page.

**Taille :** petite.

---

## Fichiers touchés (vue d'ensemble)

| Fichier | Nature |
|---|---|
| `supabase/migrations/0004…0007` | nouveaux |
| `src/fakenews/models.py` | `Proposition`, `Commentaire`, `PLATEFORMES` |
| `src/fakenews/frontend/app.py` | routes d'écriture, gardes, CSRF |
| `src/fakenews/frontend/templates/` | file d'attente, espace compte, admin comptes, commentaires |
| `src/fakenews/scraper/propositions.py` | nouveau collecteur |
| `src/fakenews/config.py` | plafonds d'écriture et de collecte |
| `.github/workflows/pipeline_hebdomadaire.yml` | step de collecte des propositions |
| `.env.example` | nouvelles variables — **obligatoire** : `test_conformite_exigences.py` échoue si une variable lue par le code n'y figure pas |
| `api/requirements.txt` | inchangé — aucune dépendance nouvelle côté frontend |
| `doc/V0/architecture.md`, `doc/V0/userstories_frontend.md`, `doc/V1/comptes-3-roles.md`, `doc/V1/roadmap.md` | contrats amendés |

---

## Risques et points de vigilance

1. **Le pseudo n'est pas une identité.** Tant qu'un compte n'a pas de code
   personnel, n'importe qui connaissant le mot de passe partagé peut l'occuper.
   Les propositions et commentaires d'un spectateur sont donc attribués « à titre
   indicatif ». La promotion referme la porte pour le compte promu, pas pour le
   passé.
2. **Diffamation.** Le site publiait déjà des verdicts automatisés nommant des
   médias — d'où l'authentification, posée comme condition bloquante (US-04
   frontend). Il publiera en plus des textes rédigés par des humains. Le retrait
   d'US-08 est nécessaire, pas suffisant : c'est le moment de rouvrir la question
   juridique laissée en attente dans `architecture.md`.
3. **Coût.** Chaque proposition acceptée consomme les appels réseau de
   l'évaluateur et, si elle dépasse le seuil, un appel LLM de contextualisation.
   Les plafonds existants (`EVALUATEUR_PLAFOND_ARTICLES`,
   `LLM_PLAFOND_CONTEXTUALISEUR`) s'appliquent — et la famine du reliquat
   décrite en phase 14 (F3) ferait passer les propositions **après** les articles
   les plus récents. F3 devrait être corrigé avant que la file serve vraiment.
4. **Le frontend grossit.** `app.py` fait déjà 630 lignes ; cette version y ajoute
   une dizaine de routes. Le découper (routeurs FastAPI par domaine) au moment où
   ça gêne, pas avant — mais le seuil approche.
5. **Attentes des utilisateurs.** Une file d'attente dont le pipeline est en pause
   ne produit rien de visible. Si des personnes réelles proposent des articles, il
   faudra soit déclencher les runs à la main, soit réactiver le `schedule` — c'est
   une décision d'exploitation, pas de code.

---

## Ordre de livraison recommandé

```
Phase 0 (F2, F4)  →  Phase 1 (identité, rôles, CSRF)  →  Phase 2 (propositions)
                                                              ↓
                                    Phase 4 (commentaires) ← Phase 3 (pipeline)
```

Les phases 3 et 4 sont indépendantes l'une de l'autre : la 4 peut passer avant la
3 si l'on veut de la participation visible plus tôt, au prix d'une file d'attente
qui ne débouche encore sur rien.

---

## État d'avancement

- **Phase 0** : **terminée le 2026-09-10**, sauf F3.
  - F1 (verdict de fact-checking non rattachable) corrigé — hors phase 0, traité
    à la suite de l'audit.
  - **F2** corrigé, en **deux** sites : la comparaison de `/login` et la
    validation de la signature du cookie, cette dernière découverte en préparant
    le correctif. L'écran de changement de code d'US-05 peut être écrit.
  - **F4** traité par un délai croissant sur les échecs plutôt que par un refus
    (qui aurait rouvert le déni de service de la phase 7) : 60 essais passent de
    0,10 s à 278 s, un mot de passe correct n'est jamais ralenti. Le mot de passe
    partagé peut recevoir un pouvoir d'écriture.
  - **F3** (famine du reliquat de l'évaluateur) reste ouvert. Il ne bloque pas la
    phase 1, mais doit être corrigé **avant la phase 3** : sinon un article
    proposé et accepté passe après les articles les plus récents de la collecte
    automatique, et peut n'être jamais analysé.
- **Phase 1 (identité et rôles opposables)** : **terminée le 2026-09-11.**
  Migration `0004` (contrainte étendue au contributeur, avec rattrapage),
  `exige_role` fondée sur un ORDRE de rôles, jeton anti-CSRF sur toutes les
  écritures, enregistrement du compte à la première connexion (US-07), écran
  superadmin de promotion/rétrogradation avec code provisoire affiché une fois
  (US-06), changement de code personnel (US-05). F15-02 (normalisation NFC) traité
  au passage : c'était le préalable annoncé à US-05.
- **Phase 2 (propositions et file d'attente)** : **terminée le 2026-09-11.**
  Migration `0005` (table `propositions`, index unique partiel sur les statuts
  vivants, valeur `proposition` ajoutée à `ck_articles_plateforme`), formulaire de
  proposition avec validation de schéma d'URL, déduplication contre `articles`
  puis contre la file, plafond par compte compté en base, file d'attente réservée
  aux contributeurs, acceptation et refus motivé.
  **33 tests dédiés** (`tests/test_crowdsourcing.py`), suite complète à
  **368 tests, 0 skip**.
- **Phase 3 (entrée dans le pipeline)** : **terminée le 2026-09-13.**
  - **F3 corrigé d'abord**, comme ce plan l'exigeait : `run_evaluateur` sélectionne
    désormais par `date_collecte` croissante — premier collecté, premier servi. Le
    tri par date de publication décroissante n'avait rien d'un report : au run
    suivant, les nouveautés repassaient devant et le reliquat était affamé
    définitivement. Vérifié : l'article dépassé est désormais noté au run suivant.
    Le journal dit maintenant la vérité, et nomme le cas qu'aucun tri ne règle —
    si le reliquat grossit d'un run à l'autre, l'ingestion dépasse la capacité.
  - `scraper/propositions.py` : collecte les propositions `acceptee`, les plus
    anciennement acceptées d'abord, plafonnée par `PROPOSITIONS_PLAFOND_COLLECTE`.
    Réutilise `_telecharger` (timeout, User-Agent), `nettoyer_html`,
    `canonicaliser_url` et `hacher_contenu` — il ne restait à écrire que
    l'extraction du titre et de la date, et la mise à jour du statut.
  - Sécurité : schéma `http(s)` **revalidé ici** (c'est ici qu'on ouvre la
    connexion), lecture bornée à 2 Mo, timeout explicite, et surtout collecte
    faite dans le runner GitHub Actions — jamais depuis Vercel.
  - Repli de date : `date_publication` est NOT NULL, donc une page sans date
    déclarée retombe sur la date de proposition, **avec une trace en métadonnée**
    (`date_publication_estimee`). La limite est lisible dans la donnée, pas
    seulement dans un commentaire.
  - Branché dans `pipeline_hebdomadaire.yml` **avant** l'évaluateur, pour qu'un
    article accepté soit noté dans le même run. Le `schedule` reste commenté.
  - **14 tests dédiés** (`tests/test_collecte_propositions.py`), dont un parcours
    complet proposition → collecte → score. Suite : **395 tests, 0 skip**.
- **Phase 4 (commentaires)** : **terminée le 2026-09-13.**
  Migration `0007` (table `commentaires`, contrainte de texte non vide, contrainte
  « un retrait trace toujours qui et quand »), publication par tout compte
  connecté, affichage sur la page de détail **sous** l'analyse et visuellement
  séparé, retrait par le superadmin, plafond par compte compté en base.
  - **Le retrait masque, il n'efface pas.** `retire_le is null` est la condition
    d'affichage public ; le superadmin continue de voir le contenu, son auteur, sa
    date, et qui l'a retiré. Sur un site qui publie des verdicts nommant des
    médias, un contenu retiré pour raison juridique doit rester consultable par le
    porteur du projet.
  - **Non-objectif tenu et testé :** les commentaires n'influencent pas le score.
    Un test vérifie que `score_final` et `sous_scores` sont inchangés après trois
    commentaires contestataires.
  - **19 tests dédiés** (`tests/test_commentaires.py`). Suite : **421 tests,
    0 skip**.

### Reste à faire

- **Découper `app.py`** (~1400 lignes, six domaines). Signalé aux audits 17, 18 et
  20 ; volontairement NON fait pendant la phase 4, pour qu'une régression de
  refactorisation ne se confonde pas avec une régression de fonctionnalité. La
  suite de tests est désormais assez fournie pour sécuriser l'extraction.
- **Modération a priori** des commentaires : écartée au cadrage (2026-09-10), à
  rouvrir si le volume ou le contenu l'exige.
- **RGPD** : les commentaires sont du texte rédigé par des personnes identifiables
  par leur pseudo, conservé sans durée définie. `architecture.md` classe le sujet
  hors périmètre prototype ; le mécanisme de retrait en est le premier élément
  concret, pas le dernier.

### Écarts assumés par rapport au plan initial

- **`canonicaliser_url` a déménagé** de `fakenews.scraper.normalisation` vers
  `fakenews.normalisation`. Le frontend doit canonicaliser exactement comme le
  scraper pour que la déduplication compare quelque chose, et
  `doc/V0/architecture.md` interdit qu'il importe un bloc métier. Même dilemme que
  le seuil de suspicion, même issue : un module d'infrastructure neutre. La
  duplication était exclue — deux implémentations qui divergent d'un caractère
  font diverger toute la déduplication.
- **Un contexte de gabarit commun** (`_contexte`) remplace les dictionnaires
  recopiés dans chaque route, pour que la navigation et l'avertissement ne
  dépendent pas de la vigilance de la prochaine route ajoutée.
- **Refus en 404, pas en 403**, sur les pages réservées : un spectateur n'a pas à
  apprendre que la file de modération existe.
