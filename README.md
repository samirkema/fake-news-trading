# Fake News & Trading Algorithmique

[![Pipeline hebdomadaire](https://github.com/samirkema/fake-news-trading/actions/workflows/pipeline_hebdomadaire.yml/badge.svg)](https://github.com/samirkema/fake-news-trading/actions/workflows/pipeline_hebdomadaire.yml)

Bibliothèque IA qui détecte les fake news et attribue un score de suspicion (0 = fiable, 100 = très suspect) à des articles collectés chaque semaine (RSS + Reddit), avant d'envisager un usage comme signal pour des stratégies de trading algorithmique.

> ⚠️ Prototype en développement actif. Les scores et mises en contexte produits sont générés automatiquement et ne constituent pas un verdict éditorial définitif — voir [doc/architecture.md](doc/architecture.md) pour les limites assumées.

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

Détails complets : [doc/architecture.md](doc/architecture.md) et [doc/plan_implementation.md](doc/plan_implementation.md) (section "État d'avancement" tenue à jour à chaque étape livrée).

## État actuel

- **Scraper** : collecte RSS et Reddit opérationnelle, déduplication, planification hebdomadaire.
- **Évaluateur** : score composite + signaux réputation, fact-checking, source primaire, style, LLM bootstrap (Claude). Corroboration croisée et décalage viral restent à implémenter (nécessitent une brique de clustering commune).
- **Contextualiseur** : déclenchement, génération réelle (Claude), validation des preuves et persistance en place.
- **Frontend** : liste filtrable/paginée des articles suspects, détail des scores, mise en contexte.
- **Automatisation** : les trois premiers blocs sont orchestrés en un workflow GitHub Actions hebdomadaire (`.github/workflows/pipeline_hebdomadaire.yml`).

Historique des audits menés sur ce projet : [audit/](audit/).

## Installation

Prérequis : Python 3.12+, une base PostgreSQL (locale pour le développement, [Supabase](https://supabase.com) en production).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm  # US-04 évaluateur : extraction d'entreprises (NER)
```

Copier `.env.example` en `.env` et renseigner :

- `DATABASE_URL` — chaîne de connexion PostgreSQL/Supabase
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — identifiants d'une [app Reddit de type "script"](https://reddit.com/prefs/apps) (gratuit ; optionnel, la collecte Reddit dégrade proprement si absent)
- `GOOGLE_FACT_CHECK_API_KEY` — optionnel, US-03 évaluateur dégrade proprement si absente
- `FRONTEND_PASSWORD` — uniquement en déploiement hébergé public (voir [doc/userstories_frontend.md](doc/userstories_frontend.md))

Appliquer le schéma de base de données :

```bash
psql "$DATABASE_URL" -f supabase/migrations/0001_init_schema.sql
```

## Lancer les tests

```bash
export TEST_DATABASE_URL="postgresql+psycopg2://localhost:5432/une_base_de_test_dediee"
pytest tests/ -v
```

Sans `TEST_DATABASE_URL`, les tests purs (sans dépendance base de données) tournent quand même ; les tests contre une vraie base sont ignorés (`skip`) proprement.

**Ne pas réutiliser une base de développement contenant déjà des données réelles** pour `TEST_DATABASE_URL` — utiliser une base dédiée et vide (cf. [audit/audit-phase5-automatisation.md](audit/audit-phase5-automatisation.md) pour le pourquoi).

## Lancer chaque bloc localement

```bash
export PYTHONPATH=src

python -m fakenews.scraper.run_scraper          # RSS + Reddit
python -m fakenews.evaluateur.run_evaluateur     # calcule les scores manquants
python -m fakenews.contextualiseur.run_contextualiseur  # sélectionne et journalise (pas de génération LLM pour l'instant)

uvicorn fakenews.frontend.app:app --reload       # frontend, http://localhost:8000
```

## Déploiement

- **Stockage** : Supabase (PostgreSQL managé).
- **Pipeline hebdomadaire** : GitHub Actions (`.github/workflows/pipeline_hebdomadaire.yml`), planifié le lundi. Secrets à configurer dans *Settings → Secrets and variables → Actions* du dépôt.
- **Frontend** : Vercel (`vercel.json` + `api/index.py`), lecture seule.

Détails : [doc/architecture.md](doc/architecture.md), section "Topologie de déploiement".

## Documentation

- [doc/fiche-projet-fake-news-trading.md](doc/fiche-projet-fake-news-trading.md) — objectifs et décisions du projet
- [doc/architecture.md](doc/architecture.md) — décisions d'architecture et leurs justifications
- [doc/plan_implementation.md](doc/plan_implementation.md) — séquencement et état d'avancement
- [doc/userstories_scraper.md](doc/userstories_scraper.md), [userstories_évaluateur.md](doc/userstories_évaluateur.md), [userstories_contextualiseur.md](doc/userstories_contextualiseur.md), [userstories_frontend.md](doc/userstories_frontend.md) — user stories détaillées par bloc
- [audit/](audit/) — audits de suivi (qualité, sécurité, conformité aux exigences)

## Licence

[MIT](LICENSE)
