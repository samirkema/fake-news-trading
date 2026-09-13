"""V3, US-08 — commentaires sur l'analyse d'un article
(cf. doc/V3/userstories_crowdsourcing.md).

Le point le plus délicat n'est pas la publication : c'est le RETRAIT, qui doit
masquer sans effacer. Un contenu retiré pour raison juridique doit rester
consultable par le porteur du projet.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from fakenews.frontend.app import app, get_session
from fakenews.models import Article, Commentaire, Compte, Score


@pytest.fixture
def client(db_session):
    """`https` : le cookie de session porte `Secure` (cf. test_crowdsourcing)."""
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app, base_url="https://testserver")
    app.dependency_overrides.clear()


def _connecter(client, db_session, pseudo, mot_de_passe="secret"):
    reponse = client.post(
        "/login", data={"pseudo": pseudo, "mot_de_passe": mot_de_passe}, follow_redirects=False
    )
    assert reponse.status_code == 303, f"connexion refusée pour {pseudo}"
    db_session.flush()


def _csrf(client, chemin):
    page = client.get(chemin)
    assert page.status_code == 200, f"{chemin} inaccessible ({page.status_code})"
    return page.text.split('name="csrf" value="')[1].split('"')[0]


def _creer_compte(db_session, pseudo, role, code):
    secret = db_session.execute(select(func.crypt(code, func.gen_salt("bf")))).scalar_one()
    db_session.add(Compte(pseudo=pseudo, role=role, secret_hash=secret))
    db_session.flush()


def _article(db_session, suffixe="a"):
    article = Article(
        titre=f"Titre {suffixe}", contenu="corps de l'article", domaine_source="exemple.test",
        date_publication=datetime.now(timezone.utc), url=f"https://exemple.test/{suffixe}",
        url_canonique=f"https://exemple.test/{suffixe}", hash_contenu=f"h-{suffixe}",
        plateforme="rss", metadonnees={},
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(
        Score(
            article_id=article.id,
            sous_scores={"style": {"valeur": 80.0, "raison": "test", "preuve_id": "style"}},
            poids={"style": 0.5}, score_final=80.0, non_evaluable=False,
        )
    )
    db_session.flush()
    return article


def _commenter(client, db_session, article, texte):
    return client.post(
        f"/articles/{article.id}/commentaires",
        data={"texte": texte, "csrf": _csrf(client, f"/articles/{article.id}")},
        follow_redirects=False,
    )


# --- Publication ----------------------------------------------------------------


def test_un_spectateur_peut_commenter(client, db_session, mode_heberge):
    """US-08 : tout compte connecté, spectateurs compris — c'est l'esprit du
    crowdsourcing, et la décision prise le 2026-09-10."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    _commenter(client, db_session, article, "Cet article cite une source primaire.")
    db_session.flush()

    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    assert commentaire.pseudo == "alice"
    assert commentaire.texte == "Cet article cite une source primaire."
    assert commentaire.retire_le is None


def test_le_commentaire_apparait_sur_la_page(client, db_session, mode_heberge):
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")
    _commenter(client, db_session, article, "Un apport de contexte utile.")
    db_session.flush()

    page = client.get(f"/articles/{article.id}").text
    assert "Un apport de contexte utile." in page
    assert "alice" in page


@pytest.mark.parametrize("texte", ["", "   ", "\n\t "])
def test_un_commentaire_vide_est_refuse(client, db_session, mode_heberge, texte):
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    _commenter(client, db_session, article, texte)
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 0


def test_un_commentaire_trop_long_est_refuse(client, db_session, mode_heberge):
    from fakenews.frontend.app import COMMENTAIRE_LONGUEUR_MAX

    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    _commenter(client, db_session, article, "x" * (COMMENTAIRE_LONGUEUR_MAX + 1))
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 0


def test_le_plafond_par_compte_est_opposable(client, db_session, mode_heberge, monkeypatch):
    mode_heberge("secret")
    monkeypatch.setenv("COMMENTAIRES_MAX_PAR_JOUR", "2")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    for i in range(4):
        _commenter(client, db_session, article, f"Commentaire {i}")
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 2


