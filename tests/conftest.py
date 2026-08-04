import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


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
