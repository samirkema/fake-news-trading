import httpx

from fakenews.evaluateur.fact_checking import evaluer_fact_checking


def _client_factice(reponse_json=None, leve=None, contenu_brut=None):
    def handler(request):
        if leve is not None:
            raise leve
        if contenu_brut is not None:
            return httpx.Response(200, content=contenu_brut)
        return httpx.Response(200, json=reponse_json)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_cle_absente_exclut_le_signal(monkeypatch):
    monkeypatch.delenv("GOOGLE_FACT_CHECK_API_KEY", raising=False)
    resultat = evaluer_fact_checking("Titre", cle_api=None, client=_client_factice())
    assert resultat["valeur"] is None
    assert "clé API" in resultat["raison"]
    assert resultat["preuve_id"] == "fact_checking"


def test_verdict_faux_augmente_la_suspicion():
    reponse = {"claims": [{"claimReview": [{"textualRating": "False", "url": "https://factcheck.example/1"}]}]}
    resultat = evaluer_fact_checking("Titre", cle_api="clef-test", client=_client_factice(reponse))
    assert resultat["valeur"] == 90.0
    assert resultat["preuve_id"] == "fact_checking:https://factcheck.example/1"


def test_verdict_vrai_diminue_la_suspicion():
    reponse = {"claims": [{"claimReview": [{"textualRating": "True", "url": "https://factcheck.example/2"}]}]}
    resultat = evaluer_fact_checking("Titre", cle_api="clef-test", client=_client_factice(reponse))
    assert resultat["valeur"] == 5.0


def test_aucune_correspondance_est_neutre():
    resultat = evaluer_fact_checking("Titre", cle_api="clef-test", client=_client_factice({"claims": []}))
    assert resultat["valeur"] is None
    assert resultat["preuve_id"] == "fact_checking"


def test_verdict_ambigu_est_ignore():
    reponse = {"claims": [{"claimReview": [{"textualRating": "Unproven", "url": "https://factcheck.example/3"}]}]}
    resultat = evaluer_fact_checking("Titre", cle_api="clef-test", client=_client_factice(reponse))
    assert resultat["valeur"] is None


def test_echec_reseau_degrade_en_valeur_none():
    resultat = evaluer_fact_checking(
        "Titre", cle_api="clef-test", client=_client_factice(leve=httpx.ConnectError("indisponible"))
    )
    assert resultat["valeur"] is None
    assert resultat["preuve_id"] == "fact_checking"


def test_reponse_malformee_degrade_en_valeur_none():
    resultat = evaluer_fact_checking(
        "Titre", cle_api="clef-test", client=_client_factice(contenu_brut=b"pas du json")
    )
    assert resultat["valeur"] is None
