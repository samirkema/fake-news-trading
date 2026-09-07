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
- **Automatisation** : les trois premiers blocs sont orchestrés en un workflow GitHub Actions (`.github/workflows/pipeline_hebdomadaire.yml`). ⚠️ **Le déclenchement automatique est actuellement désactivé** (projet en pause : le `schedule` est commenté pour ne pas consommer la clé Anthropic). Le workflow ne tourne que sur déclenchement manuel — les données ne se rafraîchissent donc pas toutes seules.
- **CI** : `.github/workflows/ci.yml` lance la suite de tests sur chaque push et chaque PR, contre un vrai Postgres avec les migrations appliquées, et échoue si un test est skippé.

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

Appliquer le schéma de base de données (migrations dans l'ordre) :

```bash
psql "$DATABASE_URL" -f supabase/migrations/0001_init_schema.sql
psql "$DATABASE_URL" -f supabase/migrations/0002_comptes.sql
psql "$DATABASE_URL" -f supabase/migrations/0003_scores_detail_calcul.sql
```

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
