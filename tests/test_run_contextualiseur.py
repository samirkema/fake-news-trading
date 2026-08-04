from datetime import datetime, timezone

from fakenews.contextualiseur.run_contextualiseur import selectionner_articles_a_traiter
from fakenews.models import Article, MiseEnContexte, Score


def _inserer_article_score(session, suffixe, score_final, non_evaluable=False):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu="Contenu",
        domaine_source="test-run-contextualiseur.invalid",
        date_publication=datetime.now(timezone.utc),
        url=f"https://test-run-contextualiseur.invalid/{suffixe}",
        url_canonique=f"https://test-run-contextualiseur.invalid/{suffixe}",
        hash_contenu=f"hash-rc-{suffixe}",
        plateforme="rss",
        metadonnees={},
    )
    session.add(article)
    session.flush()
    session.add(
        Score(
            article_id=article.id,
            sous_scores={"reputation": {"valeur": score_final, "raison": "t", "preuve_id": "reputation"}},
            poids={"reputation": 1.0},
            score_final=score_final,
            non_evaluable=non_evaluable,
        )
    )
    session.flush()
    return article


def test_article_au_dessus_du_seuil_est_selectionne(db_session):
    article = _inserer_article_score(db_session, "au-dessus", 90.0)

    selection = selectionner_articles_a_traiter(db_session)

    assert article.id in {s["article_id"] for s in selection}


def test_article_sous_le_seuil_n_est_pas_selectionne(db_session):
    article = _inserer_article_score(db_session, "en-dessous", 10.0)

    selection = selectionner_articles_a_traiter(db_session)

    assert article.id not in {s["article_id"] for s in selection}


def test_article_deja_traite_est_exclu(db_session):
    article = _inserer_article_score(db_session, "deja-traite", 90.0)
    db_session.add(
        MiseEnContexte(
            article_id=article.id,
            explication="déjà fait",
            faits_traces=[],
            deductions_llm=[],
            sources_utilisees=[],
            niveau_confiance=None,
            avertissement="a",
        )
    )
    db_session.flush()

    selection = selectionner_articles_a_traiter(db_session)

    assert article.id not in {s["article_id"] for s in selection}
