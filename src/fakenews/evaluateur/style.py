"""US-05 évaluateur : signaux stylistiques (cf. doc/userstories_évaluateur.md).
Aucune dépendance externe — détection de langue et lexiques minimalistes, pas de
modèle NLP lourd, cohérent avec la simplicité visée en phase prototype."""

import re

MOTS_CHARGES = {
    "fr": {
        "choquant",
        "scandale",
        "incroyable",
        "alerte",
        "urgent",
        "catastrophe",
        "explosif",
        "censuré",
        "vérité cachée",
        "ils ne veulent pas que vous sachiez",
    },
    "en": {
        "shocking",
        "scandal",
        "incredible",
        "alert",
        "urgent",
        "catastrophe",
        "explosive",
        "censored",
        "hidden truth",
        "they don't want you to know",
    },
}

# Mots-outils propres à CHAQUE langue (aucun mot présent dans les deux : « a », « on »,
# « en », « son » sont donc volontairement absents — ils ne discriminent rien).
_MOTS_OUTILS = {
    "fr": {
        "le", "la", "les", "des", "une", "un", "est", "et", "de", "du", "que",
        "qui", "pour", "dans", "sur", "avec", "par", "plus", "ne", "pas", "aux",
        "ce", "cette", "ses", "leur", "leurs", "vous", "nous", "ils", "elles",
        "mais", "donc", "sont", "apres", "après", "selon", "contre", "sans",
    },
    "en": {
        "the", "of", "and", "to", "in", "is", "that", "it", "for", "with", "as",
        "was", "are", "this", "be", "by", "from", "at", "have", "has", "not",
        "they", "you", "but", "his", "her", "its", "will", "said", "after",
    },
}

_ACCENTS_FR = re.compile(r"[àâéèêëïîôùûç]")

# Liens de toute forme (markdown Reddit, URL nue, reliquat d'attribut HTML).
_URL = re.compile(r"https?://\S+|www\.\S+")


def _detecter_langue(texte: str) -> str:
    """Compare le poids des mots-outils français et anglais — cf. US-01 scraper,
    couverture au moins anglophone/francophone.

    Deux défauts de la version précédente sont corrigés ici (cf. audit phase 10, P3) :

    - elle ne comptait QUE le français (dix mots-outils, seuil de deux) et repliait
      sur l'anglais dans tous les autres cas. Un titre de presse français court
      (« Scandale : trois ministres démissionnent ») n'atteint pas ce seuil et se
      voyait donc appliquer le lexique ANGLAIS, rendant tout le volet
      sensationnalisme francophone inopérant sur les textes courts — c'est-à-dire
      sur les titres, là où le putaclic se joue ;
    - elle dédupliquait les mots (`set`) avant de compter, ce qui effaçait
      l'information la plus utile : « le » répété six fois pesait autant qu'une
      occurrence unique.

    On compare désormais deux poids, sur les OCCURRENCES. En cas d'égalité — un
    texte très court peut n'avoir aucun mot-outil — les caractères accentués
    tranchent : ils sont un marqueur français fort et quasi absents de l'anglais."""
    mots = re.findall(r"[a-zàâäéèêëïîôöùûüç]+", texte.lower())
    poids = {
        langue: sum(1 for mot in mots if mot in liste)
        for langue, liste in _MOTS_OUTILS.items()
    }
    if poids["fr"] == poids["en"]:
        return "fr" if _ACCENTS_FR.search(texte.lower()) else "en"
    return max(poids, key=poids.get)


# En deçà, un corps de texte est trop court pour que l'absence de citation
# signifie quoi que ce soit : un post Reddit de type lien a un `selftext` vide, et
# le pénaliser de 15 points pour « aucune citation » n'est pas un signal, c'est du
# bruit (cf. audit, finding M3).
LONGUEUR_MIN_POUR_CITATION = 200

