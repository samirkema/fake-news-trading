from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.evaluateur.run_evaluateur import evaluer_articles_non_scores
from fakenews.models import Article, Score


def _inserer_article(session, domaine_source, suffixe, auteur="Auteur Test", contenu='Un article avec "une citation valable ici".'):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu=contenu,
        auteur=auteur,
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
#
# Aucune ANTHROPIC_API_KEY / GOOGLE_FACT_CHECK_API_KEY n'est configurée dans cet
# environnement de test : US-07 (llm_bootstrap) est absent de sous_scores (client LLM
# non créé, cf. run_evaluateur.py) et US-03 (fact_checking) a systématiquement
# valeur=None (clé absente, cf. fact_checking.py) — comportements dégradés attendus.
# US-04 (source_primaire) est toujours présent dans sous_scores mais reste à
# valeur=None tant que les articles de test ne citent aucune entreprise de
# ENTREPRISES_CONNUES (cf. source_primaire.py) : aucun appel réseau réel n'est donc
# déclenché par ces tests. Seuls US-01 (réputation) et US-05 (style) contribuent
# effectivement au score dans les tests ci-dessous.


def test_article_fiable_et_style_propre_recoit_un_score_bas(db_session):
    # auteur + citation + pas de vocabulaire chargé -> style à sa valeur plancher
    # (10.0), comme réputation fiable (5.0) : les deux signaux tirent vers le bas.
    article = _inserer_article(db_session, "bbc.com", "fiable")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score.non_evaluable is False
    assert set(score.sous_scores) == {"reputation", "style", "fact_checking", "source_primaire"}
    assert score.sous_scores["reputation"]["valeur"] == 5.0
    assert score.sous_scores["style"]["valeur"] == 10.0
    assert score.sous_scores["fact_checking"]["valeur"] is None
    assert score.sous_scores["source_primaire"]["valeur"] is None
    # fact_checking et source_primaire exclus (valeur=None) : seuls reputation/style
    # contribuent. (1.0*5.0 + 0.5*10.0) / 1.5 = 6.67 — colonne NUMERIC, comparer en
    # float (Decimal('6.67') == 6.67 est False : représentation binaire non exacte).
    assert float(score.score_final) == 6.67
    assert score.poids == {"reputation": 1.0, "style": 0.5, "fact_checking": 1.5, "source_primaire": 1.5}


def test_article_domaine_inconnu_reputation_exclue_mais_style_contribue(db_session):
    # Réputation exclue (domaine inconnu, cf. US-01 évaluateur) mais le style ne
    # s'exclut jamais (heuristique toujours tranchée) : l'article reste évaluable,
    # sur la seule base du style. non_évaluable ne peut plus se produire avec ces
    # deux signaux à la fois — cf. test_tous_les_signaux_exclus_donne_non_evaluable
    # (test_score.py) pour le cas non_évaluable testé au niveau de l'agrégateur seul.
    article = _inserer_article(db_session, "un-domaine-jamais-vu.example", "inconnu")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score.sous_scores["reputation"]["valeur"] is None
    assert score.non_evaluable is False
    assert float(score.score_final) == 10.0  # style seul contribue, à sa valeur plancher


def test_article_style_douteux_augmente_le_score(db_session):
    article = _inserer_article(
        db_session,
        "un-domaine-jamais-vu.example",
        "style-douteux",
        auteur=None,
        contenu="Aucune citation. Scandale et catastrophe.",
    )
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    assert score.sous_scores["style"]["valeur"] > 10.0


def test_article_deja_score_n_est_pas_re_evalue(db_session):
    article = _inserer_article(db_session, "bbc.com", "deja-score")
    evaluer_articles_non_scores(db_session)
    db_session.flush()

    premier_score_id = db_session.execute(select(Score.id).where(Score.article_id == article.id)).scalar_one()

    evaluer_articles_non_scores(db_session)  # deuxième passage : rien de neuf pour cet article

    scores = db_session.execute(select(Score).where(Score.article_id == article.id)).scalars().all()
    assert len(scores) == 1
    assert scores[0].id == premier_score_id
