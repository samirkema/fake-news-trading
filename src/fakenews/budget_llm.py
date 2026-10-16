"""Plafond mensuel de dépense LLM — filet de sécurité du pipeline.

Chaque appel Claude est consigné (tokens, coût estimé) dans `usage_llm` ; avant
chaque appel, le cumul du mois civil courant (UTC) est comparé au plafond
(défaut 2 €, surchargeable via LLM_BUDGET_MENSUEL_EUR). Plafond atteint ⇒
`BudgetLLMEpuise` : les deux blocs appelants dégradent déjà proprement sur
exception (signal LLM exclu / pas de mise en contexte).

Choix de prudence :
- échec fermé : si la table est absente ou la base illisible, l'appel est refusé
  plutôt que de dépenser sans compteur ;
- coût estimé en comptant 1 USD = 1 EUR (surestime d'environ 15 %) ;
- le contrôle précède l'appel : le dépassement possible est borné à UN appel.
"""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

from fakenews.db import SessionLocal

logger = logging.getLogger(__name__)

BUDGET_MENSUEL_EUR_PAR_DEFAUT = 2.0

# USD par million de tokens (entrée, sortie). Modèle inconnu ⇒ tarif le plus élevé.
TARIFS_PAR_MILLION = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
TARIF_PAR_DEFAUT = (15.0, 75.0)


class BudgetLLMEpuise(RuntimeError):
    """Le plafond mensuel de dépense LLM est atteint (ou invérifiable)."""


def budget_mensuel_eur() -> float:
    brut = os.environ.get("LLM_BUDGET_MENSUEL_EUR")
    if not brut:
        return BUDGET_MENSUEL_EUR_PAR_DEFAUT
    try:
        valeur = float(brut)
    except ValueError:
        logger.warning("LLM_BUDGET_MENSUEL_EUR=%r illisible — plafond par défaut.", brut)
        return BUDGET_MENSUEL_EUR_PAR_DEFAUT
    return valeur if valeur >= 0 else BUDGET_MENSUEL_EUR_PAR_DEFAUT


def estimer_cout_eur(modele: str, tokens_entree: int, tokens_sortie: int) -> float:
    prix_in, prix_out = TARIFS_PAR_MILLION.get(modele, TARIF_PAR_DEFAUT)
    return (tokens_entree * prix_in + tokens_sortie * prix_out) / 1_000_000


def _debut_du_mois() -> datetime:
    maintenant = datetime.now(timezone.utc)
    return maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def depense_du_mois_eur() -> float:
    with SessionLocal() as session:
        total = session.execute(
            text("select coalesce(sum(cout_eur), 0) from usage_llm where cree_le >= :debut"),
            {"debut": _debut_du_mois()},
        ).scalar_one()
    return float(total)


def verifier_budget() -> None:
    """Lève `BudgetLLMEpuise` si l'appel suivant n'est pas permis."""
    plafond = budget_mensuel_eur()
    try:
        depense = depense_du_mois_eur()
    except Exception as exc:
        raise BudgetLLMEpuise(
            f"budget LLM invérifiable ({type(exc).__name__}) — appel refusé par précaution "
            "(migration 0009_usage_llm.sql appliquée ?)"
        ) from exc
    if depense >= plafond:
        raise BudgetLLMEpuise(
            f"plafond mensuel LLM atteint ({depense:.2f} € dépensés sur {plafond:.2f} €)"
        )


def enregistrer_usage(modele: str, tokens_entree: int, tokens_sortie: int) -> None:
    """Consigne un appel effectué. Une panne d'écriture est journalisée en erreur
    mais ne perd pas la réponse déjà payée ; le prochain `verifier_budget` échouera
    de toute façon si la base est inutilisable."""
    cout = estimer_cout_eur(modele, tokens_entree, tokens_sortie)
    try:
        with SessionLocal() as session:
            session.execute(
                text(
                    "insert into usage_llm (modele, tokens_entree, tokens_sortie, cout_eur) "
                    "values (:m, :ti, :to, :c)"
                ),
                {"m": modele, "ti": tokens_entree, "to": tokens_sortie, "c": cout},
            )
            session.commit()
    except Exception as exc:
        logger.error("Usage LLM non consigné (%s tokens in / %s out) : %s", tokens_entree, tokens_sortie, exc)