# En deçà, un titre sans corps ne porte aucune matière stylistique : un post
# réduit à « GME » n'a ni ponctuation à juger, ni vocabulaire à peser, ni longueur
# permettant de conclure quoi que ce soit. C'est le seul cas où le signal
# s'exclut.
LONGUEUR_MIN_TITRE_JUGEABLE = 20


def evaluer_style(titre: str, contenu: str, auteur: str | None) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": "style"}. Chaque
    signal détecté contribue individuellement à la justification tracée (cf. US-05
    évaluateur, critère d'acceptation "chaque signal détecté... de façon traçable").

    `valeur` est None (signal exclu, cf. US-08) quand l'article n'offre aucune
    matière stylistique : pas de corps, un titre trop court pour être jugé, et
    aucun signal détecté par ailleurs. Affirmer alors une suspicion basse (le
    plancher à 10.0) serait une conclusion tirée de rien.

    Ce critère est volontairement ÉTROIT et ATTEIGNABLE, deux propriétés que les
    versions précédentes n'ont pas eues ensemble :

    - la première n'excluait que si titre ET contenu étaient vides — or
      `scraper/rss.py` rejette toute entrée sans titre et Reddit en impose un :
      condition jamais remplie, `non_evaluable` hors d'atteinte (audit phase 7, N2) ;
    - la deuxième excluait dès que le corps était court, ce qui aurait avalé la
      majeure partie des posts Reddit de type lien et fait disparaître leurs
      articles du frontend.

    Un post réduit à un ticker (« GME ») sans corps, lui, existe et ne se juge
    pas."""
    signaux = []
    penalite = 0.0

    if not auteur:
        signaux.append("aucun auteur identifiable")
        penalite += 20.0

    # Les URL sont retirées AVANT la recherche de citation et AVANT la mesure de
    # longueur (cf. audit phase 10, P4). Une URL entre guillemets — un lien markdown
    # dans un `selftext` Reddit, un attribut `href` qu'un flux mal nettoyé aurait
    # laissé passer — satisfait `"[^"]{10,}"` sans être une citation. Et un corps
    # réduit à une liste de liens n'a pas de prose à juger : c'est ce qui reste après
    # retrait qui décide s'il est assez long.
    corps_analysable = _URL.sub(" ", contenu).strip()
    corps_jugeable = len(corps_analysable) >= LONGUEUR_MIN_POUR_CITATION
    if corps_jugeable:
        a_une_citation = bool(re.search(r'"[^"]{10,}"|«[^»]{10,}»', corps_analysable))
        if not a_une_citation:
            signaux.append("aucune citation ou source nommée détectée")
            penalite += 15.0

    if titre.count("!") + titre.count("?") >= 2 or re.search(r"[!?]{2,}", titre):
        signaux.append("ponctuation excessive dans le titre")
        penalite += 15.0

    # Langue et vocabulaire jugés sur le texte débarrassé de ses URL, pour la même
    # raison : un nom de domaine n'est ni un mot-outil ni un marqueur de ton.
    texte_analysable = f"{titre} {corps_analysable}"
    langue = _detecter_langue(texte_analysable)
    texte_normalise = texte_analysable.lower()
    mots_trouves = sorted(m for m in MOTS_CHARGES[langue] if m in texte_normalise)
    if mots_trouves:
        signaux.append(f"vocabulaire à forte charge émotionnelle ({', '.join(mots_trouves[:3])})")
        penalite += min(30.0, 10.0 * len(mots_trouves))

    if not signaux:
        if not corps_analysable and len(titre.strip()) < LONGUEUR_MIN_TITRE_JUGEABLE:
            return {
                "valeur": None,
                "raison": (
                    "non applicable — aucun corps et titre trop court pour porter un "
                    "signal stylistique"
                ),
                "preuve_id": "style",
            }
        return {
            "valeur": 10.0,
            "raison": "aucun signal stylistique de sensationnalisme détecté",
            "preuve_id": "style",
        }

    return {
        "valeur": min(100.0, penalite),
        "raison": "; ".join(signaux),
        "preuve_id": "style",
    }