def test_le_texte_est_echappe_a_l_affichage(client, db_session, mode_heberge):
    """Le contenu vient d'un visiteur : il est rendu comme du TEXTE, jamais
    interprété. Jinja échappe par défaut — ce test verrouille ce défaut."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    _commenter(client, db_session, article, "<script>alert('xss')</script>")
    db_session.flush()

    page = client.get(f"/articles/{article.id}").text
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_commenter_exige_un_jeton_csrf(client, db_session, mode_heberge):
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    reponse = client.post(f"/articles/{article.id}/commentaires", data={"texte": "sans jeton"})
    db_session.flush()

    assert reponse.status_code == 403
    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 0


def test_commenter_un_article_inexistant_renvoie_404(client, db_session, mode_heberge):
    import uuid

    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")
    jeton = _csrf(client, f"/articles/{article.id}")

    reponse = client.post(
        f"/articles/{uuid.uuid4()}/commentaires", data={"texte": "orphelin", "csrf": jeton}
    )
    assert reponse.status_code == 404


# --- Retrait ---------------------------------------------------------------------


def _retirer(client, db_session, commentaire, article):
    return client.post(
        f"/commentaires/{commentaire.id}/retirer",
        data={"csrf": _csrf(client, f"/articles/{article.id}")},
        follow_redirects=False,
    )


def test_le_retrait_masque_sans_effacer(client, db_session, mode_heberge):
    """LE point d'US-08 : sur un site qui publie des verdicts nommant des médias,
    un contenu retiré pour raison juridique doit rester consultable par le porteur
    du projet, pas s'évaporer."""
    mode_heberge("secret")
    article = _article(db_session)
    _creer_compte(db_session, "chef", "superadmin", "code-du-chef-long")
    db_session.add(Commentaire(article_id=article.id, pseudo="alice", texte="Propos litigieux."))
    db_session.flush()
    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    _connecter(client, db_session, "chef", "code-du-chef-long")

    _retirer(client, db_session, commentaire, article)
    db_session.flush()
    db_session.refresh(commentaire)

    assert commentaire.retire_le is not None
    assert commentaire.retire_par == "chef"
    assert commentaire.texte == "Propos litigieux.", "le contenu doit être conservé"


def test_un_commentaire_retire_disparait_pour_le_public(client, db_session, mode_heberge):
    mode_heberge("secret")
    article = _article(db_session)
    db_session.add(
        Commentaire(
            article_id=article.id, pseudo="alice", texte="Propos litigieux.",
            retire_le=datetime.now(timezone.utc), retire_par="chef",
        )
    )
    db_session.flush()
    _connecter(client, db_session, "bob")

    page = client.get(f"/articles/{article.id}").text
    assert "Propos litigieux." not in page


def test_le_superadmin_voit_encore_le_commentaire_retire(client, db_session, mode_heberge):
    mode_heberge("secret")
    article = _article(db_session)
    _creer_compte(db_session, "chef", "superadmin", "code-du-chef-long")
    db_session.add(
        Commentaire(
            article_id=article.id, pseudo="alice", texte="Propos litigieux.",
            retire_le=datetime.now(timezone.utc), retire_par="chef",
        )
    )
    db_session.flush()
    _connecter(client, db_session, "chef", "code-du-chef-long")

    page = client.get(f"/articles/{article.id}").text
    assert "Propos litigieux." in page
    assert "retiré par chef" in page


def test_un_spectateur_ne_peut_pas_retirer(client, db_session, mode_heberge):
    """Garde côté serveur : l'absence de bouton n'est pas un contrôle d'accès."""
    mode_heberge("secret")
    article = _article(db_session)
    db_session.add(Commentaire(article_id=article.id, pseudo="bob", texte="Un avis."))
    db_session.flush()
    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    _connecter(client, db_session, "alice")

    reponse = _retirer(client, db_session, commentaire, article)
    db_session.flush()
    db_session.refresh(commentaire)

    assert reponse.status_code == 404
    assert commentaire.retire_le is None


