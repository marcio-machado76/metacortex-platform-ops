"""Tarefa 2.13 — avaliar o mesmo inventário repetidamente produz resultado
idêntico, sem qualquer acesso a rede.

O avaliador não importa `socket`, `paramiko` nem faz qualquer chamada de
rede — isso é verificado por inspeção do módulo, não só por execução.
"""

import copy
import socket
import sys

from fixtures import baseline_padrao, inventario_com_desvios, inventario_conforme

from inventario_vm import avaliador


def test_avaliacao_repetida_produz_resultado_identico():
    baseline = baseline_padrao()
    for inventario_fn in (inventario_conforme, inventario_com_desvios):
        inventario = inventario_fn()
        resultados = [avaliador.avaliar(copy.deepcopy(inventario), baseline) for _ in range(5)]
        primeiro = resultados[0]
        for outro in resultados[1:]:
            assert outro == primeiro


def test_modulo_avaliador_nao_importa_paramiko_nem_socket_nem_rede():
    modulo = sys.modules["inventario_vm.avaliador"]
    fonte = open(modulo.__file__, encoding="utf-8").read()
    for termo_proibido in ("paramiko", "socket.", "import socket", "requests", "urllib"):
        assert termo_proibido not in fonte, f"referência de rede encontrada: {termo_proibido!r}"


def test_avaliar_nao_faz_nenhuma_chamada_de_socket(monkeypatch):
    def _socket_proibido(*args, **kwargs):
        raise AssertionError("avaliador.avaliar tentou abrir um socket")

    monkeypatch.setattr(socket, "socket", _socket_proibido)
    baseline = baseline_padrao()
    avaliador.avaliar(inventario_conforme(), baseline)
    avaliador.avaliar(inventario_com_desvios(), baseline)
