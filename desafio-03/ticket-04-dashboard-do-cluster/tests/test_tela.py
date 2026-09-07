"""Testes da interface de terminal (`painel_cluster.tela`) — grupo 7.

Nenhum teste aqui toca rede nem importa `kubernetes`/`urllib3`: a `Leituras`
de `tela.py` existe justamente para que a tela inteira seja testável com
`Envelope`s fabricados, sem precisar simular exceção de transporte como
`test_cliente.py` faz — essa camada já foi coberta lá.

Os testes rodam a aplicação Textual de verdade, em modo headless
(`App.run_test`), e capturam o **texto** desenhado na tela — não a lista
interna de widgets — porque o que a spec pede é o que aparece, não como o
código monta. `capturar_texto()` reproduz a mesma lógica de
`App.export_screenshot()` (ver `textual.app`), trocando a exportação SVG por
texto simples (`rich.console.Console.export_text`).

Cada bloco está marcado com o número da tarefa de `tasks.md` que verifica.
Como as tarefas do grupo 7 não têm teste dedicado no enunciado original (a
verificação descrita em cada uma é "captura de texto" ou "verificar que"),
este arquivo é a prova em código do que cada tarefa pede.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest
from rich.console import Console

from painel_cluster.cliente import Destino, Envelope, EstadoEnvelope, Sessao
from painel_cluster.tela import Leituras, PainelClusterApp

FIXTURES = Path(__file__).parent / "fixtures"


def _carregar(nome: str) -> dict:
    with open(FIXTURES / nome) as f:
        return json.load(f)


def _sessao(contexto: str = "kind-metacortex-lab", servidor: str = "https://127.0.0.1:6443") -> Sessao:
    return Sessao(destino=Destino(contexto=contexto, servidor=servidor), api=None)


def _envelope_de_fixture(nome_arquivo: str) -> Envelope:
    return Envelope.de_itens(_carregar(nome_arquivo)["items"])


def capturar_texto(app: PainelClusterApp) -> str:
    """Renderiza a tela atual para texto simples, sem estilo — a mesma
    lógica de `App.export_screenshot()`, trocando a exportação SVG por
    `Console.export_text()`."""
    width, height = app.size
    console = Console(
        width=width,
        height=height,
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        record=True,
        legacy_windows=False,
        safe_box=False,
    )
    screen_render = app.screen._compositor.render_update(
        full=True, screen_stack=app._background_screens, simplify=False
    )
    console.print(screen_render)
    return console.export_text()


def _leituras_fixas(
    namespaces: list[str] = ("nyx-prod",),
    pods: Envelope | None = None,
    deployments: Envelope | None = None,
    statefulsets: Envelope | None = None,
    services: Envelope | None = None,
    endpointslices: Envelope | None = None,
    eventos: Envelope | None = None,
) -> Leituras:
    """Uma `Leituras` cujas sete funções sempre devolvem os mesmos envelopes,
    não importa o namespace pedido — para os testes em que só um cenário
    fixo interessa."""
    vazio = Envelope(EstadoEnvelope.VAZIO)
    return Leituras(
        namespaces=lambda s: Envelope.de_itens([{"metadata": {"name": n}} for n in namespaces]),
        pods=lambda s, ns: pods if pods is not None else vazio,
        deployments=lambda s, ns: deployments if deployments is not None else vazio,
        statefulsets=lambda s, ns: statefulsets if statefulsets is not None else vazio,
        services=lambda s, ns: services if services is not None else vazio,
        endpointslices=lambda s, ns: endpointslices if endpointslices is not None else vazio,
        eventos=lambda s, ns: eventos if eventos is not None else vazio,
    )


def _leituras_saudaveis() -> Leituras:
    return _leituras_fixas(
        namespaces=["nyx-dev", "nyx-prod"],
        pods=_envelope_de_fixture("pods-nyx-prod.json"),
        deployments=_envelope_de_fixture("deployments-orion-stg.json"),
        statefulsets=_envelope_de_fixture("statefulsets-nyx-dev.json"),
        services=Envelope.de_itens(
            [
                {
                    "metadata": {"name": "nyx-api"},
                    "spec": {"type": "ClusterIP", "ports": [{"port": 80, "protocol": "TCP"}]},
                }
            ]
        ),
        endpointslices=_envelope_de_fixture("endpointslices-nyx-stg.json"),
        eventos=_envelope_de_fixture("events-nyx-prod.json"),
    )


def _run(coro):
    return asyncio.run(coro)


# =========================================================================
# 7.1 — estrutura com os cinco painéis
# =========================================================================


def test_os_cinco_paineis_aparecem_na_tela():
    async def cenario():
        app = PainelClusterApp(sessao=_sessao(), leituras=_leituras_saudaveis())
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            for titulo in ("Namespaces", "Pods", "Controladores", "Services", "Eventos"):
                assert titulo in texto, f"painel {titulo!r} não apareceu na captura"

    _run(cenario())


# =========================================================================
# 7.2 — contexto e servidor visíveis permanentemente, inclusive em falha
# =========================================================================


def test_contexto_e_servidor_visiveis_com_tudo_ok():
    async def cenario():
        app = PainelClusterApp(
            sessao=_sessao("kind-metacortex-lab", "https://127.0.0.1:6443"),
            leituras=_leituras_saudaveis(),
        )
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            assert "contexto: kind-metacortex-lab" in texto
            assert "servidor: https://127.0.0.1:6443" in texto

    _run(cenario())


def test_contexto_e_servidor_visiveis_com_credencial_recusada():
    async def cenario():
        indisp = Envelope.indisponivel("credencial recusada")
        leituras = Leituras(
            namespaces=lambda s: indisp,
            pods=lambda s, ns: indisp,
            deployments=lambda s, ns: indisp,
            statefulsets=lambda s, ns: indisp,
            services=lambda s, ns: indisp,
            endpointslices=lambda s, ns: indisp,
            eventos=lambda s, ns: indisp,
        )
        app = PainelClusterApp(
            sessao=_sessao("ctx-x", "https://servidor.invalid:6443"), leituras=leituras
        )
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            assert "contexto: ctx-x" in texto
            assert "servidor: https://servidor.invalid:6443" in texto
            assert "credencial recusada" in texto
            assert "Traceback" not in texto

    _run(cenario())


def test_contexto_e_servidor_visiveis_com_cluster_inalcancavel():
    async def cenario():
        indisp = Envelope.indisponivel("cluster nao respondeu em https://servidor.invalid:6443")
        leituras = Leituras(
            namespaces=lambda s: indisp,
            pods=lambda s, ns: indisp,
            deployments=lambda s, ns: indisp,
            statefulsets=lambda s, ns: indisp,
            services=lambda s, ns: indisp,
            endpointslices=lambda s, ns: indisp,
            eventos=lambda s, ns: indisp,
        )
        app = PainelClusterApp(
            sessao=_sessao("ctx-x", "https://servidor.invalid:6443"), leituras=leituras
        )
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            assert "contexto: ctx-x" in texto
            assert "servidor: https://servidor.invalid:6443" in texto
            # Requirement "Cluster inalcançável": o endereço tentado aparece.
            assert "servidor.invalid:6443" in texto
            assert "Traceback" not in texto

    _run(cenario())


# =========================================================================
# 7.3 — seleção de namespace escopa os demais painéis
# =========================================================================


def test_trocar_de_namespace_troca_o_conteudo_dos_paineis():
    async def cenario():
        chamadas = []

        def pods_por_ns(s, ns):
            chamadas.append(ns)
            if ns == "nyx-dev":
                return Envelope.de_itens([{"metadata": {"name": "pod-do-dev"}}])
            return Envelope.de_itens([{"metadata": {"name": "pod-do-prod"}}])

        leituras = Leituras(
            namespaces=lambda s: Envelope.de_itens(
                [{"metadata": {"name": "nyx-dev"}}, {"metadata": {"name": "nyx-prod"}}]
            ),
            pods=pods_por_ns,
            deployments=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            statefulsets=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            services=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            endpointslices=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            eventos=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
        )
        app = PainelClusterApp(sessao=_sessao(), leituras=leituras)
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            assert app.namespace_selecionado == "nyx-dev"  # primeiro em ordem alfabética
            texto = capturar_texto(app)
            assert "pod-do-dev" in texto
            assert "pod-do-prod" not in texto

            # Troca de namespace pelas setas, como a spec descreve (↑ ↓
            # movem a seleção no painel focado). A troca dispara um worker
            # assíncrono (`_trocar_namespace`); espera-lo terminar de
            # verdade em vez de um `pause` com tempo fixo evita um teste
            # instável sob carga de máquina variável.
            app.query_one("#lista-namespaces").focus()
            await pilot.press("down")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert app.namespace_selecionado == "nyx-prod"
            texto2 = capturar_texto(app)
            assert "pod-do-prod" in texto2
            assert "pod-do-dev" not in texto2

    _run(cenario())


# =========================================================================
# 7.4 — busca por trecho de nome e limpeza
# =========================================================================


def test_busca_por_postgres_filtra_todos_os_paineis():
    async def cenario():
        app = PainelClusterApp(sessao=_sessao(), leituras=_leituras_saudaveis())
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto_antes = capturar_texto(app)
            assert "nyx-postgres" in texto_antes
            assert "orion-web" in texto_antes  # deployment do orion-stg, sem 'postgres' no nome

            await pilot.press("slash")
            for ch in "postgres":
                await pilot.press(ch)
            await pilot.pause()

            texto_filtrado = capturar_texto(app)
            assert "nyx-postgres" in texto_filtrado
            assert "orion-web" not in texto_filtrado

    _run(cenario())


def test_limpar_busca_com_escape_restaura_todos_os_objetos():
    async def cenario():
        app = PainelClusterApp(sessao=_sessao(), leituras=_leituras_saudaveis())
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            await pilot.press("slash")
            for ch in "postgres":
                await pilot.press(ch)
            await pilot.pause()
            assert app.busca == "postgres"

            await pilot.press("escape")
            await pilot.pause()

            assert app.busca == ""
            texto = capturar_texto(app)
            assert "orion-web" in texto

    _run(cenario())


# =========================================================================
# 7.5 — os quatro estados do envelope, desenhados de forma distinguível
# =========================================================================


def test_os_quatro_estados_do_envelope_sao_visualmente_distintos():
    async def cenario():
        ok = Envelope.de_itens([{"metadata": {"name": "p1"}, "status": {"phase": "Running"}}])
        vazio = Envelope(EstadoEnvelope.VAZIO)
        negado = Envelope.negado("sem permissao para ler pods")
        indisponivel = Envelope.indisponivel("cluster nao respondeu em https://x.invalid")

        textos = {}
        for rotulo, envelope in (
            ("ok", ok),
            ("vazio", vazio),
            ("negado", negado),
            ("indisponivel", indisponivel),
        ):
            leituras = _leituras_fixas(pods=envelope)
            app = PainelClusterApp(sessao=_sessao(), leituras=leituras)
            async with app.run_test(size=(170, 60)) as pilot:
                await pilot.pause()
                texto = capturar_texto(app)
                # A seção de Pods, isolada do resto da tela, para não
                # confundir a mensagem de um painel com a de outro.
                secao = texto.split("Pods", 1)[1].split("Controladores", 1)[0]
                textos[rotulo] = secao

        assert "p1" in textos["ok"]
        assert "nenhum objeto neste namespace" in textos["vazio"]
        assert "sem permissão para ler pods" in textos["negado"]
        assert "cluster não respondeu" in textos["indisponivel"]

        # Os quatro textos são distinguíveis dois a dois.
        valores = list(textos.values())
        assert len(set(valores)) == 4

    _run(cenario())


def test_negado_num_tipo_nao_esvazia_os_demais_paineis():
    # Requirement "Cada estado do envelope tem desenho próprio", cenário
    # "Painel sem permissão": os demais painéis continuam com seus objetos.
    async def cenario():
        leituras = _leituras_fixas(
            pods=Envelope.de_itens([{"metadata": {"name": "p1"}, "status": {"phase": "Running"}}]),
            eventos=Envelope.negado("sem permissao para ler eventos"),
        )
        app = PainelClusterApp(sessao=_sessao(), leituras=leituras)
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            assert "p1" in texto
            assert "sem permissão para ler eventos" in texto

    _run(cenario())


# =========================================================================
# 7.6 — atualização em intervalo fixo, com ritmo próprio para namespaces
# =========================================================================


def test_intervalo_de_objetos_e_de_namespaces_sao_independentes():
    async def cenario():
        contagem = {"objetos": 0, "namespaces": 0}

        def contar_pods(s, ns):
            contagem["objetos"] += 1
            return Envelope(EstadoEnvelope.VAZIO)

        def contar_namespaces(s):
            contagem["namespaces"] += 1
            return Envelope.de_itens([{"metadata": {"name": "ns1"}}])

        leituras = Leituras(
            namespaces=contar_namespaces,
            pods=contar_pods,
            deployments=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            statefulsets=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            services=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            endpointslices=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            eventos=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
        )
        # objetos recarrega muitas vezes num intervalo curto; namespaces
        # tem um intervalo bem mais longo, que não deve disparar de novo
        # nesse tempo — exatamente a garantia que a tarefa 7.6 pede.
        app = PainelClusterApp(
            sessao=_sessao(),
            leituras=leituras,
            intervalo_objetos=0.05,
            intervalo_namespaces=999.0,
        )
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause(0.30)
            # 1 leitura inicial (on_mount) + pelo menos mais uma do timer.
            assert contagem["objetos"] >= 3, contagem
            assert contagem["namespaces"] == 1, contagem

    _run(cenario())


# =========================================================================
# 7.7 — atualização sob comando e idade do dado
# =========================================================================


def _idade_objetos(texto_status: str) -> int:
    m = re.search(r"objetos: atualizado há (\d+)", texto_status)
    assert m, f"idade do dado nao encontrada em {texto_status!r}"
    return int(m.group(1))


def test_idade_do_dado_aparece_e_comando_r_zera(monkeypatch):
    async def cenario():
        contagem = {"n": 0}

        def contar(s, ns):
            contagem["n"] += 1
            return Envelope(EstadoEnvelope.VAZIO)

        leituras = _leituras_fixas()
        leituras = Leituras(
            namespaces=lambda s: Envelope.de_itens([{"metadata": {"name": "ns1"}}]),
            pods=contar,
            deployments=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            statefulsets=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            services=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            endpointslices=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
            eventos=lambda s, ns: Envelope(EstadoEnvelope.VAZIO),
        )
        # Intervalos longos o bastante para não recarregar sozinho durante
        # o teste — só o comando 'r' deve mexer na idade do dado.
        app = PainelClusterApp(
            sessao=_sessao(), leituras=leituras, intervalo_objetos=999.0, intervalo_namespaces=999.0
        )
        async with app.run_test(size=(170, 60)) as pilot:
            await pilot.pause()
            status_inicial = capturar_texto(app).splitlines()[1]
            assert "objetos: atualizado há" in status_inicial
            assert _idade_objetos(status_inicial) == 0

            await asyncio.sleep(1.3)
            app._renderizar_tudo()  # o relógio de 1s também chamaria isto
            await pilot.pause()
            status_depois_de_esperar = capturar_texto(app).splitlines()[1]
            assert _idade_objetos(status_depois_de_esperar) >= 1

            leituras_antes_do_r = contagem["n"]
            await pilot.press("r")
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert contagem["n"] > leituras_antes_do_r, "comando 'r' deveria reler agora"

            status_apos_r = capturar_texto(app).splitlines()[1]
            assert _idade_objetos(status_apos_r) == 0

    _run(cenario())


# =========================================================================
# 7.8 — coluna de critério de anormalidade
# =========================================================================


def test_criterio_de_anormalidade_aparece_na_linha_do_objeto():
    async def cenario():
        leituras = _leituras_fixas(pods=_envelope_de_fixture("pods-nyx-prod.json"))
        app = PainelClusterApp(sessao=_sessao(), leituras=leituras)
        async with app.run_test(size=(200, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            # O pod nyx-api do nyx-prod está em CrashLoopBackOff (fixture
            # 2.1) — o critério de peso 2 ("em espera: ...") tem que
            # aparecer na mesma linha do nome do pod.
            for linha in texto.splitlines():
                if "nyx-api-79c5f4d8d7" in linha:
                    assert "⚠" in linha and "em espera" in linha, linha
                    break
            else:
                pytest.fail("linha do pod nyx-api nao encontrada na captura")

    _run(cenario())


def test_objeto_sem_criterio_mostra_travessao_na_coluna_por_que():
    async def cenario():
        pods = Envelope.de_itens(
            [
                {
                    "metadata": {"name": "pod-saudavel", "creationTimestamp": "2024-01-01T00:00:00Z"},
                    "status": {
                        "phase": "Running",
                        "containerStatuses": [{"ready": True, "restartCount": 0}],
                    },
                    "spec": {"containers": [{}]},
                }
            ]
        )
        leituras = _leituras_fixas(pods=pods)
        app = PainelClusterApp(sessao=_sessao(), leituras=leituras)
        async with app.run_test(size=(200, 60)) as pilot:
            await pilot.pause()
            texto = capturar_texto(app)
            for linha in texto.splitlines():
                if "pod-saudavel" in linha:
                    assert "⚠" not in linha
                    break
            else:
                pytest.fail("linha do pod-saudavel nao encontrada na captura")

    _run(cenario())
