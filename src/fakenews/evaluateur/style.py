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

_MOTS_OUTILS_FR = {"le", "la", "les", "des", "une", "est", "et", "de", "du", "un"}


def _detecter_langue(texte: str) -> str:
    """Détection minimale (mots-outils français fréquents vs repli anglais) — cf.
    US-01 scraper, couverture au moins anglophone/francophone."""
    mots = set(re.findall(r"[a-zàâäéèêëïîôöùûüç]+", texte.lower()))
    return "fr" if len(mots & _MOTS_OUTILS_FR) >= 2 else "en"


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

    corps_jugeable = len(contenu.strip()) >= LONGUEUR_MIN_POUR_CITATION
    if corps_jugeable:
        a_une_citation = bool(re.search(r'"[^"]{10,}"|«[^»]{10,}»', contenu))
        if not a_une_citation:
            signaux.append("aucune citation ou source nommée détectée")
            penalite += 15.0

    if titre.count("!") + titre.count("?") >= 2 or re.search(r"[!?]{2,}", titre):
        signaux.append("ponctuation excessive dans le titre")
        penalite += 15.0

    langue = _detecter_langue(f"{titre} {contenu}")
    texte_normalise = f"{titre} {contenu}".lower()
    mots_trouves = sorted(m for m in MOTS_CHARGES[langue] if m in texte_normalise)
    if mots_trouves:
        signaux.append(f"vocabulaire à forte charge émotionnelle ({', '.join(mots_trouves[:3])})")
        penalite += min(30.0, 10.0 * len(mots_trouves))

    if not signaux:
        if not contenu.strip() and len(titre.strip()) < LONGUEUR_MIN_TITRE_JUGEABLE:
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
