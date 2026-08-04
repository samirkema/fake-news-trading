from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.evaluateur.run_evaluateur import evaluer_articles_non_scores
from fakenews.models import Article, Score


def _inserer_article(session, domaine_source, suffixe):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu="Contenu",
        domaine_source=domaine_source,
        date_publication=datetime.now(timezone.utc),
        url=f"https://test-run-evaluateur.invalid/{suffixe}",
        url_canonique=f"https://test-run-evaluateur.invalid/{suffixe}",
        hash_contenu=f"hash-{suffixe}",
        plateforme="rss",
        metadonnees={},
    )
    session.add(article)
    session.flush()
    return article


# NB : la base de test locale contient aussi de vraies données collectées par le
# scraper (278+ articles non scorés) — evaluer_articles_non_scores() les traite tous,
# par conception (même logique que collecter_rss/collecter_reddit). Les assertions
# ci-dessous vérifient donc le score de l'article de CE test spécifiquement, jamais
# un compte total qui inclurait les vraies données.


def test_article_fiable_recoit_un_score_bas(db_session):
    article = _inserer_article(db_session, "bbc.com", "fiable")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score.non_evaluable is False
    assert score.score_final == 5.0
    assert score.sous_scores == {
        "reputation": {
            "valeur": 5.0,
            "raison": "domaine « bbc.com » sur la liste de référence des sources fiables",
            "preuve_id": "reputation",
        }
    }
    assert score.poids == {"reputation": 1.0}


def test_article_domaine_inconnu_est_non_evaluable(db_session):
    # Seul signal implémenté = réputation ; si elle est exclue (domaine inconnu),
    # tous les signaux disponibles sont exclus -> non_évaluable (US-08 évaluateur).
    article = _inserer_article(db_session, "un-domaine-jamais-vu.example", "inconnu")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score.non_evaluable is True
    assert score.score_final is None


def test_article_deja_score_n_est_pas_re_evalue(db_session):
    article = _inserer_article(db_session, "bbc.com", "deja-score")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    premier_score_id = db_session.execute(select(Score.id).where(Score.article_id == article.id)).scalar_one()

    evaluer_articles_non_scores(db_session)  # deuxième passage : rien de neuf pour cet article

    scores = db_session.execute(select(Score).where(Score.article_id == article.id)).scalars().all()
    assert len(scores) == 1
    assert scores[0].id == premier_score_id
