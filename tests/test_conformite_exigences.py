"""Un test par critère d'acceptation, nommé d'après lui.

Raison d'être (cf. audit phase 10) : `test_correctifs_audit.py` verrouille les
régressions des correctifs DÉJÀ passés — il ne dit rien de la conformité initiale.
C'est par ce trou que quatre audits successifs ont déclaré la couche métier
conforme sans la re-dériver des user stories : un critère non tenu ne produisait
aucun signal, seulement l'absence d'un test que personne n'avait écrit.

Un critère violé doit être un test ROUGE, pas un paragraphe dans un rapport.
"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import fakenews.frontend.app as app_frontend
from fakenews.config import (
    NOM_ENV_SEUIL,
    SEUIL_SUSPICION_PAR_DEFAUT,
    entier_depuis_env,
    seuil_suspicion,
)
from fakenews.contextualiseur.declenchement import PLAFOND_APPELS_PAR_DEFAUT
from fakenews.contextualiseur.run_contextualiseur import NOM_ENV_PLAFOND
from fakenews.frontend.app import app


# --- US-01 contextualiseur ------------------------------------------------------


def test_us01_le_seuil_de_suspicion_est_configurable_sans_modifier_le_code(monkeypatch):
    """1er critère d'acceptation, mot pour mot : « le seuil est configurable sans
    modification du code ». C'était une constante de module."""
    assert seuil_suspicion() == SEUIL_SUSPICION_PAR_DEFAUT
    monkeypatch.setenv(NOM_ENV_SEUIL, "42.5")
    assert seuil_suspicion() == 42.5


def test_us01_le_seuil_par_defaut_reste_60(monkeypatch):
    """2e critère : « le seuil par défaut est fixé à 60/100 ». Rendre une valeur
    configurable ne doit pas déplacer son défaut."""
    monkeypatch.delenv(NOM_ENV_SEUIL, raising=False)
    assert seuil_suspicion() == 60.0


def test_us01_le_plafond_d_appels_du_contextualiseur_est_configurable(monkeypatch):
    """4e critère : « le nombre d'appels LLM du contextualiseur par run est plafonné
    (valeur configurable, DISTINCTE du plafond US-07 évaluateur) ». La constante
    existait mais n'était ni lue depuis l'environnement, ni même transmise."""
    assert entier_depuis_env(NOM_ENV_PLAFOND, PLAFOND_APPELS_PAR_DEFAUT) == PLAFOND_APPELS_PAR_DEFAUT
    monkeypatch.setenv(NOM_ENV_PLAFOND, "3")
    assert entier_depuis_env(NOM_ENV_PLAFOND, PLAFOND_APPELS_PAR_DEFAUT) == 3


def test_us01_le_plafond_du_contextualiseur_est_distinct_de_celui_de_l_evaluateur():
    """Le critère insiste sur « distincte » : un appel d'explication coûte plus cher
    qu'un appel de scoring court (cf. architecture.md)."""
    assert NOM_ENV_PLAFOND != "LLM_PLAFOND_EVALUATEUR"


@pytest.mark.parametrize("valeur", ["600", "-1", "101"])
def test_un_seuil_hors_bornes_echoue_au_demarrage(monkeypatch, valeur):
    """US-08 contraint le score composite à 0-100 : un seuil hors de cet intervalle
    ne peut jamais être atteint. Sans borne, une faute de frappe éteindrait le
    contextualiseur et viderait la liste du frontend, sans le moindre message."""
    monkeypatch.setenv(NOM_ENV_SEUIL, valeur)
    with pytest.raises(SystemExit) as echec:
        seuil_suspicion()
    assert NOM_ENV_SEUIL in str(echec.value)


def test_un_seuil_illisible_echoue_avec_un_diagnostic(monkeypatch):
    monkeypatch.setenv(NOM_ENV_SEUIL, "soixante")
    with pytest.raises(SystemExit) as echec:
        seuil_suspicion()
    assert "soixante" in str(echec.value)


# --- Cohérence frontend / contextualiseur ---------------------------------------


def test_le_frontend_et_le_contextualiseur_lisent_le_meme_seuil(monkeypatch):
    """Les deux blocs DOIVENT s'accorder : le frontend liste par défaut « les mêmes
    que ceux traités par le contextualiseur » (US-01 frontend, 3e critère). S'ils
    divergent, la liste montre des articles dont la mise en contexte n'a jamais été
    demandée — et la page de détail annonce alors qu'aucune n'a été générée.

    Le frontend fige le seuil au chargement du module (`SEUIL_LISTE`) ; on vérifie
    donc qu'il le tire de la MÊME source que le contextualiseur, plutôt que de
    recharger le module — un `importlib.reload` remplacerait l'objet `app` partagé
    par toute la suite et invaliderait les surcharges de dépendances des autres
    tests (constaté).
    """
    import fakenews.contextualiseur.run_contextualiseur as contextualiseur

    # Même fonction, donc même variable d'environnement et même défaut : les deux
    # blocs ne peuvent pas diverger.
    assert contextualiseur.seuil_suspicion is seuil_suspicion
    assert app_frontend.seuil_suspicion is seuil_suspicion
    assert app_frontend.SEUIL_LISTE == seuil_suspicion()


