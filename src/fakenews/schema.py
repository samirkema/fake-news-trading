"""Contrôle de cohérence entre le schéma déclaré (`fakenews.models`) et le schéma
réellement présent en base.

Raison d'être (cf. doc/audit, phase 9, finding High) : le code et le schéma sont
deux artefacts déployés par deux canaux distincts — le code part par `git push`
vers Vercel, les migrations sont appliquées à la main dans l'éditeur Supabase.
Rien ne séquence les deux. Déployer un code en avance sur sa migration éteignait
le site sans le dire : `models.Score` déclare `detail_calcul`, SQLAlchemy
l'inclut dans chaque SELECT, et toute page lisant des scores renvoyait 500 avec
un `ProgrammingError` opaque — vérifié par exécution.

Ce module ne rend pas l'erreur impossible ; il la rend impossible à rater.
"""

import logging

from sqlalchemy import inspect

from fakenews.models import Base

logger = logging.getLogger(__name__)


class SchemaIncomplet(RuntimeError):
    """La base ne porte pas toutes les colonnes que le code attend."""


def colonnes_manquantes(engine) -> dict[str, list[str]]:
    """{table: [colonnes déclarées par le code et absentes de la base]}.

    Ne signale que ce qui MANQUE. Une colonne présente en base mais inconnue du
    code est le sens d'écart inoffensif — un schéma en avance ne gêne personne,
    c'est d'ailleurs l'ordre de déploiement recommandé."""
    inspecteur = inspect(engine)
    presentes = set(inspecteur.get_table_names())
    manquantes: dict[str, list[str]] = {}

    for table in Base.metadata.sorted_tables:
        if table.name not in presentes:
            manquantes[table.name] = ["(table absente)"]
            continue
        en_base = {c["name"] for c in inspecteur.get_columns(table.name)}
        absentes = [c.name for c in table.columns if c.name not in en_base]
        if absentes:
            manquantes[table.name] = absentes

    return manquantes


def verifier_schema(engine) -> None:
    """Lève `SchemaIncomplet` avec un message actionnable si une colonne attendue
    par le code n'existe pas en base.

    Si l'introspection elle-même échoue (droits insuffisants, base momentanément
    injoignable), on journalise et on laisse passer : ce garde-fou est là pour
    diagnostiquer une erreur de déploiement, pas pour créer un nouveau mode de
    panne."""
    try:
        manquantes = colonnes_manquantes(engine)
    except Exception as exc:
        logger.warning(
            "Vérification du schéma impossible (%s) — poursuite sans contrôle.",
            type(exc).__name__,
        )
        return

    if not manquantes:
        return

    detail = "\n".join(f"  - {table} : {', '.join(cols)}" for table, cols in sorted(manquantes.items()))
    raise SchemaIncomplet(
        "La base ne correspond pas au code déployé : des colonnes attendues sont "
        "absentes.\n"
        f"{detail}\n"
        "Appliquer les migrations de supabase/migrations/ (dans l'ordre) AVANT de "
        "déployer ce code. Les migrations passent toujours en premier : un schéma "
        "en avance sur le code est inoffensif, l'inverse met le site à terre."
    )
