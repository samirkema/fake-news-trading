from datetime import date, datetime, timezone

import httpx
import pytest

from fakenews.evaluateur.source_primaire import (
    _decaler_jours_ouvres,
    _termes_distinctifs,
    _ticker_de_lentite,
    evaluer_source_primaire,
)


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


class _RequetesCaptees(list):
    """Le mock précédent ignorait complètement `request` : remplacer l'URL par une
    chaîne arbitraire, retirer `forms=8-K`, supprimer `entityName` ou inverser les
    bornes de dates laissait la suite verte (cf. audit, Mutation/Saboteur). On
    capture désormais la requête pour pouvoir l'affirmer."""

    @property
    def derniere(self) -> httpx.Request:
        assert self, "aucune requête SEC n'a été émise"
        return self[-1]


def _hits(*ids):
    return {"hits": {"hits": [{"_id": i, "_source": {"adsh": i}} for i in ids]}}


def _client_sec_factice(
    reponse_json=None, leve=None, captees: _RequetesCaptees | None = None, controle=None
):
    """`controle` : réponse servie à la requête SANS `q` (celle qui demande si
    l'entreprise a déposé quoi que ce soit dans la fenêtre). Par défaut elle
    renvoie la même chose que la requête ciblée."""

    def handler(request):
        if captees is not None:
            captees.append(request)
        if leve is not None:
            raise leve
        if controle is not None and "q" not in request.url.params:
            return httpx.Response(200, json=controle)
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


def test_aucun_depot_du_tout_dans_la_fenetre_augmente_la_suspicion():
    """Le seul cas où la pénalité est fondée : l'entreprise n'a rien déposé du tout
    pendant la fenêtre, alors que l'article prête une annonce précise. Là,
    l'absence de confirmation est réelle, pas un artefact de notre recherche."""
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Tesla rappelle 12000 Model Y",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(_hits(), controle=_hits()),
    )
    assert resultat["valeur"] == 85.0
    assert "aucun dépôt 8-K n'existe" in resultat["raison"]


def test_depot_present_mais_sans_correspondance_est_non_concluant():
    """Le cas qui produisait le faux positif de masse : l'entreprise a bien déposé,
    mais nos mots-clés n'apparaissent pas dans la prose du dépôt. Mesuré contre
    l'API réelle — `q="announces fourth quarter"` renvoie 0 hit sur un 8-K qui
    existe. Confondre ce cas avec « aucune confirmation » infligeait 85/100, sur le
    signal au poids le plus lourd, à des articles parfaitement exacts
    (cf. audit, finding H1)."""
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Tesla rappelle 12000 Model Y",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(_hits(), controle=_hits("0001193125-26-000999")),
    )
    assert resultat["valeur"] is None, "une absence de correspondance n'est pas une absence de fait"
    assert "non concluant" in resultat["raison"]


def test_la_requete_de_controle_n_est_pas_emise_si_la_ciblee_a_trouve():
    """Deux appels réseau, seulement quand c'est nécessaire."""
    captees = _RequetesCaptees()
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    evaluer_source_primaire(
        "Tesla rappelle 12000 Model Y",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(_hits("0001193125-26-000123"), captees=captees),
    )
    assert len(captees) == 1
    assert "q" in captees[0].url.params


def test_les_verbes_d_annonce_ne_servent_pas_de_termes_de_recherche():
    """« announces » est un excellent marqueur de claim et un très mauvais terme de
    recherche : un dépôt SEC décrit un fait, il ne s'annonce pas."""
    termes = _termes_distinctifs("Tesla announces record vehicle production")
    assert "announces" not in termes
    assert "tesla" in termes


def test_la_requete_sec_porte_les_bons_parametres():
    """Vérifie ce que le mock laissait passer : le formulaire, l'entité, la fenêtre
    de dates, et surtout que `q` porte des TERMES DISTINCTIFS et non le titre de
    presse entier — un titre de journaliste n'apparaît jamais verbatim dans un 8-K,
    ce qui rendait la recherche structurellement infructueuse et la pénalité de
    non-confirmation systématique (cf. audit, finding H1)."""
    captees = _RequetesCaptees()
    nlp = _NlpFactice([_EntiteFactice("Tesla Inc.", "ORG")])
    titre = "Tesla annonce le rappel de 12000 Model Y pour un défaut logiciel"

    evaluer_source_primaire(
        titre,
        "Contenu",
        datetime(2026, 1, 8, tzinfo=timezone.utc),  # jeudi
        fenetre_jours_ouvres=5,
        nlp=nlp,
        client=_client_sec_factice({"hits": {"hits": []}}, captees=captees),
    )

    # captees[0] : la requête CIBLÉE. Une requête de contrôle sans `q` la suit
    # quand la ciblée ne trouve rien — ce n'est pas elle qu'on inspecte ici.
    params = captees[0].url.params
    assert params["forms"] == "8-K"
    assert params["entityName"] == "TSLA"
    assert params["startdt"] == "2026-01-01"  # 5 jours ouvrés avant le jeudi 8
    assert params["enddt"] == "2026-01-15"  # 5 jours ouvrés après
    assert params["q"] != titre, "le titre de presse entier ne doit pas servir de requête"
    assert set(params["q"].split()) <= set(titre.lower().split()), "termes issus du titre"
    assert len(params["q"].split()) <= 2  # EDGAR conjugue : au-delà, on rate des dépôts réels


