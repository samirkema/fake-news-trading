from fakenews.contextualiseur.validation import valider_faits_traces

SOUS_SCORES = {
    "fact_checking": {"valeur": 90.0, "raison": "démenti", "preuve_id": "fact_checking:https://example.com/claim"},
    "reputation": {"valeur": None, "raison": "inconnue", "preuve_id": "reputation"},
}


def test_item_avec_preuve_id_valide_reste_dans_faits_traces():
    brouillon = {
        "faits_traces": [{"preuve_id": "fact_checking:https://example.com/claim", "texte": "démenti par un fact-checker"}],
        "deductions_llm": [],
    }
    resultat = valider_faits_traces(brouillon, SOUS_SCORES)
    assert len(resultat["faits_traces"]) == 1
    assert resultat["deductions_llm"] == []


def test_item_avec_preuve_id_inconnu_est_deplace_vers_deductions():
    brouillon = {
        "faits_traces": [{"preuve_id": "preuve-inventee", "texte": "affirmation non ancrée"}],
        "deductions_llm": [],
    }
    resultat = valider_faits_traces(brouillon, SOUS_SCORES)
    assert resultat["faits_traces"] == []
    assert len(resultat["deductions_llm"]) == 1


def test_item_referencant_un_signal_exclu_est_deplace_vers_deductions():
    # "reputation" existe dans sous_scores mais valeur=None (signal exclu) : son preuve_id
    # ne doit pas être considéré comme une preuve réelle citable.
    brouillon = {
        "faits_traces": [{"preuve_id": "reputation", "texte": "réputation douteuse"}],
        "deductions_llm": [],
    }
    resultat = valider_faits_traces(brouillon, SOUS_SCORES)
    assert resultat["faits_traces"] == []
    assert len(resultat["deductions_llm"]) == 1


def test_deductions_llm_existantes_sont_preservees():
    brouillon = {
        "faits_traces": [],
        "deductions_llm": [{"texte": "déjà une déduction"}],
    }
    resultat = valider_faits_traces(brouillon, SOUS_SCORES)
    assert resultat["deductions_llm"] == [{"texte": "déjà une déduction"}]
