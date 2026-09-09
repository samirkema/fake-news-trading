import os
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# `src` est sur le sys.path via [tool.pytest.ini_options] pythonpath dans
# pyproject.toml — plus de sys.path.insert ici (cf. audit, Layer Enforcer).


@pytest.fixture
def mode_heberge(monkeypatch):
    """Bascule en mode hébergé : mot de passe partagé défini ET mode local retiré.

    Depuis le correctif du finding H4, l'absence de FRONTEND_PASSWORD ne suffit
    plus à ouvrir le site : le mode local demande FAKENEWS_MODE=local explicite.
    Les deux modes doivent donc être posés explicitement, jamais déduits d'un
    manque — c'est tout l'objet du correctif.

    Exposé en FIXTURE et non en fonction importable : les modules de test
    faisaient `from conftest import _mode_heberge`, ce qui casse sous
    `--import-mode=importlib`, le mode recommandé par pytest et destiné à devenir
    le défaut (cf. audit phase 7, finding N6). Une fixture est résolue par pytest,
    donc indépendante du mode d'import."""

    def _basculer(mot_de_passe: str = "secret") -> None:
        monkeypatch.delenv("FAKENEWS_MODE", raising=False)
        monkeypatch.setenv("FRONTEND_PASSWORD", mot_de_passe)

    return _basculer


@pytest.fixture(autouse=True)
def _environnement_neutre(monkeypatch):
    """Aucun test n'hérite du mode d'un autre, ni de l'environnement de la machine
    qui lance la suite."""
    monkeypatch.delenv("FRONTEND_PASSWORD", raising=False)
    monkeypatch.delenv("FAKENEWS_MODE", raising=False)


@pytest.fixture(autouse=True)
def _pas_de_reseau(monkeypatch, request):
    """Interdit les connexions sortantes non locales ouvertes depuis Python.

    Rien ne l'empêchait : `test_le_detail_du_calcul_est_persiste` appelle le vrai
    `evaluer_articles_non_scores`, et il ne sortait sur le réseau que parce
    qu'aucun titre de test ne cite une entreprise de la table. Un titre malheureux
    suffisait à faire appeler la vraie API SEC depuis la CI (cf. audit phase 7,
    finding N9).

    Couverture vérifiée : `socket.create_connection`, `httpx` et `urllib` sont
    bien bloqués. NE COUVRE PAS psycopg2/libpq, qui ouvre sa socket en C, hors de
    portée d'un monkeypatch sur `socket.socket.connect` — un test pointant vers un
    Postgres distant passerait (audit phase 8). La docstring disait « toute
    connexion » : c'était une demi-vérité.

    Les doubles httpx (`MockTransport`) n'ouvrent pas de socket et ne sont donc pas
    concernés. Un test qui aurait légitimement besoin du réseau peut lever la garde
    avec `@pytest.mark.reseau`."""
    if request.node.get_closest_marker("reseau"):
        return

    vrai_connect = socket.socket.connect

    def _connect_garde(self, adresse, *args, **kwargs):
        hote = adresse[0] if isinstance(adresse, tuple) else adresse
        if isinstance(hote, str) and hote not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(
                f"Connexion réseau sortante interdite en test : {hote}. "
                "Utiliser un double (httpx.MockTransport, ClientFactice), ou marquer "
                "le test @pytest.mark.reseau si l'appel réel est vraiment voulu."
            )
        return vrai_connect(self, adresse, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", _connect_garde)


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
    # `join_transaction_mode="create_savepoint"` : le code applicatif commite et
    # annule pour de vrai (c'est son comportement en production qu'on teste), mais
    # sur un POINT DE SAUVEGARDE imbriqué — la transaction externe du test survit et
    # peut toujours tout annuler à la fin.
    #
    # Sans ce mode, un `session.rollback()` applicatif — celui de `_commiter_le_lot`
    # quand la base refuse un lot — annulait la transaction du test elle-même, que
    # la fixture tentait ensuite d'annuler à son tour (« transaction already
    # deassociated from connection »). Le test passait, mais son isolation ne tenait
    # plus qu'à la chance.
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
