import pytest

from fakenews import budget_llm
from fakenews.llm import appeler_structure
from tests._llm_factice import ClientFactice

# Capturés à l'import : la fixture autouse de conftest neutralise ces attributs.
VERIFIER = budget_llm.verifier_budget
ENREGISTRER = budget_llm.enregistrer_usage


def test_cout_haiku_estime_au_tarif_par_million():
    assert budget_llm.estimer_cout_eur("claude-haiku-4-5-20251001", 1_000_000, 1_000_000) == pytest.approx(6.0)


def test_modele_inconnu_facture_au_tarif_le_plus_haut():
    assert budget_llm.estimer_cout_eur("inconnu", 1_000_000, 0) == pytest.approx(15.0)


def test_plafond_par_defaut_2_euros(monkeypatch):
    monkeypatch.delenv("LLM_BUDGET_MENSUEL_EUR", raising=False)
    assert budget_llm.budget_mensuel_eur() == 2.0


@pytest.mark.parametrize("brut,attendu", [("1.5", 1.5), ("abc", 2.0), ("-3", 2.0)])
def test_plafond_surchargeable_et_robuste(monkeypatch, brut, attendu):
    monkeypatch.setenv("LLM_BUDGET_MENSUEL_EUR", brut)
    assert budget_llm.budget_mensuel_eur() == attendu


def test_verifier_refuse_au_plafond(monkeypatch):
    monkeypatch.setattr(budget_llm, "depense_du_mois_eur", lambda: 2.0)
    with pytest.raises(budget_llm.BudgetLLMEpuise):
        VERIFIER()


def test_verifier_autorise_sous_le_plafond(monkeypatch):
    monkeypatch.setattr(budget_llm, "depense_du_mois_eur", lambda: 1.99)
    VERIFIER()


def test_verifier_echoue_ferme_si_base_illisible(monkeypatch):
    def casse():
        raise RuntimeError("table absente")

    monkeypatch.setattr(budget_llm, "depense_du_mois_eur", casse)
    with pytest.raises(budget_llm.BudgetLLMEpuise):
        VERIFIER()


def test_enregistrer_ne_leve_pas_si_ecriture_impossible(monkeypatch):
    def casse():
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(budget_llm, "SessionLocal", casse)
    ENREGISTRER("claude-haiku-4-5-20251001", 10, 10)


def test_appeler_structure_n_appelle_pas_le_modele_hors_budget(monkeypatch):
    def refuse():
        raise budget_llm.BudgetLLMEpuise("plein")

    monkeypatch.setattr(budget_llm, "verifier_budget", refuse)
    client = ClientFactice(reponse_input={"x": 1})
    with pytest.raises(budget_llm.BudgetLLMEpuise):
        appeler_structure(client, "s", "p", {})
    assert client.dernier_appel is None


def test_appeler_structure_consigne_l_usage(monkeypatch):
    class Usage:
        input_tokens = 100
        output_tokens = 20

    class Client(ClientFactice):
        @property
        def messages(self):
            parent = super().messages

            class M:
                def create(_, **kw):
                    r = parent.create(**kw)
                    r.usage = Usage()
                    return r

            return M()

    vus = []
    monkeypatch.setattr(budget_llm, "enregistrer_usage", lambda *a: vus.append(a))
    appeler_structure(Client(reponse_input={"x": 1}), "s", "p", {}, model="m")
    assert vus == [("m", 100, 20)]