def test_un_seuil_illisible_fait_echouer_le_demarrage_du_frontend():
    """Et non chaque requête : un `SystemExit` levé dans un gestionnaire ASGI ne
    produit pas une erreur lisible, il casse le groupe de tâches du serveur —
    constaté en exécutant l'application, pas déduit (cf. audit phase 10).

    Sous-processus : c'est le seul moyen d'observer un échec à L'IMPORT sans
    recharger le module dans l'interpréteur qui fait tourner la suite."""
    import subprocess
    import sys

    environnement = {
        **os.environ,
        NOM_ENV_SEUIL: "999",
        "PYTHONPATH": str(Path(app_frontend.__file__).resolve().parents[2]),
    }
    resultat = subprocess.run(
        [sys.executable, "-c", "import fakenews.frontend.app"],
        capture_output=True, text=True, env=environnement,
    )
    assert resultat.returncode != 0
    assert NOM_ENV_SEUIL in resultat.stderr
    assert "hors de l'intervalle" in resultat.stderr


def test_le_frontend_n_importe_aucun_bloc_metier():
    """`doc/V0/architecture.md` : « les blocs ne s'appellent pas entre eux
    directement ». Le frontend importait `SEUIL_PAR_DEFAUT` depuis
    `contextualiseur.declenchement` — une valeur dont dépend le contenu affiché,
    pas un simple libellé."""
    source = Path(app_frontend.__file__).read_text(encoding="utf-8")
    assert "from fakenews.evaluateur" not in source
    assert "from fakenews.scraper" not in source
    assert "from fakenews.contextualiseur.declenchement" not in source


# --- US-04 frontend : surface exposée -------------------------------------------


@pytest.mark.parametrize("chemin", ["/docs", "/redoc", "/openapi.json"])
def test_us04_aucune_documentation_d_api_n_est_exposee(chemin):
    """US-04 frontend fait de l'authentification une « condition bloquante ». Les
    trois URL par défaut de FastAPI ne passent pas par les dépendances des routes :
    `compte_courant` ne les protégeait pas, et elles décrivaient publiquement les
    routes, leurs paramètres et le formulaire de connexion."""
    with TestClient(app) as client:
        assert client.get(chemin).status_code == 404


# --- US-07 évaluateur : plafond du backfill -------------------------------------


def test_us07_le_backfill_llm_est_plafonne_comme_le_run_hebdomadaire(monkeypatch):
    """« Le nombre d'appels LLM par run est plafonné (valeur configurable). » Le
    backfill appelle la même API payante sur toute la table `scores` : il était le
    seul chemin d'appel sans plafond."""
    from fakenews.evaluateur.backfill_llm_bootstrap import (
        NOM_ENV_PLAFOND as nom_env,
        PLAFOND_APPELS_PAR_DEFAUT as defaut,
    )

    monkeypatch.delenv(nom_env, raising=False)
    assert entier_depuis_env(nom_env, defaut) == defaut
    monkeypatch.setenv(nom_env, "5")
    assert entier_depuis_env(nom_env, defaut) == 5


# --- Documentation d'exploitation -----------------------------------------------


def test_les_variables_d_environnement_lues_sont_documentees():
    """Une variable que le code lit mais que `.env.example` ignore est invisible à
    l'exploitant : il ne peut pas la régler puisqu'il n'en connaît pas l'existence."""
    exemple = Path(__file__).resolve().parent.parent / ".env.example"
    contenu = exemple.read_text(encoding="utf-8")
    for variable in (NOM_ENV_SEUIL, NOM_ENV_PLAFOND, "LLM_PLAFOND_BACKFILL"):
        assert variable in contenu, f"{variable} lue par le code, absente de .env.example"


def test_la_lecture_de_la_configuration_n_est_pas_figee_a_l_import_du_module_config():
    """`fakenews.config` ne met AUCUNE valeur en cache : chaque appel relit
    l'environnement. C'est ce qui permet aux points d'entrée de décider eux-mêmes
    quand résoudre — au démarrage pour le frontend (`SEUIL_LISTE`), à l'appel pour
    les scripts du pipeline, qui vivent le temps d'un run."""
    valeur_initiale = os.environ.get(NOM_ENV_SEUIL)
    try:
        os.environ[NOM_ENV_SEUIL] = "33"
        assert seuil_suspicion() == 33.0
        os.environ[NOM_ENV_SEUIL] = "44"
        assert seuil_suspicion() == 44.0
    finally:
        if valeur_initiale is None:
            os.environ.pop(NOM_ENV_SEUIL, None)
        else:
            os.environ[NOM_ENV_SEUIL] = valeur_initiale
