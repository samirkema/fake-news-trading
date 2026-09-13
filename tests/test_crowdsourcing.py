"""V3 — propositions, file d'attente, rôles opposables et espace compte
(cf. doc/V3/userstories_crowdsourcing.md).

Ces tests portent sur les premières routes d'ÉCRITURE du frontend. Ils vérifient
donc autant ce qui est permis que ce qui doit être refusé — un contrôle d'accès
qui n'est testé que par le chemin autorisé ne prouve rien.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import fakenews.frontend.app as app_frontend
from fakenews.frontend.app import app, get_session
from fakenews.models import Article, Compte, Proposition


@pytest.fixture
def client(db_session):
    """`https` : le cookie de session porte l'attribut `Secure`, qu'un client HTTP
    correct refuse d'envoyer en clair. Constaté en écrivant ces tests — sur
    `http://` le jar garde le cookie et ne le renvoie jamais, ce qui donne des
    303 vers /login parfaitement trompeurs."""
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def _connecter(client, db_session, pseudo, mot_de_passe="secret"):
    reponse = client.post(
        "/login", data={"pseudo": pseudo, "mot_de_passe": mot_de_passe}, follow_redirects=False
    )
    assert reponse.status_code == 303, f"connexion refusée pour {pseudo}"
    db_session.flush()
    return reponse


def _csrf(client, chemin="/proposer"):
    page = client.get(chemin)
    assert page.status_code == 200, f"{chemin} inaccessible ({page.status_code})"
    return page.text.split('name="csrf" value="')[1].split('"')[0]


def _creer_compte(db_session, pseudo, role, code=None):
    secret = (
        db_session.execute(select(func.crypt(code, func.gen_salt("bf")))).scalar_one()
        if code
        else None
    )
    compte = Compte(pseudo=pseudo, role=role, secret_hash=secret)
    db_session.add(compte)
    db_session.flush()
    return compte


# --- US-07 — existence des comptes ---------------------------------------------


def test_us07_une_premiere_connexion_materialise_le_compte(client, db_session, mode_heberge):
    """Sans cette ligne, le superadmin ne pourrait pas « choisir un contributeur
    parmi les comptes » : la table ne contiendrait que ceux créés à la main."""
    mode_heberge("secret")
    _connecter(client, db_session, "nouvelle")

    role = db_session.execute(
        select(Compte.role).where(func.lower(Compte.pseudo) == "nouvelle")
    ).scalar_one()
    assert role == "spectateur"


def test_us07_une_seconde_connexion_ne_duplique_pas_le_compte(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "revenante")
    _connecter(client, db_session, "revenante")

    nombre = db_session.execute(
        select(func.count()).select_from(Compte).where(func.lower(Compte.pseudo) == "revenante")
    ).scalar_one()
    assert nombre == 1


# --- US-01 — proposer un article ------------------------------------------------


def test_us01_un_spectateur_peut_proposer_un_article(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    client.post(
        "/proposer",
        data={"url": "https://exemple.test/a", "note": "titre douteux", "csrf": _csrf(client)},
    )
    db_session.flush()

    proposition = db_session.execute(
        select(Proposition).where(Proposition.propose_par == "alice")
    ).scalar_one()
    assert proposition.statut == "en_attente"
    assert proposition.url_canonique == "https://exemple.test/a"
    assert proposition.note == "titre douteux"


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "javascript:alert(1)", "data:text/html,<b>x", "pas-une-url", ""]
)
def test_us01_seules_les_adresses_http_sont_acceptees(client, db_session, mode_heberge, url):
    """Le collecteur ira chercher cette adresse depuis le pipeline : `file://` et
    `data:` n'ont rien à y faire. Validé ici ET côté collecteur — une validation
    d'entrée ne se délègue pas au maillon précédent."""
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    client.post("/proposer", data={"url": url, "csrf": _csrf(client)})
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Proposition)).scalar_one() == 0


