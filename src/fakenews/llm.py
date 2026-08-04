"""Client Claude (Anthropic) partagé — infrastructure neutre au même titre que
fakenews.db, utilisée par l'évaluateur (US-07) et le contextualiseur (US-02) sans
qu'ils s'appellent entre eux (cf. doc/architecture.md, "pas d'appel direct entre
les blocs"). Fournisseur choisi : Claude (cf. doc/plan_implementation.md)."""

import os

import anthropic

# Haiku par défaut pour les deux usages (scoring court, génération plus longue) —
# budget serré du projet (cf. doc/fiche-projet-fake-news-trading.md). Surchageable
# via LLM_MODELE si un besoin de qualité supérieure apparaît pour la génération.
MODELE_PAR_DEFAUT = os.environ.get("LLM_MODELE", "claude-haiku-4-5-20251001")


def creer_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def appeler_structure(
    client: anthropic.Anthropic,
    system: str,
    prompt: str,
    schema: dict,
    model: str = MODELE_PAR_DEFAUT,
    max_tokens: int = 1024,
) -> dict:
    """Force une réponse structurée via un tool call plutôt que de parser du texte
    libre — évite les erreurs de parsing sur une réponse mal formée."""
    reponse = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        tools=[
            {
                "name": "repondre",
                "description": "Fournit la réponse structurée demandée.",
                "input_schema": schema,
            }
        ],
        tool_choice={"type": "tool", "name": "repondre"},
    )
    for bloc in reponse.content:
        if bloc.type == "tool_use":
            return bloc.input
    raise ValueError("aucune réponse structurée reçue du modèle")
