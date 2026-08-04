from fakenews.evaluateur.style import evaluer_style


def test_article_sans_signal_recoit_une_valeur_basse():
    resultat = evaluer_style(
        titre="Le conseil municipal adopte le budget 2026",
        contenu='Selon le maire, "le budget est équilibré cette année".',
        auteur="Jean Dupont",
    )
    assert resultat["valeur"] == 10.0
    assert resultat["preuve_id"] == "style"


def test_absence_d_auteur_penalise():
    avec_auteur = evaluer_style("Titre neutre", 'Une "citation exacte ici".', auteur="A")
    sans_auteur = evaluer_style("Titre neutre", 'Une "citation exacte ici".', auteur=None)
    assert sans_auteur["valeur"] > avec_auteur["valeur"]
    assert "aucun auteur" in sans_auteur["raison"]


def test_absence_de_citation_penalise():
    resultat = evaluer_style("Titre neutre", "Du texte sans aucune citation nulle part.", auteur="A")
    assert "citation" in resultat["raison"]


def test_ponctuation_excessive_dans_le_titre_penalise():
    resultat = evaluer_style("VOUS NE DEVINEREZ JAMAIS !!!", 'Contenu avec "une citation ici".', auteur="A")
    assert "ponctuation excessive" in resultat["raison"]


def test_vocabulaire_charge_francais_detecte():
    resultat = evaluer_style(
        "Scandale et catastrophe au conseil",
        'Un article avec "une citation valable".',
        auteur="A",
    )
    assert "charge émotionnelle" in resultat["raison"]


def test_vocabulaire_charge_anglais_detecte():
    resultat = evaluer_style(
        "Shocking scandal revealed",
        'An article with "a valid quote here".',
        auteur="A",
    )
    assert "charge émotionnelle" in resultat["raison"]


def test_valeur_plafonnee_a_100():
    resultat = evaluer_style(
        "SCANDALE INCROYABLE !!! CENSURÉ !!!",
        "Aucune citation. Vérité cachée que ils ne veulent pas que vous sachiez.",
        auteur=None,
    )
    assert resultat["valeur"] <= 100.0
