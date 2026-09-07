"""Testes da fronteira de leitura (`painel_cluster.cliente`).

Nenhum teste aqui toca a rede: o transporte é sempre simulado — ou por um
`ApiClient` apontado para um kubeconfig de teste sem rede real (resolução de
contexto), ou por `monkeypatch` nos métodos do cliente `kubernetes` que
fazem a chamada HTTP (leitura por tipo e classificação de falha).

As fixtures capturadas do cluster real ficam em `tests/fixtures/` e são
usadas pela camada de interpretação (fora do escopo deste grupo de tarefas);
aqui os testes usam JSON mínimo, porque o que se verifica é o comportamento
da fronteira — envelope e classificação de exceção — não a forma de um
recurso específico.
"""

from __future__ import annotations

import json
import types

import pytest
import urllib3.exceptions
from kubernetes import client
from kubernetes.client.exceptions import ForbiddenException, UnauthorizedException

from painel_cluster import cliente


# --------------------------------------------------------------------- 3.2
# O tipo de envelope com os quatro estados e o motivo associado.


def test_os_quatro_estados_sao_distinguiveis_entre_si():
    ok = cliente.Envelope.de_itens([{"metadata": {"name": "a"}}])
    vazio = cliente.Envelope.de_itens([])
    negado = cliente.Envelope.negado("sem permissao para ler eventos")
    indisponivel = cliente.Envelope.indisponivel("credencial recusada")

    estados = {ok.estado, vazio.estado, negado.estado, indisponivel.estado}
    assert estados == {
        cliente.EstadoEnvelope.OK,
        cliente.EstadoEnvelope.VAZIO,
        cliente.EstadoEnvelope.NEGADO,
        cliente.EstadoEnvelope.INDISPONIVEL,
    }
    assert ok.itens == ({"metadata": {"name": "a"}},)
    assert vazio.itens == ()
    assert negado.motivo == "sem permissao para ler eventos"
    assert indisponivel.motivo == "credencial recusada"


def test_lista_vazia_produz_estado_vazio_e_nao_ok():
    envelope = cliente.Envelope.de_itens([])
    assert envelope.estado == cliente.EstadoEnvelope.VAZIO
    assert envelope.estado != cliente.EstadoEnvelope.OK


# --------------------------------------------------------------------- 3.1
# Resolução do contexto corrente e exposição de contexto + servidor.


def _escreve_kubeconfig(tmp_path, current_context, contextos, clusters):
    caminho = tmp_path / "kubeconfig-teste.yaml"
    doc = {
        "apiVersion": "v1",
        "kind": "Config",
        "current-context": current_context,
        "clusters": clusters,
        "contexts": contextos,
        "users": [{"name": "u", "user": {}}],
    }
    import yaml

    caminho.write_text(yaml.safe_dump(doc))
    return str(caminho)


def _kubeconfig_dois_contextos(tmp_path, corrente):
    clusters = [
        {"name": "cluster-a", "cluster": {"server": "https://cluster-a.invalid:6443"}},
        {"name": "cluster-b", "cluster": {"server": "https://cluster-b.invalid:6443"}},
    ]
    contextos = [
        {"name": "contexto-a", "context": {"cluster": "cluster-a", "user": "u"}},
        {"name": "contexto-b", "context": {"cluster": "cluster-b", "user": "u"}},
    ]
    return _escreve_kubeconfig(tmp_path, corrente, contextos, clusters)


def test_o_contexto_lido_e_o_corrente_do_kubeconfig_de_teste(tmp_path):
    caminho = _kubeconfig_dois_contextos(tmp_path, corrente="contexto-b")

    nome = cliente.resolver_contexto(kubeconfig=caminho)

    assert nome == "contexto-b"


def test_conectar_expoe_contexto_e_servidor_do_contexto_corrente(tmp_path):
    caminho = _kubeconfig_dois_contextos(tmp_path, corrente="contexto-a")

    sessao = cliente.conectar(kubeconfig=caminho)

    assert sessao.destino.contexto == "contexto-a"
    assert sessao.destino.servidor == "https://cluster-a.invalid:6443"


def test_nenhuma_leitura_vai_para_outro_cluster_que_nao_o_corrente(tmp_path):
    # O cenário do Requirement "O contexto corrente é o destino": um
    # kubeconfig com vários contextos, e o destino resolvido é sempre o do
    # `current-context`, nunca o do outro.
    caminho = _kubeconfig_dois_contextos(tmp_path, corrente="contexto-a")
    sessao = cliente.conectar(kubeconfig=caminho)
    assert sessao.destino.servidor != "https://cluster-b.invalid:6443"


# --------------------------------------------------------------------- 3.7
# Encerramento com código 2 quando não há kubeconfig legível ou contexto.


