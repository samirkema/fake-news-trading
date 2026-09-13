"""V3, US-04 — entrée des propositions acceptées dans le pipeline
(cf. doc/V3/userstories_crowdsourcing.md).

La collecte tire une URL fournie par un utilisateur : ces tests vérifient autant
ce qu'elle rapporte que ce qu'elle refuse d'aller chercher.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import fakenews.scraper.propositions as collecteur
from fakenews.models import Article, Proposition

PAGE = (
    "<html><head><title>  Tesla annonce des livraisons record  </title>"
    '<meta property="article:published_time" content="2026-03-15T08:30:00Z">'
    "<style>.a{color:red}</style></head>"
    "<body><script>var x=1;</script><p>Le constructeur a publié ses chiffres.</p>"
    "</body></html>"
).encode()


@pytest.fixture
def sans_reseau(monkeypatch):
    """Remplace le téléchargement par un double : aucune sortie réseau en test
    (cf. la garde `_pas_de_reseau` de conftest), et le contenu est maîtrisé."""

    def _poser(reponse):
        def _faux_telecharger(url, taille_max=None):
            return reponse(url) if callable(reponse) else reponse

        monkeypatch.setattr(collecteur, "_telecharger", _faux_telecharger)

    return _poser


def _proposition(db_session, url="https://exemple.test/scoop", statut="acceptee", **extra):
    champs = {
        "url": url,
        "url_canonique": url,
        "propose_par": "alice",
        "statut": statut,
        "decide_par": "bob",
        "date_decision": datetime.now(timezone.utc),
        **extra,
    }
    proposition = Proposition(**champs)
    db_session.add(proposition)
    db_session.flush()
    return proposition


def test_une_proposition_acceptee_devient_un_article(db_session, sans_reseau):
    sans_reseau(PAGE)
    proposition = _proposition(db_session)

    bilan = collecteur.collecter_propositions(db_session)
    db_session.flush()
    db_session.refresh(proposition)

    assert bilan["collectees"] == 1
    article = db_session.get(Article, proposition.article_id)
    assert article is not None
    assert article.plateforme == "proposition"
    assert article.titre == "Tesla annonce des livraisons record"
    assert "publié ses chiffres" in article.contenu
    assert article.domaine_source == "exemple.test"
    assert proposition.statut == "collectee"


def test_le_balisage_ne_survit_pas_a_la_collecte(db_session, sans_reseau):
    """Même exigence que pour les flux RSS : le HTML brut fausse la détection de
    citations (US-05 évaluateur), le NER et la facturation LLM."""
    sans_reseau(PAGE)
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    article = db_session.execute(select(Article)).scalars().one()

    for indesirable in ("<p>", "<script>", "var x=1", "color:red"):
        assert indesirable not in article.contenu


def test_la_date_declaree_par_la_page_est_reprise(db_session, sans_reseau):
    sans_reseau(PAGE)
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    article = db_session.execute(select(Article)).scalars().one()

    assert article.date_publication.astimezone(timezone.utc).date().isoformat() == "2026-03-15"
    assert article.metadonnees["date_publication_estimee"] is False


def test_une_page_sans_date_retombe_sur_la_date_de_proposition(db_session, sans_reseau):
    """`articles.date_publication` est NOT NULL. Le repli est une ESTIMATION : il
    décale la fenêtre ±5 jours ouvrés d'US-04 évaluateur et le filtre par date du
    frontend, donc il doit être lisible dans la donnée."""
    sans_reseau(b"<html><head><title>Sans date</title></head><body><p>Du texte ici.</p></body></html>")
    proposition = _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    article = db_session.execute(select(Article)).scalars().one()

    assert article.metadonnees["date_publication_estimee"] is True
    assert abs(article.date_publication - proposition.date_proposition) < timedelta(seconds=5)


def test_une_page_injoignable_ne_bloque_pas_les_suivantes(db_session, sans_reseau):
    """« Dégrader, jamais bloquer », au grain de l'entrée."""
    sans_reseau(lambda url: None if "casse" in url else PAGE)
    cassee = _proposition(db_session, url="https://exemple.test/casse")
    bonne = _proposition(db_session, url="https://exemple.test/bonne")

    bilan = collecteur.collecter_propositions(db_session)
    db_session.flush()
    db_session.refresh(cassee)
    db_session.refresh(bonne)

    assert bilan == {"collectees": 1, "echecs": 1, "deja_presentes": 0}
    assert cassee.statut == "echec_collecte"
    assert cassee.motif == "page injoignable"
    assert bonne.statut == "collectee"


def test_une_page_sans_texte_est_un_echec_pas_un_article_vide(db_session, sans_reseau):
    sans_reseau(b"<html><head><title>Vide</title></head><body><script>x</script></body></html>")
    proposition = _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    db_session.refresh(proposition)

    assert proposition.statut == "echec_collecte"
    assert db_session.execute(select(func.count()).select_from(Article)).scalar_one() == 0