def test_us01_un_article_deja_analyse_renvoie_vers_sa_fiche(client, db_session, mode_heberge):
    """Proposer un article déjà en base ne doit pas créer un doublon muet."""
    mode_heberge("secret")
    article = Article(
        titre="Déjà là", contenu="corps", domaine_source="exemple.test",
        date_publication=datetime.now(timezone.utc), url="https://exemple.test/connu",
        url_canonique="https://exemple.test/connu", hash_contenu="h-connu",
        plateforme="rss", metadonnees={},
    )
    db_session.add(article)
    db_session.flush()
    _connecter(client, db_session, "alice")

    reponse = client.post(
        "/proposer",
        data={"url": "https://exemple.test/connu", "csrf": _csrf(client)},
        follow_redirects=False,
    )
    db_session.flush()

    assert str(article.id) in reponse.headers["location"]
    assert db_session.execute(select(func.count()).select_from(Proposition)).scalar_one() == 0


def test_us01_une_url_deja_dans_la_file_n_est_pas_empilee(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "alice")
    jeton = _csrf(client)

    for _ in range(2):
        client.post("/proposer", data={"url": "https://exemple.test/b", "csrf": jeton})
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Proposition)).scalar_one() == 1


def test_us01_le_plafond_par_compte_est_opposable(client, db_session, mode_heberge, monkeypatch):
    """Sans plafond, un seul compte remplit la file et rend le travail des
    contributeurs impraticable."""
    mode_heberge("secret")
    monkeypatch.setenv("PROPOSITIONS_MAX_PAR_JOUR", "2")
    _connecter(client, db_session, "alice")
    jeton = _csrf(client)

    for i in range(4):
        client.post("/proposer", data={"url": f"https://exemple.test/p{i}", "csrf": jeton})
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Proposition)).scalar_one() == 2


# --- US-02, US-03 — file d'attente et décision ----------------------------------


def _proposer(db_session, url="https://exemple.test/c", par="alice"):
    proposition = Proposition(url=url, url_canonique=url, propose_par=par)
    db_session.add(proposition)
    db_session.flush()
    return proposition


def test_us02_un_spectateur_n_accede_pas_a_la_file(client, db_session, mode_heberge):
    """La garde est côté serveur : masquer le lien dans le gabarit n'est pas un
    contrôle d'accès. Accès direct à l'URL, donc."""
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    assert client.get("/file").status_code == 404
    assert client.get("/admin/comptes").status_code == 404


def test_us02_un_contributeur_accede_a_la_file(client, db_session, mode_heberge):
    mode_heberge("secret")
    _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "bob", "code-de-bob-long")

    assert client.get("/file").status_code == 200


def test_us02_le_superadmin_est_aussi_contributeur(client, db_session, mode_heberge):
    """La garde compare un ORDRE de rôles, pas une égalité : le superadmin
    propose et décide comme les autres."""
    mode_heberge("secret")
    _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    _connecter(client, db_session, "chef", "code-du-chef-long")

    assert client.get("/file").status_code == 200
    assert client.get("/admin/comptes").status_code == 200


def test_us03_un_contributeur_accepte_une_proposition(client, db_session, mode_heberge):
    mode_heberge("secret")
    proposition = _proposer(db_session)
    _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "bob", "code-de-bob-long")

    client.post(f"/file/{proposition.id}/accepter", data={"csrf": _csrf(client, "/file")})
    db_session.flush()
    db_session.refresh(proposition)

    assert proposition.statut == "acceptee"
    assert proposition.decide_par == "bob"
    assert proposition.date_decision is not None
    # L'acceptation autorise l'entrée, elle ne collecte pas : l'article n'existe
    # pas encore (US-04, c'est le pipeline qui le crée).
    assert proposition.article_id is None
    assert db_session.execute(select(func.count()).select_from(Article)).scalar_one() == 0


def test_us03_un_refus_sans_motif_est_rejete(client, db_session, mode_heberge):
    """Un refus sans raison est un mur, pas une décision."""
    mode_heberge("secret")
    proposition = _proposer(db_session)
    _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "bob", "code-de-bob-long")

    client.post(f"/file/{proposition.id}/refuser", data={"motif": "   ", "csrf": _csrf(client, "/file")})
    db_session.flush()
    db_session.refresh(proposition)

    assert proposition.statut == "en_attente"


def test_us03_un_refus_motive_est_visible_par_le_proposant(client, db_session, mode_heberge):
    mode_heberge("secret")
    proposition = _proposer(db_session, par="alice")
    _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "bob", "code-de-bob-long")
    client.post(
        f"/file/{proposition.id}/refuser",
        data={"motif": "Satire assumée", "csrf": _csrf(client, "/file")},
    )
    db_session.flush()

    autre = TestClient(app, base_url="https://testserver")
    _connecter(autre, db_session, "alice")
    assert "Satire assumée" in autre.get("/compte").text


