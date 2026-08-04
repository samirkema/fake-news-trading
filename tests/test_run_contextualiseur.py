from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.contextualiseur.run_contextualiseur import selectionner_articles_a_traiter, traiter_selection
from fakenews.models import Article, MiseEnContexte, Score
from tests._llm_factice import ClientFactice


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


def test_traiter_selection_genere_et_persiste(db_session):
    article = _inserer_article_score(db_session, "a-generer", 90.0)
    selection = selectionner_articles_a_traiter(db_session)

    client = ClientFactice(
        reponse_input={
            "explication": "Signaux de suspicion détectés sur cet article.",
            "faits_traces": [{"preuve_id": "reputation", "texte": "domaine douteux"}],
            "deductions_llm": [],
            "niveau_confiance": "moyen",
        }
    )
    nb_generes = traiter_selection(db_session, selection, client=client)
    db_session.flush()

    assert nb_generes == len(selection)
    mise_en_contexte = db_session.execute(
        select(MiseEnContexte).where(MiseEnContexte.article_id == article.id)
    ).scalar_one()
    assert mise_en_contexte.explication == "Signaux de suspicion détectés sur cet article."
    assert mise_en_contexte.sources_utilisees == ["reputation"]
    assert mise_en_contexte.avertissement  # avertissement systématique (US-04) porté par la donnée


def test_traiter_selection_un_echec_n_interrompt_pas_les_suivants(db_session):
    article_1 = _inserer_article_score(db_session, "echec", 95.0)
    article_2 = _inserer_article_score(db_session, "ok", 90.0)
    selection = selectionner_articles_a_traiter(db_session)

    appels = {"n": 0}

    class _MessagesFactices:
        def create(self, **kwargs):
            appels["n"] += 1
            if appels["n"] == 1:
                raise RuntimeError("erreur API transitoire")
            from tests._llm_factice import BlocFactice, ReponseFactice

            return ReponseFactice(
                [BlocFactice("tool_use", {"explication": "ok", "faits_traces": [], "deductions_llm": [], "niveau_confiance": "faible"})]
            )

    class ClientQuiEchoueUneFois:
        @property
        def messages(self):
            return _MessagesFactices()

    nb_generes = traiter_selection(db_session, selection, client=ClientQuiEchoueUneFois())
    db_session.flush()

    assert nb_generes == 1
    total = (
        db_session.execute(
            select(MiseEnContexte).where(MiseEnContexte.article_id.in_([article_1.id, article_2.id]))
        )
        .scalars()
        .all()
    )
    assert len(total) == 1
