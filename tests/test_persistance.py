from datetime import datetime, timezone

from sqlalchemy import select

from fakenews.models import Article
from fakenews.scraper.persistance import enregistrer_ou_mettre_a_jour


def _champs(**overrides):
    defaults = dict(
        titre="Titre",
        contenu="Contenu",
        auteur=None,
        domaine_source="test-persistance-a.invalid",
        date_publication=datetime.now(timezone.utc),
        url="https://test-persistance-a.invalid/x",
        url_canonique="https://test-persistance-a.invalid/x",
        hash_contenu="hash-a",
        plateforme="rss",
        metadonnees={},
    )
    defaults.update(overrides)
    return defaults


def _articles_de_test(session):
    """La base de test locale contient aussi de vraies données collectées par le
    scraper (278+ lignes) — on ne doit compter que ce que CE test a écrit, identifié
    par le domaine factice réservé aux tests de ce fichier (*.invalid)."""
    return (
        session.execute(select(Article).where(Article.domaine_source.like("test-persistance-%")))
        .scalars()
        .all()
    )


def test_meme_url_canonique_est_un_doublon(db_session):
    enregistrer_ou_mettre_a_jour(db_session, _champs(hash_contenu="hash-1"))
    resultat = enregistrer_ou_mettre_a_jour(db_session, _champs(hash_contenu="hash-2"))  # contenu modifié, même URL
    db_session.flush()

    assert resultat in ("mis_a_jour", "inchange")
    assert len(_articles_de_test(db_session)) == 1


def test_meme_hash_meme_domaine_est_un_doublon(db_session):
    enregistrer_ou_mettre_a_jour(
        db_session,
        _champs(url_canonique="https://test-persistance-a.invalid/x", hash_contenu="hash-partage"),
    )
    resultat = enregistrer_ou_mettre_a_jour(
        db_session,
        _champs(url_canonique="https://test-persistance-a.invalid/y", hash_contenu="hash-partage"),
    )
    db_session.flush()

    assert resultat in ("mis_a_jour", "inchange")
    assert len(_articles_de_test(db_session)) == 1


def test_meme_hash_domaine_different_n_est_pas_un_doublon(db_session):
    # Reproduit et corrige le bug d'audit MET-1 (audit/audit-phase1-fin-phase2-debut.md) :
    # une dépêche republiée par un domaine différent est une corroboration à conserver,
    # pas un doublon à fusionner.
    enregistrer_ou_mettre_a_jour(
        db_session,
        _champs(
            domaine_source="test-persistance-a.invalid",
            url_canonique="https://test-persistance-a.invalid/story",
            hash_contenu="hash-partage",
        ),
    )
    resultat = enregistrer_ou_mettre_a_jour(
        db_session,
        _champs(
            domaine_source="test-persistance-b.invalid",
            url_canonique="https://test-persistance-b.invalid/story",
            hash_contenu="hash-partage",
        ),
    )
    db_session.flush()

    articles = _articles_de_test(db_session)
    assert resultat == "ajoute"
    assert len(articles) == 2
    assert {a.domaine_source for a in articles} == {"test-persistance-a.invalid", "test-persistance-b.invalid"}


def test_metadonnees_volatiles_mises_a_jour_si_differentes(db_session):
    enregistrer_ou_mettre_a_jour(db_session, _champs(metadonnees={"score": 1}))
    resultat = enregistrer_ou_mettre_a_jour(db_session, _champs(metadonnees={"score": 2}))
    db_session.flush()

    article = _articles_de_test(db_session)[0]
    assert resultat == "mis_a_jour"
    assert article.metadonnees == {"score": 2}
