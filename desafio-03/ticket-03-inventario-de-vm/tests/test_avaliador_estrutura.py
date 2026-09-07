"""Tarefa 2.1 — estrutura do inventário e da entrada de conformidade.

Verifica que ambas serializam para JSON com campo desconhecido saindo como
`null` (nunca ausente, nunca omitido).
"""

import json

from fixtures import inventario_conforme


def test_inventario_serializa_com_campo_desconhecido_como_nulo():
    inventario = inventario_conforme()
    inventario["so"]["distribuicao"] = None
    inventario["ssh"]["login_de_root"] = None

    bruto = json.dumps(inventario)
    reconstituido = json.loads(bruto)

    assert reconstituido["so"]["distribuicao"] is None
    assert "distribuicao" in reconstituido["so"]  # presente, não ausente
    assert reconstituido["ssh"]["login_de_root"] is None
    assert "login_de_root" in reconstituido["ssh"]


def test_entrada_de_conformidade_serializa_com_campo_desconhecido_como_nulo():
    entrada_desvio = {
        "regra": "swap.habilitado",
        "esperado": False,
        "encontrado": {"habilitado": True, "tamanho": "2G"},
        "veredito": "desvio",
        "severidade": "critico",
        "motivo": None,
    }
    entrada_nao_verificado = {
        "regra": "ssh.login_de_root",
        "esperado": False,
        "encontrado": None,
        "veredito": "nao_verificado",
        "severidade": None,
        "motivo": "sem privilégio",
    }

    for entrada in (entrada_desvio, entrada_nao_verificado):
        reconstituida = json.loads(json.dumps(entrada))
        assert set(reconstituida.keys()) == {
            "regra",
            "esperado",
            "encontrado",
            "veredito",
            "severidade",
            "motivo",
        }

    reconstituida_desvio = json.loads(json.dumps(entrada_desvio))
    assert reconstituida_desvio["motivo"] is None

    reconstituida_nv = json.loads(json.dumps(entrada_nao_verificado))
    assert reconstituida_nv["severidade"] is None
    assert reconstituida_nv["encontrado"] is None
