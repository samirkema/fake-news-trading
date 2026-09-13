# Fake News & Trading Algorithmique

[![CI](https://github.com/samirkema/fake-news-trading/actions/workflows/ci.yml/badge.svg)](https://github.com/samirkema/fake-news-trading/actions/workflows/ci.yml)

Bibliothèque IA qui détecte les fake news et attribue un score de suspicion (0 = fiable, 100 = très suspect) à des articles collectés chaque semaine (RSS + Reddit), avant d'envisager un usage comme signal pour des stratégies de trading algorithmique.

> ⚠️ Prototype en développement actif. Les scores et mises en contexte produits sont générés automatiquement et ne constituent pas un verdict éditorial définitif — voir [doc/V0/architecture.md](doc/V0/architecture.md) pour les limites assumées.

## Architecture

Quatre blocs indépendants, communiquant uniquement via un stockage partagé (PostgreSQL/Supabase) — jamais d'appel direct entre blocs :

```
Scraper  -->  Évaluateur  -->  Contextualiseur  -->  Frontend
   |               |                  |                 |
   +---------------+------------------+-----------------+
                            |
              Stockage partagé (Supabase / PostgreSQL)
```

| Bloc | Rôle |
|---|---|
| **Scraper** | Collecte RSS + Reddit, déduplication, normalisation |
| **Évaluateur** | Calcule des signaux de fiabilité et un score composite 0-100 |
| **Contextualiseur** | Génère une explication pour les articles jugés suspects |
| **Frontend** | Consultation en lecture seule (FastAPI + Jinja2) |

Détails complets : [doc/V0/architecture.md](doc/V0/architecture.md) et [doc/V0/plan_implementation.md](doc/V0/plan_implementation.md) (section "État d'avancement" tenue à jour à chaque étape livrée).

## État actuel

- **Scraper** : collecte RSS et Reddit opérationnelle, déduplication, orchestration hebdomadaire écrite (déclenchement automatique en pause, voir ci-dessous).
- **Évaluateur** : score composite + signaux réputation, fact-checking, source primaire, style, LLM bootstrap (Claude). Corroboration croisée et décalage viral restent à implémenter (nécessitent une brique de clustering commune).
- **Contextualiseur** : déclenchement, génération réelle (Claude), validation des preuves et persistance en place.
- **Frontend** : liste filtrable/paginée des articles suspects, détail des scores, mise en contexte.
- **Crowdsourcing (V3, phases 1-2)** : tout compte connecté peut proposer un article ; les contributeurs disposent d'une file d'attente pour accepter ou refuser ; le superadmin nomme les contributeurs ; chacun gère son code personnel depuis son espace compte ; tout compte connecté peut commenter l'analyse d'un article, le superadmin pouvant retirer un commentaire sans l'effacer. Une proposition acceptée est collectée puis notée par le pipeline (`python -m fakenews.scraper.propositions`, branché avant l'évaluateur). ⚠️ **Le pipeline hebdomadaire restant en pause**, cela n'arrive qu'au déclenchement manuel du workflow — l'interface l'annonce telle quelle (« acceptée — en attente d'analyse », sans promettre d'échéance : l'article entre en file derrière le reliquat de l'évaluateur). Voir [doc/V3/](doc/V3/).
- **Automatisation** : les trois premiers blocs sont orchestrés en un workflow GitHub Actions (`.github/workflows/pipeline_hebdomadaire.yml`). ⚠️ **Le déclenchement automatique est actuellement désactivé** (projet en pause : le `schedule` est commenté pour ne pas consommer la clé Anthropic). Le workflow ne tourne que sur déclenchement manuel — les données ne se rafraîchissent donc pas toutes seules.
- **CI** : `.github/workflows/ci.yml` lance la suite de tests sur chaque push et chaque PR, contre un vrai Postgres avec les migrations appliquées, et échoue si un test est skippé.

Deux familles de tests jouent des rôles distincts, à ne pas confondre :

| Fichier | Ce qu'il garde |
|---|---|
| `tests/test_correctifs_audit.py` | les correctifs d'audit **déjà passés** — anti-régression |
| `tests/test_conformite_exigences.py` | une sélection de **critères d'acceptation critiques** (seuils configurables, plafonds, auth fail-closed) |
| `tests/test_signaux_corpus_reel.py` + `tests/corpus/` | les signaux face à des **entrées réelles** (verdicts de fact-checkers, titres de presse, HTML de flux) |

La troisième famille existe parce que les défauts les plus graves trouvés jusqu'ici étaient invisibles aux fixtures synthétiques : `"False"` et `"True"` passaient, c'est `"Inaccurate"` qui inversait le verdict.

Historique des audits menés sur ce projet : [doc/audit/](doc/audit/).

## Installation

Prérequis : Python 3.12+, une base PostgreSQL (locale pour le développement, [Supabase](https://supabase.com) en production).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Modèle NER pour US-04 évaluateur, version épinglée (même que la CI et le pipeline).
pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

`requirements.txt` couvre le pipeline batch et les tests. Le frontend déployé sur Vercel utilise `api/requirements.txt`, volontairement réduit à FastAPI + Jinja2 + SQLAlchemy.

Copier `.env.example` en `.env` et renseigner :

- `DATABASE_URL` — chaîne de connexion PostgreSQL/Supabase
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — identifiants d'une [app Reddit de type "script"](https://reddit.com/prefs/apps) (gratuit ; optionnel, la collecte Reddit dégrade proprement si absent)
- `GOOGLE_FACT_CHECK_API_KEY` — optionnel, US-03 évaluateur dégrade proprement si absente
- `FRONTEND_PASSWORD` — mot de passe partagé, obligatoire en déploiement hébergé. **Non défini = accès refusé**, pas « accès libre » : le défaut est fermé. À la connexion l'utilisateur saisit aussi un pseudo qui détermine son rôle via la table `comptes` (fondation V1, voir [doc/V1/comptes-3-roles.md](doc/V1/comptes-3-roles.md))
- `FAKENEWS_MODE=local` — développement uniquement, désactive l'authentification du frontend. À ne jamais définir en hébergé
- `FAKENEWS_PROXYS_DE_CONFIANCE` — nombre de proxys devant l'application, pour le plafond anti-bruteforce de `/login`. **`1` sur Vercel** ; non définie ailleurs tant que la topologie n'a pas été constatée (`X-Forwarded-For` est alors ignoré, ce qui est le défaut sûr)
- `CONTEXTUALISEUR_SEUIL` — seuil de suspicion 0-100 (défaut `60`). **Lu par le contextualiseur ET par le frontend** : les régler différemment ferait lister des articles dont la mise en contexte n'a jamais été demandée. Une valeur hors bornes fait échouer le démarrage plutôt que de vider la liste en silence
- `LLM_PLAFOND_EVALUATEUR` — appels LLM de l'évaluateur par run (défaut `50`)
- `EVALUATEUR_PLAFOND_ARTICLES` — articles évalués par run (défaut `300`)
- `LLM_PLAFOND_CONTEXTUALISEUR` — appels LLM du contextualiseur par run (défaut `20`), distinct de `LLM_PLAFOND_EVALUATEUR` : un appel d'explication coûte plus cher qu'un appel de scoring court
- `LLM_PLAFOND_BACKFILL` — appels LLM des scripts de backfill (défaut `100`)
- `PROPOSITIONS_MAX_PAR_JOUR` — propositions d'articles par compte sur 24 h (défaut `10`, V3 crowdsourcing)
- `PROPOSITIONS_PLAFOND_COLLECTE` — propositions acceptées collectées par run (défaut `20`)
- `COMMENTAIRES_MAX_PAR_JOUR` — commentaires par compte sur 24 h (défaut `20`)
- `LLM_MODELE` — modèle Claude utilisé pour le scoring et la génération (défaut `claude-haiku-4-5-20251001`)
- `SEC_EDGAR_USER_AGENT` — User-Agent déclaré pour l'API SEC EDGAR (`NomApp/1.0 (contact@example.com)`)

Appliquer le schéma de base de données (migrations dans l'ordre) :

```bash
psql "$DATABASE_URL" -f supabase/migrations/0001_init_schema.sql
psql "$DATABASE_URL" -f supabase/migrations/0002_comptes.sql
psql "$DATABASE_URL" -f supabase/migrations/0003_scores_detail_calcul.sql
psql "$DATABASE_URL" -f supabase/migrations/0004_comptes_role_privilegie.sql
psql "$DATABASE_URL" -f supabase/migrations/0005_propositions.sql
psql "$DATABASE_URL" -f supabase/migrations/0006_index_date_collecte.sql
psql "$DATABASE_URL" -f supabase/migrations/0007_commentaires.sql
```

Depuis la `0004`, **aucun rôle privilégié ne peut exister sans code personnel** :
un `contributeur` décide quels articles entrent dans la base, ce pouvoir ne doit
pas appartenir à quiconque connaît le mot de passe partagé. La migration pose un
code aléatoire aux contributeurs déjà présents — ils en redemandent un.

La migration `0002` crée le compte superadmin avec un code personnel **aléatoire et inconnu** : personne ne peut s'y connecter tant que le vrai code n'a pas été posé (la commande est en commentaire à la fin du fichier). C'est volontaire — un superadmin sans code personnel serait accessible avec le simple mot de passe partagé.

## Lancer les tests

```bash
export TEST_DATABASE_URL="postgresql+psycopg2://localhost:5432/une_base_de_test_dediee"
psql "$TEST_DATABASE_URL" -f supabase/migrations/0001_init_schema.sql   # + 0002, 0003
pytest -v
```

Sans `TEST_DATABASE_URL`, les tests purs tournent quand même et les tests contre une vraie base sont ignorés (`skip`). **Ce n'est pas un mode acceptable pour valider une modification** : ces skips représentaient 43 % de la suite (toute l'authentification, tout le frontend, toute la persistance) et donnaient un vert trompeur. La CI définit toujours `TEST_DATABASE_URL` et échoue si un test est skippé.

**Ne pas réutiliser une base de développement contenant déjà des données réelles** pour `TEST_DATABASE_URL` — utiliser une base dédiée et vide (cf. [audit/audit-phase5-automatisation.md](doc/audit/audit-phase5-automatisation.md) pour le pourquoi).

## Lancer chaque bloc localement

```bash
export PYTHONPATH=src

python -m fakenews.scraper.run_scraper          # RSS + Reddit
python -m fakenews.scraper.propositions          # articles proposés et acceptés (V3)
python -m fakenews.evaluateur.run_evaluateur     # calcule les scores manquants
python -m fakenews.contextualiseur.run_contextualiseur  # sélectionne, génère (Claude) et persiste

# Frontend. FAKENEWS_MODE=local désactive l'authentification — mode développement
# UNIQUEMENT : sans lui, l'accès est refusé tant que FRONTEND_PASSWORD n'est pas défini.
FAKENEWS_MODE=local uvicorn fakenews.frontend.app:app --reload   # http://localhost:8000
```

## Déploiement

- **Stockage** : Supabase (PostgreSQL managé).
- **Pipeline hebdomadaire** : GitHub Actions (`.github/workflows/pipeline_hebdomadaire.yml`). Le `schedule` du lundi est **commenté** (projet en pause) : seul le déclenchement manuel fonctionne. Secrets à configurer dans *Settings → Secrets and variables → Actions* du dépôt.
- **Frontend** : Vercel (`vercel.json` + `api/index.py`), lecture seule. Variables à définir dans *Settings → Environment Variables* du projet Vercel : `DATABASE_URL`, `FRONTEND_PASSWORD`, et `FAKENEWS_PROXYS_DE_CONFIANCE=1` (cf. [Installation](#installation)). Ne **jamais** y définir `FAKENEWS_MODE`.

### Ordre de déploiement : les migrations d'abord

**Appliquer les migrations avant de déployer le code, toujours.** Les deux partent par des canaux séparés — le code par `git push`, le schéma à la main — et rien ne les synchronise. L'écart n'a pas le même coût dans les deux sens :

| Situation | Conséquence |
|---|---|
| Schéma en avance sur le code | inoffensif — l'ancien code ignore ce qu'il ne déclare pas |
| **Code en avance sur le schéma** | **panne totale** — toute page lisant des scores renvoie 500 |

Depuis l'audit de phase 9, le second cas échoue au démarrage avec un message nommant la colonne manquante (`fakenews.schema`) plutôt que par une erreur SQL opaque sur chaque page. Le garde-fou rend l'erreur visible ; il ne dispense pas de l'ordre.

À savoir aussi : déployer une version qui change le format du cookie de session **déconnecte tout le monde**. C'est le cas du passage au format `pseudo:expiration:signature` — les sessions ouvertes redirigent vers `/login`, il suffit de se reconnecter.

Détails : [doc/V0/architecture.md](doc/V0/architecture.md), section "Topologie de déploiement".

## Documentation

- [doc/V0/fiche-projet-fake-news-trading.md](doc/V0/fiche-projet-fake-news-trading.md) — objectifs et décisions du projet
- [doc/V0/architecture.md](doc/V0/architecture.md) — décisions d'architecture et leurs justifications
- [doc/V0/plan_implementation.md](doc/V0/plan_implementation.md) — séquencement et état d'avancement
- [doc/V0/userstories_scraper.md](doc/V0/userstories_scraper.md), [doc/V0/userstories_évaluateur.md](doc/V0/userstories_évaluateur.md), [doc/V0/userstories_contextualiseur.md](doc/V0/userstories_contextualiseur.md), [doc/V0/userstories_frontend.md](doc/V0/userstories_frontend.md) — user stories détaillées par bloc
- [doc/audit/](doc/audit/) — audits de suivi (qualité, sécurité, conformité aux exigences), du plus ancien au plus récent

## Licence

[MIT](LICENSE)