def test_article_sans_claim_verifiable_est_non_applicable():
    """US-04 : la non-confirmation ne pénalise que « pour une claim présentée comme
    un fait précis et vérifiable ». Cette condition n'était pas implémentée : un
    commentaire d'humeur citant une entreprise récoltait 85/100 sur le signal au
    poids le plus lourd (cf. audit, finding H1)."""
    captees = _RequetesCaptees()
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])

    resultat = evaluer_source_primaire(
        "Tesla, mon avis perso",
        "je trouve que cette boite est vraiment cool",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice({"hits": {"hits": []}}, captees=captees),
    )

    assert resultat["valeur"] is None
    assert "aucune claim factuelle" in resultat["raison"]
    assert not captees, "aucun appel réseau ne doit partir pour un article sans claim"


def test_titre_sans_aucun_terme_utilisable_est_non_applicable():
    """Sans le moindre terme distinctif, la requête ciblée n'a aucun sens : on
    s'abstient plutôt que d'interroger SEC EDGAR à vide."""
    captees = _RequetesCaptees()
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Il a dit que",  # que des mots-outils : aucun terme retenu
        "Ils ont annoncé le rappel de 12000 véhicules.",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(_hits(), captees=captees),
    )
    assert resultat["valeur"] is None
    assert "peu spécifique" in resultat["raison"]
    assert not captees, "aucun appel réseau sans terme de recherche exploitable"


@pytest.mark.parametrize(
    "entite, attendu",
    [
        ("Tesla Inc.", "TSLA"),
        ("Ford Motor Company", "F"),
        ("General Motors", "GM"),
        ("Meta Platforms Inc", "META"),
        ("Goldman Sachs Group", "GS"),
        ("AMC Entertainment", "AMC"),
        # Les cinq faux positifs prouvés par l'audit (finding H6) : l'ancien
        # matching par sous-chaîne promouvait chacun de ces noms en ticker.
        ("Oxford Analytica", None),
        ("Fordham University", None),
        ("Intelsat", None),
        ("Amcor plc", None),
        ("Metaverse Studios", None),
        ("AMC Networks", None),  # société réelle mais distincte (AMCX, pas AMC)
    ],
)
def test_correspondance_ticker_sur_jetons_entiers(entite, attendu):
    assert _ticker_de_lentite(entite) == attendu


def test_echec_sec_ne_recopie_pas_le_message_d_exception():
    """`raison` est persistée en base puis rendue dans le frontend : elle ne doit
    porter que le TYPE de l'exception (cf. audit, finding H2)."""
    nlp = _NlpFactice([_EntiteFactice("Tesla", "ORG")])
    resultat = evaluer_source_primaire(
        "Tesla annonce un rappel massif",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=nlp,
        client=_client_sec_factice(leve=httpx.ConnectError("secret-dans-le-message")),
    )
    assert "secret-dans-le-message" not in resultat["raison"]
    assert "ConnectError" in resultat["raison"]


def test_echec_ner_ne_recopie_pas_non_plus_le_message_d_exception():
    """Même exigence que le test précédent, sur l'AUTRE chemin d'échec du module.

    Le correctif du finding H2 avait traité trois sites sur quatre : celui-ci
    interpolait encore `{exc}` brut dans `raison`, donc en base puis à l'écran. Une
    exception spaCy cite le chemin d'installation du modèle, c'est-à-dire
    l'arborescence du serveur (cf. audit phase 10)."""

    class _NlpQuiEchoue:
        def __call__(self, texte):
            raise OSError("[E050] Can't find model at /home/deploy/.venv/lib/en_core_web_sm")

    resultat = evaluer_source_primaire(
        "Tesla annonce un rappel massif",
        "Contenu",
        datetime(2026, 1, 5, tzinfo=timezone.utc),
        nlp=_NlpQuiEchoue(),
    )
    assert resultat["valeur"] is None
    assert "/home/deploy" not in resultat["raison"]
    assert "en_core_web_sm" not in resultat["raison"]
    assert "OSError" in resultat["raison"]


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
