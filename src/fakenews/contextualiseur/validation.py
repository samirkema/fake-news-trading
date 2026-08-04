"""US-02 contextualiseur : validation des `faits_traces` contre les `preuve_id` réels
produits par l'évaluateur (cf. doc/userstories_contextualiseur.md, doc/architecture.md
interface evaluer(article)). Indépendant du fournisseur LLM utilisé pour générer le
brouillon d'explication — cette partie ne fait aucun appel externe."""


def valider_faits_traces(brouillon: dict, sous_scores: dict) -> dict:
    """brouillon: {"faits_traces": [{"preuve_id": ..., ...}, ...], "deductions_llm": [...]}
    — sortie brute (non validée) du LLM de génération.
    sous_scores: {signal: {"valeur": float | None, "raison": str, "preuve_id": str}}
    — sortie evaluer(article) pour cet article.

    Retourne {"faits_traces": [...], "deductions_llm": [...]} : tout item de
    `faits_traces` dont le `preuve_id` cité ne correspond à aucun signal réellement
    évalué (valeur non None) pour cet article est déplacé vers `deductions_llm` —
    la distinction n'est pas laissée à la seule discipline du prompt."""
    preuve_ids_valides = {
        resultat["preuve_id"] for resultat in sous_scores.values() if resultat.get("valeur") is not None
    }

    faits_traces = []
    deductions_llm = list(brouillon.get("deductions_llm", []))
    for item in brouillon.get("faits_traces", []):
        if item.get("preuve_id") in preuve_ids_valides:
            faits_traces.append(item)
        else:
            deductions_llm.append(item)

    return {"faits_traces": faits_traces, "deductions_llm": deductions_llm}