def test_une_adresse_non_http_n_est_jamais_telechargee(db_session, monkeypatch):
    """La proposition a été validée à la saisie, mais c'est ICI qu'on ouvre la
    connexion : la validation ne se délègue pas au maillon précédent."""
    appels = []
    monkeypatch.setattr(collecteur, "_telecharger", lambda url, taille_max=None: appels.append(url))
    proposition = _proposition(db_session, url="file:///etc/passwd")

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    db_session.refresh(proposition)

    assert appels == [], "aucune connexion ne doit être ouverte vers un schéma non http(s)"
    assert proposition.statut == "echec_collecte"


def test_seules_les_propositions_acceptees_sont_collectees(db_session, sans_reseau):
    sans_reseau(PAGE)
    for statut in ("en_attente", "refusee", "collectee"):
        extra = {"motif": "hors sujet"} if statut == "refusee" else {}
        _proposition(db_session, url=f"https://exemple.test/{statut}", statut=statut, **extra)

    bilan = collecteur.collecter_propositions(db_session)

    assert bilan["collectees"] == 0
    assert db_session.execute(select(func.count()).select_from(Article)).scalar_one() == 0


def test_un_article_deja_collecte_est_rattache_sans_doublon(db_session, sans_reseau):
    """Le scraper automatique a pu ramener la même URL entre l'acceptation et la
    collecte : on rattache, on ne duplique pas."""
    sans_reseau(PAGE)
    url = "https://exemple.test/deja"
    existant = Article(
        titre="Déjà collecté", contenu="corps", domaine_source="exemple.test",
        date_publication=datetime.now(timezone.utc), url=url, url_canonique=url,
        hash_contenu="h-deja", plateforme="rss", metadonnees={},
    )
    db_session.add(existant)
    db_session.flush()
    proposition = _proposition(db_session, url=url)

    bilan = collecteur.collecter_propositions(db_session)
    db_session.flush()
    db_session.refresh(proposition)

    assert bilan["deja_presentes"] == 1
    assert proposition.article_id == existant.id
    assert db_session.execute(select(func.count()).select_from(Article)).scalar_one() == 1


def test_le_plafond_par_run_est_opposable(db_session, sans_reseau, monkeypatch):
    sans_reseau(PAGE)
    monkeypatch.setenv(collecteur.NOM_ENV_PLAFOND, "2")
    for i in range(4):
        _proposition(db_session, url=f"https://exemple.test/p{i}")

    bilan = collecteur.collecter_propositions(db_session)

    assert bilan["collectees"] == 2


def test_les_plus_anciennement_acceptees_passent_d_abord(db_session, sans_reseau):
    """Même principe que le correctif F3 sur l'évaluateur : sans ordre stable sur
    l'ancienneté, une proposition acceptée peut être doublée indéfiniment."""
    sans_reseau(PAGE)
    ancienne = _proposition(
        db_session, url="https://exemple.test/ancienne",
        date_decision=datetime.now(timezone.utc) - timedelta(days=3),
    )
    _proposition(db_session, url="https://exemple.test/recente")

    collecteur.collecter_propositions(db_session, plafond=1)
    db_session.flush()
    db_session.refresh(ancienne)

    assert ancienne.statut == "collectee"


def test_la_lecture_est_bornee_en_taille(db_session, monkeypatch):
    """Ces URL viennent des utilisateurs : une réponse démesurée ne doit pas
    gonfler la mémoire du runner."""
    recu = {}

    def _faux(url, taille_max=None):
        recu["taille_max"] = taille_max
        return PAGE

    monkeypatch.setattr(collecteur, "_telecharger", _faux)
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)

    assert recu["taille_max"] == collecteur.TAILLE_MAX_OCTETS
    assert collecteur.TAILLE_MAX_OCTETS <= 2_000_000


def test_parcours_complet_de_la_proposition_au_score(db_session, sans_reseau, monkeypatch):
    """US-01 → US-04 de bout en bout, sans le frontend : une proposition acceptée
    devient un article, qui reçoit un score et devient donc consultable.

    C'est le seul test qui vérifie que les deux moitiés du crowdsourcing se
    rejoignent. Sans lui, la file d'attente et l'évaluateur pourraient très bien
    fonctionner chacun de leur côté sans jamais se parler."""
    from fakenews.evaluateur.run_evaluateur import evaluer_articles_non_scores
    from fakenews.models import Score

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_FACT_CHECK_API_KEY", raising=False)
    sans_reseau(PAGE)
    proposition = _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    # `plafond_llm=0` : aucun appel payant, les signaux hors ligne suffisent ici.
    evaluer_articles_non_scores(db_session, plafond_llm=0)
    db_session.flush()
    db_session.refresh(proposition)

    score = db_session.execute(
        select(Score).where(Score.article_id == proposition.article_id)
    ).scalar_one()
    assert proposition.statut == "collectee"
    assert score.sous_scores, "l'article proposé doit être noté comme n'importe quel autre"


