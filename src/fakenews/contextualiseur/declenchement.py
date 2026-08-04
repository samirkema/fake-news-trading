"""US-01 contextualiseur : déclenchement conditionnel sur seuil de suspicion
(cf. doc/userstories_contextualiseur.md)."""

import logging

logger = logging.getLogger(__name__)

SEUIL_PAR_DEFAUT = 60.0
PLAFOND_APPELS_PAR_DEFAUT = 20


def articles_a_traiter(scores: list[dict], seuil: float = SEUIL_PAR_DEFAUT, plafond: int | None = PLAFOND_APPELS_PAR_DEFAUT) -> list[dict]:
    """scores: liste de {"article_id": ..., "score_final": float | None, "non_evaluable": bool}
    (sortie de US-08 évaluateur pour chaque article scoré cette semaine).

    Retourne les articles au-dessus du seuil (atteint ou dépassé), triés par score
    décroissant, plafonnés au nombre d'appels LLM autorisés par run (les articles en
    trop restent non traités cette semaine — pas de report automatique au run suivant,
    cf. limite documentée dans l'audit de suivi). Un article `non_évaluable` est traité
    comme sous le seuil."""
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
