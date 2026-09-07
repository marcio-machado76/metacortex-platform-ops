"""Coletor — único módulo que fala com a rede (Grupo 4 de `tasks.md`).

Abre uma conexão SSH somente-leitura e executa um único script composto que
emite blocos delimitados por marcador, um por grupo de dados — ver
`design.md`, decisão "Um script composto com marcadores", e decisão D5 em
`docs/02-decisoes-tecnicas.md`. Devolve um inventário no formato consumido
por `avaliador.avaliar` (ver o docstring de `inventario_vm.avaliador`).

Nenhum comando enviado ao host escreve, instala, remove ou reinicia
qualquer coisa — ver Tarefa 4.11 e o Requirement "A coleta não altera o
host" em `specs/coleta-de-inventario/spec.md`. Cada comando do script
composto (`montar_script_composto`) é de leitura: `hostname`, `cat`,
`uname`, `systemctl list-units`/`is-active`, `swapon --show`, `ss`, `awk`
sobre `/etc/passwd`, `cat` de `authorized_keys`, `sshd -T` (só imprime a
configuração efetiva, não a altera) e `timedatectl show`.

## Nota sobre uma lacuna de contrato herdada do Grupo 2 (não corrigida aqui)

O docstring de `avaliador.py` fixa `portas_em_escuta` e `chaves_ssh.lidas` /
`chaves_ssh.arquivos_ilegiveis` como listas que "nunca são `None`" — ao
contrário de `servicos`, que tem `None` como valor sentinela explícito para
"gerenciador indisponível". Isso significa que, se o comando `ss` ou o
`awk`/`cat` usados para ler `/etc/passwd` não existirem no host (recurso
inexistente, uma das três causas de `nao_verificado` previstas na spec),
este coletor não tem como sinalizar isso: a única opção dentro do contrato
existente é devolver lista vazia, que a avaliação lê como "nenhuma porta
em escuta" / "nenhuma chave lida" — silenciosamente diferente de "não
verificado". Não alterei o contrato do inventário para resolver isso (seria
mudar uma decisão já fixada pela sessão anterior, fora do escopo desta
sessão); o achado está registrado em
`docs/03-divergencias-da-implementacao.md`, seção "Grupos 4 e 5".
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import paramiko


class FalhaDeAlcance(Exception):
    """Host não pôde ser alcançado, autenticado ou ter sua identidade
    verificada — ver Requirement "Falha de alcance é reportada de forma
    legível" em `specs/relatorio-e-saida/spec.md`.

    A mensagem é construída aqui, pronta para leitura humana, e nunca inclui
    o conteúdo da chave privada nem o rastro de pilha da exceção original de
    Paramiko/socket — quem captura esta exceção (a CLI) repassa apenas
    ``str(exc)`` ao usuário, nunca a exceção original.
    """


# ---------------------------------------------------------------------------
# Conexão e verificação de identidade do host (Tarefa 4.1)
# ---------------------------------------------------------------------------


def _preparar_cliente(aceitar_host_desconhecido: bool) -> paramiko.SSHClient:
    """Monta o cliente SSH com a política de identidade de host (decisão D3).

    Por padrão, host cujo identidade não conste no `known_hosts` do usuário
    (mais as chaves de sistema) é recusado — `paramiko.RejectPolicy`, que já
    é o padrão do `SSHClient`, mas é fixada aqui explicitamente porque a
    política é uma decisão de segurança do produto, não um acaso da
    biblioteca. Com `--aceitar-host-desconhecido`, a política muda para
    `AutoAddPolicy`, e o chamador (`coletar`) registra no inventário que a
    identidade não foi verificada.
    """
    cliente = paramiko.SSHClient()
    cliente.load_system_host_keys()
    try:
        cliente.load_host_keys(str(_caminho_known_hosts()))
    except IOError:
        pass
    if aceitar_host_desconhecido:
        cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    else:
        cliente.set_missing_host_key_policy(paramiko.RejectPolicy())
    return cliente


def _caminho_known_hosts():
    from pathlib import Path

    return Path.home() / ".ssh" / "known_hosts"


def _host_e_conhecido(cliente: paramiko.SSHClient, host: str, porta: int) -> bool:
    """Verifica se `host` já tinha identidade registrada antes de conectar.

    Usado só para decidir o valor de `host.identidade_verificada` no
    inventário quando `--aceitar-host-desconhecido` está em uso — ver
    Requirement "Conexão autenticada com identidade do host verificada",
    cenário "Host desconhecido com autorização explícita".
    """
    apelido = host if porta == 22 else f"[{host}]:{porta}"
    chaves = cliente.get_host_keys()
    return bool(chaves.lookup(apelido)) or bool(chaves.lookup(host))


def _conectar(
    host: str,
    usuario: str,
    chave: str,
    porta: int,
    timeout: int,
    aceitar_host_desconhecido: bool,
) -> Tuple[paramiko.SSHClient, bool]:
    """Abre a sessão SSH. Devolve `(cliente, identidade_verificada)`.

    Nenhum comando é executado no host antes desta função retornar com
    sucesso: a verificação de identidade acontece dentro de
    `SSHClient.connect`, antes de qualquer `exec_command` — ver Tarefa 4.1.

    Traduz cada falha de transporte num `FalhaDeAlcance` com mensagem
    legível e distinta por causa (Tarefa 4.2): identidade não verificada,
    credencial recusada, endereço sem serviço e tempo esgotado.
    """
    cliente = _preparar_cliente(aceitar_host_desconhecido)
    identidade_ja_conhecida = _host_e_conhecido(cliente, host, porta)

    try:
        cliente.connect(
            hostname=host,
            port=porta,
            username=usuario,
            key_filename=chave,
            timeout=timeout,
            auth_timeout=timeout,
            banner_timeout=timeout,
            allow_agent=False,
            look_for_keys=False,
        )
    except paramiko.AuthenticationException:
        raise FalhaDeAlcance(
            f"autenticação falhou para {usuario}@{host}:{porta}: a chave "
            "informada foi recusada pelo host"
        ) from None
    except paramiko.BadHostKeyException:
        raise FalhaDeAlcance(
            f"identidade de {host}:{porta} não confere com a base de hosts "
            "conhecidos (a chave apresentada pelo host mudou)"
        ) from None
    except paramiko.SSHException as exc:
        if "not found in known_hosts" in str(exc):
            raise FalhaDeAlcance(
                f"identidade de {host}:{porta} não pôde ser verificada: "
                "host não consta na base de hosts conhecidos (use "
                "--aceitar-host-desconhecido para prosseguir mesmo assim)"
            ) from None
        raise FalhaDeAlcance(
            f"falha ao estabelecer sessão SSH com {host}:{porta} "
            f"({exc.__class__.__name__})"
        ) from None
    except (socket.timeout, TimeoutError):
        raise FalhaDeAlcance(
            f"tempo esgotado ao tentar conectar em {host}:{porta}"
        ) from None
    except paramiko.ssh_exception.NoValidConnectionsError:
        raise FalhaDeAlcance(
            f"{host}:{porta} não respondeu: nenhum serviço SSH alcançável"
        ) from None
    except ConnectionRefusedError:
        raise FalhaDeAlcance(
            f"{host}:{porta} recusou a conexão: nenhum serviço SSH escutando"
        ) from None
    except OSError as exc:
        raise FalhaDeAlcance(
            f"não foi possível alcançar {host}:{porta}: {exc.strerror or exc}"
        ) from None

    identidade_verificada = True
    if aceitar_host_desconhecido and not identidade_ja_conhecida:
        identidade_verificada = False
    return cliente, identidade_verificada


# ---------------------------------------------------------------------------
# Script composto com marcadores (Tarefa 4.3)
# ---------------------------------------------------------------------------

# A ordem importa, e o motivo não é estético — ver `montar_script_composto`.
NOMES_DE_BLOCO = (
    "HOSTNAME",
    "SO",
    "KERNEL",
    "NTP",
    "SERVICOS",
    "SWAP",
    "PORTAS",
    "CHAVES",
    "LOGIN_ROOT",
)


def montar_script_composto() -> str:
    """Monta o script único executado no host numa única sessão (decisão D5).

    Protocolo: cada bloco abre com ``echo '@@INV:<NOME>@@'`` numa linha só, o
    comando roda com stderr silenciado (para não poluir o bloco com texto de
    erro do interpretador) e, por fim, ``echo "@@STATUS:$?@@"`` grava o
    código de saída do comando. O código de saída é o que permite ao
    analisador (Tarefa 4.4) distinguir "o comando rodou e não achou nada"
    (ex.: sem swap habilitado, código 0) de "o comando não existe no host"
    (recurso ausente, código diferente de 0) — os dois produzem bloco sem
    conteúdo, mas com significados opostos.

    Sem ``set -e``: um comando que falha não interrompe o script — os
    demais blocos continuam sendo produzidos (ver design.md, "o script não
    interrompe").

    Só comandos de leitura — ver o docstring do módulo.
    """
    linhas: List[str] = ["#!/bin/sh"]

    def bloco(nome: str, comando: str) -> None:
        linhas.append(f"echo '@@INV:{nome}@@'")
        linhas.append(comando)
        linhas.append('echo "@@STATUS:$?@@"')

    bloco("HOSTNAME", "hostname 2>/dev/null")
    bloco("SO", "cat /etc/os-release 2>/dev/null")
    bloco("KERNEL", "uname -r 2>/dev/null")
    bloco(
        "NTP",
        "timedatectl show -p NTPSynchronized --value 2>/dev/null; "
        "echo '---'; "
        "if systemctl is-active --quiet chrony 2>/dev/null || "
        "systemctl is-active --quiet chronyd 2>/dev/null; then "
        "echo 'MECANISMO:chrony'; "
        "elif systemctl is-active --quiet systemd-timesyncd 2>/dev/null; then "
        "echo 'MECANISMO:systemd-timesyncd'; "
        "fi",
    )
    # NTP vem ANTES de SERVICOS de propósito. `timedatectl` fala com o
    # `systemd-timedated` por D-Bus, e o systemd ativa esse serviço sob demanda:
    # a própria coleta muda o estado que ela observa. Com SERVICOS antes, a
    # primeira execução via a unidade inativa e a segunda a via ativa — duas
    # coletas seguidas divergiam, quebrando o critério de repetibilidade sem que
    # o host tivesse mudado por conta própria. Acionando o D-Bus primeiro, toda
    # execução amostra o mesmo estado. Descoberto na validação contra VM real.
    bloco(
        "SERVICOS",
        "systemctl list-units --all --no-legend --no-pager --plain "
        "-t service,socket,timer 2>/dev/null",
    )
    bloco("SWAP", "swapon --noheadings --bytes --show=NAME,SIZE 2>/dev/null")
    bloco("PORTAS", "ss -H -tulnp 2>/dev/null")
    bloco(
        "CHAVES",
        "awk -F: '{print $6}' /etc/passwd 2>/dev/null | sort -u | "
        "while read -r lar; do "
        'arq="$lar/.ssh/authorized_keys"; '
        'if [ -r "$arq" ]; then '
        'echo "LIDO:$arq"; cat "$arq" 2>/dev/null; echo "@@FIM-ARQUIVO@@"; '
        'elif [ -e "$arq" ]; then echo "ILEGIVEL:$arq"; '
        "fi; done",
    )
    bloco("LOGIN_ROOT", "sshd -T 2>/dev/null | grep -i '^permitrootlogin '")
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Analisador de blocos (Tarefa 4.4)
# ---------------------------------------------------------------------------

_MARCADOR_ABERTURA = re.compile(r"@@INV:([A-Z_]+)@@\s*\n?")
_MARCADOR_STATUS = re.compile(r"@@STATUS:(-?\d+)@@\s*$")


@dataclass
class ResultadoBloco:
    """Resultado da análise de um bloco da saída do script composto.

    `motivo` é `None` quando o bloco está bem-formado (marcador de abertura
    e de status presentes); nesse caso `codigo` traz o código de saída do
    comando e `texto` o que ele produziu (que pode ser string vazia).
    Quando `motivo` não é `None`, `texto` e `codigo` não devem ser usados
    para extrair dado — o campo correspondente do inventário vira `None`.
    """

    texto: Optional[str]
    codigo: Optional[int]
    motivo: Optional[str]

    @property
    def ok(self) -> bool:
        return self.motivo is None


def analisar_blocos(saida: str) -> Dict[str, ResultadoBloco]:
    """Divide a saída do script composto em blocos por marcador.

    Três motivos distintos levam um bloco a não ter conteúdo utilizável —
    ver Tarefa 4.4 e design.md, decisão "Um script composto com marcadores":

    - **ausente**: o marcador de abertura do bloco não aparece em lugar
      nenhum da saída. Acontece quando a conexão cai ou o tempo se esgota
      antes do script chegar a esse bloco.
    - **vazio**: o marcador de abertura aparece, mas não há marcador de
      status em seguida e também não há nenhum outro conteúdo — o script foi
      cortado no meio do bloco (ex.: saída truncada bem no início dele).
    - **formato não reconhecido**: há conteúdo entre a abertura e o próximo
      marcador (ou o fim da saída), mas o marcador de status não aparece
      nele — a saída desse trecho não corresponde ao protocolo esperado
      (ex.: host que não roda o interpretador esperado e ecoa outra coisa).

    Quando o marcador de status aparece, o bloco é considerado bem-formado:
    `codigo` é o código de saída do comando e `texto` é o que ele produziu,
    incluindo string vazia (comando rodou com sucesso e não imprimiu nada —
    distinto de comando ausente, cujo código de saída não é zero).
    """
    aberturas = list(_MARCADOR_ABERTURA.finditer(saida))
    conteudo_por_nome: Dict[str, str] = {}
    for indice, casamento in enumerate(aberturas):
        nome = casamento.group(1)
        inicio = casamento.end()
        fim = aberturas[indice + 1].start() if indice + 1 < len(aberturas) else len(saida)
        # Em saída adversarial ou repetida, o último marcador de um nome
        # repetido prevalece — não deveria acontecer com o script gerado
        # aqui, que só emite cada marcador uma vez.
        conteudo_por_nome[nome] = saida[inicio:fim]

    resultado: Dict[str, ResultadoBloco] = {}
    for nome in NOMES_DE_BLOCO:
        bruto = conteudo_por_nome.get(nome)
        if bruto is None:
            resultado[nome] = ResultadoBloco(None, None, "bloco ausente na saída do script")
            continue
        casamento_status = _MARCADOR_STATUS.search(bruto.rstrip("\n"))
        if casamento_status is None:
            texto_bruto = bruto.strip()
            if not texto_bruto:
                resultado[nome] = ResultadoBloco(
                    None, None, "bloco vazio: nenhum conteúdo antes do próximo marcador"
                )
            else:
                resultado[nome] = ResultadoBloco(
                    texto_bruto,
                    None,
                    "formato não reconhecido: marcador de status ausente no bloco",
                )
            continue
        texto = bruto.rstrip("\n")[: casamento_status.start()].rstrip("\n")
        codigo = int(casamento_status.group(1))
        resultado[nome] = ResultadoBloco(texto, codigo, None)
    return resultado


# ---------------------------------------------------------------------------
# Extração de campos a partir dos blocos (Tarefas 4.5 a 4.9)
# ---------------------------------------------------------------------------


def _texto_ok(bloco: ResultadoBloco) -> Optional[str]:
    """Texto do bloco quando ele rodou com sucesso (`ok` e código 0), senão `None`."""
    if not bloco.ok or bloco.codigo != 0:
        return None
    return bloco.texto or ""


def _extrair_hostname(bloco: ResultadoBloco) -> Optional[str]:
    texto = _texto_ok(bloco)
    if not texto:
        return None
    primeira_linha = texto.strip().splitlines()[0].strip() if texto.strip() else ""
    return primeira_linha or None


def _extrair_so(bloco: ResultadoBloco) -> Tuple[Optional[str], Optional[str]]:
    """Extrai `(distribuicao, versao)` de `/etc/os-release` (Tarefa 4.5)."""
    texto = _texto_ok(bloco)
    if not texto or not texto.strip():
        return None, None
    campos: Dict[str, str] = {}
    for linha in texto.splitlines():
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        campos[chave.strip()] = valor.strip().strip('"')
    distribuicao = campos.get("ID") or campos.get("NAME")
    if not distribuicao:
        return None, None  # conteúdo presente, mas formato não reconhecido
    return distribuicao, campos.get("VERSION_ID")


def _extrair_kernel(bloco: ResultadoBloco) -> Optional[str]:
    texto = _texto_ok(bloco)
    if not texto or not texto.strip():
        return None
    return texto.strip().splitlines()[0].strip() or None


_SUFIXOS_DE_UNIDADE = ("service", "socket", "timer")


def _extrair_servicos(bloco: ResultadoBloco) -> Optional[List[dict]]:
    """Extrai a lista de unidades a partir de `systemctl list-units` (Tarefa 4.6).

    `None` só quando o gerenciador de serviços está indisponível (comando
    falhou) ou a saída não tem nenhuma linha reconhecível — a ausência de
    uma unidade específica não faz o campo virar `None`: ela simplesmente
    não aparece na lista, e é `avaliador.py` quem traduz "unidade esperada
    ausente" em `desvio` (Requirement "Recurso ausente é desvio, não falta
    de verificação").
    """
    if not bloco.ok or bloco.codigo != 0:
        return None
    texto = (bloco.texto or "").strip()
    if not texto:
        return []
    servicos: List[dict] = []
    for linha in texto.splitlines():
        linha = linha.lstrip("●").strip()
        if not linha:
            continue
        campos = linha.split()
        if len(campos) < 3:
            continue
        nome, _carga, estado = campos[0], campos[1], campos[2]
        sufixo = nome.rsplit(".", 1)[-1] if "." in nome else ""
        tipo = sufixo if sufixo in _SUFIXOS_DE_UNIDADE else "service"
        servicos.append({"nome": nome, "tipo": tipo, "estado": estado})
    if not servicos:
        # havia conteúdo, mas nenhuma linha correspondeu ao formato esperado
        return None
    # ordenação estável (Tarefa 4.10): por nome, que é único por unidade
    return sorted(servicos, key=lambda servico: servico["nome"])


def _formatar_bytes(total: int) -> str:
    for unidade, divisor in (("G", 1024**3), ("M", 1024**2), ("K", 1024)):
        if total >= divisor:
            valor = f"{total / divisor:.1f}".rstrip("0").rstrip(".")
            return f"{valor}{unidade}"
    return f"{total}B"


def _extrair_swap(bloco: ResultadoBloco) -> Tuple[Optional[bool], Optional[str]]:
    """Extrai `(habilitado, tamanho)` a partir de `swapon --show` (Tarefa 4.7).

    Saída vazia com código 0 é um valor legítimo — "sem swap habilitado" —
    e não uma falha de coleta; por isso a checagem de sucesso vem antes de
    checar se há conteúdo, ao contrário das demais extrações desta seção.
    """
    if not bloco.ok or bloco.codigo != 0:
        return None, None
    texto = (bloco.texto or "").strip()
    if not texto:
        return False, None
    total_bytes = 0
    linhas_validas = 0
    for linha in texto.splitlines():
        campos = linha.split()
        if len(campos) < 2:
            continue
        try:
            total_bytes += int(campos[-1])
        except ValueError:
            continue
        else:
            linhas_validas += 1
    if linhas_validas == 0:
        return None, None  # formato não reconhecido
    return True, _formatar_bytes(total_bytes)


_PADRAO_PROCESSO = re.compile(r'users:\(\("([^"]+)"')


def _separar_endereco_porta(campo: str) -> Tuple[Optional[str], Optional[int]]:
    """Separa endereço e porta de uma coluna `Local Address:Port` do `ss`.

    Achado durante o smoke test local (não é um dos critérios de aceite,
    que exigem VM): `ss` anota endereços de loopback com um identificador de
    zona, ex.: `127.0.0.53%lo:53` (o stub resolver do systemd-resolved). O
    sufixo `%<interface>` não é parte do endereço IP e faz
    `ipaddress.ip_address` (usado por `avaliador.classificar_endereco_de_escuta`)
    levantar `ValueError` se deixado no `bind`. Removido aqui, antes do
    endereço entrar no inventário.
    """
    if campo.startswith("["):
        endereco, _, resto = campo[1:].partition("]:")
    else:
        endereco, _, resto = campo.rpartition(":")
    if not resto.isdigit():
        return None, None
    endereco = endereco.split("%", 1)[0]
    if endereco in ("*", ""):
        endereco = "0.0.0.0"
    return endereco, int(resto)


def _extrair_portas(bloco: ResultadoBloco) -> Optional[List[dict]]:
    """Extrai a lista de portas em escuta a partir de `ss -H -tulnp` (Tarefa 4.7).

    Porta em loopback aparece igual a qualquer outra — a classificação de
    endereço é responsabilidade do avaliador (`classificar_endereco_de_escuta`),
    não do coletor.
    """
    if not bloco.ok or bloco.codigo != 0:
        return None
    texto = (bloco.texto or "").strip()
    if not texto:
        return []
    portas: List[dict] = []
    for linha in texto.splitlines():
        campos = linha.split(None, 5)
        if len(campos) < 5:
            continue
        protocolo = campos[0].lower()
        if protocolo not in ("tcp", "udp"):
            continue
        bind, porta = _separar_endereco_porta(campos[4])
        if bind is None or porta is None:
            continue
        casamento = _PADRAO_PROCESSO.search(linha)
        processo = casamento.group(1) if casamento else None
        portas.append({"porta": porta, "protocolo": protocolo, "bind": bind, "processo": processo})
    if not portas:
        return None  # havia conteúdo, mas nenhuma linha reconhecida
    # ordenação estável (Tarefa 4.10)
    return sorted(portas, key=lambda p: (p["porta"], p["protocolo"], p["bind"]))


def _extrair_chaves(bloco: ResultadoBloco) -> Tuple[List[dict], List[str]]:
    """Extrai `(lidas, arquivos_ilegiveis)` a partir do bloco CHAVES (Tarefa 4.8).

    O sub-protocolo dentro do bloco: `LIDO:<caminho>` abre a leitura de um
    arquivo (as linhas seguintes, até `@@FIM-ARQUIVO@@`, são o conteúdo de
    `authorized_keys` daquele arquivo); `ILEGIVEL:<caminho>` marca um
    arquivo que existe mas não pôde ser lido pelo usuário da coleta —
    contado **e nomeado**, como a spec exige (`docs/01-comportamento.md`,
    seção "Escopo das chaves").

    `identificacao` é o último campo de cada linha de chave — o comentário,
    que é o que a regra `chaves_ssh.emitidas_por` lê (ver achado sobre o
    baseline em `docs/02-decisoes-tecnicas.md`: confere etiqueta, não
    procedência; este coletor implementa o que está escrito).
    """
    if not bloco.ok or bloco.codigo != 0:
        # Ver nota no docstring do módulo: o contrato existente não tem
        # como distinguir isso de "nenhuma chave no host" além de lista
        # vazia.
        return [], []
    texto = bloco.texto or ""
    lidas: List[dict] = []
    ilegiveis: List[str] = []
    arquivo_atual: Optional[str] = None
    for linha in texto.splitlines():
        linha_tratada = linha.strip()
        if linha_tratada.startswith("LIDO:"):
            arquivo_atual = linha_tratada[len("LIDO:") :]
            continue
        if linha_tratada.startswith("ILEGIVEL:"):
            ilegiveis.append(linha_tratada[len("ILEGIVEL:") :])
            arquivo_atual = None
            continue
        if linha_tratada == "@@FIM-ARQUIVO@@":
            arquivo_atual = None
            continue
        if not linha_tratada or linha_tratada.startswith("#"):
            continue
        if arquivo_atual is None:
            continue
        campos = linha_tratada.split()
        identificacao = campos[-1] if campos else linha_tratada
        lidas.append({"identificacao": identificacao, "origem": arquivo_atual})
    # ordenação estável (Tarefa 4.10)
    lidas.sort(key=lambda chave: (chave["origem"], chave["identificacao"]))
    ilegiveis.sort()
    return lidas, ilegiveis


_PERMITE_ROOT_FALSO = {"no"}
_PERMITE_ROOT_VERDADEIRO = {"yes", "without-password", "prohibit-password", "forced-commands-only"}


def _extrair_login_de_root(bloco: ResultadoBloco) -> Optional[bool]:
    """Extrai a configuração efetiva de `PermitRootLogin` (Tarefa 4.9).

    Sem privilégio, `sshd -T` falha (código de saída diferente de 0) e o
    campo sai `None` — é essa a via pela qual o critério de aceite 3 se
    manifesta (`nao_verificado` em vez de `conforme`).

    `sshd` aceita mais valores que `yes`/`no` para esta diretiva
    (`without-password`, `prohibit-password`, `forced-commands-only`); o
    baseline modela a regra como booleana. Esta implementação decide que
    apenas `no` satisfaz "login de root desabilitado" — qualquer outro
    valor reconhecido significa que login de root continua possível de
    alguma forma, então mapeia para `True`. O baseline e o enunciado não
    cobrem esse detalhe; achado registrado em
    `docs/03-divergencias-da-implementacao.md`.
    """
    texto = _texto_ok(bloco)
    if not texto or not texto.strip():
        return None
    _, _, valor = texto.strip().partition(" ")
    valor = valor.strip().lower()
    if valor in _PERMITE_ROOT_FALSO:
        return False
    if valor in _PERMITE_ROOT_VERDADEIRO:
        return True
    return None  # valor não reconhecido


def _extrair_ntp(bloco: ResultadoBloco) -> Tuple[Optional[bool], Optional[str]]:
    """Extrai `(sincronizado, mecanismo)` (Tarefa 4.9)."""
    texto = _texto_ok(bloco)
    if texto is None:
        return None, None
    linhas = texto.splitlines()
    if not linhas or not linhas[0].strip():
        return None, None
    valor = linhas[0].strip().lower()
    if valor in ("yes", "true"):
        sincronizado = True
    elif valor in ("no", "false"):
        sincronizado = False
    else:
        return None, None  # formato não reconhecido
    mecanismo = None
    for linha in linhas[1:]:
        if linha.startswith("MECANISMO:"):
            mecanismo = linha[len("MECANISMO:") :] or None
            break
    return sincronizado, mecanismo


# ---------------------------------------------------------------------------
# Execução do script e orquestração da coleta (Tarefas 4.3–4.10)
# ---------------------------------------------------------------------------


def _executar_script_composto(cliente: paramiko.SSHClient, timeout: int) -> str:
    """Executa o script composto numa única chamada de `exec_command`.

    O stderr é lido e descartado sem nunca ser incluído no inventário, em
    mensagem de erro ou em qualquer outro lugar — os únicos dados que
    atravessam esta função para o resto do programa são os blocos marcados
    no stdout.
    """
    script = montar_script_composto()
    try:
        _, stdout, stderr = cliente.exec_command(script, timeout=timeout)
        saida = stdout.read().decode("utf-8", errors="replace")
        stderr.read()
    except (socket.timeout, TimeoutError):
        raise FalhaDeAlcance("tempo esgotado durante a coleta no host") from None
    return saida


def _agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def montar_inventario_de_blocos(
    blocos: Dict[str, ResultadoBloco],
    host: str,
    identidade_verificada: bool,
    coletado_em: Optional[str] = None,
) -> dict:
    """Monta o inventário (formato de `avaliador.py`) a partir dos blocos já
    analisados. Separado de `coletar` para ser testável sem rede — ver
    Tarefas 4.4 a 4.10: um transporte simulado grava a saída do script
    composto e chama esta função diretamente.

    `identidade_verificada` vai para `host.identidade_verificada`: campo
    aditivo ao formato descrito no docstring de `avaliador.py`, que não
    define onde registrar o que o Requirement "Host desconhecido com
    autorização explícita" exige ("o resultado registra que a identidade do
    host não foi verificada"). Decisão documentada em
    `docs/03-divergencias-da-implementacao.md`, seção "Grupos 4 e 5". O
    avaliador não lê este campo — nenhuma regra do baseline depende dele —
    então ele é inerte para a avaliação e não altera o comportamento
    testado no Grupo 2.
    """
    distribuicao, versao_so = _extrair_so(blocos["SO"])
    servicos = _extrair_servicos(blocos["SERVICOS"])
    habilitado_swap, tamanho_swap = _extrair_swap(blocos["SWAP"])
    portas = _extrair_portas(blocos["PORTAS"])
    lidas, ilegiveis = _extrair_chaves(blocos["CHAVES"])
    login_de_root = _extrair_login_de_root(blocos["LOGIN_ROOT"])
    sincronizado, mecanismo = _extrair_ntp(blocos["NTP"])

    return {
        "host": {
            "endereco": host,
            "hostname": _extrair_hostname(blocos["HOSTNAME"]),
            "coletado_em": coletado_em or _agora_iso(),
            "identidade_verificada": identidade_verificada,
        },
        "so": {"distribuicao": distribuicao, "versao": versao_so},
        "kernel": {"versao": _extrair_kernel(blocos["KERNEL"])},
        "servicos": servicos,
        "swap": {"habilitado": habilitado_swap, "tamanho": tamanho_swap},
        # `portas_em_escuta` nunca é `None` (contrato de avaliador.py) — ver
        # a nota do docstring do módulo sobre a lacuna que isso deixa.
        "portas_em_escuta": portas if portas is not None else [],
        "chaves_ssh": {"lidas": lidas, "arquivos_ilegiveis": ilegiveis},
        "ssh": {"login_de_root": login_de_root},
        "ntp": {"sincronizado": sincronizado, "mecanismo": mecanismo},
    }


def coletar(
    host: str,
    usuario: str,
    chave: str,
    porta: int = 22,
    timeout: int = 15,
    aceitar_host_desconhecido: bool = False,
) -> dict:
    """Conecta em `host` por SSH e devolve o inventário completo.

    Único ponto do pacote que abre socket. Uma conexão, um script composto
    — ver decisão D5. Levanta `FalhaDeAlcance` (nunca a exceção original de
    Paramiko/socket) quando o host não pôde ser alcançado, autenticado ou
    ter sua identidade verificada.
    """
    cliente, identidade_verificada = _conectar(
        host, usuario, chave, porta, timeout, aceitar_host_desconhecido
    )
    try:
        saida = _executar_script_composto(cliente, timeout)
    finally:
        cliente.close()

    blocos = analisar_blocos(saida)
    return montar_inventario_de_blocos(blocos, host, identidade_verificada)
