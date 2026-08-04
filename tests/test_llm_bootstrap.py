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
    assert "quota dépassé" in resultat["raison"]


def test_reponse_malformee_degrade_en_valeur_none():
    client = ClientFactice(reponse_input={"justification": "manque le score"})  # clé score_suspicion absente
    resultat = evaluer_llm_bootstrap("Titre", "Contenu", client=client)
    assert resultat["valeur"] is None