def test_resolver_contexto_sai_com_codigo_2_sem_kubeconfig(tmp_path, capsys):
    caminho_inexistente = str(tmp_path / "nao-existe.yaml")

    with pytest.raises(SystemExit) as exc_info:
        cliente.resolver_contexto(kubeconfig=caminho_inexistente)

    assert exc_info.value.code == 2
    saida = capsys.readouterr()
    assert "Traceback" not in saida.err
    assert "Traceback" not in saida.out


def test_resolver_contexto_sai_com_codigo_2_sem_current_context(tmp_path, capsys):
    caminho = tmp_path / "kubeconfig-sem-contexto.yaml"
    caminho.write_text(
        "apiVersion: v1\nkind: Config\n"
        "clusters:\n- cluster:\n    server: https://c.invalid\n  name: c\n"
        "contexts:\n- context:\n    cluster: c\n    user: u\n  name: ctx\n"
        "users:\n- name: u\n  user: {}\n"
    )

    with pytest.raises(SystemExit) as exc_info:
        cliente.resolver_contexto(kubeconfig=str(caminho))

    assert exc_info.value.code == 2
    saida = capsys.readouterr()
    assert "Traceback" not in saida.err


def test_conectar_tambem_sai_com_codigo_2_sem_kubeconfig(tmp_path, capsys):
    caminho_inexistente = str(tmp_path / "nao-existe.yaml")

    with pytest.raises(SystemExit) as exc_info:
        cliente.conectar(kubeconfig=caminho_inexistente)

    assert exc_info.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


# --------------------------------------------------------------------- 3.3
# Leitura dos sete tipos por LIST, sem nenhuma interpretação nesta camada.


def _resposta_crua(bruto: dict) -> types.SimpleNamespace:
    """Simula o objeto que o cliente kubernetes devolve com
    `_preload_content=False`: só o atributo `.data`, em bytes."""
    return types.SimpleNamespace(data=json.dumps(bruto).encode())


def _sessao_falsa():
    destino = cliente.Destino(contexto="ctx-teste", servidor="https://servidor.invalid")
    return cliente.Sessao(destino=destino, api=client.ApiClient())


@pytest.mark.parametrize(
    "nome_funcao, metodo_mockado, chamada",
    [
        ("ler_namespaces", "kubernetes.client.CoreV1Api.list_namespace",
         lambda s: cliente.ler_namespaces(s)),
        ("ler_pods", "kubernetes.client.CoreV1Api.list_namespaced_pod",
         lambda s: cliente.ler_pods(s, "nyx-prod")),
        ("ler_deployments", "kubernetes.client.AppsV1Api.list_namespaced_deployment",
         lambda s: cliente.ler_deployments(s, "nyx-prod")),
        ("ler_statefulsets", "kubernetes.client.AppsV1Api.list_namespaced_stateful_set",
         lambda s: cliente.ler_statefulsets(s, "nyx-dev")),
        ("ler_services", "kubernetes.client.CoreV1Api.list_namespaced_service",
         lambda s: cliente.ler_services(s, "nyx-stg")),
        ("ler_endpointslices", "kubernetes.client.DiscoveryV1Api.list_namespaced_endpoint_slice",
         lambda s: cliente.ler_endpointslices(s, "nyx-stg")),
        ("ler_eventos", "kubernetes.client.CoreV1Api.list_namespaced_event",
         lambda s: cliente.ler_eventos(s, "nyx-prod")),
    ],
)
def test_leitura_de_cada_tipo_nao_interpreta_o_json_cru(
    monkeypatch, nome_funcao, metodo_mockado, chamada
):
    # Um objeto com as tres formas de ausencia que o D9 planta — chave
    # ausente, valor nulo e chave presente com lista vazia — para provar que
    # a fronteira de leitura nao toca em nenhuma delas. Se esta camada
    # normalizasse, o teste abaixo pegaria.
    item_cru = {
        "metadata": {"name": "objeto-de-teste"},
        "status": {"campoNulo": None, "campoVazio": [], "algo": "valor"},
        # "campoAusente" de proposito nao existe.
    }
    bruto = {"kind": "List", "items": [item_cru]}

    modulo, atributo = metodo_mockado.rsplit(".", 1)
    monkeypatch.setattr(
        metodo_mockado,
        lambda self, *a, **k: _resposta_crua(bruto),
        raising=True,
    )

    envelope = chamada(_sessao_falsa())

    assert envelope.estado == cliente.EstadoEnvelope.OK
    assert len(envelope.itens) == 1
    # Byte a byte igual ao que a API mandou: nenhuma chave foi acrescentada,
    # removida ou normalizada.
    assert envelope.itens[0] == item_cru
    assert "campoAusente" not in envelope.itens[0]["status"]
    assert envelope.itens[0]["status"]["campoNulo"] is None
    assert envelope.itens[0]["status"]["campoVazio"] == []


