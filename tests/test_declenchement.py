from fakenews.contextualiseur.declenchement import articles_a_traiter


def _score(article_id, score_final, non_evaluable=False):
    return {"article_id": article_id, "score_final": score_final, "non_evaluable": non_evaluable}


def test_seuls_les_articles_au_dessus_du_seuil_sont_retenus():
    scores = [_score("a", 80.0), _score("b", 40.0), _score("c", 60.0)]
    resultat = articles_a_traiter(scores, seuil=60.0, plafond=None)
    assert {a["article_id"] for a in resultat} == {"a", "c"}


def test_article_non_evaluable_traite_comme_sous_le_seuil():
    scores = [_score("a", None, non_evaluable=True)]
    resultat = articles_a_traiter(scores, seuil=0.0, plafond=None)
    assert resultat == []


def test_tri_par_score_decroissant():
    scores = [_score("bas", 61.0), _score("haut", 99.0), _score("moyen", 75.0)]
    resultat = articles_a_traiter(scores, seuil=60.0, plafond=None)
    assert [a["article_id"] for a in resultat] == ["haut", "moyen", "bas"]


def test_plafond_garde_les_scores_les_plus_eleves():
    scores = [_score("a", 100.0), _score("b", 90.0), _score("c", 80.0)]
    resultat = articles_a_traiter(scores, seuil=0.0, plafond=2)
    assert [a["article_id"] for a in resultat] == ["a", "b"]


def test_seuil_par_defaut_est_60():
    scores = [_score("a", 59.9), _score("b", 60.0)]
    resultat = articles_a_traiter(scores)
    assert [a["article_id"] for a in resultat] == ["b"]


def test_journalise_le_nombre_traite_vs_le_total_scoré(caplog):
    # US-01 contextualiseur exige la journalisation du nombre d'articles traités
    # vs. le nombre total scoré (doc/userstories_contextualiseur.md).
    scores = [_score("a", 80.0), _score("b", 40.0), _score("c", 90.0)]
    with caplog.at_level("INFO"):
        articles_a_traiter(scores, seuil=60.0, plafond=None)
    assert "2" in caplog.text and "3" in caplog.text
