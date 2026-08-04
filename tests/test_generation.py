from fakenews.contextualiseur.generation import generer_mise_en_contexte
from tests._llm_factice import ClientFactice

SOUS_SCORES = {
    "reputation": {"valeur": 90.0, "raison": "domaine douteux", "preuve_id": "reputation"},
    "style": {"valeur": None, "raison": "n/a", "preuve_id": "style"},
}


def test_faits_traces_avec_preuve_id_valide_conserves():
    client = ClientFactice(
        reponse_input={
            "explication": "Article suspect.",
            "faits_traces": [{"preuve_id": "reputation", "texte": "domaine sur liste douteuse"}],
            "deductions_llm": [],
            "niveau_confiance": "moyen",
        }
    )
    resultat = generer_mise_en_contexte("Titre", "Contenu", SOUS_SCORES, client=client)
    assert len(resultat["faits_traces"]) == 1
    assert resultat["sources_utilisees"] == ["reputation"]
    assert resultat["niveau_confiance"] == "moyen"


def test_faits_traces_avec_preuve_id_invente_est_deplace():
    # Le LLM invente un preuve_id qui n'existe pas dans sous_scores -> doit être
    # rejeté par validation.py, pas silencieusement accepté.
    client = ClientFactice(
        reponse_input={
            "explication": "Article suspect.",
            "faits_traces": [{"preuve_id": "fact_checking:invente", "texte": "démenti inventé"}],
            "deductions_llm": [],
            "niveau_confiance": "faible",
        }
    )
    resultat = generer_mise_en_contexte("Titre", "Contenu", SOUS_SCORES, client=client)
    assert resultat["faits_traces"] == []
    assert len(resultat["deductions_llm"]) == 1
    assert resultat["sources_utilisees"] == []


def test_preuve_id_d_un_signal_exclu_est_rejete():
    # "style" existe dans sous_scores mais valeur=None (exclu) : son preuve_id ne
    # doit pas être citable comme une preuve réelle.
    client = ClientFactice(
        reponse_input={
            "explication": "Article suspect.",
            "faits_traces": [{"preuve_id": "style", "texte": "style putaclic"}],
            "deductions_llm": [],
            "niveau_confiance": "faible",
        }
    )
    resultat = generer_mise_en_contexte("Titre", "Contenu", SOUS_SCORES, client=client)
    assert resultat["faits_traces"] == []


def test_prompt_inclut_les_signaux_avec_preuve_id():
    client = ClientFactice(
        reponse_input={"explication": "x", "faits_traces": [], "deductions_llm": [], "niveau_confiance": "faible"}
    )
    generer_mise_en_contexte("Titre", "Contenu", SOUS_SCORES, client=client)
    prompt_envoye = client.dernier_appel["messages"][0]["content"]
    assert "preuve_id=reputation" in prompt_envoye
    # Le signal exclu (valeur=None) ne doit pas être présenté comme un signal
    # exploitable dans le prompt.
    assert "preuve_id=style" not in prompt_envoye
