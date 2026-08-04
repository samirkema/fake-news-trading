"""US-02 contextualiseur : génération de l'explication ancrée sur les preuves de
l'évaluateur (cf. doc/userstories_contextualiseur.md). Réutilise validation.py (déjà
construit sans LLM) pour appliquer le garde-fou preuve_id sur la sortie du modèle."""

from fakenews.contextualiseur.validation import valider_faits_traces
from fakenews.llm import appeler_structure, creer_client

SCHEMA = {
    "type": "object",
    "properties": {
        "explication": {
            "type": "string",
            "description": "3-5 phrases : ce qui rend l'article suspect et la réalité connue si établie",
        },
        "faits_traces": {
            "type": "array",
            "description": "Chaque item DOIT citer un preuve_id présent dans la liste des signaux fournis",
            "items": {
                "type": "object",
                "properties": {
                    "preuve_id": {"type": "string"},
                    "texte": {"type": "string"},
                },
                "required": ["preuve_id", "texte"],
            },
        },
        "deductions_llm": {
            "type": "array",
            "description": "Déductions sans ancrage sur un signal fourni",
            "items": {
                "type": "object",
                "properties": {"texte": {"type": "string"}},
                "required": ["texte"],
            },
        },
        "niveau_confiance": {"type": "string", "enum": ["faible", "moyen", "élevé"]},
    },
    "required": ["explication", "faits_traces", "deductions_llm", "niveau_confiance"],
}

SYSTEM = (
    "Tu rédiges une mise en contexte factuelle pour un article détecté comme suspect "
    "par un système de scoring automatisé. Règles strictes :\n"
    "1. Chaque item de faits_traces doit citer EXACTEMENT un des preuve_id fournis "
    "dans la liste des signaux ci-dessous — jamais tes connaissances générales, non "
    "vérifiables ici.\n"
    "2. Tout ce que tu déduis ou infères sans pouvoir le rattacher à un preuve_id va "
    "dans deductions_llm, jamais dans faits_traces.\n"
    "3. Si aucun signal ne fournit de preuve factuelle externe (fact-checking, source "
    "primaire), n'invente aucun contre-récit : dis-le explicitement dans l'explication "
    "et limite-toi aux signaux disponibles (réputation, style...).\n"
    "4. Formulation toujours prudente : 'signaux de suspicion détectés', jamais "
    "d'affirmation catégorique nommant la source comme mensongère."
)


def _formatter_signaux(sous_scores: dict) -> str:
    lignes = [
        f"- {nom} (preuve_id={resultat['preuve_id']}) : valeur={resultat['valeur']}, {resultat['raison']}"
        for nom, resultat in sous_scores.items()
        if resultat.get("valeur") is not None
    ]
    return "\n".join(lignes) if lignes else "(aucun signal exploitable pour cet article)"


def generer_mise_en_contexte(titre: str, contenu: str, sous_scores: dict, client=None) -> dict:
    """Retourne {"explication", "faits_traces", "deductions_llm", "sources_utilisees",
    "niveau_confiance"} — faits_traces déjà validés contre les preuve_id réels."""
    client = client or creer_client()
    prompt = (
        f"Titre : {titre}\n\n"
        f"Contenu (extrait) :\n{contenu[:2000]}\n\n"
        f"Signaux produits par l'évaluateur :\n{_formatter_signaux(sous_scores)}"
    )
    brut = appeler_structure(client, SYSTEM, prompt, SCHEMA, max_tokens=1500)

    valide = valider_faits_traces(
        {"faits_traces": brut.get("faits_traces", []), "deductions_llm": brut.get("deductions_llm", [])},
        sous_scores,
    )
    sources_utilisees = sorted({item["preuve_id"] for item in valide["faits_traces"]})

    return {
        "explication": brut["explication"],
        "faits_traces": valide["faits_traces"],
        "deductions_llm": valide["deductions_llm"],
        "sources_utilisees": sources_utilisees,
        "niveau_confiance": brut.get("niveau_confiance"),
    }
