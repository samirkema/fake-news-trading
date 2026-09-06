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
