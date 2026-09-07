"""Tarefas 4.5 a 4.9: extração dos campos do inventário a partir dos blocos
do script composto.

Sem VM disponível, a verificação declarada em cada uma destas tarefas que
não exige explicitamente "contra uma/as VM(s)" é feita aqui com blocos
sintéticos no formato exato que `coletor.montar_script_composto` produz
(marcador de abertura, conteúdo, marcador de status) — o mesmo transporte
simulado do resto do Grupo 4. As tarefas 4.3 e 4.5, que pedem
explicitamente verificação contra VM, não são cobertas por este arquivo —
ver `docs/03-divergencias-da-implementacao.md`.
"""

from __future__ import annotations

from inventario_vm import coletor


def _blocos(**conteudos: str) -> dict:
    """Monta um dict completo de `ResultadoBloco`, com todo bloco não citado
    saindo `ok` e com texto vazio (código 0)."""
    saida = ""
    for nome in coletor.NOMES_DE_BLOCO:
        if nome in conteudos:
            saida += f"@@INV:{nome}@@\n{conteudos[nome]}\n@@STATUS:0@@\n"
        else:
            saida += f"@@INV:{nome}@@\n@@STATUS:0@@\n"
    return coletor.analisar_blocos(saida)


# ---------------------------------------------------------------------------
# Tarefa 4.6 — unidades preservando nome completo e tipo
# ---------------------------------------------------------------------------


def test_socket_e_servico_sao_distinguiveis_na_saida():
    conteudo_servicos = (
        "ssh.socket        loaded active   listening OpenSSH Server socket\n"
        "ssh.service       loaded inactive dead      OpenSSH server daemon\n"
        "chrony.service    loaded active   running   chrony daemon\n"
    )
    blocos = _blocos(SERVICOS=conteudo_servicos)
    servicos = coletor._extrair_servicos(blocos["SERVICOS"])

    por_nome = {s["nome"]: s for s in servicos}
    assert por_nome["ssh.socket"]["tipo"] == "socket"
    assert por_nome["ssh.socket"]["estado"] == "active"
    assert por_nome["ssh.service"]["tipo"] == "service"
    assert por_nome["ssh.service"]["estado"] == "inactive"
    # a ordenação é estável (Tarefa 4.10): por nome de unidade
    assert [s["nome"] for s in servicos] == sorted(por_nome.keys())


def test_servicos_none_quando_gerenciador_indisponivel():
    saida = "".join(
        f"@@INV:{nome}@@\n@@STATUS:0@@\n" for nome in coletor.NOMES_DE_BLOCO if nome != "SERVICOS"
    )
    saida += "@@INV:SERVICOS@@\n@@STATUS:127@@\n"  # systemctl: comando não encontrado
    blocos = coletor.analisar_blocos(saida)
    assert coletor._extrair_servicos(blocos["SERVICOS"]) is None


# ---------------------------------------------------------------------------
# Tarefa 4.7 — swap e portas
# ---------------------------------------------------------------------------


def test_swap_habilitado_traz_tamanho():
    blocos = _blocos(SWAP="/swapfile                              2147483648")
    habilitado, tamanho = coletor._extrair_swap(blocos["SWAP"])
    assert habilitado is True
    assert tamanho == "2G"


def test_swap_desabilitado_sem_conteudo_e_codigo_zero():
    blocos = _blocos(SWAP="")
    habilitado, tamanho = coletor._extrair_swap(blocos["SWAP"])
    assert habilitado is False
    assert tamanho is None


def test_porta_em_loopback_aparece_no_inventario():
    conteudo_portas = (
        "tcp   LISTEN 0      128        127.0.0.1:8125       0.0.0.0:*\n"
        "tcp   LISTEN 0      128        0.0.0.0:22            0.0.0.0:*     users:((\"sshd\",pid=100,fd=3))\n"
    )
    blocos = _blocos(PORTAS=conteudo_portas)
    portas = coletor._extrair_portas(blocos["PORTAS"])

    loopback = [p for p in portas if p["bind"] == "127.0.0.1"]
    assert len(loopback) == 1
    assert loopback[0]["porta"] == 8125
    assert loopback[0]["protocolo"] == "tcp"

    publica = [p for p in portas if p["bind"] == "0.0.0.0" and p["porta"] == 22][0]
    assert publica["processo"] == "sshd"


def test_processo_e_none_quando_ss_nao_reporta():
    conteudo_portas = "udp   UNCONN 0      0        127.0.0.1:323        0.0.0.0:*\n"
    blocos = _blocos(PORTAS=conteudo_portas)
    portas = coletor._extrair_portas(blocos["PORTAS"])
    assert portas[0]["processo"] is None


