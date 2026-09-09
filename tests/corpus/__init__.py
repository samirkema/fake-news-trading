"""Corpus d'entrées RÉELLES pour les signaux de l'évaluateur.

Raison d'être (cf. audit phase 10, thème transverse) : les quatre défauts
Critique/High de cet audit — verdict de fact-checking inversé, lexique de langue
inopérant sur les titres, `href` compté comme citation — étaient tous invisibles
aux fixtures synthétiques de la suite. `"False"` et `"True"` passaient ; c'est
`"Inaccurate"`, le verdict le plus courant de Full Fact, qui cassait. Un test
n'expose que la variété de ses entrées.

Ces jeux ne sont donc pas des exemples inventés pour illustrer le code : ce sont
des formulations effectivement produites par des fact-checkers signataires de
l'IFCN, des titres de presse tels qu'ils apparaissent en flux, et des fragments
HTML tels que les flux RSS les livrent.
"""

# --- Verdicts de fact-checking (US-03 évaluateur) -------------------------------
#
# `textualRating` est du texte libre : chaque organisation a son propre barème.
# Sources des formulations : PolitiFact (Truth-O-Meter), Snopes, Full Fact,
# FactCheck.org, AFP Factuel, Les Décodeurs.
#
# Attendu : "faux" | "vrai" | "neutre". "neutre" couvre aussi bien l'ambigu
# explicite (mixture, half true) que le verdict qu'aucun barème ne rend
# interprétable — dans les deux cas US-03 veut un signal exclu, pas un pari.
VERDICTS_REELS = [
    # -- PolitiFact --
    ("True", "vrai"),
    ("Mostly True", "vrai"),
    ("Half True", "neutre"),
    ("Mostly False", "faux"),
    ("False", "faux"),
    ("Pants on Fire!", "faux"),
    # -- Snopes --
    ("Mixture", "neutre"),
    ("Unproven", "neutre"),
    ("Outdated", "neutre"),
    ("Miscaptioned", "faux"),
    ("Misattributed", "faux"),
    ("Correct Attribution", "vrai"),
    ("Scam", "faux"),
    ("Labeled Satire", "neutre"),
    ("Legend", "neutre"),
    # -- Full Fact : c'est cette famille qui était lue à l'envers --
    ("Incorrect", "faux"),
    ("Inaccurate", "faux"),
    ("This is not true", "faux"),
    ("Not accurate", "faux"),
    ("Unsupported", "neutre"),
    # -- FactCheck.org / AFP (anglophone) --
    ("Misleading", "faux"),
    ("Altered", "faux"),
    ("No evidence", "faux"),
    ("Fabricated", "faux"),
    ("Missing context", "neutre"),
    ("Unverified", "neutre"),
    # -- AFP Factuel / Les Décodeurs (francophone) --
    ("Faux", "faux"),
    ("Vrai", "vrai"),
    ("Trompeur", "faux"),
    ("Infondé", "faux"),
    ("Détourné", "faux"),
    ("En partie vrai", "neutre"),
    ("Non prouvé", "neutre"),
    ("Avéré", "vrai"),
]

# Formes niées d'un verdict positif. Chacune contient littéralement le terme
# positif (` true ` est dans ` not true `) : sans l'ordre des niveaux et sans les
# entrées dédiées, toutes basculeraient vers « vrai ».
VERDICTS_NIES = [
    "Not true",
    "This claim is not accurate",
    "Not correct",
    "Untrue",
    "Unconfirmed",
    "Unverified",
    "Not confirmed",
]


# --- Titres de presse courts (US-05 évaluateur, détection de langue) ------------
#
# Des TITRES, pas des paragraphes : c'est le format où le putaclic se joue, et
# celui que la détection précédente échouait à classer (seuil de deux mots-outils
# français, jamais atteint sur une ligne de dix mots).
TITRES_FR = [
    "Scandale : trois ministres démissionnent",
    "Le gouvernement annonce une réforme des retraites",
    "Incendie à Marseille : deux blessés",
    "Les prix du carburant repartent à la hausse",
    "Emmanuel Macron reçoit le chancelier allemand",
    "Grève des transports : trafic perturbé mardi",
    "Un séisme de magnitude 5 secoue les Pyrénées",
    "La Bourse de Paris termine en baisse",
    "Procès des attentats : le verdict attendu vendredi",
    "Nouvelle alerte à la pollution en Île-de-France",
    "Vaccin : ce que révèle la dernière étude",
    "Football : le PSG s'impose face à Lyon",
    "Météo : de fortes pluies attendues dans le Sud",
    "Tesla rappelle 12 000 véhicules en Europe",
    "Choquant : la vérité cachée sur les vaccins",
]

TITRES_EN = [
    "Shocking: the hidden truth about vaccines",
    "Stocks fall as inflation data disappoints",
    "Apple announces record quarterly results",
    "Breaking: explosion reported in downtown Chicago",
    "Scientists discover new species in the Amazon",
    "President signs the bill into law",
    "Tesla recalls 12,000 vehicles over brake defect",
    "Storm warning issued for the east coast",
    "Fed holds interest rates steady",
    "Report: unemployment falls to a five-year low",
    "Urgent alert: they don't want you to know this",
    "Manchester United beats Liverpool at home",
    "New study links coffee to longer life",
    "Boeing faces lawsuit over safety concerns",
    "Oil prices surge after supply disruption",
]


# --- Fragments HTML tels que livrés par les flux RSS (US-01/US-04 scraper) ------
#
# (fragment livré par le flux, texte attendu après nettoyage).
# Le point commun de ces cas : tous contiennent des guillemets doubles dans des
# ATTRIBUTS, jamais dans une citation. C'est ce qui faisait passer un article sans
# aucune source nommée pour un article qui en cite une.
RESUMES_RSS_HTML = [
    (
        '<p>Le ministre a quitté la réunion sans commenter. '
        '<a href="https://www.lemonde.fr/politique/article/123.html">Lire la suite</a></p>',
        "Le ministre a quitté la réunion sans commenter. Lire la suite",
    ),
    (
        '<img src="https://ichef.bbci.co.uk/news/240/cpsprodpb/image.jpg" '
        'alt="A view of the harbour" />Rescuers searched the harbour overnight.',
        "Rescuers searched the harbour overnight.",
    ),
    (
        "<div class=\"entry-content\"><p>Les march&eacute;s ont cl&ocirc;tur&eacute; "
        "en baisse.</p></div>",
        "Les marchés ont clôturé en baisse.",
    ),
    (
        '<script type="text/javascript">var trackingId = "UA-1234567-1";</script>'
        "<p>Storm warnings remain in place.</p>",
        "Storm warnings remain in place.",
    ),
    (
        '<style>.byline { font-size: "12px"; }</style><p>The company declined to '
        "comment.</p>",
        "The company declined to comment.",
    ),
]

# Fragment sans la moindre citation, mais bourré de guillemets d'attributs : le cas
# exact qui échappait à la pénalité « aucune source nommée détectée ».
RESUME_RSS_SANS_CITATION = (
    '<div class="article-body" data-id="a1b2c3">'
    '<p>La préfecture a confirmé la fermeture de trois routes départementales '
    "après les intempéries de la nuit. Les équipes techniques sont mobilisées "
    "depuis le début de la matinée pour dégager les axes concernés et rétablir "
    "la circulation dans le courant de la journée.</p>"
    '<a href="https://www.example.fr/regions/intemperies-2026.html" '
    'title="Toutes nos informations sur les intempéries">En savoir plus</a></div>'
)