def test_us03_une_proposition_deja_decidee_n_est_pas_redecidee(client, db_session, mode_heberge):
    """Deux contributeurs qui cliquent en même temps ne doivent pas produire deux
    décisions dont la seconde écrase la première."""
    mode_heberge("secret")
    proposition = _proposer(db_session)
    _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "bob", "code-de-bob-long")
    jeton = _csrf(client, "/file")

    client.post(f"/file/{proposition.id}/accepter", data={"csrf": jeton})
    client.post(f"/file/{proposition.id}/refuser", data={"motif": "trop tard", "csrf": jeton})
    db_session.flush()
    db_session.refresh(proposition)

    assert proposition.statut == "acceptee"
    assert proposition.motif is None


def test_us03_un_spectateur_ne_peut_pas_decider(client, db_session, mode_heberge):
    mode_heberge("secret")
    proposition = _proposer(db_session)
    _connecter(client, db_session, "alice")

    reponse = client.post(f"/file/{proposition.id}/accepter", data={"csrf": _csrf(client)})
    db_session.flush()
    db_session.refresh(proposition)

    assert reponse.status_code == 404
    assert proposition.statut == "en_attente"


# --- US-06 — nommer un contributeur ---------------------------------------------


def test_us06_le_superadmin_promeut_avec_un_code_provisoire(client, db_session, mode_heberge):
    """La promotion pose un code personnel : sans lui, le mot de passe partagé
    ouvrirait ce compte privilégié (migration 0004)."""
    mode_heberge("secret")
    _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    cible = _creer_compte(db_session, "alice", "spectateur")
    _connecter(client, db_session, "chef", "code-du-chef-long")

    reponse = client.post(
        f"/admin/comptes/{cible.id}/promouvoir",
        data={"csrf": _csrf(client, "/admin/comptes")},
        follow_redirects=True,
    )
    db_session.flush()
    db_session.refresh(cible)

    assert cible.role == "contributeur"
    assert cible.secret_hash is not None
    code_provisoire = reponse.text.split("<code>")[1].split("</code>")[0]
    assert len(code_provisoire) >= 12


def test_us06_un_spectateur_ne_peut_promouvoir_personne(client, db_session, mode_heberge):
    mode_heberge("secret")
    cible = _creer_compte(db_session, "bob", "spectateur")
    _connecter(client, db_session, "alice")

    reponse = client.post(f"/admin/comptes/{cible.id}/promouvoir", data={"csrf": _csrf(client)})
    db_session.flush()
    db_session.refresh(cible)

    assert reponse.status_code == 404
    assert cible.role == "spectateur"


def test_us06_la_retrogradation_efface_le_code_personnel(client, db_session, mode_heberge):
    mode_heberge("secret")
    _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    cible = _creer_compte(db_session, "bob", "contributeur", code="code-de-bob-long")
    _connecter(client, db_session, "chef", "code-du-chef-long")

    client.post(
        f"/admin/comptes/{cible.id}/retrograder", data={"csrf": _csrf(client, "/admin/comptes")}
    )
    db_session.flush()
    db_session.refresh(cible)

    assert cible.role == "spectateur"
    assert cible.secret_hash is None


def test_us06_un_superadmin_ne_se_retrograde_pas(client, db_session, mode_heberge):
    """Se rétrograder fermerait la seule porte d'administration du site — et le
    schéma refuse de toute façon un superadmin sans code."""
    mode_heberge("secret")
    chef = _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    _connecter(client, db_session, "chef", "code-du-chef-long")

    # Jeton pris sur une autre page : il est lié au COMPTE, pas au formulaire —
    # et la ligne d'un superadmin n'offre justement aucun bouton à actionner.
    client.post(f"/admin/comptes/{chef.id}/retrograder", data={"csrf": _csrf(client)})
    db_session.flush()
    db_session.refresh(chef)

    assert chef.role == "superadmin"


# --- US-05 — espace compte ------------------------------------------------------


