"""Tarefas 4.1 e 4.2: verificação de identidade do host e tradução das
falhas de transporte em `FalhaDeAlcance` com mensagem legível.

Sem VM de laboratório disponível, estes testes trocam `paramiko.SSHClient`
por `tests.fakes_transporte.ClienteSSHFalso` (ver o docstring daquele
módulo). Isso não substitui a validação de rede real do Grupo 6 — apenas
prova que a camada de tradução de exceções e a política de identidade de
host estão corretas, o que independe de host algum.
"""

from __future__ import annotations

import socket

import paramiko
import pytest

from inventario_vm import coletor
from tests.fakes_transporte import ClienteSSHFalso


def _fixar_cliente_falso(monkeypatch, cliente: ClienteSSHFalso) -> None:
    monkeypatch.setattr(coletor.paramiko, "SSHClient", lambda: cliente)


# ---------------------------------------------------------------------------
# Tarefa 4.1 — política de identidade de host
# ---------------------------------------------------------------------------


def test_politica_padrao_e_rejeitar_host_desconhecido():
    cliente = coletor._preparar_cliente(aceitar_host_desconhecido=False)
    assert isinstance(cliente._policy, paramiko.RejectPolicy)


def test_com_aceitar_host_desconhecido_politica_vira_autoadd():
    cliente = coletor._preparar_cliente(aceitar_host_desconhecido=True)
    assert isinstance(cliente._policy, paramiko.AutoAddPolicy)


def test_host_desconhecido_sem_autorizacao_e_recusado_antes_de_qualquer_comando(monkeypatch):
    """Requirement 'Conexão autenticada com identidade do host verificada',
    cenário 'Host desconhecido sem autorização explícita'."""
    cliente_falso = ClienteSSHFalso(
        excecao_ao_conectar=paramiko.SSHException(
            "Server '203.0.113.10' not found in known_hosts"
        )
    )
    _fixar_cliente_falso(monkeypatch, cliente_falso)

    with pytest.raises(coletor.FalhaDeAlcance) as excinfo:
        coletor.coletar(host="203.0.113.10", usuario="roster", chave="/tmp/chave-fake")

    mensagem = str(excinfo.value)
    assert "identidade" in mensagem
    assert "não pôde ser verificada" in mensagem
    # Nenhum comando foi executado no host: a falha ocorreu dentro de
    # connect(), antes de exec_command ser chamado.
    assert cliente_falso.comandos_executados == []


def test_host_desconhecido_com_autorizacao_prossegue_e_marca_identidade_nao_verificada(
    monkeypatch,
):
    """Requirement 'Conexão autenticada com identidade do host verificada',
    cenário 'Host desconhecido com autorização explícita'."""
    saida_minima = "".join(
        f"@@INV:{nome}@@\n@@STATUS:0@@\n" for nome in coletor.NOMES_DE_BLOCO
    )
    cliente_falso = ClienteSSHFalso(saida_stdout=saida_minima)
    _fixar_cliente_falso(monkeypatch, cliente_falso)

    inventario = coletor.coletar(
        host="203.0.113.10",
        usuario="roster",
        chave="/tmp/chave-fake",
        aceitar_host_desconhecido=True,
    )

    assert inventario["host"]["identidade_verificada"] is False
    assert isinstance(cliente_falso.politica_definida, paramiko.AutoAddPolicy)


# ---------------------------------------------------------------------------
# Tarefa 4.2 — falhas de transporte com mensagem distinta e sem rastro de pilha
# ---------------------------------------------------------------------------


def _coletar_com_excecao(monkeypatch, excecao):
    cliente_falso = ClienteSSHFalso(excecao_ao_conectar=excecao)
    _fixar_cliente_falso(monkeypatch, cliente_falso)
    with pytest.raises(coletor.FalhaDeAlcance) as excinfo:
        coletor.coletar(host="203.0.113.10", usuario="roster", chave="/tmp/chave-fake")
    return str(excinfo.value)


def test_endereco_sem_servico_produz_mensagem_propria(monkeypatch):
    erro_sem_servico = paramiko.ssh_exception.NoValidConnectionsError(
        {("203.0.113.10", 22): OSError("Connection refused")}
    )
    mensagem = _coletar_com_excecao(monkeypatch, erro_sem_servico)
    assert "não respondeu" in mensagem or "nenhum serviço SSH" in mensagem
    assert "Traceback" not in mensagem


def test_credencial_recusada_produz_mensagem_propria(monkeypatch):
    mensagem = _coletar_com_excecao(
        monkeypatch, paramiko.AuthenticationException("Authentication failed.")
    )
    assert "autenticação falhou" in mensagem
    assert "Traceback" not in mensagem


def test_tempo_esgotado_produz_mensagem_propria(monkeypatch):
    mensagem = _coletar_com_excecao(monkeypatch, socket.timeout("timed out"))
    assert "tempo esgotado" in mensagem
    assert "Traceback" not in mensagem


def test_as_tres_mensagens_sao_distintas_entre_si(monkeypatch):
    m1 = _coletar_com_excecao(
        monkeypatch,
        paramiko.ssh_exception.NoValidConnectionsError(
            {("203.0.113.10", 22): OSError("Connection refused")}
        ),
    )
    m2 = _coletar_com_excecao(
        monkeypatch, paramiko.AuthenticationException("Authentication failed.")
    )
    m3 = _coletar_com_excecao(monkeypatch, socket.timeout("timed out"))
    assert len({m1, m2, m3}) == 3


def test_mensagem_de_falha_de_autenticacao_nao_contem_caminho_nem_conteudo_de_chave(
    monkeypatch, tmp_path
):
    """Requirement 'A chave privada não vaza', cenário 'Falha de autenticação'."""
    caminho_chave = tmp_path / "chave-privada-secreta"
    caminho_chave.write_text("CONTEUDO-SECRETO-DA-CHAVE-PRIVADA\n")

    cliente_falso = ClienteSSHFalso(
        excecao_ao_conectar=paramiko.AuthenticationException("Authentication failed.")
    )
    _fixar_cliente_falso(monkeypatch, cliente_falso)

    with pytest.raises(coletor.FalhaDeAlcance) as excinfo:
        coletor.coletar(host="203.0.113.10", usuario="roster", chave=str(caminho_chave))

    mensagem = str(excinfo.value)
    assert "CONTEUDO-SECRETO-DA-CHAVE-PRIVADA" not in mensagem
