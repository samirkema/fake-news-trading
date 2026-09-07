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
import time
from datetime import date, datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

URL_RECHERCHE = "https://efts.sec.gov/LATEST/search-index"
TIMEOUT_SECONDES = 10.0
FENETRE_JOURS_OUVRES_PAR_DEFAUT = 5

VALEUR_CONFIRME = 5.0
VALEUR_NON_CONFIRME = 85.0

# La politique d'accès équitable de la SEC plafonne à 10 requêtes/seconde. Rien ne
# throttlait les appels jusqu'ici (cf. audit, finding M9) : un run sur plusieurs
# centaines d'articles pouvait déclencher un blocage d'IP.
INTERVALLE_MIN_SEC = 0.15
_dernier_appel = 0.0


def _respecter_le_debit_sec() -> None:
    """Le pipeline est strictement séquentiel : pas de verrou. Il y en avait un,
    qui protégeait un compteur qu'aucune concurrence n'atteint et faisait le
    `sleep` à l'intérieur (cf. audit phase 7, finding N11). Si un jour l'évaluateur
    parallélise ses appels, c'est le débit lui-même qu'il faudra repenser, pas ce
    verrou qu'il aurait fallu ajouter."""
    global _dernier_appel
    attente = INTERVALLE_MIN_SEC - (time.monotonic() - _dernier_appel)
    if attente > 0:
        time.sleep(attente)
    _dernier_appel = time.monotonic()


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
    "jpmorgan chase": "JPM",
}

# Jetons génériques d'habillage social, retirés en second passage seulement (cf.
# _identifier_entreprise) : les retirer d'emblée casserait « general motors », dont
# « motors » fait partie du nom.
_JETONS_GENERIQUES = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc", "co",
    "company", "group", "holdings", "holding", "plc", "sa", "ag", "nv", "the",
    "motor", "motors", "platforms", "technologies", "technology", "systems",
    "international", "industries", "labs", "laboratories",
}

_TOKENS_RE = re.compile(r"[a-z0-9]+")

# Table inversée : tuple de jetons -> ticker. La comparaison se fait sur des
# séquences de jetons ENTIÈRES, jamais par sous-chaîne. L'ancien `nom_connu in
# nom_normalise` promouvait « Oxford Analytica » en Ford, « Fordham University » en
# Ford, « Intelsat » en Intel, « Amcor plc » en AMC et « Metaverse Studios » en Meta
# (cf. audit, finding H6).
_ENTREPRISES_PAR_JETONS = {
    tuple(_TOKENS_RE.findall(nom)): ticker for nom, ticker in ENTREPRISES_CONNUES.items()
}

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


def _ticker_de_lentite(texte_entite: str) -> str | None:
    """Ticker d'une entité ORG, par correspondance sur la séquence complète de
    jetons — jamais par sous-chaîne.

    Deux passages : d'abord le nom tel quel (« general motors » doit rester
    entier), puis le nom débarrassé de son habillage social (« ford motor company »
    -> « ford »). Une entité qui ne correspond à aucun nom connu est simplement
    inconnue : c'est la bonne direction d'erreur, puisqu'un ticker non reconnu rend
    le signal non applicable plutôt que pénalisant (cf. US-04, dernier critère)."""
    jetons = tuple(_TOKENS_RE.findall(texte_entite.lower()))
    if not jetons:
        return None
    if jetons in _ENTREPRISES_PAR_JETONS:
        return _ENTREPRISES_PAR_JETONS[jetons]
    essentiels = tuple(j for j in jetons if j not in _JETONS_GENERIQUES)
    if essentiels and essentiels != jetons:
        return _ENTREPRISES_PAR_JETONS.get(essentiels)
    return None


def _identifier_entreprise(titre: str, contenu: str, nlp=None) -> str | None:
    """Retourne le ticker de la première entreprise reconnue (table de correspondance
    ci-dessus) parmi les entités ORG détectées par spaCy, ou None si aucune ne
    correspond à la table."""
    nlp = nlp or _charger_nlp()
    doc = nlp(f"{titre}. {contenu[:2000]}")
    for entite in doc.ents:
        if entite.label_ != "ORG":
            continue
        ticker = _ticker_de_lentite(entite.text)
        if ticker is not None:
            return ticker
    return None


# Mots-outils écartés des termes de recherche : ils sont présents dans tous les
# dépôts et ne discriminent rien.
_MOTS_OUTILS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "over", "after",
    "says", "said", "will", "have", "has", "its", "his", "her", "their", "about",
    "les", "des", "une", "pour", "dans", "avec", "sur", "que", "qui", "son", "ses",
    "leur", "leurs", "cette", "aux", "par", "plus", "est", "sont", "vers", "chez",
}

