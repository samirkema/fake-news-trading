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


# Le backfill ne charge plus toute la table `scores` en mémoire d'un coup
# (cf. audit, finding M10) : le filtre porte sur du JSONB, donc il reste côté
# Python, mais l'itération se fait par lots.
TAILLE_LOT = 200


def backfiller_llm_bootstrap(session: Session, client=None) -> int:
    if client is None:
        # Même protection que run_evaluateur : ANTHROPIC_API_KEY absente ne doit pas
        # produire une trace brute d'exception (cf. audit, finding M12).
        try:
            client = creer_client()
        except Exception as exc:
            logger.error("Backfill LLM impossible — client indisponible (%s).", exc)
            return 0

    nb_traites = 0
    decalage = 0
    while True:
        lot = (
            session.execute(select(Score).order_by(Score.id).limit(TAILLE_LOT).offset(decalage))
            .scalars()
            .all()
        )
        if not lot:
            break
        decalage += len(lot)
        for score in lot:
            if not _sans_llm_valide(score):
                continue
            article = session.get(Article, score.article_id)
            if article is None:
                logger.warning("Score %s orphelin (article absent) — ignoré.", score.id)
                continue
            resultat = evaluer_llm_bootstrap(article.titre, article.contenu, client=client)

            # Réassignation (pas mutation en place) pour que SQLAlchemy détecte le
            # changement sur la colonne JSONB sans flag_modified explicite.
            score.sous_scores = {**score.sous_scores, "llm_bootstrap": resultat}
            recalcul = calculer_score_composite(score.sous_scores, POIDS_PAR_DEFAUT)
            # Fusion, pas écrasement : remplacer `poids` par POIDS_PAR_DEFAUT
            # effaçait la trace des poids réellement appliqués au calcul d'origine,
            # que models.py documente comme la raison d'être de la colonne
            # (cf. audit, finding M10).
            score.poids = {
                **(score.poids or {}),
                **{s: POIDS_PAR_DEFAUT.get(s, 0.0) for s in score.sous_scores},
            }
            score.detail_calcul = recalcul["detail"]
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
