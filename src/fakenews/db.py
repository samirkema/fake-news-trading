import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

_session_factory = None


def SessionLocal():
    """Connexion paresseuse : DATABASE_URL n'est lue qu'au premier appel réel, pas à
    l'import du module — sinon importer ce module (même transitivement, ex. pour des
    tests purs sans DB) exige DATABASE_URL sans raison (cf. audit de suivi, régression
    sur la collecte pytest)."""
    global _session_factory
    if _session_factory is None:
        engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory()
