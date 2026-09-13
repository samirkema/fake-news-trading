"""US-02 contextualiseur : validation des `faits_traces` contre les `preuve_id` réels
produits par l'évaluateur (cf. doc/userstories_contextualiseur.md, doc/architecture.md
interface evaluer(article)). Indépendant du fournisseur LLM utilisé pour générer le
brouillon d'explication — cette partie ne fait aucun appel externe."""


import logging
import re

logger = logging.getLogger(__name__)


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


# Un verdict catégorique se compose presque toujours d'une DÉSIGNATION suivie d'un
# VERBE d'accusation. Les décrire séparément couvre leur produit croisé ; la version
# précédente listait six phrases entières et n'en adoucissait qu'une sur six sur des
# formulations réalistes (audit phase 13).
_DESIGNATION = (
    r"(?:cet? article|cette information|cette affirmation|cette source|ce site|ce média|"
    r"ce contenu|cet auteur|l['’]auteur|ce journal|cette publication)"
)
_ADVERBE = r"(?:\s+(?:catégoriquement|totalement|absolument|complètement|clairement|délibérément|manifestement))?"
_ACCUSATION = (
    r"(?:est" + _ADVERBE + r"\s+(?:faux|fausse|mensonger|mensongère|bidon|truqué[e]?|"
    r"une? (?:fake news|mensonge|désinformation|intox|manipulation|propagande))"
    r"|(?:ment|a" + _ADVERBE + r"\s+menti|invente|fabrique|manipule|désinforme)"
    r"|publie" + _ADVERBE + r"\s+de la (?:propagande|désinformation|fausse information))"
)
# `[^.;!?]*` avale la fin de la proposition : sans lui, le complément du verbe
# remplacé restait orphelin (« … présente des signaux de non-fiabilité ses lecteurs »).
_FORMULATION_CATEGORIQUE = re.compile(
    rf"\b({_DESIGNATION})\s+{_ACCUSATION}[^.;!?]*", re.I
)
_HEDGE = r"\1 présente des signaux de non-fiabilité"


def valider_formulation_prudente(explication: str) -> str:
    """US-04 contextualiseur : adoucit les affirmations catégoriques désignant une
    source comme mensongère, et journalise chaque réécriture — une sortie de modèle
    modifiée en silence n'est pas traçable (US-08).

    ponytail: garde-fou lexical, pas sémantique. Il couvre les tournures directes
    (désignation + accusation) ; une périphrase y échappe. La première ligne de
    défense reste la consigne de prompt dans `generation.py`."""
    texte, nb = _FORMULATION_CATEGORIQUE.subn(_HEDGE, explication)
    if nb:
        logger.info(
            "%d affirmation(s) catégorique(s) adoucie(s) dans l'explication générée (US-04).",
            nb,
        )
    return texte
