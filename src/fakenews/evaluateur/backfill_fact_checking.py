"""Correctif ponctuel, pas un composant du pipeline hebdomadaire : recalcule le
signal fact_checking (US-03) pour les scores déjà calculés dont ce signal est exclu
(cf. doc/architecture.md, "pas de rescoring en v1"). Exception assumée et
strictement scopée à ce seul signal, pour rattraper une fenêtre où
GOOGLE_FACT_CHECK_API_KEY n'était pas encore configurée au moment des runs initiaux
— ne remplace pas le principe général de non-rescoring, qui reste en vigueur pour
tous les autres signaux et pour les runs futurs (cf. backfill_llm_bootstrap.py, même
logique appliquée au signal llm_bootstrap)."""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.db import SessionLocal
from fakenews.evaluateur.fact_checking import evaluer_fact_checking
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.models import Article, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _sans_fact_checking_valide(score: Score) -> bool:
    signal = score.sous_scores.get("fact_checking")
    return signal is None or signal.get("valeur") is None


def backfiller_fact_checking(session: Session, client: httpx.Client | None = None) -> int:
    scores = session.execute(select(Score)).scalars().all()
    a_traiter = [s for s in scores if _sans_fact_checking_valide(s)]
    logger.info("%d score(s) sans signal fact_checking valide sur %d au total", len(a_traiter), len(scores))
    if not a_traiter:
        return 0

    ferme_client = client is None
    client = client or httpx.Client(timeout=10.0)
    nb_traites = 0
    try:
        for score in a_traiter:
            article = session.get(Article, score.article_id)
            resultat = evaluer_fact_checking(article.titre, client=client)

            # Réassignation (pas mutation en place) pour que SQLAlchemy détecte le
            # changement sur la colonne JSONB sans flag_modified explicite.
            score.sous_scores = {**score.sous_scores, "fact_checking": resultat}
            recalcul = calculer_score_composite(score.sous_scores, POIDS_PAR_DEFAUT)
            score.poids = {signal: POIDS_PAR_DEFAUT[signal] for signal in score.sous_scores}
            score.score_final = recalcul["score_final"]
            score.non_evaluable = recalcul["non_evaluable"]
            nb_traites += 1
    finally:
        if ferme_client:
            client.close()

    session.commit()
    logger.info("%d score(s) mis à jour avec un signal fact_checking valide", nb_traites)
    return nb_traites


def main():
    with SessionLocal() as session:
        backfiller_fact_checking(session)


if __name__ == "__main__":
    main()
