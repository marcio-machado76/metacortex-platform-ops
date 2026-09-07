"""Avaliador — função pura ``(inventário, baseline) -> conformidade``.

Não importa Paramiko, não abre socket, não lê nada além do baseline
informado pelo chamador. Isso é o que torna o critério de aceite mais
difícil ("duas execuções seguidas devolvem o mesmo veredito") demonstrável
em teste automatizado, sem host — ver `design.md`, seção "Quatro módulos,
com a rede confinada em um".

## A estrutura do inventário (Tarefa 2.1)

O inventário é um dado, não um objeto vivo (`design.md`): um dicionário
simples, serializável em JSON, no formato abaixo. Campo que não pôde ser
observado vem com valor ``None`` — nunca ausente, nunca inventado
(`docs/01-comportamento.md`, seção "O inventário").

    {
        "host": {
            "endereco": str,
            "hostname": str | None,
            "coletado_em": str,       # ISO 8601 UTC, sufixo "Z"
        },
        "so": {
            "distribuicao": str | None,
            "versao": str | None,
        },
        "kernel": {
            "versao": str | None,
        },
        "servicos": [
            {"nome": str, "tipo": "service" | "socket" | "timer", "estado": str},
            ...
        ] | None,                     # None quando o gerenciador de serviços
                                       # está indisponível no host
        "swap": {
            "habilitado": bool | None,
            "tamanho": str | None,
        },
        "portas_em_escuta": [
            {
                "porta": int,
                "protocolo": str,     # "tcp" | "udp"
                "bind": str,          # endereço IP de vínculo
                "processo": str | None,
            },
            ...
        ],                             # a lista em si nunca é None
        "chaves_ssh": {
            "lidas": [
                {"identificacao": str, "origem": str},
                ...
            ],
            "arquivos_ilegiveis": [str, ...],  # caminhos de arquivos que
                                                # existem mas não puderam
                                                # ser lidos
        },
        "ssh": {
            "login_de_root": bool | None,
        },
        "ntp": {
            "sincronizado": bool | None,
            "mecanismo": str | None,
        },
    }

**Nota sobre uma lacuna da especificação (ver
`docs/03-divergencias-da-implementacao.md`):** a tabela de
`docs/01-comportamento.md` descreve `chaves_ssh` como "lista de
`{identificacao, origem}`", mas o texto da seção "Escopo das chaves" exige
que arquivos existentes e ilegíveis sejam "contados e nomeados" para
sustentar o veredito `nao_verificado`. A tabela não nomeia o campo que
carrega essa informação. Esta implementação resolve a lacuna com a chave
`chaves_ssh.lidas` (a lista de chaves legíveis, no formato descrito) e
`chaves_ssh.arquivos_ilegiveis` (a lista de caminhos ilegíveis).

## A estrutura da entrada de conformidade (Tarefa 2.1)

    {
        "regra": str,           # caminho da regra no baseline, ex.: "so.distribuicao"
        "esperado": Any,        # valor declarado pelo baseline para a regra
        "encontrado": Any,      # o que foi observado no host, formato por regra
        "veredito": "conforme" | "desvio" | "nao_verificado",
        "severidade": str | None,  # presente (não None) apenas quando veredito == "desvio"
        "motivo": str | None,      # presente (não None) apenas quando veredito == "nao_verificado"
    }

`severidade` e `motivo` estão sempre presentes como chaves (nunca ausentes),
com valor `None` quando não se aplicam — mesma convenção de "nunca ausente,
nunca inventado" usada no inventário. Essa extensão da convenção às entradas
de conformidade não está explicitada em `docs/01-comportamento.md`, que fala
da regra apenas para campos do inventário; foi uma decisão desta
implementação para manter as duas estruturas (inventário e conformidade)
consistentes para um consumidor de máquina (o Roster). Ver
`docs/03-divergencias-da-implementacao.md`.
"""

from __future__ import annotations

import ipaddress
import re
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# Versão mais recente do formato de baseline que esta ferramenta conhece.
# Ver Requirement "Regra desconhecida não é silenciada" em
# specs/avaliacao-de-conformidade/spec.md.
VERSAO_BASELINE_CONHECIDA = 1

VEREDITO_CONFORME = "conforme"
VEREDITO_DESVIO = "desvio"
VEREDITO_NAO_VERIFICADO = "nao_verificado"

