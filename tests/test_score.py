from fakenews.evaluateur.score import calculer_score_composite


def test_moyenne_ponderee_simple():
    sous_scores = {
        "a": {"valeur": 100.0, "raison": "", "preuve_id": "a"},
        "b": {"valeur": 0.0, "raison": "", "preuve_id": "b"},
    }
    poids = {"a": 1.0, "b": 1.0}
    resultat = calculer_score_composite(sous_scores, poids)
    assert resultat["score_final"] == 50.0
    assert resultat["non_evaluable"] is False


def test_signal_exclu_valeur_none_n_influence_pas_le_score():
    sous_scores = {
        "a": {"valeur": 100.0, "raison": "", "preuve_id": "a"},
        "b": {"valeur": None, "raison": "non applicable", "preuve_id": "b"},
    }
    poids = {"a": 1.0, "b": 1.0}
    resultat = calculer_score_composite(sous_scores, poids)
    assert resultat["score_final"] == 100.0
    assert resultat["detail"]["b"]["exclu"] is True


def test_tous_les_signaux_exclus_donne_non_evaluable_sans_division_par_zero():
    sous_scores = {
        "a": {"valeur": None, "raison": "", "preuve_id": "a"},
        "b": {"valeur": None, "raison": "", "preuve_id": "b"},
    }
    poids = {"a": 1.0, "b": 1.0}
    resultat = calculer_score_composite(sous_scores, poids)
    assert resultat["score_final"] is None
    assert resultat["non_evaluable"] is True


def test_poids_differents_ponderent_correctement():
    sous_scores = {
        "lourd": {"valeur": 100.0, "raison": "", "preuve_id": "lourd"},
        "leger": {"valeur": 0.0, "raison": "", "preuve_id": "leger"},
    }
    poids = {"lourd": 3.0, "leger": 1.0}
    resultat = calculer_score_composite(sous_scores, poids)
    assert resultat["score_final"] == 75.0


def test_signal_absent_du_dictionnaire_de_poids_a_un_poids_nul():
    sous_scores = {
        "connu": {"valeur": 80.0, "raison": "", "preuve_id": "connu"},
        "inconnu_du_bareme": {"valeur": 0.0, "raison": "", "preuve_id": "x"},
    }
    poids = {"connu": 1.0}
    resultat = calculer_score_composite(sous_scores, poids)
    assert resultat["score_final"] == 80.0
    assert resultat["detail"]["inconnu_du_bareme"]["poids"] == 0.0


def test_poids_par_defaut_couvre_les_sept_signaux():
    from fakenews.evaluateur.score import POIDS_PAR_DEFAUT

    assert set(POIDS_PAR_DEFAUT) == {
        "reputation",
        "corroboration",
        "fact_checking",
        "source_primaire",
        "style",
        "decalage_viral",
        "llm_bootstrap",
    }
