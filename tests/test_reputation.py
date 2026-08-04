from fakenews.evaluateur.reputation import evaluer_reputation


def test_domaine_fiable():
    resultat = evaluer_reputation("bbc.com")
    assert resultat["valeur"] == 5.0
    assert resultat["preuve_id"] == "reputation"


def test_domaine_douteux():
    resultat = evaluer_reputation("naturalnews.com")
    assert resultat["valeur"] == 90.0


def test_domaine_inconnu_est_exclu_pas_penalise():
    resultat = evaluer_reputation("un-site-jamais-vu.example")
    assert resultat["valeur"] is None


def test_domaine_none_est_exclu():
    resultat = evaluer_reputation(None)
    assert resultat["valeur"] is None


def test_satire_n_est_ni_fiable_ni_douteuse():
    # Les domaines de satire auto-déclarée ne doivent être ni pénalisés ni avantagés
    # par ce signal (cf. userstories_scraper.md US-01, catégorie distincte de la
    # désinformation) — absence délibérée des deux listes.
    for domaine in ("theonion.com", "babylonbee.com", "legorafi.fr"):
        assert evaluer_reputation(domaine)["valeur"] is None
