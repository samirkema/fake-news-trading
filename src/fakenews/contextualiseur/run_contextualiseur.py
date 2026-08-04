"""Point d'entrée du contextualiseur : sélectionne les articles à traiter (US-01
contextualiseur), génère leur mise en contexte via Claude (US-02, ancrée sur les
preuves de l'évaluateur et validée par validation.py) et la persiste (US-03), avec
l'avertissement automatisé systématique (US-04)."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.contextualiseur.declenchement import articles_a_traiter
from fakenews.contextualiseur.generation import generer_mise_en_contexte
from fakenews.contextualiseur.persistance import enregistrer_mise_en_contexte
from fakenews.db import SessionLocal
from fakenews.llm import creer_client
from fakenews.models import Article, MiseEnContexte, Score

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


def traiter_selection(session: Session, selection: list[dict], client=None) -> int:
    """Génère et persiste la mise en contexte de chaque article sélectionné. Un
    échec de génération pour un article n'interrompt pas les suivants (cf.
    doc/architecture.md, dégrader jamais bloquer)."""
    nb_generes = 0
    for item in selection:
        article = session.get(Article, item["article_id"])
        score = session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
        try:
            resultat = generer_mise_en_contexte(article.titre, article.contenu, score.sous_scores, client=client)
        except Exception as exc:
            logger.warning("génération de mise en contexte échouée pour l'article %s : %s", article.id, exc)
            continue

        enregistrer_mise_en_contexte(
            session,
            article_id=article.id,
            explication=resultat["explication"],
            faits_traces=resultat["faits_traces"],
            deductions_llm=resultat["deductions_llm"],
            sources_utilisees=resultat["sources_utilisees"],
            niveau_confiance=resultat.get("niveau_confiance"),
            avertissement=AVERTISSEMENT,
        )
        nb_generes += 1

    session.commit()
    return nb_generes


def main():
    with SessionLocal() as session:
        selection = selectionner_articles_a_traiter(session)
        if not selection:
            logger.info("Aucun article au-dessus du seuil à traiter cette semaine.")
            return

        try:
            client = creer_client()
        except Exception as exc:
            logger.warning(
                "%d article(s) sélectionné(s) mais génération LLM indisponible (%s) — "
                "aucune mise en contexte générée cette semaine.",
                len(selection),
                exc,
            )
            return

        nb_generes = traiter_selection(session, selection, client=client)
        logger.info("%d/%d mise(s) en contexte générée(s) et persistée(s).", nb_generes, len(selection))


if __name__ == "__main__":
    main()
