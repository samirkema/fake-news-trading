"""US-07 évaluateur : scoring de suspicion via un LLM en ligne, en bootstrap avant
le modèle maison fine-tuné (cf. doc/fiche-projet-fake-news-trading.md,
doc/userstories_évaluateur.md). Fournisseur : Claude (cf. fakenews.llm)."""

import logging

from fakenews.llm import (
    CONSIGNE_CONTENU_NON_FIABLE,
    appeler_structure,
    creer_client,
    encadrer_contenu_non_fiable,
)

logger = logging.getLogger(__name__)

SCHEMA = {
    "type": "object",
    "properties": {
        "score_suspicion": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": "0 = fiable, 100 = très suspect",
        },
        "justification": {"type": "string", "description": "1-2 phrases maximum"},
    },
    "required": ["score_suspicion", "justification"],
}

SYSTEM = (
    "Tu es un évaluateur de fiabilité de l'information. Pour l'article fourni, donne "
    "un score de suspicion de 0 (fiable) à 100 (très suspect) et une justification "
    "courte (1-2 phrases). Base-toi sur la plausibilité factuelle, la présence "
    "d'éléments vérifiables et le ton employé — pas sur tes propres connaissances "
    "générales du sujet, que tu ne peux pas vérifier ici."
    + CONSIGNE_CONTENU_NON_FIABLE
)


def evaluer_llm_bootstrap(titre: str, contenu: str, client=None) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": "llm_bootstrap"}.
    En cas d'échec de l'appel (indisponibilité, quota, réponse malformée), le signal
    est marqué exclu (valeur=None) plutôt que de faire planter l'évaluateur (cf.
    doc/architecture.md, dégrader jamais bloquer)."""
    try:
        client = client or creer_client()
        prompt = "Article à évaluer :\n" + encadrer_contenu_non_fiable(
            f"Titre : {titre}\n\nContenu :\n{contenu[:4000]}"
        )
        resultat = appeler_structure(client, SYSTEM, prompt, SCHEMA)
        return {
            "valeur": float(resultat["score_suspicion"]),
            "raison": resultat["justification"],
            "preuve_id": "llm_bootstrap",
        }
    except Exception as exc:
        # Seul le TYPE de l'exception est conservé : `raison` est persistée en base
        # puis affichée dans le frontend, et un message brut peut transporter une
        # URL contenant une clé d'API (cf. audit, finding H2).
        logger.warning("appel LLM bootstrap échoué pour un article : %s", exc)
        return {
            "valeur": None,
            "raison": f"appel LLM indisponible ({type(exc).__name__})",
            "preuve_id": "llm_bootstrap",
        }