SEVERIDADES_EM_ORDEM = ("critico", "alto", "medio")


# ---------------------------------------------------------------------------
# Leitura do baseline (Tarefa 2.2)
# ---------------------------------------------------------------------------


def carregar_baseline(caminho: str) -> dict:
    """Lê e faz o parse do arquivo de baseline em YAML.

    Avisa (via `warnings.warn`) quando a versão declarada no arquivo é
    posterior à conhecida por esta ferramenta, e prossegue de qualquer
    forma — a avaliação nunca é abortada por causa da versão do baseline.
    """
    with open(caminho, "r", encoding="utf-8") as arquivo:
        baseline = yaml.safe_load(arquivo)

    versao = baseline.get("versao") if isinstance(baseline, dict) else None
    if isinstance(versao, (int, float)) and versao > VERSAO_BASELINE_CONHECIDA:
        warnings.warn(
            f"baseline na versão {versao!r}, mais recente que a versão "
            f"{VERSAO_BASELINE_CONHECIDA!r} conhecida por esta ferramenta; "
            "a avaliação prossegue mesmo assim.",
            UserWarning,
            stacklevel=2,
        )
    return baseline


def _regras_do_baseline(baseline: dict) -> List[Tuple[str, Any]]:
    """Achata `baseline["esperado"]` em uma lista de (caminho, valor).

    A ordem de iteração é a ordem de declaração no arquivo (PyYAML preserva
    a ordem das chaves de um mapeamento), o que é o que torna a avaliação
    determinística sem precisar de uma ordenação artificial adicional.
    """
    regras: List[Tuple[str, Any]] = []

    def _percorrer(prefixo: str, no: dict) -> None:
        for chave, valor in no.items():
            caminho = f"{prefixo}.{chave}" if prefixo else str(chave)
            if isinstance(valor, dict):
                _percorrer(caminho, valor)
            else:
                regras.append((caminho, valor))

    _percorrer("", baseline.get("esperado", {}) or {})
    return regras


def _severidade_por_regra(baseline: dict) -> Dict[str, str]:
    mapa: Dict[str, str] = {}
    for severidade, regras in (baseline.get("severidade", {}) or {}).items():
        for regra in regras or []:
            mapa[regra] = severidade
    return mapa


# ---------------------------------------------------------------------------
# Registro de regras indexado pelo caminho do baseline (Tarefa 2.3)
# ---------------------------------------------------------------------------

RegraFn = Callable[[dict, Any], dict]
REGISTRO_REGRAS: Dict[str, RegraFn] = {}


def registrar(caminho: str) -> Callable[[RegraFn], RegraFn]:
    """Decorador que registra uma função de avaliação sob o caminho do baseline."""

    def _decorador(fn: RegraFn) -> RegraFn:
        REGISTRO_REGRAS[caminho] = fn
        return fn

    return _decorador


def _resultado(
    veredito: str, encontrado: Any = None, motivo: Optional[str] = None
) -> dict:
    return {"veredito": veredito, "encontrado": encontrado, "motivo": motivo}


# ---------------------------------------------------------------------------
# Comparação de versão (Tarefa 2.4)
# ---------------------------------------------------------------------------

_PADRAO_VERSAO_NUMERICA = re.compile(r"^(\d+(?:\.\d+)*)")


def _versao_para_componentes(versao: Optional[str]) -> Optional[Tuple[int, ...]]:
    """Extrai os componentes numéricos iniciais de uma string de versão.

    Ex.: "22.04" -> (22, 4); "6.8.0-31-generic" -> (6, 8, 0). Um caractere
    que não seja dígito ou ponto encerra a extração. Retorna `None` quando a
    string não começa com um componente numérico (formato anômalo).
    """
    if not versao:
        return None
    casamento = _PADRAO_VERSAO_NUMERICA.match(versao.strip())
    if not casamento:
        return None
    return tuple(int(parte) for parte in casamento.group(1).split("."))


def _versao_atende_minima(atual: Tuple[int, ...], minima: Tuple[int, ...]) -> bool:
    tamanho = max(len(atual), len(minima))
    atual_completa = atual + (0,) * (tamanho - len(atual))
    minima_completa = minima + (0,) * (tamanho - len(minima))
    return atual_completa >= minima_completa


