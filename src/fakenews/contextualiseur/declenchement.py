"""US-01 contextualiseur : déclenchement conditionnel sur seuil de suspicion
(cf. doc/userstories_contextualiseur.md)."""

import logging

from fakenews.config import SEUIL_SUSPICION_PAR_DEFAUT

logger = logging.getLogger(__name__)

# Le seuil vit dans `fakenews.config` : le frontend en a besoin lui aussi, et il ne
# doit pas l'importer d'ici (cf. audit phase 10 — « les blocs ne s'appellent pas
# entre eux », doc/V0/architecture.md). Réexporté sous son ancien nom pour rester
# lisible depuis ce module, qui est celui qui l'APPLIQUE.
SEUIL_PAR_DEFAUT = SEUIL_SUSPICION_PAR_DEFAUT
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

    # Journal volontairement modeste sur son dénominateur : cette fonction ne voit
    # que la liste qu'on lui passe, pas le corpus scoré. Elle affirmait « sur N
    # scoré(s) CETTE SEMAINE » alors que sa propre docstring explique que l'appelant
    # lui remet le backlog complet — deux phrases contradictoires dans le même
    # fichier. Le comptage exigé par US-01 (« traités vs. total scoré par
    # l'évaluateur ») est produit par `selectionner_articles_a_traiter`, qui a
    # l'accès base pour le calculer honnêtement (cf. audit phase 10).
    logger.info(
        "%d article(s) retenu(s) parmi %d candidat(s) fourni(s) (seuil=%.1f%s)",
        len(candidats),
        len(scores),
        seuil,
        f", plafonné à {plafond}" if plafond is not None else "",
    )
    return candidats
