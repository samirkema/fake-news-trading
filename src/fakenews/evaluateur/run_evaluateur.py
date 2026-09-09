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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fakenews.config import entier_depuis_env
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

# Plafond d'articles traités par run. Chaque article déclenche 2 à 3 appels réseau
# synchrones à 10 s de timeout : sans borne, un backlog de plusieurs centaines
# d'articles fait un run de plusieurs heures, exposé au timeout GitHub Actions
# (cf. audit, finding M9). Le reliquat est traité au run suivant — les articles
# non scorés restent sélectionnés tant qu'ils n'ont pas de Score.
PLAFOND_ARTICLES_PAR_DEFAUT = 300

# Un seul `commit()` en fin de run rendait l'écriture tout-ou-rien : un article
# refusé par une contrainte (un score LLM hors bornes, cf. llm_bootstrap) faisait
# perdre les 299 autres — et avec eux les appels réseau et LLM déjà PAYÉS pour les
# produire (cf. audit phase 10, P2). On commite par tranches : le dégât maximal
# passe de 300 articles à 25, et les articles perdus restent sans Score, donc
# resélectionnés au run suivant.
TAILLE_LOT_COMMIT = 25


def _commiter_le_lot(session: Session, identifiants: list) -> int:
    """Persiste le lot courant. Retourne le nombre d'articles réellement écrits.

    Un échec n'interrompt pas le run : on annule la transaction, on nomme les
    articles perdus (ils n'ont pas de Score, donc le prochain run les reprendra) et
    on continue — conforme à « dégrader, jamais bloquer » (doc/V0/architecture.md),
    qui n'était appliqué qu'aux appels externes, pas à l'écriture."""
    if not identifiants:
        return 0
    try:
        session.commit()
        return len(identifiants)
    except Exception as exc:
        session.rollback()
        logger.error(
            "Écriture d'un lot de %d score(s) refusée (%s) — articles non scorés, "
            "repris au prochain run : %s",
            len(identifiants), type(exc).__name__,
            ", ".join(str(i) for i in identifiants),
        )
        return 0


def evaluer_articles_non_scores(
    session: Session,
    plafond_llm: int = PLAFOND_APPELS_LLM_PAR_DEFAUT,
    plafond_articles: int = PLAFOND_ARTICLES_PAR_DEFAUT,
) -> int:
    restants = session.execute(
        select(func.count())
        .select_from(Article)
        .outerjoin(Score, Score.article_id == Article.id)
        .where(Score.id.is_(None))
    ).scalar_one()
    articles = (
        session.execute(
            select(Article)
            .outerjoin(Score, Score.article_id == Article.id)
            .where(Score.id.is_(None))
            # Les plus récents d'abord : un backlog qui déborde doit livrer
            # l'actualité de la semaine, pas des articles périmés.
            .order_by(Article.date_publication.desc(), Article.id)
            .limit(plafond_articles)
        )
        .scalars()
        .all()
    )
    if restants > len(articles):
        logger.warning(
            "%d article(s) non scoré(s) pour un plafond de %d — %d reporté(s) au prochain run.",
            restants, plafond_articles, restants - len(articles),
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
    nb_persistes = 0
    lot = []
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
            # `.get` et non indexation directe : un signal ajouté sans entrée au
            # barème levait un KeyError ici alors que score.py le tolère à 0.0
            # (cf. audit, finding L4). Un seul comportement pour un seul concept.
            poids_utilises = {signal: POIDS_PAR_DEFAUT.get(signal, 0.0) for signal in sous_scores}

            session.add(
                Score(
                    article_id=article.id,
                    sous_scores=sous_scores,
                    poids=poids_utilises,
                    # US-08 exige la trace de la contribution de chaque signal ;
                    # elle était calculée puis jetée (cf. audit, finding M4).
                    detail_calcul=resultat["detail"],
                    score_final=resultat["score_final"],
                    non_evaluable=resultat["non_evaluable"],
                )
            )
            lot.append(article.id)
            if len(lot) >= TAILLE_LOT_COMMIT:
                nb_persistes += _commiter_le_lot(session, lot)
                lot = []
    finally:
        client_fact_checking.close()
        client_sec_edgar.close()

    nb_persistes += _commiter_le_lot(session, lot)
    logger.info(
        "%d/%d article(s) évalué(s) et persisté(s), %d appel(s) LLM bootstrap",
        nb_persistes, len(articles), nb_appels_llm,
    )
    return nb_persistes


def main():
    plafond = entier_depuis_env("LLM_PLAFOND_EVALUATEUR", PLAFOND_APPELS_LLM_PAR_DEFAUT)
    plafond_articles = entier_depuis_env(
        "EVALUATEUR_PLAFOND_ARTICLES", PLAFOND_ARTICLES_PAR_DEFAUT
    )
    with SessionLocal() as session:
        evaluer_articles_non_scores(
            session, plafond_llm=plafond, plafond_articles=plafond_articles
        )


if __name__ == "__main__":
    main()
