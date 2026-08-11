"""Correctif ponctuel, pas un composant du pipeline hebdomadaire : recalcule le
signal llm_bootstrap (US-07) pour les scores déjà calculés qui ne l'ont jamais reçu
ou qui l'ont reçu exclu suite à un appel raté (cf. doc/architecture.md, "pas de
rescoring en v1"). Exception assumée et strictement scopée à ce seul signal, pour
rattraper une fenêtre où ANTHROPIC_API_KEY n'était pas encore configurée au moment
du run initial — ne remplace pas le principe général de non-rescoring, qui reste en
vigueur pour tous les autres signaux et pour les runs futurs."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.db import SessionLocal
from fakenews.evaluateur.llm_bootstrap import evaluer_llm_bootstrap
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.llm import creer_client
from fakenews.models import Article, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _sans_llm_valide(score: Score) -> bool:
    signal = score.sous_scores.get("llm_bootstrap")
    return signal is None or signal.get("valeur") is None


def backfiller_llm_bootstrap(session: Session, client=None) -> int:
    scores = session.execute(select(Score)).scalars().all()
    a_traiter = [s for s in scores if _sans_llm_valide(s)]
    logger.info("%d score(s) sans signal LLM valide sur %d au total", len(a_traiter), len(scores))
    if not a_traiter:
        return 0

    client = client or creer_client()
    nb_traites = 0
    for score in a_traiter:
        article = session.get(Article, score.article_id)
        resultat = evaluer_llm_bootstrap(article.titre, article.contenu, client=client)

        # Réassignation (pas mutation en place) pour que SQLAlchemy détecte le
        # changement sur la colonne JSONB sans flag_modified explicite.
        score.sous_scores = {**score.sous_scores, "llm_bootstrap": resultat}
        recalcul = calculer_score_composite(score.sous_scores, POIDS_PAR_DEFAUT)
        score.poids = {signal: POIDS_PAR_DEFAUT[signal] for signal in score.sous_scores}
        score.score_final = recalcul["score_final"]
        score.non_evaluable = recalcul["non_evaluable"]
        nb_traites += 1

    session.commit()
    logger.info("%d score(s) mis à jour avec un signal llm_bootstrap valide", nb_traites)
    return nb_traites


def main():
    with SessionLocal() as session:
        backfiller_llm_bootstrap(session)


if __name__ == "__main__":
    main()
