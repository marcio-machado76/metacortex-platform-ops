"""Tarefas 2.2 e 2.3 — leitura do baseline e registro de regras."""

import warnings

import pytest

from fixtures import CAMINHO_BASELINE_REAL, baseline_padrao, inventario_conforme
from inventario_vm import avaliador


# --- Tarefa 2.2 -------------------------------------------------------------


def test_carregar_baseline_real_nao_avisa():
    with warnings.catch_warnings(record=True) as capturados:
        warnings.simplefilter("always")
        baseline = avaliador.carregar_baseline(str(CAMINHO_BASELINE_REAL))
    assert baseline["versao"] == 1
    assert len(capturados) == 0


def test_carregar_baseline_versao_futura_avisa_e_prossegue(tmp_path):
    caminho = tmp_path / "baseline_futuro.yaml"
    caminho.write_text(
        """
versao: 99
aplica_a: vms-do-parque
esperado:
  so:
    distribuicao: ubuntu
severidade:
  alto: [so.distribuicao]
""".strip(),
        encoding="utf-8",
    )

    with pytest.warns(UserWarning, match="99"):
        baseline = avaliador.carregar_baseline(str(caminho))

    # Prossegue com a avaliação mesmo com versão desconhecida.
    resultado = avaliador.avaliar(inventario_conforme(), baseline)
    assert len(resultado["conformidade"]) == 1


# --- Tarefa 2.3 -------------------------------------------------------------


def test_regra_sem_funcao_registrada_produz_nao_verificado_com_motivo():
    baseline = {
        "versao": 1,
        "esperado": {"grupo_inventado": {"regra_inventada": "qualquer-coisa"}},
        "severidade": {},
    }
    resultado = avaliador.avaliar(inventario_conforme(), baseline)

    assert len(resultado["conformidade"]) == 1
    entrada = resultado["conformidade"][0]
    assert entrada["regra"] == "grupo_inventado.regra_inventada"
    assert entrada["veredito"] == "nao_verificado"
    assert entrada["motivo"]
    assert "não implementa" in entrada["motivo"]
    # Regra desconhecida não é contada como conforme.
    assert resultado["resumo"]["conforme"] == 0
    assert resultado["resumo"]["nao_verificado"] == 1


def test_todas_as_onze_regras_do_baseline_real_tem_funcao_registrada():
    baseline = baseline_padrao()
    regras = avaliador._regras_do_baseline(baseline)
    assert len(regras) == 11
    for regra, _ in regras:
        assert regra in avaliador.REGISTRO_REGRAS, f"regra sem função registrada: {regra}"
