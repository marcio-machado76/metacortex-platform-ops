"""Driver de validação do grupo 10 (`openspec/changes/adicionar-painel-de-cluster/tasks.md`).

Ferramenta de VERIFICAÇÃO, escrita por fora da implementação — não faz parte
do pacote `painel_cluster`, não é importada por ele, e não altera nenhum
arquivo do projeto. Só lê.

Sobe a aplicação Textual de verdade (`PainelClusterApp`), com uma `Sessao`
real produzida por `painel_cluster.cliente.conectar()` — ou seja, toda
chamada à API do cluster passa pelo código de produção inalterado. Roda em
modo headless (`App.run_test`, a mesma técnica que `tests/test_tela.py` já
usa) e captura o texto desenhado na tela com a mesma lógica de
`capturar_texto()` daquele arquivo (comentário ali: "a mesma lógica de
`App.export_screenshot()`, trocando a exportação SVG por
`Console.export_text()`").

Uso:
    KUBECONFIG=/tmp/painel-cluster-validacao/kubeconfig \
    .venv/bin/python /tmp/painel-cluster-validacao/validar-criterios-de-aceite.py <cenario>

Cenários: dev, prod-stg-orionstg, orion-prod, sem-events, cert-vencido,
endereco-morto, busca
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve()))

REPO = Path("/home/marcio/Documentos/pos-graduacao/desafios/desafios-skills/"
            "metacortex-platform-ops/metacortex-platform-ops/desafio-03/"
            "ticket-04-dashboard-do-cluster")
sys.path.insert(0, str(REPO / "src"))

from rich.console import Console  # noqa: E402

from painel_cluster import cliente  # noqa: E402
from painel_cluster.tela import PainelClusterApp  # noqa: E402


def capturar_texto(app: PainelClusterApp) -> str:
    """Idêntica a `tests/test_tela.py:capturar_texto` — reaproduzida aqui
    porque este script vive fora do pacote de testes."""
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


def linha(t: str) -> None:
    print()
    print("=" * 88)
    print(t)
    print("=" * 88)


async def _subir_e_esperar(app: PainelClusterApp, pilot, ciclos: int = 3, espera: float = 0.6):
    """Espera o primeiro ciclo de leitura terminar. As leituras são reais
    (thread + chamada de rede), então usa `workers.wait_for_complete()` mais
    algumas pausas — o mesmo padrão de `tests/test_tela.py`."""
    await pilot.pause()
    for _ in range(ciclos):
        await app.workers.wait_for_complete()
        await pilot.pause(espera)


async def navegar_para(pilot, app: PainelClusterApp, alvo_ns: str, todos_ns_ordenados: list[str]):
    app.query_one("#lista-namespaces").focus()
    atual_idx = todos_ns_ordenados.index(app.namespace_selecionado)
    alvo_idx = todos_ns_ordenados.index(alvo_ns)
    passos = alvo_idx - atual_idx
    tecla = "down" if passos > 0 else "up"
    for _ in range(abs(passos)):
        await pilot.press(tecla)
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause(0.3)
    assert app.namespace_selecionado == alvo_ns, (app.namespace_selecionado, alvo_ns)


def conectar(kubeconfig: str | None):
    sessao = cliente.conectar(kubeconfig)
    print(f"contexto resolvido : {sessao.destino.contexto}")
    print(f"servidor resolvido : {sessao.destino.servidor}")
    return sessao


NAMESPACES_ORDENADOS = ["nyx-dev", "nyx-prod", "nyx-stg", "orion-prod", "orion-stg"]


async def cenario_namespace(kubeconfig: str | None, namespace: str, tamanho=(230, 70)):
    sessao = conectar(kubeconfig)
    app = PainelClusterApp(sessao=sessao)
    async with app.run_test(size=tamanho) as pilot:
        await _subir_e_esperar(app, pilot)
        print(f"namespaces carregados: {app.namespaces}")
        if not app.namespaces or app.namespace_selecionado is None:
            print("nenhum namespace disponivel (leitura de namespaces nao chegou a 'ok') "
                  "- capturando o estado da tela como esta, sem navegar")
        elif app.namespace_selecionado != namespace:
            await navegar_para(pilot, app, namespace, list(app.namespaces))
        else:
            await app.workers.wait_for_complete()
            await pilot.pause(0.3)
        print(f"namespace selecionado: {app.namespace_selecionado}")
        texto = capturar_texto(app)
        print(texto)


async def cenario_busca(kubeconfig: str | None, namespace: str, termo: str, tamanho=(230, 70)):
    sessao = conectar(kubeconfig)
    app = PainelClusterApp(sessao=sessao)
    async with app.run_test(size=tamanho) as pilot:
        await _subir_e_esperar(app, pilot)
        if app.namespace_selecionado != namespace:
            await navegar_para(pilot, app, namespace, list(app.namespaces))
        print(f"namespace selecionado: {app.namespace_selecionado}")
        print("\n--- ANTES DA BUSCA ---")
        print(capturar_texto(app))

        await pilot.press("slash")
        for ch in termo:
            await pilot.press(ch)
        await pilot.pause()
        print(f"\n--- DEPOIS DE BUSCAR {termo!r} (app.busca={app.busca!r}) ---")
        print(capturar_texto(app))

        await pilot.press("escape")
        await pilot.pause()
        print(f"\n--- DEPOIS DE Esc (app.busca={app.busca!r}) ---")
        print(capturar_texto(app))


def main():
    cenario = sys.argv[1]
    kubeconfig = sys.argv[2] if len(sys.argv) > 2 else None

    if cenario == "dev":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-dev"))
    elif cenario == "prod":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-prod"))
    elif cenario == "stg":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-stg"))
    elif cenario == "orion-prod":
        asyncio.run(cenario_namespace(kubeconfig, "orion-prod"))
    elif cenario == "orion-stg":
        asyncio.run(cenario_namespace(kubeconfig, "orion-stg"))
    elif cenario == "sem-events":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-prod"))
    elif cenario == "cert-vencido":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-dev", tamanho=(170, 50)))
    elif cenario == "endereco-morto":
        asyncio.run(cenario_namespace(kubeconfig, "nyx-dev", tamanho=(170, 50)))
    elif cenario == "busca":
        asyncio.run(cenario_busca(kubeconfig, "nyx-prod", "postgres"))
    elif cenario == "platform-ro-sessao":
        # critério 10 / tarefa 10.10 — sessão completa sob platform-ro:
        # troca de 3 namespaces + busca + refresh, tudo leitura.
        asyncio.run(cenario_sessao_platform_ro(kubeconfig))
    else:
        print(f"cenario desconhecido: {cenario}", file=sys.stderr)
        raise SystemExit(1)


async def cenario_sessao_platform_ro(kubeconfig: str | None):
    sessao = conectar(kubeconfig)
    app = PainelClusterApp(sessao=sessao)
    async with app.run_test(size=(230, 70)) as pilot:
        await _subir_e_esperar(app, pilot)
        for ns in ["nyx-dev", "nyx-prod", "nyx-stg", "orion-prod", "orion-stg"]:
            await navegar_para(pilot, app, ns, list(app.namespaces))
            print(f"-- lido namespace {ns} --")
        await pilot.press("slash")
        for ch in "postgres":
            await pilot.press(ch)
        await pilot.pause()
        print(f"busca aplicada: {app.busca!r}")
        await pilot.press("escape")
        await pilot.press("r")
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause(0.5)
        print("comando 'r' executado")
        print(capturar_texto(app))
        await pilot.press("q")
        await pilot.pause()
    print("sessao encerrada por 'q', sem excecao")


if __name__ == "__main__":
    main()
