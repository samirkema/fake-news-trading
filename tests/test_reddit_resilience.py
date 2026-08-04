from types import SimpleNamespace

from fakenews.scraper.reddit import collecter_reddit


def _bon_post(suffixe):
    return SimpleNamespace(
        title=f"Titre {suffixe}",
        selftext="Corps",
        created_utc=1704110400,
        permalink=f"/r/test/comments/{suffixe}/titre/",
        author=SimpleNamespace(name="auteur"),
        score=1,
        num_comments=0,
    )


class _SubredditFactice:
    def __init__(self, posts):
        self._posts = posts

    def new(self, limit):
        return iter(self._posts)


class _ClientFactice:
    def __init__(self, posts_par_subreddit):
        self._posts = posts_par_subreddit

    def subreddit(self, nom):
        return _SubredditFactice(self._posts.get(nom, []))


def test_un_post_malforme_n_interrompt_pas_le_reste_du_subreddit(db_session, monkeypatch, caplog):
    # Reproduit et corrige le bug d'audit QUAL-1 : un post sans les attributs attendus
    # (ici un objet vide, simulant une soumission malformée) ne doit ignorer que ce
    # post, pas interrompre la collecte du reste du subreddit ni des subreddits suivants.
    monkeypatch.setattr("fakenews.scraper.reddit.SUBREDDITS", ["a", "b"])

    post_malforme = SimpleNamespace()  # aucun attribut -> AttributeError dans normaliser_submission
    client = _ClientFactice(
        {
            "a": [post_malforme, _bon_post("1")],
            "b": [_bon_post("2")],
        }
    )

    with caplog.at_level("WARNING"):
        bilan = collecter_reddit(db_session, client=client)

    assert bilan["a"]["statut"] == "ok"
    assert bilan["a"]["ignores"] == 1
    assert bilan["a"]["ajoutes"] == 1
    assert bilan["b"]["statut"] == "ok"
    assert bilan["b"]["ajoutes"] == 1

    # Le poste ignoré doit être visible en warning (finding QUAL-1-bis, audit de suivi) :
    # un taux d'échec élevé sur r/a ne doit pas être noyé au niveau INFO.
    avertissements = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("r/a" in m and "1 post" in m for m in avertissements)


def test_client_impossible_a_creer_degrade_sans_planter(db_session, monkeypatch, caplog):
    # Reproduit et corrige le bug High de l'audit de suivi (Phase 5) : sans identifiants
    # Reddit configurés, creer_client() lève KeyError — auparavant hors de toute
    # protection, ça faisait planter tout run_scraper.py et empêchait évaluateur/
    # contextualiseur de s'exécuter dans le pipeline hebdomadaire.
    monkeypatch.setattr("fakenews.scraper.reddit.SUBREDDITS", ["a", "b"])

    def _creer_client_qui_echoue():
        raise KeyError("REDDIT_CLIENT_ID")

    monkeypatch.setattr("fakenews.scraper.reddit.creer_client", _creer_client_qui_echoue)

    with caplog.at_level("WARNING"):
        bilan = collecter_reddit(db_session)  # pas de client injecté -> passe par creer_client()

    assert bilan == {
        "a": {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0},
        "b": {"statut": "indisponible", "ajoutes": 0, "mis_a_jour": 0, "ignores": 0},
    }
    assert any("Reddit indisponible" in r.message for r in caplog.records if r.levelname == "WARNING")