def _avaliar_versao_minima(encontrado: Optional[str], esperado: Any, motivo_ausente: str) -> dict:
    if encontrado is None:
        return _resultado(VEREDITO_NAO_VERIFICADO, motivo=motivo_ausente)
    atual = _versao_para_componentes(encontrado)
    minima = _versao_para_componentes(str(esperado))
    if atual is None or minima is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            encontrado=encontrado,
            motivo=f"formato de versão não reconhecido: '{encontrado}'",
        )
    veredito = VEREDITO_CONFORME if _versao_atende_minima(atual, minima) else VEREDITO_DESVIO
    return _resultado(veredito, encontrado=encontrado)


@registrar("so.distribuicao")
def _regra_so_distribuicao(inventario: dict, esperado: Any) -> dict:
    encontrado = (inventario.get("so") or {}).get("distribuicao")
    if encontrado is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo="distribuição do sistema operacional não pôde ser lida",
        )
    veredito = (
        VEREDITO_CONFORME
        if str(encontrado).strip().lower() == str(esperado).strip().lower()
        else VEREDITO_DESVIO
    )
    return _resultado(veredito, encontrado=encontrado)


@registrar("so.versao_minima")
def _regra_so_versao_minima(inventario: dict, esperado: Any) -> dict:
    encontrado = (inventario.get("so") or {}).get("versao")
    return _avaliar_versao_minima(
        encontrado, esperado, "versão do sistema operacional não pôde ser lida"
    )


@registrar("kernel.versao_minima")
def _regra_kernel_versao_minima(inventario: dict, esperado: Any) -> dict:
    encontrado = (inventario.get("kernel") or {}).get("versao")
    return _avaliar_versao_minima(encontrado, esperado, "versão do kernel não pôde ser lida")


# ---------------------------------------------------------------------------
# Serviços ativos e proibidos (Tarefas 2.5 e 2.6)
# ---------------------------------------------------------------------------


def _forma_ativa(nome_esperado: str, servicos: List[dict]) -> Optional[str]:
    """Forma ("service"/"socket"/o tipo exato) em que a unidade está ativa.

    Nome com sufixo (contém ".") casa exatamente, incluindo o tipo. Nome sem
    sufixo casa com ".service" ou ".socket" — ver Requirement "Unidade ativa
    por socket satisfaz a exigência de unidade ativa" e decisão D9.
    """
    if "." in nome_esperado:
        for servico in servicos:
            if servico.get("nome") == nome_esperado and servico.get("estado") == "active":
                return servico.get("tipo")
        return None
    for sufixo in ("service", "socket"):
        nome_completo = f"{nome_esperado}.{sufixo}"
        for servico in servicos:
            if servico.get("nome") == nome_completo and servico.get("estado") == "active":
                return sufixo
    return None


@registrar("servicos.ativos")
def _regra_servicos_ativos(inventario: dict, esperado: Any) -> dict:
    servicos = inventario.get("servicos")
    if servicos is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo="gerenciador de serviços indisponível no host",
        )
    encontrado: Dict[str, dict] = {}
    algum_ausente = False
    for nome in esperado or []:
        forma = _forma_ativa(nome, servicos)
        encontrado[nome] = {"ativo": forma is not None, "forma": forma}
        if forma is None:
            algum_ausente = True
    veredito = VEREDITO_DESVIO if algum_ausente else VEREDITO_CONFORME
    return _resultado(veredito, encontrado=encontrado)


@registrar("servicos.proibidos")
def _regra_servicos_proibidos(inventario: dict, esperado: Any) -> dict:
    servicos = inventario.get("servicos")
    if servicos is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo="gerenciador de serviços indisponível no host",
        )
    ativos_proibidos = [
        nome
        for nome in (esperado or [])
        if any(s.get("nome") == nome and s.get("estado") == "active" for s in servicos)
    ]
    veredito = VEREDITO_DESVIO if ativos_proibidos else VEREDITO_CONFORME
    return _resultado(veredito, encontrado=ativos_proibidos)


# ---------------------------------------------------------------------------
# Swap (Tarefa 2.7)
# ---------------------------------------------------------------------------


