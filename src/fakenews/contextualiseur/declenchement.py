"""US-01 contextualiseur : déclenchement conditionnel sur seuil de suspicion
(cf. doc/userstories_contextualiseur.md)."""

import logging

logger = logging.getLogger(__name__)

SEUIL_PAR_DEFAUT = 60.0
PLAFOND_APPELS_PAR_DEFAUT = 20


def articles_a_traiter(scores: list[dict], seuil: float = SEUIL_PAR_DEFAUT, plafond: int | None = PLAFOND_APPELS_PAR_DEFAUT) -> list[dict]:
    """scores: liste de {"article_id": ..., "score_final": float | None, "non_evaluable": bool}
    (sortie de US-08 évaluateur pour tous les articles scorés n'ayant pas encore de
    mise en contexte — pas seulement ceux de la semaine : l'appelant passe le
    backlog complet, cf. run_contextualiseur.selectionner_articles_a_traiter).

    Retourne les articles au-dessus du seuil (atteint ou dépassé), triés par score
    décroissant, plafonnés au nombre d'appels LLM autorisés par run. Les articles en
    trop sont bien repris aux runs suivants : traiter un article lui donne une
    `MiseEnContexte`, ce qui le sort du pool, et les suivants remontent dans le
    classement. La file avance donc par tranches de `plafond`, du score le plus
    élevé au plus faible. Un article `non_évaluable` est traité comme sous le seuil.

    (La docstring précédente affirmait le contraire — « cette semaine », « pas de
    report automatique » : deux descriptions inexactes du comportement réel,
    cf. audit, finding L7.)"""
    candidats = [
        s
        for s in scores
        if not s.get("non_evaluable") and s.get("score_final") is not None and s["score_final"] >= seuil
    ]
    candidats.sort(key=lambda s: s["score_final"], reverse=True)
    if plafond is not None:
        candidats = candidats[:plafond]

    logger.info(
        "%d article(s) à traiter sur %d scoré(s) cette semaine (seuil=%.1f%s)",
        len(candidats),
        len(scores),
        seuil,
        f", plafonné à {plafond}" if plafond is not None else "",
    )
    return candidats
