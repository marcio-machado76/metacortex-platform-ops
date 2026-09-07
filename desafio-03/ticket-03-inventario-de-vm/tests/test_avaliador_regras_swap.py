"""Tarefa 2.7 — swap.habilitado."""

from inventario_vm import avaliador


def test_swap_desligado_conforme_com_esperado_desligado():
    inventario = {"swap": {"habilitado": False, "tamanho": None}}
    resultado = avaliador._regra_swap_habilitado(inventario, False)
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"] == {"habilitado": False, "tamanho": None}


def test_swap_ligado_e_desvio_com_tamanho_no_encontrado():
    inventario = {"swap": {"habilitado": True, "tamanho": "2G"}}
    resultado = avaliador._regra_swap_habilitado(inventario, False)
    assert resultado["veredito"] == "desvio"
    assert resultado["encontrado"] == {"habilitado": True, "tamanho": "2G"}


def test_swap_desconhecido_e_nao_verificado():
    inventario = {"swap": {"habilitado": None, "tamanho": None}}
    resultado = avaliador._regra_swap_habilitado(inventario, False)
    assert resultado["veredito"] == "nao_verificado"
    assert resultado["motivo"]
