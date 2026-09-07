import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fakenews.schema import verifier_schema

load_dotenv()

_session_factory = None


def SessionLocal():
    """Connexion paresseuse : DATABASE_URL n'est lue qu'au premier appel réel, pas à
    l'import du module — sinon importer ce module (même transitivement, ex. pour des
    tests purs sans DB) exige DATABASE_URL sans raison (cf. audit de suivi, régression
    sur la collecte pytest).

    Le schéma est contrôlé UNE FOIS, à la création du moteur : un code déployé en
    avance sur ses migrations doit le dire tout de suite et clairement, pas se
    manifester par un `ProgrammingError` opaque sur chaque page (cf. audit phase 9
    et fakenews.schema)."""
    global _session_factory
    if _session_factory is None:
        engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
        verifier_schema(engine)
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory()
