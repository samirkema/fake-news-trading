"""Point d'entrée de l'évaluateur : calcule les signaux disponibles pour les articles
pas encore scorés, et persiste le score composite (US-08).

Implémentés : US-01 (réputation), US-05 (style), US-07 (LLM bootstrap, Claude).
US-02 (corroboration), US-03 (fact-checking), US-04 (source primaire), US-06
(décalage viral) restent à faire — nécessitent respectivement du clustering
(embeddings/GDELT), une clé API Google Fact Check, du NER (spaCy) + SEC EDGAR, et le
clustering de US-02. `sous_scores` ne contient que les signaux réellement calculés,
pas d'entrées factices pour les signaux manquants."""

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.db import SessionLocal
from fakenews.evaluateur.llm_bootstrap import evaluer_llm_bootstrap
from fakenews.evaluateur.reputation import evaluer_reputation
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.evaluateur.style import evaluer_style
from fakenews.llm import creer_client
from fakenews.models import Article, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PLAFOND_APPELS_LLM_PAR_DEFAUT = 50


def evaluer_articles_non_scores(session: Session, plafond_llm: int = PLAFOND_APPELS_LLM_PAR_DEFAUT) -> int:
    articles = (
        session.execute(
            select(Article).outerjoin(Score, Score.article_id == Article.id).where(Score.id.is_(None))
        )
        .scalars()
        .all()
    )

    # Client créé une seule fois pour tout le run (pas par article) : si les
    # identifiants sont absents/invalides, on le sait dès le début et on dégrade
    # proprement (US-07 exclu partout) plutôt que de retenter et journaliser un
    # échec identique des centaines de fois (cf. doc/architecture.md).
    client_llm = None
    try:
        client_llm = creer_client()
    except Exception as exc:
        logger.warning("LLM bootstrap indisponible pour tout ce run : %s", exc)

    nb_appels_llm = 0
    for article in articles:
        sous_scores = {
            "reputation": evaluer_reputation(article.domaine_source),
            "style": evaluer_style(article.titre, article.contenu, article.auteur),
        }

        # US-07 : plafonné par run. Pas de priorisation par cluster (non disponible,
        # cf. docstring du module) — traité dans l'ordre rencontré ; au-delà du
        # plafond, signal absent plutôt que fabriqué.
        if client_llm is not None and nb_appels_llm < plafond_llm:
            sous_scores["llm_bootstrap"] = evaluer_llm_bootstrap(article.titre, article.contenu, client=client_llm)
            nb_appels_llm += 1

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
    logger.info("%d article(s) évalué(s), %d appel(s) LLM bootstrap", len(articles), nb_appels_llm)
    return len(articles)


def main():
    plafond = int(os.environ.get("LLM_PLAFOND_EVALUATEUR", PLAFOND_APPELS_LLM_PAR_DEFAUT))
    with SessionLocal() as session:
        evaluer_articles_non_scores(session, plafond_llm=plafond)


if __name__ == "__main__":
    main()
