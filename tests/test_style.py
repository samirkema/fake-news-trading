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


def test_absence_de_citation_penalise_sur_un_corps_assez_long():
    corps = "Du texte sans aucune citation nulle part, mais suffisamment long. " * 5
    resultat = evaluer_style("Titre neutre", corps, auteur="A")
    assert "citation" in resultat["raison"]


def test_corps_trop_court_n_est_pas_penalise_pour_absence_de_citation():
    """Un post Reddit de type lien a un `selftext` vide : lui reprocher de ne pas
    citer ses sources n'est pas un signal, c'est du bruit (audit, finding M3)."""
    resultat = evaluer_style("Titre neutre", "", auteur="A")
    assert "citation" not in resultat["raison"]


def test_ni_titre_ni_contenu_exclut_le_signal():
    """`style` doit pouvoir être exclu, sinon `non_evaluable` est inatteignable et
    les cinq mécanismes qui le défendent sont du code mort (audit, finding M3)."""
    resultat = evaluer_style("   ", "", auteur="A")
    assert resultat["valeur"] is None
    assert "non applicable" in resultat["raison"]


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


def test_le_maximum_structurel_du_signal_de_style_est_80():
    """Ce test s'appelait `test_valeur_plafonnee_a_100` et assertait `<= 100.0` sur
    un cas atteignant 45,0 : il passait avec OU SANS le `min(100.0, penalite)`. Une
    ligne de couverture, pas un test (cf. audit phase 10).

    En cherchant un cas qui SATURE, on découvre que c'est impossible : les quatre
    pénalités du module valent 20 (pas d'auteur) + 15 (pas de citation) + 15
    (ponctuation) + 30 (vocabulaire, déjà plafonné) = **80**. Le `min(100.0, …)`
    est donc structurellement inatteignable aujourd'hui — un garde-fou contre un
    futur réglage des pénalités, pas une contrainte vive. Le dire dans un test vaut
    mieux que de laisser croire qu'il est exercé.

    Asserter la valeur EXACTE rend ce test sensible à chacune des quatre
    constantes : en modifier une seule le fait échouer."""
    contenu = (
        "Aucune citation ici. Vérité cachée que ils ne veulent pas que vous sachiez. "
        "Scandale et catastrophe : une alerte urgente et explosive a été censurée, "
        "un contenu incroyable et choquant que les autorités ont voulu dissimuler. "
    ) * 3
    resultat = evaluer_style(
        "SCANDALE INCROYABLE !!! CENSURÉ !!! ALERTE URGENTE !!!", contenu, auteur=None
    )

    assert resultat["valeur"] == 80.0
    assert resultat["valeur"] <= 100.0