def test_un_contributeur_non_plus(client, db_session, mode_heberge):
    """Le retrait est une décision éditoriale, pas une capacité de contributeur."""
    mode_heberge("secret")
    article = _article(db_session)
    _creer_compte(db_session, "bob", "contributeur", "code-de-bob-long")
    db_session.add(Commentaire(article_id=article.id, pseudo="alice", texte="Un avis."))
    db_session.flush()
    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    _connecter(client, db_session, "bob", "code-de-bob-long")

    reponse = _retirer(client, db_session, commentaire, article)
    db_session.flush()
    db_session.refresh(commentaire)

    assert reponse.status_code == 404
    assert commentaire.retire_le is None


def test_retirer_exige_un_jeton_csrf(client, db_session, mode_heberge):
    mode_heberge("secret")
    article = _article(db_session)
    _creer_compte(db_session, "chef", "superadmin", "code-du-chef-long")
    db_session.add(Commentaire(article_id=article.id, pseudo="alice", texte="Un avis."))
    db_session.flush()
    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    _connecter(client, db_session, "chef", "code-du-chef-long")

    reponse = client.post(f"/commentaires/{commentaire.id}/retirer", data={})
    db_session.flush()
    db_session.refresh(commentaire)

    assert reponse.status_code == 403
    assert commentaire.retire_le is None


def test_un_retrait_ne_reecrit_pas_le_precedent(client, db_session, mode_heberge):
    """La condition « pas déjà retiré » est dans l'`update` : deux retraits
    simultanés ne doivent pas écraser l'horodatage du premier."""
    mode_heberge("secret")
    article = _article(db_session)
    _creer_compte(db_session, "chef", "superadmin", "code-du-chef-long")
    db_session.add(Commentaire(article_id=article.id, pseudo="alice", texte="Un avis."))
    db_session.flush()
    commentaire = db_session.execute(select(Commentaire)).scalars().one()
    _connecter(client, db_session, "chef", "code-du-chef-long")

    _retirer(client, db_session, commentaire, article)
    db_session.flush()
    db_session.refresh(commentaire)
    premier_retrait = commentaire.retire_le

    _retirer(client, db_session, commentaire, article)
    db_session.flush()
    db_session.refresh(commentaire)

    assert commentaire.retire_le == premier_retrait


# --- Non-objectif explicite : aucun effet sur le score ----------------------------


def test_les_commentaires_n_influencent_pas_le_score(client, db_session, mode_heberge):
    """Non-objectif d'US-08, écrit noir sur blanc : un vote humain non authentifié
    rendrait le score manipulable par quiconque connaît le mot de passe partagé, et
    retirerait au `detail_calcul` sa propriété d'être reconstituable."""
    mode_heberge("secret")
    article = _article(db_session)
    score = db_session.execute(select(Score).where(Score.article_id == article.id)).scalar_one()
    avant = (score.score_final, dict(score.sous_scores))
    _connecter(client, db_session, "alice")

    for i in range(3):
        _commenter(client, db_session, article, f"Je conteste ce score ({i}).")
    db_session.flush()
    db_session.refresh(score)

    assert (score.score_final, dict(score.sous_scores)) == avant


def test_l_avertissement_automatise_reste_affiche(client, db_session, mode_heberge):
    """US-04 frontend : chaque page affichant un score reprend l'avertissement.
    Les commentaires ne doivent pas le repousser hors de la page."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")
    _commenter(client, db_session, article, "Un commentaire quelconque.")
    db_session.flush()

    page = client.get(f"/articles/{article.id}").text
    assert "Évaluation automatisée générée par algorithme" in page
    assert "n'entrent dans aucun calcul" in page


# ==============================================================================
# Correctifs de l'audit phase 21
# ==============================================================================


def test_audit_phase21_la_section_est_dans_le_corps_pas_dans_le_titre(
    client, db_session, mode_heberge
):
    """F21-01 — la section avait été insérée par un remplacement de
    `{% endblock %}` qui a touché LES DEUX blocs du gabarit : une copie correcte
    en fin de contenu, et une copie parasite dans le bloc `title`, donc dans le
    `<head>`. La page servait deux formulaires et des identifiants dupliqués.

    Les dix-neuf tests d'origine ne pouvaient pas le voir : ils cherchent une
    sous-chaîne dans `reponse.text`, et la trouvaient — deux fois. Un test de
    sous-chaîne ne teste pas une page."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    page = client.get(f"/articles/{article.id}").text
    titre = page[page.index("<title>") : page.index("</title>")]

    assert "<section" not in titre, "le titre de l'onglet ne doit pas contenir de balises"
    assert page.count('id="commentaires"') == 1, "la section ne doit exister qu'une fois"
    assert page.count('id="texte"') == 1, "identifiant dupliqué = HTML invalide et label ambigu"


