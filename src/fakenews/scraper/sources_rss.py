"""Sources RSS retenues pour la collecte (US-01 scraper, cf. doc/userstories_scraper.md).

Chaque entrée : nom du flux, domaine associé (utilisé comme `domaine_source`), URL du flux,
et un éventuel `repli` (même forme) utilisé si le flux principal est indisponible.

Statut vérifié à l'implémentation (curl direct) :
- reutersagency.com/feed n'existe plus (Reuters a supprimé ses flux RSS publics en 2020) ->
  repli sur The Guardian World (US-01 scraper).
- infowars.com/rss.xml répond HTTP 200 mais sert une page "Off Air", pas un flux RSS.
- worldnewsdailyreport.com/feed/ répond HTTP 200 mais sert du HTML (mur anti-bot), pas un flux RSS.
  Les deux sont exclus de la liste active pour l'instant plutôt que codés en dur comme
  fonctionnels — à revérifier périodiquement, pas une liste figée.
"""

RSS_SOURCES = [
    # -- Haute réputation --
    {
        "nom": "BBC World",
        "domaine_source": "bbc.com",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "nom": "Le Monde",
        "domaine_source": "lemonde.fr",
        "url": "https://www.lemonde.fr/rss/une.xml",
    },
    {
        "nom": "Reuters",
        "domaine_source": "reuters.com",
        "url": "https://www.reutersagency.com/feed/",
        "repli": {
            "nom": "The Guardian World",
            "domaine_source": "theguardian.com",
            "url": "https://www.theguardian.com/world/rss",
        },
    },
    # -- Douteux (anglophone) --
    {
        "nom": "NaturalNews",
        "domaine_source": "naturalnews.com",
        "url": "https://www.naturalnews.com/rss.xml",
    },
    {
        "nom": "Before It's News",
        "domaine_source": "beforeitsnews.com",
        "url": "https://beforeitsnews.com/rss/",
    },
    # -- Satire auto-déclarée --
    {
        "nom": "The Onion",
        "domaine_source": "theonion.com",
        "url": "https://theonion.com/feed/",
    },
    {
        "nom": "Babylon Bee",
        "domaine_source": "babylonbee.com",
        "url": "https://babylonbee.com/feed",
    },
    {
        "nom": "Le Gorafi",
        "domaine_source": "legorafi.fr",
        "url": "https://www.legorafi.fr/feed/",
    },
]
