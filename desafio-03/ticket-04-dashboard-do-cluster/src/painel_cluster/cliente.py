"""Fronteira de leitura do cluster.

Este é o único módulo do `painel_cluster` autorizado a importar `kubernetes`
e `urllib3` (D2, D8 em `docs/02-decisoes-tecnicas.md`; D-D e D-E em
`openspec/changes/adicionar-painel-de-cluster/design.md`). Nenhum outro
módulo do pacote pode fazer esses dois imports — é o que o teste de
contenção do grupo 8 verifica.

O que este módulo faz, e só isto:
  - Resolve o contexto corrente do kubeconfig, e nunca troca de contexto.
  - Lê, por `LIST`, os sete tipos de recurso que a tela usa — namespaces em
    escopo de cluster; pods, Deployments, StatefulSets, Services,
    EndpointSlices e eventos em escopo de namespace — sempre com
    `_preload_content=False`, para preservar a forma original do JSON (D2,
    D9: ausente, nulo e vazio são três fatos distintos na resposta crua, e
    viram o mesmo `None` no modelo tipado).
  - Devolve cada leitura dentro de um `Envelope` com um dos quatro estados
    `ok`, `vazio`, `negado`, `indisponivel` (D10). A falha de um tipo nunca
    contamina os demais.
  - Classifica os três ambientes hostis por **tipo de exceção**, nunca por
    texto de mensagem (medido em `evidencias/hipotese-d2-excecoes.md`):
    `ForbiddenException` (403) é permissão negada só naquele tipo;
    `UnauthorizedException` (401) é credencial recusada, em qualquer tipo;
    `urllib3.exceptions.MaxRetryError` é cluster que não responde.

O que este módulo não faz: não interpreta nenhum campo do JSON que recebe.
Isso é o trabalho de `modelo.py` (D-A do `design.md`) — aqui só existe rede e
classificação de falha.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from enum import Enum
from typing import Any, Callable

import urllib3.exceptions
from kubernetes import client, config
from kubernetes.client.exceptions import (
    ApiException,
    ForbiddenException,
    UnauthorizedException,
)
from kubernetes.config.config_exception import ConfigException

__all__ = [
    "Destino",
    "Envelope",
    "EstadoEnvelope",
    "Sessao",
    "conectar",
    "resolver_contexto",
    "ler_namespaces",
    "ler_pods",
    "ler_deployments",
    "ler_statefulsets",
    "ler_services",
    "ler_endpointslices",
    "ler_eventos",
]


class EstadoEnvelope(str, Enum):
    """Os quatro estados que a leitura de um tipo de recurso pode assumir.

    Nenhum quinto estado existe, e nenhum deles é uma exceção que sobe até
    quem chama — ver `01-comportamento.md`, seção "O envelope por tipo de
    recurso".
    """

    OK = "ok"
    VAZIO = "vazio"
    NEGADO = "negado"
    INDISPONIVEL = "indisponivel"


@dataclasses.dataclass(frozen=True)
class Envelope:
    """O que toda leitura devolve — nunca uma lista solta (D-C do design.md).

    `itens` só é preenchido no estado `ok`, com o JSON cru de cada objeto,
    exatamente como a API o devolveu. `motivo` só é preenchido em `negado` e
    `indisponivel`, e nunca afirma mais do que o tipo de exceção sustenta —
    por exemplo, nunca diz que uma credencial está "expirada" quando o que se
    sabe é que ela foi recusada (401 não distingue as duas causas).
    """

    estado: EstadoEnvelope
    itens: tuple[dict[str, Any], ...] = ()
    motivo: str | None = None

    @classmethod
    def de_itens(cls, itens: list[dict[str, Any]]) -> "Envelope":
        itens_tupla = tuple(itens) if itens else ()
        if not itens_tupla:
            return cls(EstadoEnvelope.VAZIO)
        return cls(EstadoEnvelope.OK, itens=itens_tupla)

    @classmethod
    def negado(cls, motivo: str) -> "Envelope":
        return cls(EstadoEnvelope.NEGADO, motivo=motivo)

    @classmethod
    def indisponivel(cls, motivo: str) -> "Envelope":
        return cls(EstadoEnvelope.INDISPONIVEL, motivo=motivo)


@dataclasses.dataclass(frozen=True)
class Destino:
    """O cluster para onde toda leitura desta sessão vai: o contexto
    corrente do kubeconfig no instante em que o painel subiu, e o endereço do
    apiserver daquele contexto. Fica visível na tela o tempo todo — é o que
    impede alguém de tirar conclusão sobre produção olhando homologação."""

    contexto: str
    servidor: str


@dataclasses.dataclass(frozen=True)
class Sessao:
    """Amarra o `Destino` resolvido ao `ApiClient` já configurado para ele.

    Uma `Sessao` nunca troca de contexto depois de criada — para apontar a
    outro cluster é preciso encerrar o painel, trocar o contexto corrente do
    kubeconfig por fora, e subir de novo (Requirement "Contexto corrente e só
    ele").
    """

    destino: Destino
    api: client.ApiClient


def resolver_contexto(kubeconfig: str | None = None) -> str:
    """Devolve o nome do contexto corrente do kubeconfig.

    Cobre os dois casos do Requirement "Contexto corrente e só ele", cenário
    "Não existe kubeconfig legível": arquivo de kubeconfig inexistente ou
    ilegível, e arquivo legível sem `current-context` (ou apontando para um
    nome que não existe na lista de contextos) — o cliente `kubernetes`
    levanta a mesma `ConfigException` nos três casos, medido em
    `verificacoes/`. Encerra com código 2 e mensagem que nomeia a causa, sem
    rastreamento de pilha: a `ConfigException` é capturada aqui, e nada é
    relançado.
    """
    try:
        _, atual = config.list_kube_config_contexts(config_file=kubeconfig)
    except ConfigException as exc:
        print(
            "painel-cluster: nao ha kubeconfig legivel, ou o contexto "
            f"corrente nao existe nele ({exc})",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return atual["name"]


def conectar(kubeconfig: str | None = None) -> Sessao:
    """Resolve o contexto corrente, carrega a configuração dele no cliente
    oficial, e devolve a `Sessao` (destino + `ApiClient`) que todas as
    leituras da execução vão usar.

    É o único ponto do projeto que chama `config.load_kube_config` — nenhuma
    outra função deste módulo troca de contexto.
    """
    nome_contexto = resolver_contexto(kubeconfig)
    try:
        config.load_kube_config(config_file=kubeconfig, context=nome_contexto)
    except ConfigException as exc:
        print(
            "painel-cluster: nao ha kubeconfig legivel, ou o contexto "
            f"corrente nao existe nele ({exc})",
            file=sys.stderr,
        )
        raise SystemExit(2)
    cfg = client.Configuration.get_default_copy()
    destino = Destino(contexto=nome_contexto, servidor=cfg.host)
    return Sessao(destino=destino, api=client.ApiClient())


def _executar(tipo: str, servidor: str, fn: Callable[..., Any], *args: Any) -> Envelope:
    """O único lugar do projeto com licença para saber o que uma exceção do
    cliente `kubernetes` ou do `urllib3` significa (D-D do design.md).

    Não interpreta nenhum campo do JSON: só decide, a partir do **tipo** da
    exceção, qual dos quatro estados do envelope se aplica, e desserializa a
    resposta crua quando a chamada teve sucesso.
    """
    try:
        resposta = fn(*args, _preload_content=False)
    except ForbiddenException:
        return Envelope.negado(f"sem permissao para ler {tipo}")
    except UnauthorizedException:
        return Envelope.indisponivel("credencial recusada")
    except urllib3.exceptions.MaxRetryError:
        return Envelope.indisponivel(f"cluster nao respondeu em {servidor}")
    except ApiException as exc:
        # Qualquer outra forma de ApiException (5xx do apiserver, por
        # exemplo) não é permissão nem credencial: o painel não afirma o que
        # não mede, e não deixa a exceção escapar desta fronteira. A
        # classificação mais honesta que sobra é "não respondeu do jeito
        # esperado" — o mesmo estado de indisponibilidade, com o status HTTP
        # no motivo em vez de inventar um quinto estado que a spec não pede.
        return Envelope.indisponivel(
            f"cluster nao respondeu do jeito esperado em {servidor} "
            f"(status {exc.status})"
        )

    bruto = json.loads(resposta.data)
    return Envelope.de_itens(bruto.get("items") or [])


def ler_namespaces(sessao: Sessao) -> Envelope:
    """A única leitura de escopo de cluster inteiro."""
    v1 = client.CoreV1Api(sessao.api)
    return _executar("namespaces", sessao.destino.servidor, v1.list_namespace)


def ler_pods(sessao: Sessao, namespace: str) -> Envelope:
    v1 = client.CoreV1Api(sessao.api)
    return _executar(
        "pods", sessao.destino.servidor, v1.list_namespaced_pod, namespace
    )


def ler_deployments(sessao: Sessao, namespace: str) -> Envelope:
    apps = client.AppsV1Api(sessao.api)
    return _executar(
        "deployments",
        sessao.destino.servidor,
        apps.list_namespaced_deployment,
        namespace,
    )


def ler_statefulsets(sessao: Sessao, namespace: str) -> Envelope:
    apps = client.AppsV1Api(sessao.api)
    return _executar(
        "statefulsets",
        sessao.destino.servidor,
        apps.list_namespaced_stateful_set,
        namespace,
    )


def ler_services(sessao: Sessao, namespace: str) -> Envelope:
    v1 = client.CoreV1Api(sessao.api)
    return _executar(
        "services", sessao.destino.servidor, v1.list_namespaced_service, namespace
    )


def ler_endpointslices(sessao: Sessao, namespace: str) -> Envelope:
    disc = client.DiscoveryV1Api(sessao.api)
    return _executar(
        "endpointslices",
        sessao.destino.servidor,
        disc.list_namespaced_endpoint_slice,
        namespace,
    )


def ler_eventos(sessao: Sessao, namespace: str) -> Envelope:
    v1 = client.CoreV1Api(sessao.api)
    return _executar(
        "eventos", sessao.destino.servidor, v1.list_namespaced_event, namespace
    )
