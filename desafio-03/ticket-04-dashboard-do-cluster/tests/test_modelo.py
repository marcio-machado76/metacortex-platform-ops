"""Testes da camada de interpretação (`painel_cluster.modelo`).

Escopo: grupos 4, 5 e 6 do `tasks.md` — pods, controladores, Services,
eventos e ordenação por anormalidade. Nenhum teste aqui toca rede nem
importa `kubernetes`/`urllib3`; a "captura simulada" é o próprio JSON das
fixtures em `tests/fixtures/`, mais dicionários mínimos escritos à mão para
os ramos que as fixtures não cobrem (o mesmo estilo de `test_cliente.py`).

Cada bloco de teste está marcado com o número da tarefa de `tasks.md` que ele
verifica.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from painel_cluster import modelo

FIXTURES = Path(__file__).parent / "fixtures"


def _carregar(nome_arquivo: str) -> dict:
    with open(FIXTURES / nome_arquivo) as f:
        return json.load(f)


def _item_por_nome(bruto: dict, nome: str) -> dict:
    for item in bruto["items"]:
        if item["metadata"]["name"] == nome:
            return item
    raise AssertionError(f"item {nome!r} nao encontrado na fixture")


# ===========================================================================
# Grupo 4 — interpretação de pods
# ===========================================================================

# --------------------------------------------------------------------- 4.1
# Estado exibido a partir de fase, marca de remoção e estado dos containers.


def test_pod_em_crashloop_mostra_o_motivo_e_nao_running():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-api-79c5f4d8d7-2w5kd")

    assert pod["status"]["phase"] == "Running"  # a fase sozinha mentiria
    assert modelo.estado_pod(pod) == "CrashLoopBackOff"
    assert modelo.estado_pod(pod) != "Running"


# --------------------------------------------------------------------- 4.2
# Pod em remoção: marca presente + fase Running produz Terminating.


def test_pod_com_marca_de_remocao_e_fase_running_produz_terminating():
    pod = {
        "metadata": {"name": "p", "deletionTimestamp": "2026-09-07T06:00:00Z"},
        "status": {"phase": "Running", "containerStatuses": []},
    }
    assert modelo.estado_pod(pod) == "Terminating"


def test_marca_de_remocao_prevalece_mesmo_com_container_em_crashloop():
    # Cenario nao coberto por nenhuma fixture nem cenario da spec: os dois
    # sinais presentes ao mesmo tempo. Decisao deste codigo, documentada no
    # docstring de estado_pod: Terminating vence.
    pod = {
        "metadata": {"name": "p", "deletionTimestamp": "2026-09-07T06:00:00Z"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {"state": {"waiting": {"reason": "CrashLoopBackOff"}}}
            ],
        },
    }
    assert modelo.estado_pod(pod) == "Terminating"


# --------------------------------------------------------------------- 4.3
# Contagem de containers prontos sobre o total.


def test_pod_sem_container_pronto_produz_0_1_sem_erro():
    pod = {
        "metadata": {"name": "p"},
        "status": {"phase": "Running", "containerStatuses": [{"ready": False}]},
    }
    assert modelo.prontos_pod(pod) == (0, 1)


def test_pod_sem_container_status_recua_para_spec_containers():
    # Pod ainda nao agendado: containerStatuses ausente. O total nao pode
    # virar 0/0 so porque a chave nao existe ainda.
    pod = {
        "metadata": {"name": "p"},
        "spec": {"containers": [{"name": "a"}, {"name": "b"}]},
        "status": {"phase": "Pending"},
    }
    assert modelo.prontos_pod(pod) == (0, 2)


def test_pod_saudavel_da_fixture_mostra_1_de_1_pronto():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-postgres-5877b89bf8-5g58h")
    assert modelo.prontos_pod(pod) == (1, 1)


# --------------------------------------------------------------------- 4.4
# As duas metades do motivo de falha, com a fixture 2.1.


def test_motivo_de_falha_mostra_as_duas_metades_com_causa_do_encerramento_anterior():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-api-79c5f4d8d7-2w5kd")

    motivo = modelo.motivo_falha_pod(pod)

    assert motivo.atual == "CrashLoopBackOff"
    assert motivo.causa == "OOMKilled"


def test_pod_sem_falha_produz_motivo_vazio_dos_dois_lados():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-postgres-5877b89bf8-5g58h")
    motivo = modelo.motivo_falha_pod(pod)
    assert motivo.atual is None
    assert motivo.causa is None


# --------------------------------------------------------------------- 4.5
# Sonda de prontidão por container.


def test_pod_com_dois_containers_e_uma_sonda_produz_1_de_2():
    pod = {
        "spec": {
            "containers": [
                {"name": "a", "readinessProbe": {"httpGet": {"path": "/"}}},
                {"name": "b"},
            ]
        }
    }
    sonda = modelo.sonda_prontidao_pod(pod)
    assert (sonda.com_sonda, sonda.total) == (1, 2)


def test_orion_web_sem_sonda_nenhuma_produz_0_containers_com_sonda():
    # AC5 do 01-comportamento.md: orion-web do orion-stg nao tem probe
    # nenhuma. Nao ha fixture de pod do orion-stg; o fato (container sem
    # readinessProbe) e reproduzido a mao, como o proprio nyx-api do
    # nyx-prod ja demonstra (ele TEM sonda, ao contrario do orion-web).
    bruto = _carregar("pods-nyx-prod.json")
    pod_com_sonda = _item_por_nome(bruto, "nyx-api-79c5f4d8d7-2w5kd")
    pod_sem_sonda = _item_por_nome(bruto, "nyx-postgres-5877b89bf8-5g58h")

    assert modelo.sonda_prontidao_pod(pod_com_sonda) == modelo.Sonda(com_sonda=1, total=1)
    assert modelo.sonda_prontidao_pod(pod_sem_sonda) == modelo.Sonda(com_sonda=0, total=1)


# --------------------------------------------------------------------- extra
# interpretar_pod: montagem completa, com os critérios que nascem do pod.


def test_interpretar_pod_crashloop_carrega_os_criterios_1_2_e_3():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-api-79c5f4d8d7-2w5kd")

    exibido = modelo.interpretar_pod(pod)

    pesos = {c.peso for c in exibido.criterios}
    assert pesos == {1, 2, 3}  # 0/1 pronto, waiting reason, reinicios > 0
    assert all(c.campo for c in exibido.criterios)  # todo criterio aponta campo


def test_pod_que_subiu_mas_nao_esta_pronto_mostra_running_e_fica_anormal_por_prontos():
    # spec.md, Requirement "O estado de um pod não é a sua fase", cenário
    # "Pod que subiu mas não está pronto": fase Running, zero reinícios,
    # nenhum container pronto -- sem waiting.reason nenhum (o container está
    # em `running`, só não passou na prontidão). Nenhuma fixture cobre este
    # caso (não há pod do orion-web nas fixtures); reproduzido à mão.
    pod = {
        "metadata": {"name": "orion-web-x"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {"ready": False, "restartCount": 0, "state": {"running": {"startedAt": "x"}}}
            ],
        },
    }

    exibido = modelo.interpretar_pod(pod)

    assert exibido.estado == "Running"  # a fase, sem tradução -- não há waiting nem remoção
    assert (exibido.prontos, exibido.total_containers) == (0, 1)
    assert any(c.peso == 1 for c in exibido.criterios)  # anormal pela contagem de prontos
    assert not any(c.peso in (2, 3) for c in exibido.criterios)  # não por espera nem reinício


def test_interpretar_pod_saudavel_nao_carrega_criterio_nenhum():
    bruto = _carregar("pods-nyx-prod.json")
    pod = _item_por_nome(bruto, "nyx-postgres-5877b89bf8-5g58h")
    exibido = modelo.interpretar_pod(pod)
    assert exibido.criterios == ()


# ===========================================================================
# Grupo 5 — interpretação de controladores e Services
# ===========================================================================

# --------------------------------------------------------------------- 5.1
# Normalização de ausente, nulo e coleção vazia num único ponto.


@pytest.mark.parametrize(
    "objeto",
    [
        {},  # campo ausente
        {"subsets": None},  # valor nulo
        {"subsets": []},  # coleção vazia
    ],
)
def test_normalizar_colapsa_as_tres_formas_de_ausencia_no_mesmo_resultado(objeto):
    assert modelo.normalizar(objeto.get("subsets"), []) == []


def test_normalizar_nao_apaga_valor_explicito():
    assert modelo.normalizar({"n": 3}.get("n"), 0) == 3
    assert modelo.normalizar([{"a": 1}], []) == [{"a": 1}]


def test_normalizar_e_o_unico_ponto_usado_por_enderecos_de_service():
    # Prova indireta de que a camada nao testa "in": o mesmo Service, uma
    # vez com a fatia faltando a chave "endpoints" e outra com a chave
    # presente e nula, produzem o mesmo (prontos, total).
    fatia_sem_chave = {"metadata": {"labels": {}}}
    fatia_com_nulo = {"metadata": {"labels": {}}, "endpoints": None}
    assert modelo.enderecos_de_service([fatia_sem_chave]) == modelo.enderecos_de_service(
        [fatia_com_nulo]
    )


# --------------------------------------------------------------------- 5.2
# Prontos sobre desejados para Deployment, com a fixture 2.2.


def test_deployment_sem_readyreplicas_mostra_0_de_3():
    bruto = _carregar("deployments-orion-stg.json")
    orion_web = _item_por_nome(bruto, "orion-web")
    assert "readyReplicas" not in orion_web["status"]  # a armadilha, confirmada

    exibido = modelo.interpretar_controlador(orion_web, tipo="Deployment")

    assert (exibido.prontos, exibido.desejados) == (0, 3)


# --------------------------------------------------------------------- 5.3
# Prontos sobre desejados para StatefulSet, com a fixture 2.3.


def test_statefulset_com_readyreplicas_mostra_1_de_1():
    bruto = _carregar("statefulsets-nyx-dev.json")
    nyx_postgres = _item_por_nome(bruto, "nyx-postgres")

    exibido = modelo.interpretar_controlador(nyx_postgres, tipo="StatefulSet")

    assert (exibido.prontos, exibido.desejados) == (1, 1)


def test_deployment_e_statefulset_saudaveis_usam_o_mesmo_formato_de_coluna():
    # AC3: replica unica ao lado de duas, mesmo formato.
    bruto_dev = _carregar("deployments-nyx-dev.json")
    bruto_prod = _carregar("deployments-orion-prod.json")
    nyx_api = modelo.interpretar_controlador(
        _item_por_nome(bruto_dev, "nyx-api"), tipo="Deployment"
    )
    orion_web = modelo.interpretar_controlador(
        _item_por_nome(bruto_prod, "orion-web"), tipo="Deployment"
    )
    assert (nyx_api.prontos, nyx_api.desejados) == (1, 1)
    assert (orion_web.prontos, orion_web.desejados) == (2, 2)
    assert nyx_api.criterios == () and orion_web.criterios == ()


# --------------------------------------------------------------------- 5.4
# Condição de controlador só existe onde a API a fornece.


def test_statefulset_nao_produz_coluna_de_condicao_e_nao_e_anormal():
    bruto = _carregar("statefulsets-nyx-dev.json")
    nyx_postgres = _item_por_nome(bruto, "nyx-postgres")
    assert "conditions" not in nyx_postgres["status"]  # a armadilha, confirmada

    exibido = modelo.interpretar_controlador(nyx_postgres, tipo="StatefulSet")

    assert exibido.condicao_available is None
    assert exibido.criterios == ()  # ausencia de condicao nao e estado ruim


def test_deployment_saudavel_produz_condicao_available_true():
    bruto = _carregar("deployments-nyx-dev.json")
    nyx_api = _item_por_nome(bruto, "nyx-api")
    exibido = modelo.interpretar_controlador(nyx_api, tipo="Deployment")
    assert exibido.condicao_available == modelo.Condicao(tipo="Available", status="True")


# --------------------------------------------------------------------- 5.5
# Zero afirmado contra nada ainda afirmado.


def test_controlador_recem_criado_nao_e_classificado_como_degradado():
    # observedGeneration ausente: o control plane ainda nao escreveu status
    # nenhum para a geracao corrente. readyReplicas tambem ausente (zero
    # normalizado), mas isso nao pode virar criterio de anormalidade.
    recem_criado = {
        "metadata": {"name": "novo", "generation": 1},
        "spec": {"replicas": 3},
        "status": {},
    }
    assert modelo.controlador_ainda_nao_avaliado(recem_criado) is True

    exibido = modelo.interpretar_controlador(recem_criado, tipo="Deployment")
    assert (exibido.prontos, exibido.desejados) == (0, 3)
    assert exibido.criterios == ()


def test_controlador_com_observed_generation_atrasada_tambem_nao_e_degradado():
    atrasado = {
        "metadata": {"name": "atualizando", "generation": 2},
        "spec": {"replicas": 3},
        "status": {"observedGeneration": 1, "readyReplicas": 0},
    }
    assert modelo.controlador_ainda_nao_avaliado(atrasado) is True
    assert modelo.interpretar_controlador(atrasado, tipo="Deployment").criterios == ()


def test_controlador_avaliado_e_zero_pronto_e_degradado():
    # orion-web da fixture: observedGeneration == generation (avaliado) e
    # readyReplicas ausente -> zero afirmado, nao "ainda nao sei".
    bruto = _carregar("deployments-orion-stg.json")
    orion_web = _item_por_nome(bruto, "orion-web")
    assert modelo.controlador_ainda_nao_avaliado(orion_web) is False

    exibido = modelo.interpretar_controlador(orion_web, tipo="Deployment")
    assert exibido.criterios != ()
    assert exibido.criterios[0].peso == 1
    assert exibido.criterios[0].campo == "status.readyReplicas"


# --------------------------------------------------------------------- 5.6
# Agregação de fatias de endereço por Service.


def test_varias_fatias_do_mesmo_service_produzem_um_so_grupo():
    fatias = [
        {
            "metadata": {"name": "s-a1", "labels": {"kubernetes.io/service-name": "s"}},
            "endpoints": [{"conditions": {"ready": True}}],
        },
        {
            "metadata": {"name": "s-a2", "labels": {"kubernetes.io/service-name": "s"}},
            "endpoints": [{"conditions": {"ready": False}}],
        },
        {
            "metadata": {"name": "outro-b1", "labels": {"kubernetes.io/service-name": "outro"}},
            "endpoints": [{"conditions": {"ready": True}}],
        },
    ]

    agrupado = modelo.agregar_enderecos_por_service(fatias)

    assert set(agrupado.keys()) == {"s", "outro"}
    assert len(agrupado["s"]) == 2
    assert len(agrupado["outro"]) == 1

    prontos, total = modelo.enderecos_de_service(agrupado["s"])
    assert (prontos, total) == (1, 2)


# --------------------------------------------------------------------- 5.7
# Os três estados de endereço, com a fixture 2.4 — as duas formas de
# ausência produzem o mesmo "sem endereço".


def test_service_nyx_api_sem_endereco_via_endpointslice_com_valor_nulo():
    # D5: a leitura de producao usa EndpointSlice, nao Endpoints. A fatia do
    # nyx-api tem a chave "endpoints" presente com valor null.
    bruto_slices = _carregar("endpointslices-nyx-stg.json")
    slice_nyx_api = _item_por_nome(bruto_slices, "nyx-api-4mqdq")
    assert slice_nyx_api["endpoints"] is None  # a armadilha, confirmada

    exibido = modelo.interpretar_service(
        {"metadata": {"name": "nyx-api"}}, [slice_nyx_api]
    )

    assert modelo.estado_enderecos(exibido.prontos, exibido.total_enderecos) == (
        modelo.SEM_ENDERECO
    )
    assert (exibido.prontos, exibido.total_enderecos) == (0, 0)


def test_endpoints_com_chave_ausente_normaliza_igual_ao_endpointslice_com_valor_nulo():
    # A outra metade da armadilha da D9: o mesmo Service, visto pelo objeto
    # Endpoints (que o codigo de producao nao le, D5), nao tem a chave
    # "subsets" nenhuma. Este teste prova que normalizar() trata as duas
    # formas -- chave ausente e valor nulo -- de modo identico, ainda que
    # so a segunda seja o caminho que cliente.py/modelo.py realmente usam.
    bruto_endpoints = _carregar("endpoints-nyx-stg.json")
    bruto_slices = _carregar("endpointslices-nyx-stg.json")
    endpoints_nyx_api = _item_por_nome(bruto_endpoints, "nyx-api")
    slice_nyx_api = _item_por_nome(bruto_slices, "nyx-api-4mqdq")

    assert "subsets" not in endpoints_nyx_api  # chave ausente
    assert slice_nyx_api["endpoints"] is None  # valor nulo

    subsets_normalizado = modelo.normalizar(endpoints_nyx_api.get("subsets"), [])
    endpoints_normalizado = modelo.normalizar(slice_nyx_api.get("endpoints"), [])

    assert subsets_normalizado == endpoints_normalizado == []


def test_service_com_endereco_parcialmente_pronto_mostra_2_de_3():
    fatia = {
        "metadata": {"labels": {"kubernetes.io/service-name": "s"}},
        "endpoints": [
            {"conditions": {"ready": True}},
            {"conditions": {"ready": True}},
            {"conditions": {"ready": False}},
        ],
    }
    exibido = modelo.interpretar_service({"metadata": {"name": "s"}}, [fatia])
    assert (exibido.prontos, exibido.total_enderecos) == (2, 3)
    assert modelo.estado_enderecos(2, 3) == modelo.PARCIAL


def test_service_nyx_postgres_com_todos_os_enderecos_prontos():
    bruto_slices = _carregar("endpointslices-nyx-stg.json")
    slice_postgres = _item_por_nome(bruto_slices, "nyx-postgres-kqc9f")
    exibido = modelo.interpretar_service(
        {"metadata": {"name": "nyx-postgres"}}, [slice_postgres]
    )
    assert (exibido.prontos, exibido.total_enderecos) == (1, 1)
    assert modelo.estado_enderecos(1, 1) == modelo.COMPLETO
    assert exibido.criterios == ()


# --------------------------------------------------------------------- 5.8
# Service sem endereço é sempre marcado anormal.


def test_service_sem_endereco_e_anormal_mesmo_com_todos_os_pods_do_namespace_prontos():
    # Todos os pods do namespace saudaveis -- exatamente o cenario do
    # Requirement "Um Service tem tres estados de endereco", cenario
    # "Service cujo seletor nao casa com pod nenhum". A variavel abaixo nao
    # e passada para interpretar_service em lugar nenhum: a funcao nao tem
    # como ler pod nenhum, entao o resultado nao pode depender dela -- essa
    # e a prova mais forte de que a marcacao de "sem endereco" independe do
    # estado dos pods.
    pods_do_namespace_todos_prontos = [
        modelo.interpretar_pod(
            {
                "metadata": {"name": "p1"},
                "status": {
                    "phase": "Running",
                    "containerStatuses": [{"ready": True, "restartCount": 0}],
                },
            }
        )
    ]
    assert pods_do_namespace_todos_prontos[0].criterios == ()  # todos prontos, de fato

    fatia_vazia = {"metadata": {"labels": {"kubernetes.io/service-name": "s"}}, "endpoints": None}
    exibido = modelo.interpretar_service({"metadata": {"name": "s"}}, [fatia_vazia])

    assert len(exibido.criterios) == 1
    assert exibido.criterios[0].peso == 4
    assert exibido.criterios[0].campo == "EndpointSlice.endpoints"


# ===========================================================================
# Grupo 6 — eventos e ordenação
# ===========================================================================

# --------------------------------------------------------------------- 6.1
# Janela de uma hora sobre lastTimestamp, com a fixture 2.5.


def test_eventos_fora_da_janela_de_uma_hora_nao_aparecem():
    bruto = _carregar("events-nyx-prod.json")
    # agora bem depois do lastTimestamp mais recente da fixture -> os dois
    # eventos capturados ficam fora da janela de 1h.
    instantes = [
        modelo._instante_como_data(modelo.instante_evento(ev)) for ev in bruto["items"]
    ]
    agora = max(instantes) + timedelta(hours=2)

    resultado = modelo.eventos_na_janela(bruto["items"], agora)

    assert resultado == []


def test_evento_dentro_da_janela_aparece():
    bruto = _carregar("events-nyx-prod.json")
    instantes = [
        modelo._instante_como_data(modelo.instante_evento(ev)) for ev in bruto["items"]
    ]
    agora = max(instantes)  # exatamente no instante do evento mais recente

    resultado = modelo.eventos_na_janela(bruto["items"], agora)

    assert len(resultado) == len(bruto["items"])  # os dois estao a poucos segundos


def test_evento_sem_nenhum_instante_e_excluido_da_janela():
    evento_sem_instante = {"type": "Normal", "reason": "X"}
    agora = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
    assert modelo.eventos_na_janela([evento_sem_instante], agora) == []


# --------------------------------------------------------------------- 6.2
# Ordenação do mais recente para o mais antigo; a ordem de entrada não
# influencia a de saída.


def test_ordenacao_de_eventos_nao_depende_da_ordem_de_entrada():
    e1 = {"metadata": {"name": "e1"}, "lastTimestamp": "2026-09-07T06:00:00Z"}
    e2 = {"metadata": {"name": "e2"}, "lastTimestamp": "2026-09-07T08:00:00Z"}
    e3 = {"metadata": {"name": "e3"}, "lastTimestamp": "2026-09-07T07:00:00Z"}

    ordem_a = modelo.ordenar_eventos([e1, e2, e3])
    ordem_b = modelo.ordenar_eventos([e3, e1, e2])
    ordem_c = modelo.ordenar_eventos([e2, e3, e1])

    nomes = lambda lista: [e["metadata"]["name"] for e in lista]
    assert nomes(ordem_a) == nomes(ordem_b) == nomes(ordem_c) == ["e2", "e3", "e1"]


# --------------------------------------------------------------------- 6.3
# Recuo para eventTime quando lastTimestamp vem ausente ou nulo.


def test_lastimestamp_ausente_e_lastimestamp_nulo_recuam_igual_para_eventtime():
    ausente = {"eventTime": "2026-09-07T06:00:00Z"}
    nulo = {"lastTimestamp": None, "eventTime": "2026-09-07T06:00:00Z"}

    assert modelo.instante_evento(ausente) == modelo.instante_evento(nulo) == (
        "2026-09-07T06:00:00Z"
    )


def test_lastimestamp_presente_tem_prioridade_sobre_eventtime():
    evento = {"lastTimestamp": "2026-09-07T06:00:00Z", "eventTime": "2026-09-07T09:00:00Z"}
    assert modelo.instante_evento(evento) == "2026-09-07T06:00:00Z"


# --------------------------------------------------------------------- 6.4
# Os cinco critérios de anormalidade, cada um a partir do seu próprio campo,
# sem que um derive de outro.


def test_criterio_de_reinicio_nao_depende_do_criterio_de_espera():
    # Reinicios > 0, mas nenhum container em waiting -- so o criterio de
    # peso 3 deve aparecer, nao o de peso 2.
    pod = {
        "metadata": {"name": "p"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {"ready": True, "restartCount": 5, "state": {"running": {}}}
            ],
        },
    }
    exibido = modelo.interpretar_pod(pod)
    pesos = {c.peso for c in exibido.criterios}
    assert pesos == {3}


def test_criterio_de_espera_nao_depende_do_criterio_de_reinicio():
    # Waiting reason presente, restartCount 0 -- so o criterio de peso 2 (e
    # o de peso 1, porque o container tambem nao esta pronto), nunca o 3.
    pod = {
        "metadata": {"name": "p"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {
                    "ready": False,
                    "restartCount": 0,
                    "state": {"waiting": {"reason": "ImagePullBackOff"}},
                }
            ],
        },
    }
    exibido = modelo.interpretar_pod(pod)
    pesos = {c.peso for c in exibido.criterios}
    assert pesos == {1, 2}
    assert 3 not in pesos


def test_os_cinco_criterios_apontam_um_campo_de_origem_nao_vazio():
    pod = {
        "metadata": {"name": "p"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {
                    "ready": False,
                    "restartCount": 1,
                    "state": {"waiting": {"reason": "CrashLoopBackOff"}},
                }
            ],
        },
    }
    controlador = {
        "metadata": {"name": "c", "generation": 1},
        "spec": {"replicas": 2},
        "status": {"observedGeneration": 1},
    }
    service = {"metadata": {"name": "s"}}
    fatia_vazia = [{"metadata": {"labels": {}}, "endpoints": None}]

    pod_exibido = modelo.interpretar_pod(pod)
    controlador_exibido = modelo.interpretar_controlador(controlador, tipo="Deployment")
    service_exibido = modelo.interpretar_service(service, fatia_vazia)

    eventos = modelo.eventos_warning_por_objeto(
        [
            {
                "type": "Warning",
                "reason": "BackOff",
                "involvedObject": {"kind": "Pod", "name": "p"},
            }
        ]
    )
    pod_com_evento = modelo.com_criterio_de_eventos(pod_exibido, "Pod", eventos)

    todos_os_criterios = (
        list(controlador_exibido.criterios)
        + list(service_exibido.criterios)
        + list(pod_com_evento.criterios)
    )
    pesos_encontrados = {c.peso for c in todos_os_criterios}
    assert pesos_encontrados == {1, 2, 3, 4, 5}
    assert all(c.campo for c in todos_os_criterios)  # nenhum critério sem campo de origem


# --------------------------------------------------------------------- 6.5
# Ordenação por anormalidade: degradado antes de saudável, com as fixtures
# 2.2 e 2.6.


def test_ordenacao_por_anormalidade_poe_degradado_antes_do_saudavel():
    orion_stg = _carregar("deployments-orion-stg.json")
    nyx_dev = _carregar("deployments-nyx-dev.json")
    orion_prod = _carregar("deployments-orion-prod.json")

    orion_web_degradado = modelo.interpretar_controlador(
        _item_por_nome(orion_stg, "orion-web"), tipo="Deployment"
    )
    orion_postgres_saudavel = modelo.interpretar_controlador(
        _item_por_nome(orion_stg, "orion-postgres"), tipo="Deployment"
    )
    nyx_api_saudavel = modelo.interpretar_controlador(
        _item_por_nome(nyx_dev, "nyx-api"), tipo="Deployment"
    )
    orion_web_saudavel_prod = modelo.interpretar_controlador(
        _item_por_nome(orion_prod, "orion-web"), tipo="Deployment"
    )

    assert orion_web_degradado.criterios != ()
    for saudavel in (orion_postgres_saudavel, nyx_api_saudavel, orion_web_saudavel_prod):
        assert saudavel.criterios == ()

    ordenado = modelo.ordenar_por_anormalidade(
        [
            orion_postgres_saudavel,
            orion_web_saudavel_prod,
            orion_web_degradado,
            nyx_api_saudavel,
        ]
    )

    assert ordenado[0] is orion_web_degradado
    # os saudaveis vem depois, em ordem alfabetica por nome
    nomes_saudaveis = [o.nome for o in ordenado[1:]]
    assert nomes_saudaveis == sorted(nomes_saudaveis)


# --------------------------------------------------------------------- 6.6
# Todo objeto ordenado como anormal carrega ao menos um critério exibível.


def test_todo_objeto_no_prefixo_anormal_carrega_pelo_menos_um_criterio():
    anormal_1 = modelo.PodExibido(
        nome="a",
        estado="CrashLoopBackOff",
        prontos=0,
        total_containers=1,
        reinicios=3,
        motivo=modelo.MotivoFalha(atual="CrashLoopBackOff", causa="OOMKilled"),
        sonda=modelo.Sonda(0, 1),
        criterios=(modelo.Criterio(peso=2, motivo="x", campo="y"),),
    )
    normal_1 = modelo.PodExibido(
        nome="b",
        estado="Running",
        prontos=1,
        total_containers=1,
        reinicios=0,
        motivo=modelo.MotivoFalha(atual=None, causa=None),
        sonda=modelo.Sonda(1, 1),
        criterios=(),
    )
    anormal_2 = modelo.ServiceExibido(
        nome="c", prontos=0, total_enderecos=0,
        criterios=(modelo.Criterio(peso=4, motivo="sem endereço", campo="EndpointSlice.endpoints"),),
    )

    ordenado = modelo.ordenar_por_anormalidade([normal_1, anormal_1, anormal_2])

    quantidade_anormal = sum(1 for o in [anormal_1, normal_1, anormal_2] if o.criterios)
    prefixo_anormal = ordenado[:quantidade_anormal]
    assert all(o.criterios for o in prefixo_anormal)
    assert all(len(o.criterios) >= 1 for o in prefixo_anormal)


# --------------------------------------------------------------------- extra
# Correlação de eventos Warning com objetos por (kind, nome) — o critério de
# peso 5 propriamente dito.


def test_evento_warning_marca_so_o_objeto_referenciado():
    pod_alvo = modelo.PodExibido(
        nome="alvo", estado="Running", prontos=1, total_containers=1, reinicios=0,
        motivo=modelo.MotivoFalha(None, None), sonda=modelo.Sonda(1, 1),
    )
    pod_outro = modelo.PodExibido(
        nome="outro", estado="Running", prontos=1, total_containers=1, reinicios=0,
        motivo=modelo.MotivoFalha(None, None), sonda=modelo.Sonda(1, 1),
    )
    eventos = [
        {
            "type": "Warning",
            "reason": "BackOff",
            "involvedObject": {"kind": "Pod", "name": "alvo"},
        },
        {
            "type": "Normal",
            "reason": "Scheduled",
            "involvedObject": {"kind": "Pod", "name": "outro"},
        },
    ]
    por_objeto = modelo.eventos_warning_por_objeto(eventos)

    alvo_marcado = modelo.com_criterio_de_eventos(pod_alvo, "Pod", por_objeto)
    outro_marcado = modelo.com_criterio_de_eventos(pod_outro, "Pod", por_objeto)

    assert len(alvo_marcado.criterios) == 1
    assert alvo_marcado.criterios[0].peso == 5
    assert outro_marcado.criterios == ()  # evento Normal nao conta, e nao e o mesmo nome