@registrar("swap.habilitado")
def _regra_swap_habilitado(inventario: dict, esperado: Any) -> dict:
    swap = inventario.get("swap") or {}
    habilitado = swap.get("habilitado")
    if habilitado is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO, motivo="informação de swap não pôde ser lida"
        )
    encontrado = {"habilitado": habilitado, "tamanho": swap.get("tamanho") if habilitado else None}
    veredito = VEREDITO_CONFORME if habilitado == esperado else VEREDITO_DESVIO
    return _resultado(veredito, encontrado=encontrado)


# ---------------------------------------------------------------------------
# Classificação de endereço de escuta (Tarefa 2.8)
# ---------------------------------------------------------------------------

CLASSE_PUBLICA = "publica"
CLASSE_REDE_INTERNA = "rede_interna"
CLASSE_LOOPBACK = "loopback"


def classificar_endereco_de_escuta(bind: str) -> str:
    """Classifica um endereço de vínculo em pública, rede interna ou loopback.

    Ver `docs/01-comportamento.md`, seção "Classificação de endereço de
    escuta", e decisão D8 em `docs/02-decisoes-tecnicas.md`.

    A tabela da especificação cobre explicitamente três casos: coringa
    (`0.0.0.0`/`::`) como pública, faixa privada/link-local como rede
    interna, e loopback. Ela não trata o caso de um endereço IP público
    específico (não coringa) — por exemplo, um bind explícito num IP
    público da própria interface. Esta implementação decide que esse caso
    também é "pública" (é o que `ipaddress` classifica como não-privado e
    não-loopback), por ser a leitura mais conservadora e a mais consistente
    com o espírito da regra (o que não é privado nem loopback é exposição).
    Ver `docs/03-divergencias-da-implementacao.md`.
    """
    endereco = ipaddress.ip_address(bind)
    # `0.0.0.0` e `::` são "coringa" (bind em toda interface) — a tabela da
    # especificação os classifica como pública. O módulo `ipaddress` os
    # marca como `is_private` (por estarem nas faixas reservadas
    # 0.0.0.0/8 e ::/128), então o caso coringa precisa ser checado
    # explicitamente, antes de `is_private`, para não cair em rede interna.
    if endereco.is_unspecified:
        return CLASSE_PUBLICA
    if endereco.is_loopback:
        return CLASSE_LOOPBACK
    if endereco.is_private or endereco.is_link_local:
        return CLASSE_REDE_INTERNA
    return CLASSE_PUBLICA


# ---------------------------------------------------------------------------
# Portas em escuta (Tarefa 2.9)
# ---------------------------------------------------------------------------


@registrar("portas_em_escuta.publicas_permitidas")
def _regra_portas_publicas_permitidas(inventario: dict, esperado: Any) -> dict:
    portas = inventario.get("portas_em_escuta") or []
    permitidas = set(esperado or [])
    nao_permitidas = [
        porta
        for porta in portas
        if classificar_endereco_de_escuta(porta["bind"]) == CLASSE_PUBLICA
        and porta["porta"] not in permitidas
    ]
    veredito = VEREDITO_DESVIO if nao_permitidas else VEREDITO_CONFORME
    return _resultado(veredito, encontrado=nao_permitidas)


@registrar("portas_em_escuta.somente_rede_interna")
def _regra_portas_somente_rede_interna(inventario: dict, esperado: Any) -> dict:
    portas = inventario.get("portas_em_escuta") or []
    restritas = set(esperado or [])
    expostas = [
        porta
        for porta in portas
        if porta["porta"] in restritas
        and classificar_endereco_de_escuta(porta["bind"]) == CLASSE_PUBLICA
    ]
    veredito = VEREDITO_DESVIO if expostas else VEREDITO_CONFORME
    return _resultado(veredito, encontrado=expostas)


# ---------------------------------------------------------------------------
# Chaves SSH (Tarefa 2.10)
# ---------------------------------------------------------------------------