# ==============================================================================
# Correctifs de l'audit phase 19
# ==============================================================================


@pytest.mark.parametrize(
    "issue", ["page injoignable", "collecte réussie", "adresse refusée"]
)
def test_audit_phase19_aucune_issue_ne_saute_le_commit(db_session, sans_reseau, monkeypatch, issue):
    """F19-01 — les branches d'échec sortaient par `continue` depuis l'intérieur
    du `with begin_nested()`, ce qui sautait le `session.commit()` placé après le
    bloc. Mesuré : bilan annonçant un échec, base relue en session neuve
    répondant toujours `acceptee`. Trois conséquences, toutes silencieuses — page
    morte retéléchargée à chaque run, proposant jamais informé, `article_id`
    jamais rattaché dans le cas « déjà présent ».

    Les trois formes d'issue sont couvertes : le défaut n'était pas propre au
    chemin « page injoignable », il touchait toute sortie anticipée.

    Limite de ce test : la fixture `db_session` enferme tout dans une transaction
    annulée, donc relire depuis une autre connexion est impossible ici. On vérifie
    la propriété qui manquait — une issue, un commit — plutôt que sa conséquence.
    Le bout en bout a été mesuré par sonde (cf. audit phase 19)."""
    commits = []
    vrai_commit = db_session.commit
    monkeypatch.setattr(db_session, "commit", lambda: (commits.append(1), vrai_commit())[1])

    sans_reseau(None if issue == "page injoignable" else PAGE)
    url = "file:///etc/passwd" if issue == "adresse refusée" else "https://exemple.test/x"
    proposition = _proposition(db_session, url=url)

    collecteur.collecter_propositions(db_session)

    assert len(commits) == 1, "une issue = un commit, sinon la base garde `acceptee`"
    assert proposition.statut != "acceptee", "l'issue doit être inscrite sur la proposition"


def test_audit_phase19_l_auteur_declare_par_la_page_est_repris(db_session, sans_reseau):
    """F19-02 — `auteur=None` était câblé en dur, alors qu'`evaluer_style`
    pénalise de 20 points « aucun auteur identifiable ». Tout article entré par
    proposition était donc pénalisé quel que soit son contenu, alors même que le
    titre et la date étaient déjà extraits par le même procédé."""
    sans_reseau(
        b'<html><head><title>Un titre</title>'
        b'<meta name="author" content="  Camille Duflot  "></head>'
        b"<body><p>Du texte suffisant.</p></body></html>"
    )
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    article = db_session.execute(select(Article)).scalars().one()

    assert article.auteur == "Camille Duflot"


def test_audit_phase19_l_ordre_des_attributs_meta_est_indifferent(db_session, sans_reseau):
    """Les deux ordres existent dans la nature ; n'en gérer qu'un revient à ne
    rien extraire d'un site sur deux."""
    sans_reseau(
        b'<html><head><title>Un titre</title>'
        b'<meta content="Alex Martin" property="article:author"></head>'
        b"<body><p>Du texte suffisant.</p></body></html>"
    )
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    assert db_session.execute(select(Article)).scalars().one().auteur == "Alex Martin"


def test_audit_phase19_une_page_sans_auteur_reste_sans_auteur(db_session, sans_reseau):
    """Contre-épreuve : la pénalité stylistique reste méritée quand la page ne
    signe pas. Sans ce test, renvoyer une valeur bidon passerait."""
    sans_reseau(PAGE)
    _proposition(db_session)

    collecteur.collecter_propositions(db_session)
    db_session.flush()
    assert db_session.execute(select(Article)).scalars().one().auteur is None


def test_audit_phase19_le_telechargement_s_arrete_a_la_borne(monkeypatch):
    """F19-07 — le plafond de lecture n'était exercé par aucun test : la fixture
    remplace `_telecharger`, donc le `read(taille_max)` ajouté à `rss.py` n'était
    jamais appelé. On vérifie ici la vraie fonction, avec une réponse factice qui
    prétend livrer bien plus que demandé."""
    import urllib.request
    from contextlib import contextmanager

    from fakenews.scraper.rss import _telecharger

    class ReponseGeante:
        def read(self, taille=None):
            # Un serveur hostile ignore la demande : c'est `read(n)` qui borne.
            return b"x" * (taille if taille else 50_000_000)

    @contextmanager
    def _fausse_ouverture(requete, timeout=None):
        yield ReponseGeante()

    monkeypatch.setattr(urllib.request, "urlopen", _fausse_ouverture)

    assert len(_telecharger("https://exemple.test/enorme", taille_max=1000)) == 1000
