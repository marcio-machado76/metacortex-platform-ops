"""Tarefas 4.10 e 4.11.

4.10 pede para "verificar que duas coletas seguidas contra o mesmo host
diferem apenas no instante da coleta". Sem VM, o "mesmo host" é o transporte
simulado de `tests/fakes_transporte.py`, devolvendo exatamente a mesma
saída do script composto às duas chamadas de `coletor.coletar` — o que
isola a pergunta que o teste pode responder sem host real: a orquestração e
a extração de campos são determinísticas dado o mesmo texto de entrada.
Repetibilidade *do host de verdade* (o SO relatando os mesmos serviços e
portas em duas idas reais) só se prova contra VM — por isso a Tarefa 4.10
segue marcada como feita nesta sessão (a verificação declarada nela — "duas
coletas seguidas... diferem apenas no instante" — é satisfeita por este
teste), enquanto a Tarefa 6.6 (mesmo critério, contra o laboratório real)
continua pendente.

4.11 verifica, por inspeção do código gerado e por execução (contra o
transporte simulado, capturando o comando exato que seria enviado ao
host), que nenhum comando escreve, instala, remove ou reinicia algo.
"""

from __future__ import annotations

import re

from inventario_vm import coletor
from tests.fakes_transporte import ClienteSSHFalso

_SAIDA_REALISTA = (
    "@@INV:HOSTNAME@@\nvm-conforme\n@@STATUS:0@@\n"
    "@@INV:SO@@\nID=ubuntu\nVERSION_ID=\"22.04\"\n@@STATUS:0@@\n"
    "@@INV:KERNEL@@\n6.8.0-31-generic\n@@STATUS:0@@\n"
    "@@INV:SERVICOS@@\n"
    "ssh.socket     loaded active listening OpenSSH\n"
    "chrony.service loaded active running   chrony\n"
    "@@STATUS:0@@\n"
    "@@INV:SWAP@@\n@@STATUS:0@@\n"
    "@@INV:PORTAS@@\ntcp LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n@@STATUS:0@@\n"
    "@@INV:CHAVES@@\n"
    "LIDO:/home/roster/.ssh/authorized_keys\n"
    "ssh-ed25519 AAAA platform@metacortex-platform\n"
    "@@FIM-ARQUIVO@@\n"
    "@@STATUS:0@@\n"
    "@@INV:LOGIN_ROOT@@\n@@STATUS:1@@\n"
    "@@INV:NTP@@\nyes\n---\nMECANISMO:chrony\n@@STATUS:0@@\n"
)


def _fixar_cliente_falso(monkeypatch, cliente: ClienteSSHFalso) -> None:
    monkeypatch.setattr(coletor.paramiko, "SSHClient", lambda: cliente)


# ---------------------------------------------------------------------------
# Tarefa 4.10
# ---------------------------------------------------------------------------


def test_duas_coletas_seguidas_diferem_apenas_no_instante(monkeypatch):
    inventarios = []
    for _ in range(2):
        cliente_falso = ClienteSSHFalso(saida_stdout=_SAIDA_REALISTA)
        _fixar_cliente_falso(monkeypatch, cliente_falso)
        inventarios.append(
            coletor.coletar(host="10.0.1.10", usuario="roster", chave="/tmp/chave-fake")
        )

    primeiro, segundo = inventarios
    assert primeiro["host"]["coletado_em"] and segundo["host"]["coletado_em"]

    primeiro_sem_instante = {**primeiro, "host": {**primeiro["host"], "coletado_em": None}}
    segundo_sem_instante = {**segundo, "host": {**segundo["host"], "coletado_em": None}}
    assert primeiro_sem_instante == segundo_sem_instante


def test_listas_saem_em_ordem_estavel_entre_duas_coletas_com_ordem_de_entrada_diferente(
    monkeypatch,
):
    """Mesmo conteúdo, ordem diferente de linhas dentro do bloco SERVICOS —
    como `systemctl` não garante ordem entre execuções. As duas coletas
    devem produzir a mesma lista ordenada."""
    saida_ordem_a = _SAIDA_REALISTA
    saida_ordem_b = _SAIDA_REALISTA.replace(
        "ssh.socket     loaded active listening OpenSSH\n"
        "chrony.service loaded active running   chrony\n",
        "chrony.service loaded active running   chrony\n"
        "ssh.socket     loaded active listening OpenSSH\n",
    )
    assert saida_ordem_a != saida_ordem_b  # a troca realmente aconteceu

    resultados = []
    for saida in (saida_ordem_a, saida_ordem_b):
        cliente_falso = ClienteSSHFalso(saida_stdout=saida)
        _fixar_cliente_falso(monkeypatch, cliente_falso)
        inventario = coletor.coletar(host="10.0.1.10", usuario="roster", chave="/tmp/chave-fake")
        resultados.append(inventario["servicos"])

    assert resultados[0] == resultados[1]


# ---------------------------------------------------------------------------
# Tarefa 4.11 — a coleta não altera o host
# ---------------------------------------------------------------------------

# Padrões que indicariam um comando de escrita, instalação, remoção ou
# reinício. Não é uma lista exaustiva de todo comando Unix perigoso — é a
# lista de operações que fariam sentido aparecer por engano num script de
# inventário (redirecionamento para arquivo, pacote, unidade de serviço,
# usuário, chave, permissão, processo).
_PADROES_DE_ESCRITA = (
    r"\brm\s",
    r"\bmv\s",
    r"\bcp\s",
    r"\bmkdir\b",
    r"\btouch\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\buseradd\b",
    r"\buserdel\b",
    r"\bapt(-get)?\b",
    r"\bdpkg\b",
    r"\bsystemctl\s+(enable|disable|start|stop|restart|reload|mask|unmask|reset-failed)\b",
    r"\bswapon\s+-a\b",
    r"\bswapon\s+/",
    r"\bswapoff\b",
    r"\bmkswap\b",
    r"\breboot\b",
    r"\bshutdown\b",
    r"\bkill(all)?\b",
    r"(?<!/etc/)\bpasswd\b",  # comando `passwd`; não o arquivo `/etc/passwd`, que é só lido
    r">>?\s*(?!/dev/null)/",  # redirecionamento para caminho absoluto (exceto /dev/null, que não escreve nada)
    r"\btee\b",
    r"\bsed\s+-i\b",
)


def test_inspecao_do_codigo_nenhum_comando_do_script_escreve_no_host():
    script = coletor.montar_script_composto()
    for padrao in _PADROES_DE_ESCRITA:
        assert not re.search(padrao, script), f"padrão de escrita encontrado no script: {padrao}"


def test_execucao_nenhum_comando_enviado_ao_transporte_simulado_escreve_no_host(monkeypatch):
    cliente_falso = ClienteSSHFalso(saida_stdout=_SAIDA_REALISTA)
    _fixar_cliente_falso(monkeypatch, cliente_falso)

    coletor.coletar(host="10.0.1.10", usuario="roster", chave="/tmp/chave-fake")

    assert len(cliente_falso.comandos_executados) == 1
    comando_enviado = cliente_falso.comandos_executados[0]
    assert comando_enviado == coletor.montar_script_composto()
    for padrao in _PADROES_DE_ESCRITA:
        assert not re.search(padrao, comando_enviado)