def test_leitura_sem_itens_produz_envelope_vazio(monkeypatch):
    bruto = {"kind": "PodList", "items": []}
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api.list_namespaced_pod",
        lambda self, *a, **k: _resposta_crua(bruto),
        raising=True,
    )

    envelope = cliente.ler_pods(_sessao_falsa(), "nyx-dev")

    assert envelope.estado == cliente.EstadoEnvelope.VAZIO
    assert envelope.itens == ()


# --------------------------------------------------------------------- 3.4
# Falha de autorizacao vira `negado` restrito ao tipo; os demais seguem ok.


def test_403_num_tipo_produz_negado_e_outro_tipo_no_mesmo_cliente_segue_ok(
    monkeypatch,
):
    sessao = _sessao_falsa()

    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api.list_namespaced_event",
        lambda self, *a, **k: (_ for _ in ()).throw(
            ForbiddenException(status=403, reason="Forbidden")
        ),
        raising=True,
    )
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api.list_namespaced_pod",
        lambda self, *a, **k: _resposta_crua(
            {"items": [{"metadata": {"name": "p1"}}]}
        ),
        raising=True,
    )

    eventos = cliente.ler_eventos(sessao, "nyx-prod")
    pods = cliente.ler_pods(sessao, "nyx-prod")

    assert eventos.estado == cliente.EstadoEnvelope.NEGADO
    assert "eventos" in eventos.motivo
    assert pods.estado == cliente.EstadoEnvelope.OK
    assert len(pods.itens) == 1


# --------------------------------------------------------------------- 3.5
# Falha de autenticacao vira `indisponivel` por credencial, em todos os
# tipos, e a mensagem nao afirma que a credencial esta expirada.


@pytest.mark.parametrize(
    "chamada",
    [
        lambda s: cliente.ler_pods(s, "nyx-prod"),
        lambda s: cliente.ler_deployments(s, "nyx-prod"),
        lambda s: cliente.ler_eventos(s, "nyx-prod"),
    ],
)
def test_401_produz_indisponivel_por_credencial_em_qualquer_tipo(
    monkeypatch, chamada
):
    for metodo in (
        "kubernetes.client.CoreV1Api.list_namespaced_pod",
        "kubernetes.client.AppsV1Api.list_namespaced_deployment",
        "kubernetes.client.CoreV1Api.list_namespaced_event",
    ):
        monkeypatch.setattr(
            metodo,
            lambda self, *a, **k: (_ for _ in ()).throw(
                UnauthorizedException(status=401, reason="Unauthorized")
            ),
            raising=True,
        )

    envelope = chamada(_sessao_falsa())

    assert envelope.estado == cliente.EstadoEnvelope.INDISPONIVEL
    assert "expirad" not in envelope.motivo.lower()
    assert "vencid" not in envelope.motivo.lower()
    assert "recusa" in envelope.motivo.lower()


# --------------------------------------------------------------------- 3.6
# Falha de transporte (dependencia transitiva) vira `indisponivel` por
# cluster, e a excecao nao escapa desta fronteira.


def test_falha_de_transporte_e_capturada_aqui_e_nao_escapa(monkeypatch):
    def levanta_max_retry(self, *a, **k):
        raise urllib3.exceptions.MaxRetryError(
            pool=None, url="https://servidor.invalid/api/v1/namespaces/nyx-prod/pods"
        )

    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api.list_namespaced_pod",
        levanta_max_retry,
        raising=True,
    )

    # Se a excecao escapasse desta fronteira, esta chamada levantaria
    # MaxRetryError em vez de devolver um envelope — e o teste falharia por
    # excecao nao tratada, nao por assercao.
    envelope = cliente.ler_pods(_sessao_falsa(), "nyx-prod")

    assert envelope.estado == cliente.EstadoEnvelope.INDISPONIVEL
    assert "servidor.invalid" in envelope.motivo


def test_indisponibilidade_de_transporte_nao_e_confundida_com_negado(monkeypatch):
    monkeypatch.setattr(
        "kubernetes.client.CoreV1Api.list_namespaced_pod",
        lambda self, *a, **k: (_ for _ in ()).throw(
            urllib3.exceptions.MaxRetryError(pool=None, url="https://x.invalid")
        ),
        raising=True,
    )

    envelope = cliente.ler_pods(_sessao_falsa(), "nyx-prod")

    assert envelope.estado != cliente.EstadoEnvelope.NEGADO
    assert envelope.estado == cliente.EstadoEnvelope.INDISPONIVEL
