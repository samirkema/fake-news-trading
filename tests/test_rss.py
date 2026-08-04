from datetime import datetime, timezone

import feedparser

from fakenews.scraper.rss import _extraire_contenu, _extraire_date_publication, _flux_utilisable

FLUX_VALIDE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title>
<item><title>T1</title><link>http://example.com/1</link>
<pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate><description>desc 1</description></item>
</channel></rss>"""

FLUX_VIDE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>test</title></channel></rss>"""

# Déclaration DOCTYPE non standard : feedparser lève bozo=1 mais parse quand même l'entrée.
FLUX_BOZO_MAIS_EXPLOITABLE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE rss [<!ENTITY x "y">]>
<rss version="2.0"><channel><title>test</title>
<item><title>T1</title><link>http://example.com/1</link>
<pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_flux_valide_est_utilisable():
    assert _flux_utilisable(feedparser.parse(FLUX_VALIDE)) is True


def test_flux_sans_entree_n_est_pas_utilisable():
    assert _flux_utilisable(feedparser.parse(FLUX_VIDE)) is False


def test_flux_bozo_avec_entrees_reste_utilisable():
    # Reproduit le bug relevé en audit : bozo=True ne doit pas être traité comme "indisponible"
    # tant que des entrées ont bien été extraites.
    flux = feedparser.parse(FLUX_BOZO_MAIS_EXPLOITABLE)
    assert flux.bozo == 1
    assert _flux_utilisable(flux) is True


def test_extraire_date_publication_valide():
    entree = feedparser.parse(FLUX_VALIDE).entries[0]
    assert _extraire_date_publication(entree) == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


def test_extraire_date_publication_absente_retourne_none():
    entree = {"title": "T", "link": "http://x"}
    assert _extraire_date_publication(entree) is None


def test_extraire_contenu_privilegie_content_encoded():
    entree = {"content": [{"value": "corps complet"}], "summary": "résumé"}
    assert _extraire_contenu(entree) == "corps complet"


def test_extraire_contenu_repli_sur_summary():
    entree = feedparser.parse(FLUX_VALIDE).entries[0]
    assert _extraire_contenu(entree) == "desc 1"


def test_extraire_contenu_vide_si_rien_de_disponible():
    assert _extraire_contenu({}) == ""
