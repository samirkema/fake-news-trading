"""Point d'entrée du contextualiseur : sélectionne les articles à traiter (US-01
contextualiseur) et journalise la sélection. La génération réelle par LLM (cœur de
US-02) n'est PAS branchée ici — bloquée sur le choix du fournisseur (hors périmètre,
décision non prise, cf. doc/userstories_contextualiseur.md) et sur des signaux
évaluateur plus riches à citer (fact-checking, source primaire, non implémentés).
Ce script prépare la sélection pour que la génération puisse être ajoutée plus tard
sans retoucher le reste du pipeline."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.contextualiseur.declenchement import articles_a_traiter
from fakenews.db import SessionLocal
from fakenews.models import MiseEnContexte, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def selectionner_articles_a_traiter(session: Session) -> list[dict]:
    """Articles scorés n'ayant pas encore de mise en contexte, filtrés/triés/plafonnés
    par articles_a_traiter (US-01 contextualiseur)."""
    scores = (
        session.execute(
            select(Score).outerjoin(MiseEnContexte, MiseEnContexte.article_id == Score.article_id).where(
                MiseEnContexte.id.is_(None)
            )
        )
        .scalars()
        .all()
    )
    candidats = [
        {"article_id": s.article_id, "score_final": s.score_final, "non_evaluable": s.non_evaluable}
        for s in scores
    ]
    return articles_a_traiter(candidats)


def main():
    with SessionLocal() as session:
        selection = selectionner_articles_a_traiter(session)

    if selection:
        logger.warning(
            "%d article(s) sélectionné(s) pour mise en contexte, mais la génération LLM "
            "n'est pas encore branchée (fournisseur non choisi) — aucune mise en contexte "
            "générée cette semaine.",
            len(selection),
        )
    else:
        logger.info("Aucun article au-dessus du seuil à traiter cette semaine.")


if __name__ == "__main__":
    main()
