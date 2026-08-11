"""Point d'entrée de l'évaluateur : calcule les signaux disponibles pour les articles
pas encore scorés, et persiste le score composite (US-08).

Implémentés : US-01 (réputation), US-03 (fact-checking), US-04 (source primaire),
US-05 (style), US-07 (LLM bootstrap, Claude). US-02 (corroboration) et US-06 (décalage
viral) restent à faire — nécessitent tous deux une brique de clustering commune
(embeddings/GDELT), non implémentée. `sous_scores` ne contient que les signaux
réellement calculés, pas d'entrées factices pour les signaux manquants."""

import logging
import os

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.db import SessionLocal
from fakenews.evaluateur.fact_checking import evaluer_fact_checking
from fakenews.evaluateur.llm_bootstrap import evaluer_llm_bootstrap
from fakenews.evaluateur.reputation import evaluer_reputation
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.evaluateur.source_primaire import evaluer_source_primaire
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

    # US-03/US-04 : mêmes raisons que client_llm ci-dessus pour créer les clients une
    # seule fois par run. Contrairement au LLM, la construction elle-même ne peut pas
    # échouer (clé/réseau absents sont gérés par article, cf. fact_checking.py et
    # source_primaire.py) — pas de try/except ici.
    client_fact_checking = httpx.Client(timeout=10.0)
    client_sec_edgar = httpx.Client(
        timeout=10.0,
        headers={"User-Agent": os.environ.get("SEC_EDGAR_USER_AGENT", "fakenews-evaluateur/0.1 (contact non renseigne)")},
    )

    nb_appels_llm = 0
    try:
        for article in articles:
            sous_scores = {
                "reputation": evaluer_reputation(article.domaine_source),
                "style": evaluer_style(article.titre, article.contenu, article.auteur),
                "fact_checking": evaluer_fact_checking(article.titre, client=client_fact_checking),
                "source_primaire": evaluer_source_primaire(
                    article.titre, article.contenu, article.date_publication, client=client_sec_edgar
                ),
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
    finally:
        client_fact_checking.close()
        client_sec_edgar.close()

    session.commit()
    logger.info("%d article(s) évalué(s), %d appel(s) LLM bootstrap", len(articles), nb_appels_llm)
    return len(articles)


def main():
    plafond = int(os.environ.get("LLM_PLAFOND_EVALUATEUR", PLAFOND_APPELS_LLM_PAR_DEFAUT))
    with SessionLocal() as session:
        evaluer_articles_non_scores(session, plafond_llm=plafond)


if __name__ == "__main__":
    main()
