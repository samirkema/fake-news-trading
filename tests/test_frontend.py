from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from fakenews.frontend.app import app, get_session
from fakenews.models import Article, MiseEnContexte, Score


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _inserer_article_avec_score(session, suffixe, score_final, non_evaluable=False, domaine="test-frontend.invalid"):
    article = Article(
        titre=f"Titre {suffixe}",
        contenu="Contenu",
        domaine_source=domaine,
        date_publication=datetime.now(timezone.utc),
        url=f"https://test-frontend.invalid/{suffixe}",
        url_canonique=f"https://test-frontend.invalid/{suffixe}",
        hash_contenu=f"hash-frontend-{suffixe}",
        plateforme="rss",
        metadonnees={},
    )
    session.add(article)
    session.flush()
    session.add(
        Score(
            article_id=article.id,
            sous_scores={"reputation": {"valeur": score_final, "raison": "test", "preuve_id": "reputation"}}
            if not non_evaluable
            else {"reputation": {"valeur": None, "raison": "test", "preuve_id": "reputation"}},
            poids={"reputation": 1.0},
            score_final=None if non_evaluable else score_final,
            non_evaluable=non_evaluable,
        )
    )
    session.flush()
    return article


def test_liste_par_defaut_masque_les_articles_sous_le_seuil(client, db_session):
    _inserer_article_avec_score(db_session, "suspect", 80.0)
    _inserer_article_avec_score(db_session, "fiable", 10.0)

    reponse = client.get("/")

    assert reponse.status_code == 200
    assert "Titre suspect" in reponse.text
    assert "Titre fiable" not in reponse.text


def test_liste_mode_tous_affiche_aussi_les_articles_fiables(client, db_session):
    _inserer_article_avec_score(db_session, "suspect2", 80.0)
    _inserer_article_avec_score(db_session, "fiable2", 10.0)

    reponse = client.get("/?tous=1")

    assert "Titre suspect2" in reponse.text
    assert "Titre fiable2" in reponse.text


def test_liste_masque_toujours_les_articles_non_evaluables(client, db_session):
    _inserer_article_avec_score(db_session, "non-eval", None, non_evaluable=True)

    reponse = client.get("/?tous=1")

    assert "Titre non-eval" not in reponse.text


def test_detail_affiche_signal_exclu_comme_non_applicable(client, db_session):
    article = _inserer_article_avec_score(db_session, "exclu", None, non_evaluable=True)

    reponse = client.get(f"/articles/{article.id}")

    assert reponse.status_code == 200
    assert "non applicable" in reponse.text


def test_detail_sans_mise_en_contexte_indique_pas_encore_traite(client, db_session):
    article = _inserer_article_avec_score(db_session, "sans-contexte", 80.0)

    reponse = client.get(f"/articles/{article.id}")

    # Jinja2 échappe l'apostrophe de "n'a" en &#39; dans le HTML rendu, d'où le
    # découpage de l'assertion pour éviter de dépendre de l'échappement exact.
    assert "encore été générée" in reponse.text


def test_detail_avec_mise_en_contexte_affiche_explication(client, db_session):
    article = _inserer_article_avec_score(db_session, "avec-contexte", 90.0)
    db_session.add(
        MiseEnContexte(
            article_id=article.id,
            explication="Explication de test bien visible",
            faits_traces=[],
            deductions_llm=[],
            sources_utilisees=[],
            niveau_confiance="moyen",
            avertissement="avertissement de test",
        )
    )
    db_session.flush()

    reponse = client.get(f"/articles/{article.id}")

    assert "Explication de test bien visible" in reponse.text


def test_article_introuvable_retourne_404(client, db_session):
    import uuid

    reponse = client.get(f"/articles/{uuid.uuid4()}")
    assert reponse.status_code == 404


def test_avertissement_visible_sur_la_liste_et_le_detail(client, db_session):
    article = _inserer_article_avec_score(db_session, "avert", 80.0)

    # Sous-chaîne sans apostrophe : AVERTISSEMENT complet contient "s'appuyant", que
    # Jinja2 échappe en &#39; dans le HTML rendu (cf. test précédent).
    extrait = "Évaluation automatisée générée par algorithme"
    assert extrait in client.get("/").text
    assert extrait in client.get(f"/articles/{article.id}").text


def test_authentification_requise_si_mot_de_passe_configure(client, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")

    sans_auth = client.get("/")
    assert sans_auth.status_code == 401

    avec_bon_mdp = client.get("/", auth=("peu importe", "secret"))
    assert avec_bon_mdp.status_code == 200

    avec_mauvais_mdp = client.get("/", auth=("peu importe", "faux"))
    assert avec_mauvais_mdp.status_code == 401


def test_pas_d_authentification_en_mode_local(client, monkeypatch):
    monkeypatch.delenv("FRONTEND_PASSWORD", raising=False)
    reponse = client.get("/")
    assert reponse.status_code == 200


def test_date_min_malformee_rejetee_proprement(client):
    # Reproduit puis corrige le bug d'audit : plantait en 500 (DataError SQL) avant
    # que date_min/date_max ne soient typés `date` — doit maintenant être rejeté par
    # la validation FastAPI (422), sans jamais atteindre la requête SQL.
    reponse = client.get("/?date_min=n-importe-quoi-pas-une-date")
    assert reponse.status_code == 422


def test_date_max_malformee_rejetee_proprement(client):
    reponse = client.get("/?date_max=n-importe-quoi-pas-une-date")
    assert reponse.status_code == 422


def test_date_min_valide_filtre_correctement(client, db_session):
    _inserer_article_avec_score(db_session, "date-ok", 80.0)
    reponse = client.get("/?date_min=2000-01-01")
    assert reponse.status_code == 200
    assert "Titre date-ok" in reponse.text


def test_pagination_limite_le_nombre_de_resultats_et_expose_page_suivante(client, db_session):
    for i in range(55):
        _inserer_article_avec_score(db_session, f"page-{i}", 80.0)

    page_1 = client.get("/")
    assert page_1.status_code == 200
    # class="score" n'apparaît qu'une fois par ligne de données (pas dans l'en-tête).
    assert page_1.text.count('class="score"') == 50
    assert "page suivante" in page_1.text
    assert "page précédente" not in page_1.text

    page_2 = client.get("/?page=2")
    assert page_2.status_code == 200
    assert page_2.text.count('class="score"') == 5
    assert "page précédente" in page_2.text