@registrar("chaves_ssh.emitidas_por")
def _regra_chaves_emitidas_por(inventario: dict, esperado: Any) -> dict:
    chaves_ssh = inventario.get("chaves_ssh") or {}
    lidas = chaves_ssh.get("lidas") or []
    arquivos_ilegiveis = chaves_ssh.get("arquivos_ilegiveis") or []

    estranhas = [
        chave for chave in lidas if str(esperado) not in (chave.get("identificacao") or "")
    ]
    if estranhas:
        # Prova positiva de violação vence incompletude, mesmo que também
        # existam arquivos ilegíveis.
        return _resultado(VEREDITO_DESVIO, encontrado=estranhas)
    if arquivos_ilegiveis:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo=(
                "leitura incompleta das chaves autorizadas: "
                f"{len(arquivos_ilegiveis)} arquivo(s) ilegível(is): "
                f"{', '.join(arquivos_ilegiveis)}"
            ),
        )
    return _resultado(VEREDITO_CONFORME, encontrado=lidas)


# ---------------------------------------------------------------------------
# Login de root e NTP (Tarefa 2.11)
# ---------------------------------------------------------------------------


@registrar("ssh.login_de_root")
def _regra_ssh_login_de_root(inventario: dict, esperado: Any) -> dict:
    encontrado = (inventario.get("ssh") or {}).get("login_de_root")
    if encontrado is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo=(
                "leitura da configuração efetiva de login de root exige "
                "privilégio que o usuário da coleta não tem"
            ),
        )
    veredito = VEREDITO_CONFORME if encontrado == esperado else VEREDITO_DESVIO
    return _resultado(veredito, encontrado=encontrado)


@registrar("ntp.sincronizado")
def _regra_ntp_sincronizado(inventario: dict, esperado: Any) -> dict:
    ntp = inventario.get("ntp") or {}
    sincronizado = ntp.get("sincronizado")
    if sincronizado is None:
        return _resultado(
            VEREDITO_NAO_VERIFICADO,
            motivo="sincronização de tempo não pôde ser determinada: nenhum mecanismo de tempo reconhecido",
        )
    veredito = VEREDITO_CONFORME if sincronizado == esperado else VEREDITO_DESVIO
    return _resultado(
        veredito, encontrado={"sincronizado": sincronizado, "mecanismo": ntp.get("mecanismo")}
    )


# ---------------------------------------------------------------------------
# Avaliação completa e resumo (Tarefas 2.12 e 2.13)
# ---------------------------------------------------------------------------


def _montar_entrada(regra: str, esperado: Any, resultado: dict, severidade_por_regra: Dict[str, str]) -> dict:
    veredito = resultado["veredito"]
    return {
        "regra": regra,
        "esperado": esperado,
        "encontrado": resultado.get("encontrado"),
        "veredito": veredito,
        "severidade": severidade_por_regra.get(regra) if veredito == VEREDITO_DESVIO else None,
        "motivo": resultado.get("motivo") if veredito == VEREDITO_NAO_VERIFICADO else None,
    }


def _montar_resumo(conformidade: List[dict]) -> dict:
    contagem = {VEREDITO_CONFORME: 0, VEREDITO_DESVIO: 0, VEREDITO_NAO_VERIFICADO: 0}
    por_severidade = {severidade: 0 for severidade in SEVERIDADES_EM_ORDEM}
    for entrada in conformidade:
        contagem[entrada["veredito"]] += 1
        if entrada["veredito"] == VEREDITO_DESVIO and entrada["severidade"]:
            por_severidade[entrada["severidade"]] = por_severidade.get(entrada["severidade"], 0) + 1
    return {**contagem, "por_severidade": por_severidade}


def avaliar(inventario: dict, baseline: dict) -> dict:
    """Avalia um inventário contra um baseline.

    Função pura: nenhum acesso a rede, nenhum efeito colateral. O mesmo par
    (inventário, baseline) produz sempre o mesmo resultado — ver Requirement
    "A avaliação não depende de rede".

    Retorna ``{"conformidade": [...], "resumo": {...}}``.
    """
    severidade_por_regra = _severidade_por_regra(baseline)
    conformidade: List[dict] = []
    for regra, esperado in _regras_do_baseline(baseline):
        fn = REGISTRO_REGRAS.get(regra)
        if fn is None:
            resultado = _resultado(
                VEREDITO_NAO_VERIFICADO,
                motivo=(
                    f"esta versão da ferramenta não implementa a avaliação "
                    f"da regra '{regra}'"
                ),
            )
        else:
            resultado = fn(inventario, esperado)
        conformidade.append(_montar_entrada(regra, esperado, resultado, severidade_por_regra))

    resumo = _montar_resumo(conformidade)
    return {"conformidade": conformidade, "resumo": resumo}