def test_us05_changer_son_code_invalide_les_sessions(client, db_session, mode_heberge):
    """La clé de signature du cookie dérive de `secret_hash` : changer le code
    invalide les sessions ouvertes. Propriété voulue, pas effet de bord."""
    mode_heberge("secret")
    _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    _connecter(client, db_session, "bob", "ancien-code-long")

    client.post(
        "/compte/code",
        data={
            "code_actuel": "ancien-code-long",
            "nouveau_code": "nouveau-code-assez-long",
            "confirmation": "nouveau-code-assez-long",
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()

    assert client.get("/", follow_redirects=False).status_code == 303
    neuf = TestClient(app, base_url="https://testserver")
    _connecter(neuf, db_session, "bob", "nouveau-code-assez-long")


def test_us05_un_code_accentue_fonctionne(client, db_session, mode_heberge):
    """F15-02 était le préalable annoncé à cet écran : sans normalisation NFC, un
    utilisateur choisissant un code accentué pouvait se verrouiller dehors selon
    le clavier utilisé à la reconnexion."""
    import unicodedata

    mode_heberge("secret")
    _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    _connecter(client, db_session, "bob", "ancien-code-long")

    accentue = "mon-cödé-très-long"
    client.post(
        "/compte/code",
        data={
            "code_actuel": "ancien-code-long",
            "nouveau_code": accentue,
            "confirmation": accentue,
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()

    # Les deux formes Unicode du MÊME code doivent ouvrir la session.
    for forme in ("NFC", "NFD"):
        neuf = TestClient(app, base_url="https://testserver")
        _connecter(neuf, db_session, "bob", unicodedata.normalize(forme, accentue))


def test_us05_un_code_actuel_faux_ne_change_rien(client, db_session, mode_heberge):
    """Un cookie volé ne doit pas suffire à s'approprier le compte."""
    mode_heberge("secret")
    compte = _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    ancien_hash = compte.secret_hash
    _connecter(client, db_session, "bob", "ancien-code-long")

    client.post(
        "/compte/code",
        data={
            "code_actuel": "pas-le-bon-code",
            "nouveau_code": "nouveau-code-assez-long",
            "confirmation": "nouveau-code-assez-long",
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()
    db_session.refresh(compte)

    assert compte.secret_hash == ancien_hash


@pytest.mark.parametrize(
    "nouveau,confirmation",
    [("court", "court"), ("assez-long-mais-pas-pareil", "autre-chose-assez-longue")],
)
def test_us05_un_code_invalide_est_refuse(client, db_session, mode_heberge, nouveau, confirmation):
    mode_heberge("secret")
    compte = _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    ancien_hash = compte.secret_hash
    _connecter(client, db_session, "bob", "ancien-code-long")

    client.post(
        "/compte/code",
        data={
            "code_actuel": "ancien-code-long",
            "nouveau_code": nouveau,
            "confirmation": confirmation,
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()
    db_session.refresh(compte)

    assert compte.secret_hash == ancien_hash


def test_us05_un_spectateur_n_a_pas_de_code_a_changer(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    page = client.get("/compte")
    assert page.status_code == 200
    assert "mot de passe partagé" in page.text
    assert 'name="code_actuel"' not in page.text


# --- Exigence transverse — CSRF -------------------------------------------------


@pytest.mark.parametrize(
    "chemin,donnees",
    [
        ("/proposer", {"url": "https://exemple.test/csrf"}),
        ("/compte/code", {"code_actuel": "x", "nouveau_code": "y" * 12, "confirmation": "y" * 12}),
    ],
)
def test_csrf_une_ecriture_sans_jeton_est_refusee(client, db_session, mode_heberge, chemin, donnees):
    """`samesite=lax` réduit la surface, il ne la ferme pas. Chaque route
    d'écriture doit refuser avant tout effet de bord."""
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    assert client.post(chemin, data=donnees).status_code == 403
    db_session.flush()
    assert db_session.execute(select(func.count()).select_from(Proposition)).scalar_one() == 0


def test_csrf_le_jeton_d_un_autre_compte_ne_vaut_rien(client, db_session, mode_heberge):
    mode_heberge("secret")
    _connecter(client, db_session, "alice")
    jeton_alice = _csrf(client)

    autre = TestClient(app, base_url="https://testserver")
    _connecter(autre, db_session, "mallory")
    reponse = autre.post("/proposer", data={"url": "https://exemple.test/vol", "csrf": jeton_alice})

    assert reponse.status_code == 403


# --- Le frontend n'écrit toujours pas le verdict --------------------------------


def test_le_frontend_n_ecrit_jamais_articles_scores_ni_mise_en_contexte():
    """La frontière qui remplace « lecture seule stricte » (doc/V0/architecture.md,
    décision V3) : le frontend enregistre des intentions humaines, jamais un
    verdict. Vérifié sur le source — aucune route ne doit instancier ces modèles.

    Ce contrat n'était couvert par aucun test jusqu'ici (audit phase 14, F12),
    alors que c'est le 1er critère d'acceptation d'US-04 frontend."""
    import pathlib

    source = pathlib.Path(app_frontend.__file__).read_text(encoding="utf-8")
    for interdit in ("Article(", "Score(", "MiseEnContexte("):
        assert interdit not in source, f"le frontend instancie {interdit} — il écrirait un verdict"
    # Le test précédent gardait une ORTHOGRAPHE : il serait passé si le frontend
    # écrivait via `session.execute(insert(Article))` ou `update(Score)`
    # (audit phase 17, F17-06). Ces deux verbes n'ont rien à faire ici sur les
    # tables du verdict.
    for verbe in ("insert(", "delete("):
        assert verbe not in source, f"le frontend utilise {verbe} — vérifier la table visée"
    for ecriture in ("update(Article", "update(Score", "update(MiseEnContexte"):
        assert ecriture not in source, f"le frontend fait {ecriture} — il écrirait un verdict"


# ==============================================================================
# Correctifs de l'audit phase 17
# ==============================================================================


@pytest.mark.parametrize("jeton", ["café", "jetön", "√©chec", "ジェトン"])
def test_audit_phase17_un_jeton_csrf_non_ascii_est_refuse_pas_plante(
    client, db_session, mode_heberge, jeton
):
    """F17-01 — `compare_digest` refuse deux `str` non-ASCII et lève `TypeError`.
    Mesuré : `csrf='café'` renvoyait **500** au lieu de 403.

    Troisième occurrence de la même classe de bug (après `/login` en phase 14 et
    la signature du cookie en phase 0). Le correctif n'est plus un patch de
    site : toute comparaison de secret passe par `_secrets_egaux`."""
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    reponse = client.post("/proposer", data={"url": "https://exemple.test/z", "csrf": jeton})

    assert reponse.status_code == 403, "un jeton hostile doit être refusé, pas planter"


def test_audit_phase17_la_comparaison_de_secrets_passe_par_un_point_unique():
    """La règle, pas la ligne : c'est l'absence de ce point de passage qui a
    permis d'écrire trois fois le même défaut."""
    import pathlib

    source = pathlib.Path(app_frontend.__file__).read_text(encoding="utf-8")
    appels = source.count("hmac.compare_digest(")
    assert appels == 1, (
        f"{appels} appels directs à compare_digest : tout site qui compare un "
        "secret doit passer par _secrets_egaux, sinon le prochain oubliera l'encodage"
    )


def test_audit_phase17_un_code_au_dela_de_72_octets_est_refuse(client, db_session, mode_heberge):
    """F17-02 — bcrypt ne lit que les 72 premiers octets. Mesuré : deux codes
    identiques sur 72 octets et différents ensuite ouvrent le MÊME hash. Accepter
    200 caractères promettait un secret que l'algorithme ne vérifie pas."""
    mode_heberge("secret")
    compte = _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    ancien_hash = compte.secret_hash
    _connecter(client, db_session, "bob", "ancien-code-long")

    trop_long = "A" * 73
    client.post(
        "/compte/code",
        data={
            "code_actuel": "ancien-code-long",
            "nouveau_code": trop_long,
            "confirmation": trop_long,
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()
    db_session.refresh(compte)

    assert compte.secret_hash == ancien_hash, "un code que bcrypt tronquerait doit être refusé"


def test_audit_phase17_la_borne_est_en_octets_pas_en_caracteres(client, db_session, mode_heberge):
    """Un « é » compte pour deux octets : borner en caractères laisserait passer
    des codes que bcrypt tronque quand même."""
    mode_heberge("secret")
    compte = _creer_compte(db_session, "bob", "contributeur", code="ancien-code-long")
    ancien_hash = compte.secret_hash
    _connecter(client, db_session, "bob", "ancien-code-long")

    # 40 caractères, 80 octets en UTF-8.
    accentue = "é" * 40
    client.post(
        "/compte/code",
        data={
            "code_actuel": "ancien-code-long",
            "nouveau_code": accentue,
            "confirmation": accentue,
            "csrf": _csrf(client, "/compte"),
        },
    )
    db_session.flush()
    db_session.refresh(compte)

    assert compte.secret_hash == ancien_hash


def test_audit_phase17_le_code_provisoire_ne_passe_pas_par_l_url(client, db_session, mode_heberge):
    """F17-03 — il voyageait en query string : journaux d'accès, historique du
    navigateur, cache de la barre d'adresse. Un secret à usage unique ne laisse
    pas trois traces durables."""
    mode_heberge("secret")
    _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    cible = _creer_compte(db_session, "alice", "spectateur")
    _connecter(client, db_session, "chef", "code-du-chef-long")

    redirection = client.post(
        f"/admin/comptes/{cible.id}/promouvoir",
        data={"csrf": _csrf(client, "/admin/comptes")},
        follow_redirects=False,
    )
    db_session.flush()

    assert redirection.headers["location"] == "/admin/comptes"
    assert "code_provisoire=" not in redirection.headers["location"]
    # Mais il reste affiché une fois, sur la page qui suit.
    page = client.get("/admin/comptes")
    assert "<code>" in page.text
    # ...et une seule : le cookie porteur est consommé.
    assert "<code>" not in client.get("/admin/comptes").text


def test_audit_phase17_une_repromotion_n_efface_pas_le_code_choisi(client, db_session, mode_heberge):
    """F17-07 — re-promouvoir régénérait un code provisoire et écrasait en
    silence celui que le contributeur avait choisi, en le déconnectant."""
    mode_heberge("secret")
    _creer_compte(db_session, "chef", "superadmin", code="code-du-chef-long")
    cible = _creer_compte(db_session, "bob", "contributeur", code="code-choisi-par-bob")
    ancien_hash = cible.secret_hash
    _connecter(client, db_session, "chef", "code-du-chef-long")

    client.post(
        f"/admin/comptes/{cible.id}/promouvoir", data={"csrf": _csrf(client, "/admin/comptes")}
    )
    db_session.flush()
    db_session.refresh(cible)

    assert cible.secret_hash == ancien_hash


def test_audit_phase17_un_message_arbitraire_n_est_plus_affiche(client, db_session, mode_heberge):
    """F17-05 — le texte d'erreur était repris de la query string et rendu tel
    quel : un lien forgé affichait « votre compte est suspendu, appelez le… »
    dans une page authentique du site. Seuls des CODES connus voyagent."""
    mode_heberge("secret")
    _connecter(client, db_session, "alice")

    piege = "Votre compte est suspendu, appelez le 0800123456"
    page = client.get(f"/compte?erreur={piege}")

    assert page.status_code == 200
    assert "0800123456" not in page.text
    # Contre-épreuve : un code connu, lui, est bien traduit.
    assert "Code actuel incorrect." in client.get("/compte?erreur=code_actuel_faux").text


def test_audit_phase17_le_jeton_csrf_depend_de_la_session(db_session, mode_heberge):
    """F17-04 — le jeton dérivait du seul couple (mot de passe partagé, pseudo).
    Ce mot de passe étant PARTAGÉ, tout utilisateur pouvait calculer le jeton
    d'un autre et monter une CSRF contre un contributeur.

    Il dérive désormais de la clé qui signe le cookie : il change avec le code
    personnel, et deux sessions du même pseudo n'ont pas le même jeton."""
    from fakenews.frontend.app import _calculer_csrf

    mode_heberge("secret")
    hash_a = db_session.execute(select(func.crypt("code-a", func.gen_salt("bf")))).scalar_one()
    hash_b = db_session.execute(select(func.crypt("code-b", func.gen_salt("bf")))).scalar_one()

    reference = _calculer_csrf("bob", 1000, "secret", hash_a)
    assert reference != _calculer_csrf("bob", 1000, "secret", hash_b), "doit dépendre du code personnel"
    assert reference != _calculer_csrf("bob", 2000, "secret", hash_a), "doit dépendre de la session"
    assert reference != _calculer_csrf("alice", 1000, "secret", hash_a), "doit dépendre du pseudo"
