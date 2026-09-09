"""Les signaux de l'évaluateur confrontés à des entrées réelles (cf. tests/corpus).

Ce module ne teste pas des chemins de code : il teste des EXIGENCES, sur les
formulations que le pipeline rencontre en production. Les tests unitaires existants
vérifient qu'un mécanisme fonctionne ; ceux-ci vérifient qu'il fonctionne sur ce
qu'on lui donne réellement à manger — c'est cette distinction qui a manqué pendant
quatre audits (cf. audit phase 10).
"""

import pytest

from fakenews.evaluateur.fact_checking import (
    VALEUR_FAUX,
    VALEUR_VRAI,
    _interpreter_verdict,
)
from fakenews.evaluateur.style import _detecter_langue, evaluer_style
from fakenews.scraper.rss import nettoyer_html
from tests.corpus import (
    RESUME_RSS_SANS_CITATION,
    RESUMES_RSS_HTML,
    TITRES_EN,
    TITRES_FR,
    VERDICTS_NIES,
    VERDICTS_REELS,
)

_ATTENDU = {"faux": VALEUR_FAUX, "vrai": VALEUR_VRAI, "neutre": None}


# --- US-03 évaluateur : verdicts de fact-checking -------------------------------


@pytest.mark.parametrize("verdict,attendu", VERDICTS_REELS, ids=[v for v, _ in VERDICTS_REELS])
def test_us03_les_verdicts_reels_sont_interpretes_dans_le_bon_sens(verdict, attendu):
    assert _interpreter_verdict(verdict) == _ATTENDU[attendu]


@pytest.mark.parametrize("verdict", VERDICTS_NIES)
def test_us03_un_verdict_nie_n_est_jamais_lu_comme_vrai(verdict):
    """L'invariant qui aurait tué le défaut d'origine.

    Chacune de ces formulations contient littéralement le terme positif qu'elle
    nie (` true ` dans ` not true `). Les lire comme « vrai » ne dégrade pas le
    score : il l'INVERSE, faisant passer un article démenti de 90 à 5."""
    assert _interpreter_verdict(verdict) != VALEUR_VRAI


def test_us03_aucun_verdict_reel_faux_ne_bascule_vers_vrai():
    """Formulation directe de la régression constatée : `"Inaccurate"` était lu
    comme `"accurate"`, `"Incorrect"` comme `"correct"`."""
    inversions = [
        verdict
        for verdict, attendu in VERDICTS_REELS
        if attendu == "faux" and _interpreter_verdict(verdict) == VALEUR_VRAI
    ]
    assert inversions == []


# --- US-05 évaluateur : détection de langue sur des titres ----------------------


@pytest.mark.parametrize("titre", TITRES_FR)
def test_us05_un_titre_francais_est_detecte_comme_francais(titre):
    assert _detecter_langue(titre) == "fr"


@pytest.mark.parametrize("titre", TITRES_EN)
def test_us05_un_titre_anglais_est_detecte_comme_anglais(titre):
    assert _detecter_langue(titre) == "en"


def test_us05_le_lexique_francais_s_applique_a_un_titre_francais_court():
    """Le critère d'US-05 : « les marqueurs de sensationnalisme sont évalués via
    des lexiques distincts PAR LANGUE ». Sur ce titre, la détection précédente
    répondait « en » et appliquait donc le lexique anglais : « choquant » et
    « vérité cachée » n'étaient jamais vus."""
    resultat = evaluer_style(
        "Choquant : la vérité cachée sur les vaccins", "", auteur="A. Journaliste"
    )
    assert "vocabulaire à forte charge émotionnelle" in resultat["raison"]
    assert "choquant" in resultat["raison"]


def test_us05_le_lexique_anglais_reste_applique_a_un_titre_anglais():
    resultat = evaluer_style(
        "Shocking: the hidden truth about vaccines", "", auteur="A. Reporter"
    )
    assert "shocking" in resultat["raison"]


# --- US-01/US-04 scraper : le HTML des flux ne doit pas atteindre les signaux ----


@pytest.mark.parametrize("brut,attendu", RESUMES_RSS_HTML)
def test_le_html_des_flux_est_reduit_a_du_texte_lisible(brut, attendu):
    assert nettoyer_html(brut) == attendu


def test_les_blocs_script_ne_survivent_pas_au_nettoyage():
    """Retirer les balises sans retirer leur contenu laisserait le corps du script
    dans le texte de l'article."""
    texte = nettoyer_html(
        '<script>var cle = "secret-analytics";</script><p>Le texte réel.</p>'
    )
    assert texte == "Le texte réel."
    assert "secret-analytics" not in texte


def test_us05_un_attribut_html_n_est_pas_compte_comme_une_citation():
    """Le défaut exact : `href="https://..."` satisfait `"[^"]{10,}"`. Un article
    sans la moindre source nommée échappait donc à sa pénalité."""
    contenu = nettoyer_html(RESUME_RSS_SANS_CITATION)
    resultat = evaluer_style("Intempéries : trois routes fermées", contenu, auteur="A. B.")
    assert "aucune citation ou source nommée détectée" in resultat["raison"]


def test_us05_une_vraie_citation_reste_reconnue():
    """Contre-épreuve : le correctif ne doit pas rendre la détection aveugle."""
    contenu = (
        "La préfecture a précisé la situation lors d'un point presse tenu en fin "
        "de matinée devant les élus locaux réunis pour l'occasion. "
        '"Les trois axes concernés rouvriront avant la fin de la journée", a '
        "déclaré le porte-parole, ajoutant que les équipes restaient mobilisées."
    )
    resultat = evaluer_style("Intempéries : trois routes fermées", contenu, auteur="A. B.")
    assert "aucune citation" not in resultat["raison"]


def test_us05_un_corps_reduit_a_des_liens_n_est_pas_juge_sur_ses_citations():
    """Un `selftext` Reddit fait de liens n'a pas de prose : lui reprocher
    l'absence de citation serait du bruit, pas un signal (même raison que
    LONGUEUR_MIN_POUR_CITATION)."""
    contenu = " ".join(f"https://www.exemple.com/article-numero-{n}" for n in range(8))
    resultat = evaluer_style("Discussion du jour sur les marchés", contenu, auteur="u/x")
    assert "aucune citation" not in resultat["raison"]