# Verbes d'annonce journalistique. Ce sont d'excellents marqueurs de claim, mais de
# très mauvais termes de recherche : un 8-K décrit un fait, il n'écrit pas
# « announces ». Mesuré contre l'API réelle : `q="announces fourth quarter"` -> 0
# hit sur un dépôt qui existe, `q="production deliveries"` -> 1 hit.
_VERBES_D_ANNONCE = {
    "announce", "announces", "announced", "announcement", "report", "reports",
    "reported", "says", "said", "reveals", "revealed", "unveils", "confirms",
    "annonce", "annonces", "annoncé", "annoncée", "déclare", "declare", "affirme",
    "révèle", "revele", "dévoile", "devoile", "confirme", "selon",
}
# Deux termes au maximum. Mesuré contre l'API réelle sur un 8-K Tesla existant :
# `q` conjugue les termes, donc chaque mot supplémentaire multiplie le risque de
# rater un dépôt pourtant présent. « production deliveries » -> 1 hit ;
# « announces fourth quarter » -> 0 hit, alors que le dépôt existe. Le titre entier
# était donc structurellement condamné, et quatre termes le restaient presque.
TERMES_RECHERCHE_MAX = 2
TERMES_RECHERCHE_MIN = 1

# Marqueurs d'une claim « précise et vérifiable (annonce, chiffre, décision) », au
# sens exact du 3e critère d'acceptation d'US-04.
#
# L'alternative `\d` seule, présente ici auparavant, rendait la porte quasi
# toujours passante : un horodatage Reddit, un compteur de commentaires, un
# millésime ou un numéro de fil suffisaient à qualifier « fait précis et
# vérifiable » (cf. audit phase 7, finding N4). Un chiffre ne compte désormais que
# s'il est QUANTIFIÉ — devise, pourcentage, ordre de grandeur, ou nombre assez
# grand pour ne pas être une date ni un compteur d'interface.
# Radicaux, pas formes exactes : « rappelle », « annonçant » ou « acquiring » sont
# des annonces au même titre que « rappel » ou « announce ». L'énumération de formes
# fléchies en ratait la moitié, ce qui obligeait à compenser par une règle sur les
# nombres — laquelle prenait un code postal pour un chiffre d'affaires
# (audit phase 9, finding Q10).
_MOTIF_VERBE_ANNONCE = (
    r"announc\w*|report\w*|fil(?:e\w*|ing)|acquir\w*|acquisition\w*|merg\w*|"
    r"recall\w*|lawsuit\w*|dividend\w*|earning\w*|guidance|buyback\w*|layoff\w*|"
    r"bankruptc\w*|resign\w*|appoint\w*|approv\w*|"
    r"annonc\w*|rachat\w*|fusion\w*|rappel\w*|résultat\w*|resultat\w*|"
    r"bénéfice\w*|benefice\w*|dividende\w*|licenciement\w*|démission\w*|demission\w*|"
    r"faillite\w*|nomination\w*|autoris\w*"
)
_MARQUEURS_CLAIM = re.compile(
    # une somme ou un pourcentage : « 0,25 $ », « 12 % », « $4.5bn »
    r"[$€£]\s?\d|\d\s?[$€£%]|\d\s?(?:pour cent|percent)\b"
    # un ordre de grandeur explicite : « 900 billion », « 3 milliards »
    r"|\d[\d.,\s]*\s?(?:million|millions|billion|billions|milliard|milliards|bn|md)\b"
    # Pas de règle sur les nombres « assez grands » : elle qualifiait un code
    # postal (94043), une référence (100234) ou un identifiant de post (123456)
    # de fait précis et vérifiable. Les radicaux de verbes ci-dessous couvrent les
    # vraies annonces, y compris « Tesla rappelle 12000 Model Y ».
    # une annonce, une décision, une démission…
    rf"|\b(?:{_MOTIF_VERBE_ANNONCE})\b",
    re.IGNORECASE,
)


