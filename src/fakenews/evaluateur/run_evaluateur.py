"""Point d'entrée de l'évaluateur : calcule les signaux disponibles pour les articles
pas encore scorés, et persiste le score composite (US-08). Seul US-01 (réputation) est
implémenté pour l'instant — `sous_scores` ne contient que les signaux réellement
calculés, pas d'entrées factices pour US-02 à US-07 (non implémentées)."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.db import SessionLocal
from fakenews.evaluateur.reputation import evaluer_reputation
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.models import Article, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def evaluer_articles_non_scores(session: Session) -> int:
    articles = (
        session.execute(
            select(Article).outerjoin(Score, Score.article_id == Article.id).where(Score.id.is_(None))
        )
        .scalars()
        .all()
    )

    for article in articles:
        sous_scores = {"reputation": evaluer_reputation(article.domaine_source)}
        resultat = calculer_score_composite(sous_scores, POIDS_PAR_DEFAUT)
        poids_utilises = {signal: POIDS_PAR_DEFAUT[signal] for signal in sous_scores}

        session.add(
            Score(
                article_id=article.id,
                sous_scores=sous_scores,
                poids=poids_utilises,
                score_final=resultat["score_final"],
                non_evaluable=resultat["non_evaluable"],
            )
        )

    session.commit()
    logger.info("%d article(s) évalué(s)", len(articles))
    return len(articles)


def main():
    with SessionLocal() as session:
        evaluer_articles_non_scores(session)


if __name__ == "__main__":
    main()
