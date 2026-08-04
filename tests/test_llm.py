import pytest

from fakenews.llm import appeler_structure
from tests._llm_factice import ClientFactice

SCHEMA = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}


def test_appeler_structure_retourne_l_input_du_tool_use():
    client = ClientFactice(reponse_input={"x": 42})
    resultat = appeler_structure(client, "system", "prompt", SCHEMA)
    assert resultat == {"x": 42}


def test_appeler_structure_force_le_tool_choice():
    client = ClientFactice(reponse_input={"x": 1})
    appeler_structure(client, "system", "prompt", SCHEMA)
    assert client.dernier_appel["tool_choice"] == {"type": "tool", "name": "repondre"}
    assert client.dernier_appel["tools"][0]["input_schema"] == SCHEMA
    assert client.dernier_appel["system"] == "system"


def test_appeler_structure_leve_si_aucun_tool_use():
    client = ClientFactice(reponse_input=None)  # aucun bloc tool_use
    with pytest.raises(ValueError):
        appeler_structure(client, "system", "prompt", SCHEMA)
