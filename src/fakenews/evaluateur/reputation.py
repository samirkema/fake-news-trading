"""US-01 évaluateur : réputation de la source (cf. doc/userstories_évaluateur.md).

Liste de référence conceptuellement partagée avec le scraper (doc/userstories_scraper.md
US-01 : "les domaines à faible crédibilité collectés sont tirés de la même liste de
référence que celle utilisée pour la réputation de la source") — dupliquée ici plutôt
qu'importée depuis src/fakenews/scraper/ pour respecter le principe d'architecture
"les blocs ne s'appellent pas entre eux directement" (doc/architecture.md) ; à garder
en phase manuellement avec la liste "douteux" de sources_rss.py.
"""

FIABLE = {
    "bbc.com",
    "lemonde.fr",
    "theguardian.com",
}

DOUTEUX = {
    "naturalnews.com",
    "beforeitsnews.com",
    "infowars.com",
    "worldnewsdailyreport.com",
}

VALEUR_FIABLE = 5.0
VALEUR_DOUTEUX = 90.0


def evaluer_reputation(domaine_source: str | None) -> dict:
    """Retourne {"valeur": float | None, "raison": str, "preuve_id": "reputation"}.
    `valeur` est None (signal exclu, cf. US-08) quand le domaine est absent des deux
    listes — y compris pour les domaines de satire auto-déclarée (theonion.com,
    babylonbee.com, legorafi.fr), qui ne sont ni fiables ni douteux au sens de ce
    signal et ne doivent donc être ni pénalisés ni avantagés par lui."""
    if domaine_source in DOUTEUX:
        return {
            "valeur": VALEUR_DOUTEUX,
            "raison": f"domaine « {domaine_source} » sur la liste de référence des sources douteuses",
            "preuve_id": "reputation",
        }
    if domaine_source in FIABLE:
        return {
            "valeur": VALEUR_FIABLE,
            "raison": f"domaine « {domaine_source} » sur la liste de référence des sources fiables",
            "preuve_id": "reputation",
        }
    return {
        "valeur": None,
        "raison": "réputation inconnue — domaine absent des deux listes de référence",
        "preuve_id": "reputation",
    }