def test_endereco_com_identificador_de_zona_e_normalizado():
    """Achado do smoke test local (Bash, sem VM): `ss` anota endereços de
    loopback com um sufixo `%interface` (ex.: stub resolver do
    systemd-resolved). O sufixo não é parte do endereço IP e precisa ser
    removido antes de `avaliador.classificar_endereco_de_escuta` (que usa
    `ipaddress.ip_address`) receber o valor."""
    conteudo_portas = "tcp   LISTEN 0 128 127.0.0.53%lo:53   0.0.0.0:*\n"
    blocos = _blocos(PORTAS=conteudo_portas)
    portas = coletor._extrair_portas(blocos["PORTAS"])
    assert portas[0]["bind"] == "127.0.0.53"


# ---------------------------------------------------------------------------
# Tarefa 4.8 — chaves autorizadas e arquivos ilegíveis
# ---------------------------------------------------------------------------


def test_arquivo_ilegivel_e_contado_e_nomeado():
    conteudo_chaves = (
        "LIDO:/home/roster/.ssh/authorized_keys\n"
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA platform@metacortex-platform\n"
        "@@FIM-ARQUIVO@@\n"
        "ILEGIVEL:/home/outro/.ssh/authorized_keys\n"
    )
    blocos = _blocos(CHAVES=conteudo_chaves)
    lidas, ilegiveis = coletor._extrair_chaves(blocos["CHAVES"])

    assert lidas == [
        {
            "identificacao": "platform@metacortex-platform",
            "origem": "/home/roster/.ssh/authorized_keys",
        }
    ]
    assert ilegiveis == ["/home/outro/.ssh/authorized_keys"]


def test_duas_chaves_estranha_e_da_plataforma_sao_distinguiveis_por_origem():
    conteudo_chaves = (
        "LIDO:/home/roster/.ssh/authorized_keys\n"
        "ssh-ed25519 AAAA platform@metacortex-platform\n"
        "ssh-ed25519 BBBB dozer@laptop-pessoal\n"
        "@@FIM-ARQUIVO@@\n"
    )
    blocos = _blocos(CHAVES=conteudo_chaves)
    lidas, ilegiveis = coletor._extrair_chaves(blocos["CHAVES"])
    identificacoes = {chave["identificacao"] for chave in lidas}
    assert identificacoes == {"platform@metacortex-platform", "dozer@laptop-pessoal"}
    assert ilegiveis == []


# ---------------------------------------------------------------------------
# Tarefa 4.9 — login de root e sincronização de tempo
# ---------------------------------------------------------------------------


def test_login_de_root_sai_nulo_sem_privilegio():
    """Sem privilégio, `sshd -T` falha: o bloco fica bem-formado mas com
    código de saída diferente de zero e sem conteúdo — exatamente o
    critério de aceite 3 (usuário comum, sem sudo)."""
    saida = "".join(
        f"@@INV:{nome}@@\n@@STATUS:0@@\n"
        for nome in coletor.NOMES_DE_BLOCO
        if nome != "LOGIN_ROOT"
    )
    saida += "@@INV:LOGIN_ROOT@@\n@@STATUS:1@@\n"
    blocos = coletor.analisar_blocos(saida)
    assert coletor._extrair_login_de_root(blocos["LOGIN_ROOT"]) is None


def test_login_de_root_desabilitado_e_reconhecido_com_privilegio():
    blocos = _blocos(LOGIN_ROOT="permitrootlogin no")
    assert coletor._extrair_login_de_root(blocos["LOGIN_ROOT"]) is False


def test_login_de_root_habilitado_e_reconhecido_com_privilegio():
    blocos = _blocos(LOGIN_ROOT="permitrootlogin yes")
    assert coletor._extrair_login_de_root(blocos["LOGIN_ROOT"]) is True


def test_ntp_sincronizado_e_mecanismo():
    blocos = _blocos(NTP="yes\n---\nMECANISMO:chrony")
    sincronizado, mecanismo = coletor._extrair_ntp(blocos["NTP"])
    assert sincronizado is True
    assert mecanismo == "chrony"


def test_ntp_sem_mecanismo_reconhecido_fica_com_mecanismo_none_mas_sincronizado_valido():
    blocos = _blocos(NTP="yes\n---")
    sincronizado, mecanismo = coletor._extrair_ntp(blocos["NTP"])
    assert sincronizado is True
    assert mecanismo is None

