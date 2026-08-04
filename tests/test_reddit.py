from datetime import datetime, timezone
from types import SimpleNamespace

from fakenews.scraper.reddit import normaliser_submission


def _fake_submission(**overrides):
    defaults = dict(
        title="Un titre",
        selftext="Le corps du post",
        created_utc=1704110400,  # 2024-01-01 12:00:00 UTC
        permalink="/r/stocks/comments/abc123/un_titre/",
        author=SimpleNamespace(name="un_auteur"),
        score=42,
        num_comments=7,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_normaliser_submission_champs_de_base():
    resultat = normaliser_submission(_fake_submission(), "stocks")
    assert resultat["titre"] == "Un titre"
    assert resultat["contenu"] == "Le corps du post"
    assert resultat["auteur"] == "un_auteur"
    assert resultat["plateforme"] == "reddit"
    assert resultat["domaine_source"] == "reddit.com/r/stocks"
    assert resultat["url"] == "https://www.reddit.com/r/stocks/comments/abc123/un_titre/"
    assert resultat["date_publication"] == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_normaliser_submission_metadonnees_volatiles():
    resultat = normaliser_submission(_fake_submission(score=100, num_comments=20), "wallstreetbets")
    assert resultat["metadonnees"] == {
        "subreddit": "wallstreetbets",
        "score": 100,
        "nb_commentaires": 20,
    }


def test_normaliser_submission_auteur_supprime():
    resultat = normaliser_submission(_fake_submission(author=None), "news")
    assert resultat["auteur"] is None


def test_normaliser_submission_post_sans_texte():
    resultat = normaliser_submission(_fake_submission(selftext=""), "worldnews")
    assert resultat["contenu"] == ""


def test_normaliser_submission_url_canonique_ignore_les_traqueurs():
    resultat = normaliser_submission(
        _fake_submission(permalink="/r/stocks/comments/abc123/un_titre/?utm_source=share"), "stocks"
    )
    assert resultat["url_canonique"] == "https://www.reddit.com/r/stocks/comments/abc123/un_titre/"
