from datetime import date, datetime, timezone

import httpx

from fakenews.evaluateur.source_primaire import _decaler_jours_ouvres, evaluer_source_primaire


class _EntiteFactice:
    def __init__(self, texte, label):
        self.text = texte
        self.label_ = label


class _DocFactice:
    def __init__(self, entites):
        self.ents = entites


class _NlpFactice:
    """Remplace spaCy dans les tests — même principe que ClientFactice pour le LLM
    (tests/_llm_factice.py) : pas de dépendance à un vrai modèle NER en test unitaire."""

    def __init__(self, entites):
        self._entites = entites

    def __call__(self, texte):
        return _DocFactice(self._entites)


def _client_sec_factice(reponse_json=None, leve=None):
    def handler(request):
        if leve is not None:
            raise leve
        return httpx.Response(200, json=reponse_json)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_decaler_jours_ouvres_saute_le_weekend():
    vendredi = date(2026, 8, 7)
    assert _decaler_jours_ouvres(vendredi, 1) == date(2026, 8, 10)  # lundi suivant, pas samedi


def test_entreprise_non_reconnue_est_non_applicable():
    nlp = _NlpFactice([_EntiteFactice("Une PME Obscure Inc.", "ORG")])
    resultat = evaluer_source_primaire(
        "Titre", "Contenu", datetime(2026, 1, 5, tzinfo=timezone.utc), nlp=nlp, client=_client_sec_factice()
    )
    assert resultat["valeur"] is None
    assert "non applicable" in resultat["raison"]
    assert resultat["preuve_id"] == "source_primaire"


def test_aucune_entite_org_est_non_applicable():
    nlp = _NlpFactice([])
    resultat = evaluer_source_primaire(
        "Titre", "Contenu", datetime(2026, 1, 5, tzinfo=timezone.utc), nlp=nlp, client=_client_sec_factice()
    )
    assert resultat["valeur"] is None


def test_entite_non_org_est_ignoree():
    nlp = _NlpFactice([_EntiteFactice("Tesla", "PERSON")])
    resultat = evaluer_source_primaire(
        "Titre", "Contenu", datetime(2026, 1, 5, tzinfo=timezone.utc), nlp=nlp, client=_client_sec_factice()
    )
    assert resultat["valeur"] is None


def test_extraction_ner_echouee_degrade_en_valeur_none():
    def nlp_qui_leve(texte):
        raise RuntimeError("modèle indisponible")

    resultat = evaluer_source_primaire(
        "Titre", "Contenu", datetime(2026, 1, 5, tzinfo=timezone.utc), nlp=nlp_qui_leve, client=_client_sec_factice()
    )
    assert resultat["valeur"] is None
    assert "extraction" in resultat["raison"]


def test_entreprise_reconnue_et_depot_trouve_confirme():
    nlp = _NlpFactice([_EntiteFactice("Tesla Inc.", "ORG")])
    reponse = {"hits": {"hits": [{"_id": "0001193125-26-000123", "_source": {"adsh": "0001193125-26-000123"}}]}}
    resultat = evaluer_source_primaire(
        "Tesla annonce un rappel",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(reponse),
    )
    assert resultat["valeur"] == 5.0
    assert resultat["preuve_id"] == "source_primaire:0001193125-26-000123"


def test_entreprise_reconnue_mais_aucun_depot_trouve_augmente_suspicion():
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Tesla annonce un rappel",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice({"hits": {"hits": []}}),
    )
    assert resultat["valeur"] == 85.0
    assert resultat["preuve_id"] == "source_primaire"


def test_echec_sec_edgar_degrade_en_valeur_none():
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Tesla annonce un rappel",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(leve=httpx.ConnectError("indisponible")),
    )
    assert resultat["valeur"] is None
    assert resultat["preuve_id"] == "source_primaire"
