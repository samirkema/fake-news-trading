"""US-04 évaluateur : vérification contre la source primaire SEC EDGAR, pour les
articles citant une entreprise cotée aux États-Unis (cf. doc/userstories_évaluateur.md).

Extraction des entreprises via NER (spaCy, modèle `en_core_web_sm`) : spaCy détecte
les mentions d'organisation dans le texte, mais ne donne pas de ticker boursier — une
table de correspondance nom→ticker (ci-dessous) reste nécessaire pour interroger SEC
EDGAR. Cette table est volontairement limitée aux grandes capitalisations les plus
fréquemment citées dans l'actualité financière : une entreprise cotée absente de la
table est traitée comme "non applicable" (valeur=None), pas comme une absence de
confirmation pénalisante — limite assumée, du même ordre que le biais géographique de
SEC EDGAR lui-même (cf. userstories_évaluateur.md, US-04, dernier critère)."""

import logging
import os
import re
from datetime import date, datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

URL_RECHERCHE = "https://efts.sec.gov/LATEST/search-index"
TIMEOUT_SECONDES = 10.0
FENETRE_JOURS_OUVRES_PAR_DEFAUT = 5

VALEUR_CONFIRME = 5.0
VALEUR_NON_CONFIRME = 85.0

ENTREPRISES_CONNUES = {
    "apple": "AAPL",
    "tesla": "TSLA",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "gamestop": "GME",
    "amc entertainment": "AMC",
    "amc": "AMC",
    "boeing": "BA",
    "intel": "INTC",
    "coinbase": "COIN",
    "moderna": "MRNA",
    "pfizer": "PFE",
    "exxon": "XOM",
    "jpmorgan": "JPM",
    "goldman sachs": "GS",
    "walmart": "WMT",
    "disney": "DIS",
    "starbucks": "SBUX",
    "ford": "F",
    "general motors": "GM",
    "berkshire hathaway": "BRK.A",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "paypal": "PYPL",
}

_SUFFIXES_SOCIETE = re.compile(r"\b(inc|incorporated|corp|corporation|ltd|llc|co|company|group|holdings)\b\.?", re.IGNORECASE)

_NLP = None


def _charger_nlp():
    """Modèle chargé paresseusement et une seule fois par process (coûteux à
    l'initialisation) — pas au niveau module, pour ne pas pénaliser les imports/tests
    qui n'exercent pas ce signal. Absence du modèle (non téléchargé) : l'exception
    remonte à l'appelant, qui dégrade proprement (cf. evaluer_source_primaire)."""
    global _NLP
    if _NLP is None:
        import spacy

        _NLP = spacy.load("en_core_web_sm")
    return _NLP


def _identifier_entreprise(titre: str, contenu: str, nlp=None) -> str | None:
    """Retourne le ticker de la première entreprise reconnue (table de correspondance
    ci-dessus) parmi les entités ORG détectées par spaCy, ou None si aucune ne
    correspond à la table."""
    nlp = nlp or _charger_nlp()
    doc = nlp(f"{titre}. {contenu[:2000]}")
    for entite in doc.ents:
        if entite.label_ != "ORG":
            continue
        nom_normalise = _SUFFIXES_SOCIETE.sub("", entite.text.lower()).strip()
        for nom_connu, ticker in ENTREPRISES_CONNUES.items():
            if nom_connu in nom_normalise:
                return ticker
    return None


def _decaler_jours_ouvres(jour: date, n: int) -> date:
    """Avance/recule de `n` jours ouvrés (lundi-vendredi), sans tenir compte des jours
    fériés — simplification assumée, cohérente avec le reste du projet (le dépôt SEC
    peut légitimement tomber un jour férié, marge suffisante pour l'usage visé ici)."""
    pas = 1 if n >= 0 else -1
    restant = abs(n)
    while restant > 0:
        jour += timedelta(days=pas)
        if jour.weekday() < 5:
            restant -= 1
    return jour


def evaluer_source_primaire(
    titre: str,
    contenu: str,
    date_publication: datetime,
    fenetre_jours_ouvres: int = FENETRE_JOURS_OUVRES_PAR_DEFAUT,
    nlp=None,
    client: httpx.Client | None = None,
) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": str}. En cas de
    "trouvé", `preuve_id` inclut le numéro d'accession du dépôt SEC EDGAR (cf.
    doc/architecture.md)."""
    try:
        ticker = _identifier_entreprise(titre, contenu, nlp=nlp)
    except Exception as exc:
        logger.warning("extraction NER échouée, signal exclu : %s", exc)
        return {
            "valeur": None,
            "raison": f"extraction d'entreprise indisponible ({exc})",
            "preuve_id": "source_primaire",
        }

    if ticker is None:
        return {
            "valeur": None,
            "raison": "non applicable — aucune entreprise cotée reconnue dans l'article",
            "preuve_id": "source_primaire",
        }

    debut = _decaler_jours_ouvres(date_publication.date(), -fenetre_jours_ouvres)
    fin = _decaler_jours_ouvres(date_publication.date(), fenetre_jours_ouvres)

    ferme_client = client is None
    client = client or httpx.Client(
        timeout=TIMEOUT_SECONDES,
        headers={
            "User-Agent": os.environ.get(
                "SEC_EDGAR_USER_AGENT", "fakenews-evaluateur/0.1 (contact non renseigne)"
            )
        },
    )
    try:
        reponse = client.get(
            URL_RECHERCHE,
            params={
                "q": titre,
                "forms": "8-K",
                "dateRange": "custom",
                "startdt": debut.isoformat(),
                "enddt": fin.isoformat(),
                "entityName": ticker,
            },
        )
        reponse.raise_for_status()
        hits = reponse.json().get("hits", {}).get("hits", [])
    except Exception as exc:
        logger.warning("recherche SEC EDGAR échouée ou réponse malformée pour %s : %s", ticker, exc)
        return {
            "valeur": None,
            "raison": f"recherche SEC EDGAR indisponible ({exc})",
            "preuve_id": "source_primaire",
        }
    finally:
        if ferme_client:
            client.close()

    if hits:
        premier = hits[0]
        accession = premier.get("_id") or premier.get("_source", {}).get("adsh")
        return {
            "valeur": VALEUR_CONFIRME,
            "raison": f"annonce confirmée par un dépôt SEC EDGAR ({ticker}) dans la fenêtre de ±{fenetre_jours_ouvres} jours ouvrés",
            "preuve_id": f"source_primaire:{accession}" if accession else "source_primaire",
        }

    return {
        "valeur": VALEUR_NON_CONFIRME,
        "raison": f"aucune confirmation trouvée en source primaire SEC EDGAR pour {ticker} dans la fenêtre de ±{fenetre_jours_ouvres} jours ouvrés",
        "preuve_id": "source_primaire",
    }
