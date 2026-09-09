import pytest

from fakenews.evaluateur.llm_bootstrap import evaluer_llm_bootstrap
from tests._llm_factice import ClientFactice


def test_reponse_valide_est_transformee_en_signal():
    client = ClientFactice(reponse_input={"score_suspicion": 75.0, "justification": "Ton alarmiste, pas de source."})
    resultat = evaluer_llm_bootstrap("Titre", "Contenu", client=client)
    assert resultat == {
        "valeur": 75.0,
        "raison": "Ton alarmiste, pas de source.",
        "preuve_id": "llm_bootstrap",
    }


def test_echec_de_l_appel_degrade_en_valeur_none():
    client = ClientFactice(leve=RuntimeError("quota dépassé"))
    resultat = evaluer_llm_bootstrap("Titre", "Contenu", client=client)
    assert resultat["valeur"] is None
    assert resultat["preuve_id"] == "llm_bootstrap"
    # `raison` est persistée puis affichée dans le frontend : elle porte le TYPE de
    # l'exception, jamais son message brut, qui peut transporter une URL contenant
    # une clé d'API (cf. audit, finding H2 — prouvé sur fact_checking).
    assert "RuntimeError" in resultat["raison"]
    assert "quota dépassé" not in resultat["raison"]


def test_reponse_malformee_degrade_en_valeur_none():
    client = ClientFactice(reponse_input={"justification": "manque le score"})  # clé score_suspicion absente
    resultat = evaluer_llm_bootstrap("Titre", "Contenu", client=client)
    assert resultat["valeur"] is None


@pytest.mark.parametrize("hors_bornes", [150.0, -20.0, 101.0, 100.5])
def test_un_score_hors_bornes_est_exclu_pas_ecrete(hors_bornes):
    """Le `minimum`/`maximum` du SCHEMA est une consigne au modèle, pas une
    validation : rien ne rejette une valeur hors bornes côté API. Elle traversait
    l'agrégateur jusqu'à la contrainte SQL `ck_scores_score_final_range`, où
    l'IntegrityError faisait échouer le `commit()` de TOUT le run (audit phase 10).

    Exclu et non écrêté : ramener 150 à 100 fabriquerait une suspicion maximale à
    partir d'une réponse que le modèle a manifestement ratée."""
    client = ClientFactice(
        reponse_input={"score_suspicion": hors_bornes, "justification": "peu importe"}
    )
    resultat = evaluer_llm_bootstrap("Titre", "Contenu", client=client)
    assert resultat["valeur"] is None
    assert "hors bornes" in resultat["raison"]


@pytest.mark.parametrize("aux_bornes", [0.0, 100.0])
def test_les_bornes_elles_memes_restent_acceptees(aux_bornes):
    """Contre-épreuve : le contrôle est inclusif, 0 et 100 sont des scores légitimes."""
    client = ClientFactice(
        reponse_input={"score_suspicion": aux_bornes, "justification": "aux bornes"}
    )
    assert evaluer_llm_bootstrap("Titre", "Contenu", client=client)["valeur"] == aux_bornes
