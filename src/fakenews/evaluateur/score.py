"""US-08 évaluateur : agrégation des sous-scores US-01 à US-07 en un score composite
final 0-100 (cf. doc/userstories_évaluateur.md, doc/architecture.md interface evaluer(article))."""

POIDS_PAR_DEFAUT = {
    "reputation": 1.0,
    "corroboration": 1.0,
    "fact_checking": 1.5,
    "source_primaire": 1.5,
    "style": 0.5,
    "decalage_viral": 1.0,
    "llm_bootstrap": 1.5,
}


def calculer_score_composite(sous_scores: dict, poids: dict = POIDS_PAR_DEFAUT) -> dict:
    """sous_scores: {signal: {"valeur": float | None, "raison": str, "preuve_id": str}}.
    Un signal exclu du calcul (neutre/non applicable) a valeur=None.

    Retourne {"score_final": float | None, "non_evaluable": bool, "detail": {...}} —
    detail trace la contribution (valeur, poids, exclu) de chaque signal, pour
    l'explicabilité déjà exigée signal par signal (US-08 évaluateur)."""
    detail = {}
    somme_ponderee = 0.0
    somme_poids = 0.0

    for signal, resultat in sous_scores.items():
        valeur = resultat.get("valeur")
        poids_signal = poids.get(signal, 0.0)
        if valeur is None:
            detail[signal] = {"valeur": None, "poids": poids_signal, "exclu": True}
            continue
        detail[signal] = {"valeur": valeur, "poids": poids_signal, "exclu": False}
        somme_ponderee += poids_signal * valeur
        somme_poids += poids_signal

    if somme_poids == 0:
        # Tous les signaux sont exclus : pas de score plutôt qu'une division par zéro
        # ou une valeur par défaut trompeuse (cf. US-08 évaluateur).
        return {"score_final": None, "non_evaluable": True, "detail": detail}

    return {
        "score_final": round(somme_ponderee / somme_poids, 2),
        "non_evaluable": False,
        "detail": detail,
    }
