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


# Itération par lots plutôt qu'un `select(Score)` intégral en mémoire
# (cf. audit, finding M10) : le filtre porte sur du JSONB, donc il reste côté Python.
TAILLE_LOT = 200


def backfiller_fact_checking(session: Session, client: httpx.Client | None = None) -> int:
    ferme_client = client is None
    client = client or httpx.Client(timeout=10.0)
    nb_traites = 0
    nb_valides = 0
    decalage = 0
    try:
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
                if not _sans_fact_checking_valide(score):
                    continue
                article = session.get(Article, score.article_id)
                if article is None:
                    logger.warning("Score %s orphelin (article absent) — ignoré.", score.id)
                    continue
                resultat = evaluer_fact_checking(article.titre, client=client)

                # Réassignation (pas mutation en place) pour que SQLAlchemy détecte le
                # changement sur la colonne JSONB sans flag_modified explicite.
                score.sous_scores = {**score.sous_scores, "fact_checking": resultat}
                recalcul = calculer_score_composite(score.sous_scores, POIDS_PAR_DEFAUT)
                # Fusion, pas écrasement : `poids` trace les poids réellement
                # appliqués, y compris ceux d'un calcul antérieur (finding M10).
                score.poids = {
                    **(score.poids or {}),
                    **{s: POIDS_PAR_DEFAUT.get(s, 0.0) for s in score.sous_scores},
                }
                score.detail_calcul = recalcul["detail"]
                score.score_final = recalcul["score_final"]
                score.non_evaluable = recalcul["non_evaluable"]
                nb_traites += 1
                # Clé absente, API indisponible ou aucune correspondance : le signal
                # est réécrit mais reste exclu. Les compter comme « valides » faisait
                # annoncer un rattrapage réussi après N échecs (cf. audit phase 10).
                if resultat.get("valeur") is not None:
                    nb_valides += 1
    finally:
        if ferme_client:
            client.close()

    session.commit()
    logger.info(
        "%d score(s) réévalué(s), dont %d ont produit un signal fact_checking "
        "exploitable (%d sans correspondance ou en échec, signal resté exclu).",
        nb_traites, nb_valides, nb_traites - nb_valides,
    )
    return nb_traites


def main():
    with SessionLocal() as session:
        backfiller_fact_checking(session)


if __name__ == "__main__":
    main()
