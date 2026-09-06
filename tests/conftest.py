import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# `src` est sur le sys.path via [tool.pytest.ini_options] pythonpath dans
# pyproject.toml — plus de sys.path.insert ici (cf. audit, Layer Enforcer).


def _mode_heberge(monkeypatch, mot_de_passe: str = "secret") -> None:
    """Bascule en mode hébergé : mot de passe partagé défini ET mode local retiré.

    Depuis le correctif du finding H4, l'absence de FRONTEND_PASSWORD ne suffit
    plus à ouvrir le site : le mode local demande FAKENEWS_MODE=local explicite.
    Les deux modes doivent donc être posés explicitement, jamais déduits d'un
    manque — c'est tout l'objet du correctif."""
    monkeypatch.delenv("FAKENEWS_MODE", raising=False)
    monkeypatch.setenv("FRONTEND_PASSWORD", mot_de_passe)


@pytest.fixture(autouse=True)
def _environnement_neutre(monkeypatch):
    """Aucun test n'hérite du mode d'un autre, ni de l'environnement de la machine
    qui lance la suite."""
    monkeypatch.delenv("FRONTEND_PASSWORD", raising=False)
    monkeypatch.delenv("FAKENEWS_MODE", raising=False)


@pytest.fixture
def db_session():
    """Session contre une vraie base Postgres de test, dans une transaction annulée
    après chaque test (aucune pollution entre tests, aucune écriture durable). Exige
    TEST_DATABASE_URL ; les tests qui en dépendent sont ignorés (skip) si absente,
    plutôt que de deviner une configuration locale."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL non définie — tests contre une vraie base ignorés")

    engine = create_engine(url)
    try:
        connection = engine.connect()
    except Exception as exc:
        pytest.skip(f"base de test injoignable ({url}): {exc}")

    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
