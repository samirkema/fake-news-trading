"""US-03 évaluateur : vérification via l'API Google Fact Check Tools (gratuite, cf.
doc/userstories_évaluateur.md). Clé optionnelle (GOOGLE_FACT_CHECK_API_KEY, cf.
.env.example) — absente, appel en échec ou réponse malformée : signal exclu
(dégrader jamais bloquer, cf. doc/architecture.md), pas de plantage de l'évaluateur."""

import logging
import os
import re
import unicodedata

import httpx

logger = logging.getLogger(__name__)

URL_API = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
TIMEOUT_SECONDES = 10.0

VALEUR_FAUX = 90.0
VALEUR_VRAI = 5.0

# Les verdicts (textualRating) sont du texte libre côté fact-checkers, pas une
# énumération fixe. Trois propriétés font l'interprétation correcte, et l'ORDRE
# entre elles compte autant que les listes elles-mêmes (cf. audit phase 10, P1) :
#
# 1. COMPARAISON SUR JETONS ENTIERS, jamais par sous-chaîne. `mot in note` lisait
#    « Inaccurate » comme « accurate » et « Incorrect » comme « correct » : deux des
#    verdicts les plus courants des fact-checkers anglophones étaient interprétés à
#    l'envers, faisant passer l'article de 90 (très suspect) à 5 (fiable) — soit
#    exactement le contraire de ce qu'exige US-03. Borner chaque expression
#    d'espaces suffit à fermer ça : ` accurate ` ne se trouve pas dans
#    ` inaccurate `, ni ` correct ` dans ` incorrect `.
# 2. UN NIVEAU AMBIGU EXPLICITE, TESTÉ EN PREMIER. « Half true » et « Barely true »
#    contiennent littéralement ` true ` : le bordage seul ne les sauverait pas. Ils
#    ne sont ni vrais ni faux — la table de correspondance du projet les situe à 40
#    et 60 (cf. userstories_évaluateur.md) — donc signal neutre et exclu du calcul,
#    conforme au 4e critère d'US-03.
# 3. FAUX AVANT VRAI. « Not true » contient ` true ` : seul l'ordre le rattrape.
#
# En cas de doute on retourne None (signal exclu) plutôt qu'une valeur : US-03 veut
# un signal neutre en l'absence de correspondance exploitable, pas un pari.


def _aplatir(texte: str) -> str:
    """Minuscules, sans accents, ponctuation réduite à des espaces simples. Les
    verdicts arrivent tels que le fact-checker les a écrits : « FAUX », « Faux. »,
    « mostly-false » et « Mostly False » doivent se comparer à la même chose."""
    sans_accent = "".join(
        c
        for c in unicodedata.normalize("NFD", texte.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sans_accent).strip()


def _borner(expression: str) -> str:
    """Encadre d'espaces pour que la recherche porte sur des jetons entiers."""
    return f" {_aplatir(expression)} "


VERDICTS_AMBIGUS = {
    "half true", "half truth", "barely true", "partly true", "partly false",
    "mixture", "mixed", "unproven", "unsupported", "exaggerated", "outdated",
    "missing context", "lacks context", "needs context", "no consensus",
    "en partie vrai", "en partie faux", "plutot vrai", "plutot faux",
    "non prouve", "invérifiable", "à nuancer", "contexte manquant",
    # Formes niées des verdicts « vrai » : elles contiennent le terme positif
    # (` confirmed ` est dans ` not confirmed `) et basculeraient donc vers VRAI si
    # rien ne les interceptait plus tôt. Neutre est la direction d'erreur sûre.
    "unconfirmed", "unverified", "not confirmed", "not verified",
    "non confirmé", "non vérifié",
}
MOTS_FAUX = {
    "false", "faux", "pants on fire", "misleading", "trompeur", "incorrect",
    "mostly false", "largement faux", "fake", "inaccurate", "untrue",
    "not true", "not accurate", "not correct", "fabricated", "debunked",
    "no evidence", "altered", "manipulated", "scam", "hoax", "miscaptioned",
    "misattributed", "mislabeled", "erroné", "infondé", "mensonger",
    "aucune preuve", "détourné", "truqué",
}
MOTS_VRAI = {
    "true", "vrai", "correct", "accurate", "mostly true", "largement vrai",
    "confirmed", "verified", "exact", "avéré", "confirmé", "vérifié",
}

# Niveaux ordonnés, bornés une seule fois au chargement du module. L'ordre de ce
# tuple EST la règle d'interprétation : le changer réintroduit le défaut.
_NIVEAUX = (
    (frozenset(_borner(v) for v in VERDICTS_AMBIGUS), None),
    (frozenset(_borner(v) for v in MOTS_FAUX), VALEUR_FAUX),
    (frozenset(_borner(v) for v in MOTS_VRAI), VALEUR_VRAI),
)


def _interpreter_verdict(note_textuelle: str) -> float | None:
    note = _borner(note_textuelle)
    for expressions, valeur in _NIVEAUX:
        if any(expression in note for expression in expressions):
            return valeur
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
        # `raison` est persistée dans scores.sous_scores PUIS rendue dans le
        # frontend (templates/detail.html). Interpoler `exc` brut y recopiait la
        # clé API : httpx met l'URL complète — `?key=...` compris — dans le message
        # de HTTPStatusError (cf. audit, finding H2). Seul le type est conservé ;
        # le détail complet reste dans le log, où GitHub masque les secrets.
        logger.warning("appel Google Fact Check Tools échoué ou réponse malformée : %s", exc)
        return {
            "valeur": None,
            "raison": f"fact-checking indisponible ({type(exc).__name__})",
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
