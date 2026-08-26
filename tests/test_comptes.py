"""Fondation V1 de l'auth à 3 rôles (cf. doc/V1/comptes-3-roles.md).

Ces tests exercent `compte_courant` directement (le rôle résolu n'est encore
branché sur aucune capacité visible). Ils exigent que la migration
`0002_comptes.sql` soit appliquée à TEST_DATABASE_URL, comme `0001` l'est déjà.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text

from fakenews.frontend.app import (
    NOM_COOKIE,
    AccesRefuse,
    CompteCourant,
    _valeur_cookie,
    compte_courant,
)
from fakenews.models import Compte


def _requete(valeur_cookie=None):
    cookies = {} if valeur_cookie is None else {NOM_COOKIE: valeur_cookie}
    return SimpleNamespace(cookies=cookies)


def test_pseudo_inconnu_est_spectateur(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    compte = compte_courant(_requete(_valeur_cookie("inconnu", "secret")), db_session)
    assert compte == CompteCourant(pseudo="inconnu", role="spectateur")


def test_pseudo_dans_comptes_prend_son_role(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    db_session.add(Compte(pseudo="alice", role="contributeur"))
    db_session.flush()
    compte = compte_courant(_requete(_valeur_cookie("alice", "secret")), db_session)
    assert compte.role == "contributeur"


def test_lookup_insensible_a_la_casse(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    db_session.add(Compte(pseudo="Bob", role="contributeur"))
    db_session.flush()
    # le pseudo est normalisé en minuscules à la connexion -> "bob"
    compte = compte_courant(_requete(_valeur_cookie("bob", "secret")), db_session)
    assert compte.role == "contributeur"


def test_migration_seed_samirkema_est_superadmin(db_session):
    role = db_session.execute(
        select(Compte.role).where(func.lower(Compte.pseudo) == "samirkema")
    ).scalar_one_or_none()
    assert role == "superadmin", "migration 0002_comptes.sql non appliquée à TEST_DATABASE_URL ?"


def test_cookie_absent_refuse(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    with pytest.raises(AccesRefuse):
        compte_courant(_requete(), db_session)


def test_cookie_falsifie_refuse(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    # signature valide pour "bob", réutilisée en prétendant être "samirkema"
    signature = _valeur_cookie("bob", "secret").split(":", 1)[1]
    with pytest.raises(AccesRefuse):
        compte_courant(_requete(f"samirkema:{signature}"), db_session)


def test_mauvais_mot_de_passe_dans_la_signature_refuse(db_session, monkeypatch):
    monkeypatch.setenv("FRONTEND_PASSWORD", "secret")
    with pytest.raises(AccesRefuse):
        compte_courant(_requete(_valeur_cookie("alice", "autre-secret")), db_session)


def test_mode_local_est_superadmin(db_session, monkeypatch):
    monkeypatch.delenv("FRONTEND_PASSWORD", raising=False)
    compte = compte_courant(_requete(), db_session)
    assert compte == CompteCourant(pseudo="local", role="superadmin")


def test_cookie_superadmin_lie_au_secret_hash(db_session, monkeypatch):
    """Avec un code personnel (secret_hash), le cookie de samirkema ne peut PAS
    être forgé avec le seul mot de passe partagé."""
    monkeypatch.setenv("FRONTEND_PASSWORD", "partage")
    db_session.execute(
        text(
            "update comptes set secret_hash = crypt('code-perso', gen_salt('bf')) "
            "where lower(pseudo) = 'samirkema'"
        )
    )
    db_session.flush()
    hash_actuel = db_session.execute(
        select(Compte.secret_hash).where(func.lower(Compte.pseudo) == "samirkema")
    ).scalar_one()

    bon = _valeur_cookie("samirkema", "partage", hash_actuel)
    assert compte_courant(_requete(bon), db_session).role == "superadmin"

    with pytest.raises(AccesRefuse):
        compte_courant(_requete(_valeur_cookie("samirkema", "partage")), db_session)
