"""Point d'entrée du contextualiseur : sélectionne les articles à traiter (US-01
contextualiseur), génère leur mise en contexte via Claude (US-02, ancrée sur les
preuves de l'évaluateur et validée par validation.py) et la persiste (US-03), avec
l'avertissement automatisé systématique (US-04)."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fakenews.config import entier_depuis_env, seuil_suspicion
from fakenews.contextualiseur.avertissement import AVERTISSEMENT
from fakenews.contextualiseur.declenchement import (
    PLAFOND_APPELS_PAR_DEFAUT,
    articles_a_traiter,
)
from fakenews.contextualiseur.generation import generer_mise_en_contexte
from fakenews.contextualiseur.persistance import enregistrer_mise_en_contexte
from fakenews.db import SessionLocal
from fakenews.llm import creer_client
from fakenews.models import Article, MiseEnContexte, Score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


NOM_ENV_PLAFOND = "LLM_PLAFOND_CONTEXTUALISEUR"


def selectionner_articles_a_traiter(session: Session) -> list[dict]:
    """Articles scorés n'ayant pas encore de mise en contexte, au-dessus du seuil,
    triés par score décroissant et plafonnés (US-01 contextualiseur).

    Le seuil et le plafond viennent de l'environnement (`fakenews.config`), comme
    l'exigent les 1er et 4e critères d'acceptation d'US-01 : c'étaient jusqu'ici des
    constantes de module, donc modifiables seulement par un commit — et le plafond
    n'était même pas transmis (cf. audit phase 10).

    Le tri et le plafond sont poussés dans SQL. La version précédente chargeait en
    mémoire TOUS les scores sans mise en contexte : comme un article sous le seuil
    n'en reçoit jamais, ce pool ne se vide pas — il contient tous les articles jugés
    fiables depuis le début du projet, JSONB compris, pour n'en retenir que 20."""
    seuil = seuil_suspicion()
    plafond = entier_depuis_env(NOM_ENV_PLAFOND, PLAFOND_APPELS_PAR_DEFAUT)

    total_score = session.execute(select(func.count()).select_from(Score)).scalar_one()
    lignes = session.execute(
        select(Score.article_id, Score.score_final, Score.non_evaluable)
        .outerjoin(MiseEnContexte, MiseEnContexte.article_id == Score.article_id)
        .where(MiseEnContexte.id.is_(None))
        # Un article `non_évaluable` est traité comme sous le seuil (US-01) ; son
        # `score_final` est NULL, que la comparaison écarterait déjà — le filtre
        # explicite dit l'intention plutôt que de la laisser au hasard de SQL.
        .where(Score.non_evaluable.is_(False))
        .where(Score.score_final >= seuil)
        .order_by(Score.score_final.desc(), Score.article_id)
        .limit(plafond)
    ).all()

    candidats = [
        {"article_id": l.article_id, "score_final": float(l.score_final), "non_evaluable": l.non_evaluable}
        for l in lignes
    ]
    selection = articles_a_traiter(candidats, seuil=seuil, plafond=plafond)

    # US-01, 5e critère : « chaque run journalise le nombre d'articles traités vs. le
    # nombre total scoré par l'évaluateur ». Ce ratio n'était produit nulle part : le
    # seul journal comparait la sélection au pool des articles SANS mise en contexte,
    # pas au corpus scoré, donc ne mesurait pas le taux de suspicion annoncé.
    logger.info(
        "Taux de suspicion : %d article(s) au-dessus du seuil %.1f sur %d scoré(s) "
        "au total (plafond d'appels : %d).",
        len(selection), seuil, total_score, plafond,
    )
    return selection


def traiter_selection(session: Session, selection: list[dict], client=None) -> int:
    """Génère et persiste la mise en contexte de chaque article sélectionné. Un
    échec de génération pour un article n'interrompt pas les suivants (cf.
    doc/architecture.md, dégrader jamais bloquer)."""
    nb_generes = 0
    for item in selection:
        # Récupération DANS le try : elle en était sortie, si bien qu'un article
        # supprimé entre la sélection et le traitement faisait tomber tout le run —
        # exactement ce que la docstring ci-dessus promet d'éviter (finding L6).
        try:
            article = session.get(Article, item["article_id"])
            if article is None:
                logger.warning("article %s introuvable — ignoré.", item["article_id"])
                continue
            score = session.execute(
                select(Score).where(Score.article_id == article.id)
            ).scalar_one()
            resultat = generer_mise_en_contexte(article.titre, article.contenu, score.sous_scores, client=client)
        except Exception as exc:
            logger.warning(
                "génération de mise en contexte échouée pour l'article %s : %s",
                item["article_id"], exc,
            )
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
