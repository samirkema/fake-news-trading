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


def evaluer_style(titre: str, contenu: str, auteur: str | None) -> dict:
    """Retourne {"valeur": float, "raison": str, "preuve_id": "style"}. Chaque
    signal détecté contribue individuellement à la justification tracée (cf. US-05
    évaluateur, critère d'acceptation "chaque signal détecté... de façon traçable")."""
    signaux = []
    penalite = 0.0

    if not auteur:
        signaux.append("aucun auteur identifiable")
        penalite += 20.0

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
