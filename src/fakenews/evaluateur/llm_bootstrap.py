"""US-07 évaluateur : scoring de suspicion via un LLM en ligne, en bootstrap avant
le modèle maison fine-tuné (cf. doc/fiche-projet-fake-news-trading.md,
doc/userstories_évaluateur.md). Fournisseur : Claude (cf. fakenews.llm)."""

import logging

from fakenews.llm import appeler_structure, creer_client

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
)


def evaluer_llm_bootstrap(titre: str, contenu: str, client=None) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": "llm_bootstrap"}.
    En cas d'échec de l'appel (indisponibilité, quota, réponse malformée), le signal
    est marqué exclu (valeur=None) plutôt que de faire planter l'évaluateur (cf.
    doc/architecture.md, dégrader jamais bloquer)."""
    try:
        client = client or creer_client()
        resultat = appeler_structure(client, SYSTEM, f"Titre : {titre}\n\nContenu :\n{contenu[:4000]}", SCHEMA)
        return {
            "valeur": float(resultat["score_suspicion"]),
            "raison": resultat["justification"],
            "preuve_id": "llm_bootstrap",
        }
    except Exception as exc:
        logger.warning("appel LLM bootstrap échoué pour un article : %s", exc)
        return {
            "valeur": None,
            "raison": f"appel LLM indisponible ({exc})",
            "preuve_id": "llm_bootstrap",
        }
