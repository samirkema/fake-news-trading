from fakenews.scraper.normalisation import canonicaliser_url, hacher_contenu


def test_canonicaliser_url_retire_query_string():
    assert canonicaliser_url("https://x.com/a?utm_source=y") == "https://x.com/a"


def test_canonicaliser_url_retire_fragment():
    assert canonicaliser_url("https://x.com/a#section") == "https://x.com/a"


def test_canonicaliser_url_normalise_la_casse_scheme_et_host():
    assert canonicaliser_url("HTTPS://X.COM/a") == "https://x.com/a"


def test_canonicaliser_url_preserve_la_casse_du_chemin():
    assert canonicaliser_url("https://x.com/Article-Titre") == "https://x.com/Article-Titre"


def test_canonicaliser_url_deux_urls_equivalentes_donnent_le_meme_resultat():
    a = canonicaliser_url("https://x.com/a?ref=1&utm_campaign=z")
    b = canonicaliser_url("https://x.com/a?ref=2#truc")
    assert a == b == "https://x.com/a"


def test_hacher_contenu_deterministe():
    assert hacher_contenu("titre", "contenu") == hacher_contenu("titre", "contenu")


def test_hacher_contenu_sensible_au_titre_et_au_contenu():
    base = hacher_contenu("titre", "contenu")
    assert hacher_contenu("autre titre", "contenu") != base
    assert hacher_contenu("titre", "autre contenu") != base