def _termes_distinctifs(titre: str) -> list[str]:
    """Termes utilisables comme requête plein texte contre les dépôts SEC.

    Le code passait auparavant le TITRE DE PRESSE entier en `q`. EDGAR conjugue
    tous les mots de `q` : un titre de journaliste n'apparaît jamais tel quel dans
    un 8-K, donc la recherche ne remontait rien — vérifié empiriquement (une
    requête sur un vrai titre Tesla dans une fenêtre valide renvoie 0 hit, là où
    `q=Tesla` en renvoie 2). Toute la pénalité de non-confirmation reposait donc
    sur une requête structurellement condamnée (cf. audit, finding H1)."""
    vus = []
    for mot in _TOKENS_RE.findall(titre.lower()):
        if mot in _MOTS_OUTILS or mot in _JETONS_GENERIQUES or mot in _VERBES_D_ANNONCE:
            continue
        if not mot.isdigit() and len(mot) < 4:
            continue
        if mot not in vus:
            vus.append(mot)
    return vus[:TERMES_RECHERCHE_MAX]


def _porte_une_claim_verifiable(titre: str, contenu: str) -> bool:
    """US-04 : « Absence de confirmation en source primaire, POUR UNE CLAIM
    PRÉSENTÉE COMME UN FAIT PRÉCIS ET VÉRIFIABLE (annonce, chiffre, décision),
    augmente le score de suspicion. » Cette condition n'était pas implémentée : la
    pénalité de 85 tombait sur tout article citant une entreprise connue, y compris
    un commentaire d'humeur sans la moindre affirmation factuelle."""
    return bool(_MARQUEURS_CLAIM.search(f"{titre}\n{contenu[:2000]}"))


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

    # Deux garde-fous AVANT tout appel réseau, chacun adossé à un critère d'US-04.
    if not _porte_une_claim_verifiable(titre, contenu):
        return {
            "valeur": None,
            "raison": (
                f"non applicable — l'article cite {ticker} mais ne porte aucune claim "
                "factuelle précise (annonce, chiffre, décision) à confronter à la source primaire"
            ),
            "preuve_id": "source_primaire",
        }

    termes = _termes_distinctifs(titre)
    if len(termes) < TERMES_RECHERCHE_MIN:
        return {
            "valeur": None,
            "raison": (
                f"non applicable — titre trop peu spécifique pour interroger SEC EDGAR sur {ticker} "
                "sans produire une absence de résultat non concluante"
            ),
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
    def _chercher(termes_recherche: str | None) -> list:
        params = {
            "forms": "8-K",
            "dateRange": "custom",
            "startdt": debut.isoformat(),
            "enddt": fin.isoformat(),
            "entityName": ticker,
        }
        if termes_recherche:
            params["q"] = termes_recherche
        _respecter_le_debit_sec()
        reponse = client.get(URL_RECHERCHE, params=params)
        reponse.raise_for_status()
        return reponse.json().get("hits", {}).get("hits", [])

    try:
        # Requête ciblée : les termes distinctifs du titre, pas le titre entier.
        hits = _chercher(" ".join(termes))
        # Requête de contrôle, seulement si la ciblée n'a rien donné : l'entreprise
        # a-t-elle déposé QUOI QUE CE SOIT dans la fenêtre ? Sans elle, une absence
        # de résultat est ambiguë — elle peut vouloir dire « aucun dépôt » (une
        # vraie absence de confirmation) aussi bien que « nos mots-clés n'étaient
        # pas dans la prose du dépôt » (une limite de notre recherche). Les deux
        # étaient confondus, et pénalisés à 85 (cf. audit, finding H1).
        depots_dans_la_fenetre = hits if hits else _chercher(None)
    except Exception as exc:
        # Type seul dans `raison` : elle est persistée puis affichée (cf. finding H2).
        logger.warning("recherche SEC EDGAR échouée ou réponse malformée pour %s : %s", ticker, exc)
        return {
            "valeur": None,
            "raison": f"recherche SEC EDGAR indisponible ({type(exc).__name__})",
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

    if depots_dans_la_fenetre:
        # L'entreprise a déposé, mais nos termes n'y correspondent pas : non
        # concluant. US-04 veut alors le signal « non disponible », pas une
        # pénalité — une absence de correspondance n'est pas une absence de fait.
        return {
            "valeur": None,
            "raison": (
                f"non concluant — {len(depots_dans_la_fenetre)} dépôt(s) 8-K de {ticker} dans la "
                f"fenêtre, mais aucun ne correspond aux termes « {' '.join(termes)} »"
            ),
            "preuve_id": "source_primaire",
        }

    return {
        "valeur": VALEUR_NON_CONFIRME,
        "raison": (
            f"claim factuelle sur {ticker} alors qu'aucun dépôt 8-K n'existe en source primaire "
            f"SEC EDGAR dans la fenêtre de ±{fenetre_jours_ouvres} jours ouvrés"
        ),
        "preuve_id": "source_primaire",
    }
