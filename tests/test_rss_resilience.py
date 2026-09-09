"""Résilience de la collecte RSS au grain de l'ENTRÉE.

Pendant de `test_reddit_resilience.py`, qui couvrait déjà le grain du post côté
Reddit. `rss.py` n'avait pas cette protection : une seule entrée malformée faisait
remonter l'exception hors de `collecter_rss`, emportant les flux suivants ET la
collecte Reddit qui s'exécute après dans `run_scraper` (cf. audit phase 10).
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from fakenews.models import Article
from fakenews.scraper import rss


def _flux(*entrees) -> SimpleNamespace:
    return SimpleNamespace(entries=list(entrees), bozo=0, bozo_exception=None)


def _entree(titre: str, lien: str, description: str = "Un résumé.") -> dict:
    return {
        "title": titre,
        "link": lien,
        "description": description,
        "published_parsed": (2026, 1, 5, 10, 0, 0, 0, 0, 0),
    }


@pytest.fixture
def une_seule_source(monkeypatch):
    """Une seule source configurée, dont on pilote entièrement le flux."""

    def _configurer(flux):
        monkeypatch.setattr(
            rss,
            "RSS_SOURCES",
            [{"nom": "Flux Test", "domaine_source": "test-rss.invalid", "url": "https://test-rss.invalid/feed"}],
        )
        monkeypatch.setattr(rss, "_recuperer_flux", lambda source: (source, flux))

    return _configurer


def test_une_entree_en_echec_n_interrompt_pas_le_flux(db_session, une_seule_source, monkeypatch):
    """Le cœur du correctif : la deuxième entrée échoue, les deux autres passent."""
    une_seule_source(
        _flux(
            _entree("Article un", "https://test-rss.invalid/a"),
            _entree("Article deux", "https://test-rss.invalid/b"),
            _entree("Article trois", "https://test-rss.invalid/c"),
        )
    )

    vrai_hachage = rss.hacher_contenu

    def _hachage_capricieux(titre, contenu):
        if titre == "Article deux":
            raise ValueError("entrée impossible à normaliser")
        return vrai_hachage(titre, contenu)

    monkeypatch.setattr(rss, "hacher_contenu", _hachage_capricieux)

    bilan = rss.collecter_rss(db_session)

    assert bilan["Flux Test"]["statut"] == "ok"
    assert bilan["Flux Test"]["ajoutes"] == 2
    assert bilan["Flux Test"]["ignores_erreur"] == 1

    titres = set(
        db_session.execute(
            select(Article.titre).where(Article.domaine_source == "test-rss.invalid")
        ).scalars()
    )
    assert titres == {"Article un", "Article trois"}


def test_une_ecriture_refusee_par_la_base_laisse_la_session_utilisable(
    db_session, une_seule_source, monkeypatch
):
    """Le cas que le point de sauvegarde existe pour absorber : c'est la BASE qui
    refuse, pas le code applicatif.

    (Une première version de ce test faisait porter le rejet à deux entrées de même
    URL canonique — mais `canonicaliser_url` retire la query string, si bien que la
    déduplication applicative interceptait le doublon et la contrainte SQL n'était
    jamais atteinte. Le test passait sans rien exercer. On force donc une violation
    que le code applicatif ne peut pas voir venir : `contenu` NOT NULL.)

    Sans `begin_nested`, la session reste en attente de rollback après le refus et
    TOUTES les entrées suivantes échouent en cascade sur `PendingRollbackError`,
    masquant leur propre cause."""
    une_seule_source(
        _flux(
            _entree("Premier", "https://test-rss.invalid/1"),
            _entree("Second", "https://test-rss.invalid/2"),
            _entree("Troisieme", "https://test-rss.invalid/3"),
        )
    )

    vrai_extraire = rss._extraire_contenu

    def _contenu_invalide(entree):
        # `contenu` est NOT NULL en base : le refus vient de Postgres, au flush.
        return None if entree.get("title") == "Second" else vrai_extraire(entree)

    monkeypatch.setattr(rss, "_extraire_contenu", _contenu_invalide)

    bilan = rss.collecter_rss(db_session)

    assert bilan["Flux Test"]["ignores_erreur"] == 1
    titres = set(
        db_session.execute(
            select(Article.titre).where(Article.domaine_source == "test-rss.invalid")
        ).scalars()
    )
    # Les entrées d'AVANT et d'APRÈS le refus sont toutes deux préservées : le
    # savepoint ne défait que l'entrée fautive.
    assert titres == {"Premier", "Troisieme"}


def test_le_html_du_flux_ne_se_retrouve_pas_dans_le_contenu_stocke(db_session, une_seule_source):
    """Le nettoyage a lieu à la collecte : ce qui est persisté est déjà du texte."""
    une_seule_source(
        _flux(
            _entree(
                "Avec du balisage",
                "https://test-rss.invalid/html",
                description='<p>Le texte r&eacute;el.</p><a href="https://ailleurs.invalid/x">Lire</a>',
            )
        )
    )

    rss.collecter_rss(db_session)

    contenu = db_session.execute(
        select(Article.contenu).where(Article.titre == "Avec du balisage")
    ).scalar_one()
    assert contenu == "Le texte réel. Lire"
    assert "<" not in contenu
    assert "href" not in contenu