def test_audit_phase21_les_commentaires_viennent_apres_l_analyse(
    client, db_session, mode_heberge
):
    """US-08, 3ᵉ critère : « affichés SOUS l'analyse et la mise en contexte,
    jamais mêlés à elles ». Une assertion de POSITION, pas de présence — c'est la
    seule qui distingue « la page contient le texte » de « la page est juste »."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")
    _commenter(client, db_session, article, "Un avis de lecteur.")
    db_session.flush()

    page = client.get(f"/articles/{article.id}").text

    assert page.index("Score composite") < page.index('id="commentaires"')
    assert page.index("Mise en contexte") < page.index('id="commentaires"')
    assert page.index("Un avis de lecteur.") > page.index("Mise en contexte")


@pytest.mark.parametrize("refus", ["vide", "trop long"])
def test_audit_phase21_un_refus_ramene_la_ou_le_message_s_affiche(
    client, db_session, mode_heberge, refus
):
    """F21-02 — le succès renvoyait vers `#commentaires`, l'échec vers le haut de
    la page, alors que le message est rendu en bas. L'utilisateur ne voyait rien
    se passer."""
    mode_heberge("secret")
    article = _article(db_session)
    _connecter(client, db_session, "alice")

    texte, attendu = ("   ", "commentaire_vide") if refus == "vide" else ("x" * 3000, "commentaire_trop_long")
    reponse = _commenter(client, db_session, article, texte)

    assert reponse.headers["location"].endswith("#commentaires"), (
        "un refus doit ramener à la section, sinon le message reste hors du champ de vision"
    )
    assert attendu in reponse.headers["location"]


def test_audit_phase21_un_commentaire_retire_occupe_toujours_le_quota(
    client, db_session, mode_heberge, monkeypatch
):
    """F21-04 — décision explicitée : exclure les retirés rendrait le retrait
    avantageux pour son auteur (publier, se faire retirer, recommencer), alors
    que le plafond existe pour freiner ce cycle."""
    mode_heberge("secret")
    monkeypatch.setenv("COMMENTAIRES_MAX_PAR_JOUR", "1")
    article = _article(db_session)
    db_session.add(
        Commentaire(
            article_id=article.id, pseudo="alice", texte="Retiré.",
            retire_le=datetime.now(timezone.utc), retire_par="chef",
        )
    )
    db_session.flush()
    _connecter(client, db_session, "alice")

    _commenter(client, db_session, article, "Un second essai.")
    db_session.flush()

    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 1


def test_audit_phase21_un_article_non_evalue_reste_commentable(client, db_session, mode_heberge):
    """F21-03 — décision explicitée plutôt que laissée au hasard du routage : la
    page annonce « pas encore été évalué » et accepte quand même le commentaire,
    qui attendra l'analyse."""
    mode_heberge("secret")
    article = Article(
        titre="Sans score", contenu="corps", domaine_source="exemple.test",
        date_publication=datetime.now(timezone.utc), url="https://exemple.test/sans-score",
        url_canonique="https://exemple.test/sans-score", hash_contenu="h-sans-score",
        plateforme="rss", metadonnees={},
    )
    db_session.add(article)
    db_session.flush()
    _connecter(client, db_session, "alice")

    page = client.get(f"/articles/{article.id}").text
    assert "n'a pas encore été évalué" in page

    _commenter(client, db_session, article, "J'attends l'analyse.")
    db_session.flush()
    assert db_session.execute(select(func.count()).select_from(Commentaire)).scalar_one() == 1
