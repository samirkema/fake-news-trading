"""US-03 évaluateur : vérification via l'API Google Fact Check Tools (gratuite, cf.
doc/userstories_évaluateur.md). Clé optionnelle (GOOGLE_FACT_CHECK_API_KEY, cf.
.env.example) — absente, appel en échec ou réponse malformée : signal exclu
(dégrader jamais bloquer, cf. doc/architecture.md), pas de plantage de l'évaluateur."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

URL_API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
TIMEOUT_SECONDES = 10.0

# Les verdicts (textualRating) sont du texte libre côté fact-checkers, pas une
# énumération fixe : on ne tranche que sur les formulations non ambiguës. Un verdict
# du type "unproven"/"mixture" reste non traité (cf. _interpreter_verdict), traité
# comme une absence de correspondance exploitable plutôt que d'être forcé vers vrai/faux.
MOTS_FAUX = {
    "false", "faux", "pants on fire", "misleading", "trompeur", "incorrect",
    "mostly false", "largement faux", "fake",
}
MOTS_VRAI = {"true", "vrai", "correct", "accurate", "mostly true", "largement vrai"}

VALEUR_FAUX = 90.0
VALEUR_VRAI = 5.0


def _interpreter_verdict(note_textuelle: str) -> float | None:
    note = note_textuelle.strip().lower()
    if any(mot in note for mot in MOTS_FAUX):
        return VALEUR_FAUX
    if any(mot in note for mot in MOTS_VRAI):
        return VALEUR_VRAI
    return None


def evaluer_fact_checking(titre: str, cle_api: str | None = None, client: httpx.Client | None = None) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": str}. `preuve_id`
    inclut l'URL de la ClaimReview trouvée (cf. doc/architecture.md), ou "fact_checking"
    seul en l'absence de clé/de correspondance/en cas d'échec."""
    cle_api = cle_api or os.environ.get("GOOGLE_FACT_CHECK_API_KEY")
    if not cle_api:
        return {
            "valeur": None,
            "raison": "clé API Google Fact Check absente",
            "preuve_id": "fact_checking",
        }

    ferme_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDES)
    try:
        reponse = client.get(URL_API, params={"query": titre, "key": cle_api})
        reponse.raise_for_status()
        claims = reponse.json().get("claims") or []
        for claim in claims:
            for review in claim.get("claimReview") or []:
                note = review.get("textualRating")
                if not note:
                    continue
                valeur = _interpreter_verdict(note)
                if valeur is not None:
                    url = review.get("url")
                    return {
                        "valeur": valeur,
                        "raison": f"claim vérifiée par un fact-checker : verdict « {note} »",
                        "preuve_id": f"fact_checking:{url}" if url else "fact_checking",
                    }
    except Exception as exc:
        logger.warning("appel Google Fact Check Tools échoué ou réponse malformée : %s", exc)
        return {
            "valeur": None,
            "raison": f"fact-checking indisponible ({exc})",
            "preuve_id": "fact_checking",
        }
    finally:
        if ferme_client:
            client.close()

    return {
        "valeur": None,
        "raison": "aucune correspondance exploitable trouvée dans les bases de fact-checking",
        "preuve_id": "fact_checking",
    }
