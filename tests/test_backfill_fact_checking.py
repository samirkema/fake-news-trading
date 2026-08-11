from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from fakenews.evaluateur.backfill_fact_checking import backfiller_fact_checking
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.models import Article, Score


def _client_factice(reponse_json):
    def handler(request):
        return httpx.Response(200, json=reponse_json)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _inserer_article_score(session, suffixe, sous_scores):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu="Contenu",
        domaine_source="bbc.com",
        date_publication=datetime.now(timezone.utc),
        url=f"https://test-backfill-fc.invalid/{suffixe}",
        url_canonique=f"https://test-backfill-fc.invalid/{suffixe}",
        hash_contenu=f"hash-backfill-fc-{suffixe}",
        plateforme="rss",
        metadonnees={},
    )
    session.add(article)
    session.flush()

    resultat = calculer_score_composite(sous_scores, POIDS_PAR_DEFAUT)
    score = Score(
        article_id=article.id,
        sous_scores=sous_scores,
        poids={signal: POIDS_PAR_DEFAUT[signal] for signal in sous_scores},
        score_final=resultat["score_final"],
        non_evaluable=resultat["non_evaluable"],
    )
    session.add(score)
    session.flush()
    return article, score


def test_signal_exclu_par_cle_absente_est_retente(db_session, monkeypatch):
    monkeypatch.setenv("GOOGLE_FACT_CHECK_API_KEY", "clef-test")
    article, score = _inserer_article_score(
        db_session,
        "cle-absente",
        {
            "reputation": {"valeur": 5.0, "raison": "test", "preuve_id": "reputation"},
            "fact_checking": {"valeur": None, "raison": "clé API Google Fact Check absente", "preuve_id": "fact_checking"},
        },
    )
    reponse = {"claims": [{"claimReview": [{"textualRating": "False", "url": "https://factcheck.example/1"}]}]}
    client = _client_factice(reponse)

    nb = backfiller_fact_checking(db_session, client=client)
    db_session.flush()

    assert nb == 1
    score_maj = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score_maj.sous_scores["fact_checking"]["valeur"] == 90.0
    assert "fact_checking" in score_maj.poids
    # (1.0*5.0 + 1.5*90.0) / 2.5 = 56.0
    assert float(score_maj.score_final) == 56.0


def test_signal_deja_valide_n_est_pas_retraite(db_session, monkeypatch):
    monkeypatch.setenv("GOOGLE_FACT_CHECK_API_KEY", "clef-test")
    article, score = _inserer_article_score(
        db_session,
        "deja-ok",
        {
            "reputation": {"valeur": 5.0, "raison": "test", "preuve_id": "reputation"},
            "fact_checking": {"valeur": 5.0, "raison": "déjà calculé", "preuve_id": "fact_checking:https://x"},
        },
    )

    def handler(request):
        raise AssertionError("ne doit jamais être appelé")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    nb = backfiller_fact_checking(db_session, client=client)
    db_session.flush()

    assert nb == 0
    score_inchange = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score_inchange.sous_scores["fact_checking"]["valeur"] == 5.0
