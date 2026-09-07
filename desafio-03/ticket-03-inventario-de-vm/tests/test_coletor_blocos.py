"""Tarefa 4.4: o analisador de blocos do script composto.

Bloco ausente, vazio e em formato não reconhecido precisam levar o campo
correspondente a `None`, com motivos distintos entre si. Nenhum destes
testes precisa de host: a entrada é a saída (textual) que o script composto
produziria — o mesmo formato que `coletor.montar_script_composto` gera, só
que aqui escrito à mão para forçar cada um dos três desfechos.
"""

from __future__ import annotations

from inventario_vm import coletor


def _saida_com(substituicoes: dict) -> str:
    """Monta uma saída completa de script composto, com blocos "OK" por
    padrão para todo nome em `coletor.NOMES_DE_BLOCO`, exceto os
    sobrescritos em `substituicoes` (nome -> texto bruto do bloco, incluindo
    o marcador de abertura, ou omitido para simular bloco ausente)."""
    partes = []
    for nome in coletor.NOMES_DE_BLOCO:
        if nome in substituicoes and substituicoes[nome] is None:
            continue  # bloco ausente: nem o marcador de abertura aparece
        if nome in substituicoes:
            partes.append(substituicoes[nome])
        else:
            partes.append(f"@@INV:{nome}@@\nconteudo-padrao\n@@STATUS:0@@\n")
    return "".join(partes)


def test_bloco_ausente_gera_motivo_proprio():
    saida = _saida_com({"SWAP": None})
    blocos = coletor.analisar_blocos(saida)
    assert blocos["SWAP"].texto is None
    assert blocos["SWAP"].motivo == "bloco ausente na saída do script"
    assert not blocos["SWAP"].ok


def test_bloco_vazio_gera_motivo_proprio():
    saida = _saida_com({"SWAP": "@@INV:SWAP@@\n"})
    blocos = coletor.analisar_blocos(saida)
    assert blocos["SWAP"].texto is None
    assert "vazio" in blocos["SWAP"].motivo
    assert not blocos["SWAP"].ok


def test_bloco_formato_nao_reconhecido_gera_motivo_proprio():
    saida = _saida_com({"SWAP": "@@INV:SWAP@@\nisso nao e o protocolo esperado\n"})
    blocos = coletor.analisar_blocos(saida)
    assert blocos["SWAP"].motivo is not None
    assert "formato não reconhecido" in blocos["SWAP"].motivo
    assert not blocos["SWAP"].ok


def test_os_tres_motivos_sao_distintos_entre_si():
    saida = _saida_com(
        {
            "SWAP": None,
            "PORTAS": "@@INV:PORTAS@@\n",
            "KERNEL": "@@INV:KERNEL@@\nlixo sem marcador de status\n",
        }
    )
    blocos = coletor.analisar_blocos(saida)
    motivos = {blocos["SWAP"].motivo, blocos["PORTAS"].motivo, blocos["KERNEL"].motivo}
    assert len(motivos) == 3


def test_bloco_bem_formado_com_saida_vazia_e_codigo_zero_nao_e_falha():
    """Comando rodou com sucesso e não imprimiu nada (ex.: sem swap) é
    diferente de bloco vazio/ausente: `ok` é verdadeiro e `codigo == 0`."""
    saida = _saida_com({"SWAP": "@@INV:SWAP@@\n@@STATUS:0@@\n"})
    blocos = coletor.analisar_blocos(saida)
    assert blocos["SWAP"].ok
    assert blocos["SWAP"].codigo == 0
    assert blocos["SWAP"].texto == ""


def test_bloco_com_codigo_de_saida_diferente_de_zero_e_distinguivel_de_vazio_por_sucesso():
    """Comando que não existe no host (recurso ausente) sai com código
    diferente de zero — bem-formado (`ok`), mas não bem-sucedido."""
    saida = _saida_com({"SWAP": "@@INV:SWAP@@\n@@STATUS:127@@\n"})
    blocos = coletor.analisar_blocos(saida)
    assert blocos["SWAP"].ok
    assert blocos["SWAP"].codigo == 127


def test_campo_do_inventario_vira_null_nos_tres_casos():
    for substituicao in (
        {"SWAP": None},
        {"SWAP": "@@INV:SWAP@@\n"},
        {"SWAP": "@@INV:SWAP@@\nlixo\n"},
    ):
        saida = _saida_com(substituicao)
        blocos = coletor.analisar_blocos(saida)
        inventario = coletor.montar_inventario_de_blocos(
            blocos, host="10.0.0.1", identidade_verificada=True
        )
        assert inventario["swap"]["habilitado"] is None
        assert inventario["swap"]["tamanho"] is None
