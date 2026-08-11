from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.evaluateur.backfill_llm_bootstrap import backfiller_llm_bootstrap
from fakenews.evaluateur.score import POIDS_PAR_DEFAUT, calculer_score_composite
from fakenews.models import Article, Score
from tests._llm_factice import ClientFactice


def _inserer_article_score(session, suffixe, sous_scores):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu="Contenu",
        domaine_source="bbc.com",
        date_publication=datetime.now(timezone.utc),
        url=f"https://test-backfill.invalid/{suffixe}",
        url_canonique=f"https://test-backfill.invalid/{suffixe}",
        hash_contenu=f"hash-backfill-{suffixe}",
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


def test_signal_manquant_est_backfille(db_session):
    article, score = _inserer_article_score(
        db_session,
        "sans-llm",
        {"reputation": {"valeur": 5.0, "raison": "test", "preuve_id": "reputation"}},
    )
    client = ClientFactice(reponse_input={"score_suspicion": 42.0, "justification": "test"})

    nb = backfiller_llm_bootstrap(db_session, client=client)
    db_session.flush()

    assert nb == 1
    score_maj = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score_maj.sous_scores["llm_bootstrap"]["valeur"] == 42.0
    assert "llm_bootstrap" in score_maj.poids
    # (1.0*5.0 + 1.5*42.0) / 2.5 = 27.2
    assert float(score_maj.score_final) == 27.2


def test_signal_exclu_par_echec_precedent_est_retente(db_session):
    article, score = _inserer_article_score(
        db_session,
        "llm-exclu",
        {
            "reputation": {"valeur": 5.0, "raison": "test", "preuve_id": "reputation"},
            "llm_bootstrap": {"valeur": None, "raison": "appel LLM indisponible", "preuve_id": "llm_bootstrap"},
        },
    )
    client = ClientFactice(reponse_input={"score_suspicion": 80.0, "justification": "test"})

    nb = backfiller_llm_bootstrap(db_session, client=client)
    db_session.flush()

    assert nb == 1
    score_maj = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score_maj.sous_scores["llm_bootstrap"]["valeur"] == 80.0


def test_signal_deja_valide_n_est_pas_retraite(db_session):
    article, score = _inserer_article_score(
        db_session,
        "llm-deja-ok",
        {
            "reputation": {"valeur": 5.0, "raison": "test", "preuve_id": "reputation"},
            "llm_bootstrap": {"valeur": 10.0, "raison": "déjà calculé", "preuve_id": "llm_bootstrap"},
        },
    )
    client = ClientFactice(reponse_input={"score_suspicion": 99.0, "justification": "ne doit jamais être appelé"})

    nb = backfiller_llm_bootstrap(db_session, client=client)
    db_session.flush()

    assert nb == 0
    score_inchange = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score_inchange.sous_scores["llm_bootstrap"]["valeur"] == 10.0
