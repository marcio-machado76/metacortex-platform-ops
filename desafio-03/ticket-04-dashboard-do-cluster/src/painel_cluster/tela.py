"""Interface de terminal (grupo 7 do `tasks.md`).

Consome o retrato de `modelo.py` — que por sua vez interpreta o JSON cru que
`cliente.py` devolve dentro de um `Envelope` — e desenha os painéis com
Textual. Este módulo:

  - não faz rede: toda leitura passa pelas funções injetadas em `Leituras`,
    por padrão as de `cliente.py`, chamadas em thread separada
    (`asyncio.to_thread`) para não bloquear o laço de eventos do Textual;
  - **não** contém a string literal `import kubernetes` nem `import urllib3`
    em lugar nenhum do seu próprio texto-fonte — é o que o teste de
    contenção do grupo 8 verifica. Importar `painel_cluster.cliente` para
    reaproveitar os tipos `Envelope`, `EstadoEnvelope`, `Destino` e `Sessao`
    não viola essa regra: a regra é sobre os dois pacotes de terceiros
    (`kubernetes`, `urllib3`), não sobre o módulo `cliente` em si — que é
    exatamente o ponto por onde o resto do projeto recebe o envelope (D-C do
    `design.md`). O ponto de entrada (`cli.py`, grupo 9) faz o mesmo import
    pelo mesmo motivo: alguém precisa chamar `cliente.conectar()`.

## Duas lacunas herdadas do `modelo.py`, preenchidas aqui

`01-comportamento.md` pede duas colunas que os dataclasses de `modelo.py`
não carregam: **idade** do pod (`metadata.creationTimestamp`) e **tipo** /
**portas** do Service (`spec.type`, `spec.ports`). Nenhuma das duas passa
pela armadilha ausente/nulo/vazio que motiva `modelo.py` existir — são
leituras diretas, sem "zero afirmado contra nada afirmado" para decidir —
então em vez de alterar um módulo de fora do meu escopo (grupos 4/5/6, já
testado por outra onda), este módulo lê o campo bruto direto do item do
envelope, usando o mesmo `modelo.normalizar()` público que a D9 já
padronizou. Ver `docs/03-divergencias-da-implementacao.md` para o registro
formal desta lacuna.

## Onde este módulo decidiu sozinho, porque a spec não dizia

Estão documentadas no ponto em que aparecem, com uma âncora `# DECISÃO:` para
quem revisar. O resumo, para quem só quer a lista:

  - Como o Tab alterna foco quando existem quatro painéis de objeto, não um
    só (a spec descreve um alternador de dois estados).
  - Como o painel de Services se comporta quando `services` está `ok` mas
    `endpointslices` não está — a spec nunca cobre o cruzamento de dois
    envelopes dentro do mesmo painel.
  - Como o painel de Controladores se comporta quando `deployments` e
    `statefulsets` chegam em estados diferentes.
  - Que existe um estado "tela inteira" para os dois ambientes hostis que
    afetam todos os tipos ao mesmo tempo (credencial recusada, cluster
    inalcançável), além do desenho por painel que a spec exige explicitamente.
  - Se a busca por nome também filtra a lista de eventos (a spec só fala de
    "objetos").
  - Onde a idade do dado aparece — pergunta que o `design.md` deixa
    explicitamente em aberto.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import DataTable, Input, ListView, ListItem, Label, Static

from . import modelo
from .cliente import Destino, Envelope, EstadoEnvelope, Sessao

__all__ = ["Leituras", "PainelClusterApp"]


# ---------------------------------------------------------------------------
# Injeção das funções de leitura — permite testar a tela inteira sem rede,
# sem precisar simular exceção de `kubernetes`/`urllib3` como os testes de
# `cliente.py` fazem. Um teste de tela passa uma `Leituras` cujas funções
# devolvem `Envelope` prontos; a tela nunca sabe se eles vieram do cluster ou
# de um dublê.
# ---------------------------------------------------------------------------

LeitorNamespaces = Callable[[Sessao], Envelope]
LeitorTipo = Callable[[Sessao, str], Envelope]


@dataclasses.dataclass(frozen=True)
class Leituras:
    """As sete funções de leitura que a tela chama a cada ciclo. `padrao()`
    aponta para as de `cliente.py`; os testes do grupo 7 constroem a sua
    própria instância com funções que devolvem envelopes fabricados."""

    namespaces: LeitorNamespaces
    pods: LeitorTipo
    deployments: LeitorTipo
    statefulsets: LeitorTipo
    services: LeitorTipo
    endpointslices: LeitorTipo
    eventos: LeitorTipo

    @classmethod
    def padrao(cls) -> "Leituras":
        from . import cliente

        return cls(
            namespaces=cliente.ler_namespaces,
            pods=cliente.ler_pods,
            deployments=cliente.ler_deployments,
            statefulsets=cliente.ler_statefulsets,
            services=cliente.ler_services,
            endpointslices=cliente.ler_endpointslices,
            eventos=cliente.ler_eventos,
        )


@dataclasses.dataclass
class _EnvelopesObjetos:
    """Os seis envelopes de escopo de namespace do ciclo mais recente."""

    pods: Envelope
    deployments: Envelope
    statefulsets: Envelope
    services: Envelope
    endpointslices: Envelope
    eventos: Envelope


_ENVELOPE_VAZIO_INICIAL = Envelope(EstadoEnvelope.VAZIO)
_ENVELOPES_INICIAIS = _EnvelopesObjetos(
    pods=_ENVELOPE_VAZIO_INICIAL,
    deployments=_ENVELOPE_VAZIO_INICIAL,
    statefulsets=_ENVELOPE_VAZIO_INICIAL,
    services=_ENVELOPE_VAZIO_INICIAL,
    endpointslices=_ENVELOPE_VAZIO_INICIAL,
    eventos=_ENVELOPE_VAZIO_INICIAL,
)


# ---------------------------------------------------------------------------
# Formatação — funções puras, sem estado, fáceis de testar isoladamente.
# Nenhuma delas afirma saúde (D7 / Requirement "A tela relata, e não afirma
# saúde"): traduzem o vocabulário que `modelo.py` já calculou para texto, sem
# inventar um julgamento nôvo.
# ---------------------------------------------------------------------------


def formatar_duracao(delta: timedelta) -> str:
    """Humaniza um intervalo de tempo — usado tanto para a idade de um pod
    (`metadata.creationTimestamp`) quanto para a idade do dado da tela
    ("atualizado há Ns"). É o mesmo conceito — tempo decorrido — em dois
    lugares, por isso uma função só."""
    segundos = max(0, int(delta.total_seconds()))
    if segundos < 60:
        return f"{segundos}s"
    minutos, segundos = divmod(segundos, 60)
    if minutos < 60:
        return f"{minutos}m{segundos}s" if segundos else f"{minutos}m"
    horas, minutos = divmod(minutos, 60)
    if horas < 24:
        return f"{horas}h{minutos}m" if minutos else f"{horas}h"
    dias, horas = divmod(horas, 24)
    return f"{dias}d{horas}h" if horas else f"{dias}d"


def _instante_como_data(valor: str) -> datetime:
    """Mesma conversão de `modelo._instante_como_data`, duplicada de
    propósito: a original é privada (fora de `__all__`), e este módulo não
    lê internals de `modelo.py` — só o que ele expõe."""
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def idade_pod(pod: dict, agora: datetime) -> str:
    """Coluna "idade" da tabela de Pods (`01-comportamento.md`), calculada
    direto de `metadata.creationTimestamp` — não passa por `modelo.py`
    porque `PodExibido` não carrega este campo (lacuna registrada no
    docstring do módulo)."""
    criado_em = modelo.normalizar(pod.get("metadata"), {}).get("creationTimestamp")
    if not criado_em:
        return "—"
    return formatar_duracao(agora - _instante_como_data(criado_em))


def texto_sonda(sonda: "modelo.Sonda") -> str:
    """`—` sem sonda num pod de um container só; `✓` com sonda num pod de um
    container só; `N/M` em pod com mais de um container, sempre como
    contagem — nunca reduzido a um sim/não (Requirement "Ausência de sonda
    de prontidão é exibida como fato")."""
    if sonda.total <= 1:
        return "✓" if sonda.com_sonda > 0 else "—"
    return f"{sonda.com_sonda}/{sonda.total}"


def texto_motivo_pod(motivo: "modelo.MotivoFalha") -> str:
    if not motivo.atual:
        return "—"
    if motivo.causa:
        return f"{motivo.atual} (causa: {motivo.causa})"
    return motivo.atual


def texto_condicao(condicao: "modelo.Condicao | None") -> str:
    """`—` quando a API não fornece condição para este tipo de controlador
    (StatefulSet) — ausência de dado, não estado ruim (Requirement "Condição
    de controlador só existe onde a API a fornece")."""
    if condicao is None:
        return "—"
    return f"{condicao.tipo}={condicao.status}"


def texto_criterios(criterios: tuple["modelo.Criterio", ...]) -> str:
    """A coluna "por quê" (D-F do `design.md`): todos os critérios
    satisfeitos, não só o mais grave — auditabilidade completa."""
    if not criterios:
        return "—"
    return "⚠ " + "; ".join(c.motivo for c in criterios)


def texto_portas_service(spec: dict) -> str:
    portas = modelo.normalizar(spec.get("ports"), [])
    if not portas:
        return "—"
    partes = []
    for p in portas:
        porta = p.get("port")
        protocolo = p.get("protocol") or "TCP"
        partes.append(f"{porta}/{protocolo}")
    return ", ".join(partes)


def texto_enderecos_service(
    prontos: int, total: int, motivo_indisponibilidade: str | None
) -> str:
    """As três formas de `01-comportamento.md` ("sem endereço", "N de M
    prontos", "N prontos"), mais uma quarta que a spec não cobre: quando o
    envelope de `endpointslices` não está `ok`/`vazio` mas o de `services`
    está — ver `# DECISÃO` na função que monta a linha de Services."""
    if motivo_indisponibilidade is not None:
        return f"endereços indisponíveis — {motivo_indisponibilidade}"
    if total == 0:
        return "⚠ sem endereço"
    if prontos == total:
        return f"{prontos} prontos"
    return f"{prontos} de {total} prontos"


# ---------------------------------------------------------------------------
# Texto de estado de envelope — o que cada painel mostra quando não está
# `ok` com itens. A fronteira (`cliente.py`) já registra, no `motivo`, um
# texto curto "voltado a máquina" (docs/03-divergencias-da-implementacao.md,
# item 2); a frase final que aparece na tela é responsabilidade desta
# camada, não um repasse literal de `envelope.motivo` — a mesma divisão que
# a onda anterior já tinha decidido para `cliente.py`.
# ---------------------------------------------------------------------------


def texto_estado_envelope(rotulo_tipo: str, envelope: Envelope) -> str | None:
    """`None` quando o envelope tem itens para desenhar (chamador deve
    mostrar a tabela); texto da mensagem nos outros três estados."""
    if envelope.estado in (EstadoEnvelope.OK,):
        return None
    if envelope.estado == EstadoEnvelope.VAZIO:
        return "nenhum objeto neste namespace"
    if envelope.estado == EstadoEnvelope.NEGADO:
        return f"sem permissão para ler {rotulo_tipo}"
    # INDISPONIVEL: o motivo carrega o fato que esta camada não pode
    # reconstruir sozinha — endereço tentado, ou "credencial recusada", ou o
    # status HTTP do 5xx (D-D do design.md: a classificação já aconteceu na
    # fronteira; aqui só se exibe o que ela apurou).
    return f"cluster não respondeu — {envelope.motivo}"


def _todos_indisponiveis(envelopes: list[Envelope]) -> bool:
    """Verdadeiro quando **todo** envelope do ciclo está `indisponivel` — o
    sinal estrutural (não uma leitura de texto de exceção) de que a falha é
    de sessão inteira (credencial ou transporte), não de um tipo isolado.

    # DECISÃO: `01-comportamento.md` pede uma "tela inteira em estado de
    # indisponibilidade" para os dois ambientes hostis que afetam a sessão
    # toda, mas `cliente.py` só devolve envelope por tipo — não existe um
    # sinal de sessão. Como uma falha de credencial ou de transporte atinge
    # todas as chamadas do mesmo ciclo da mesma forma, o fato de todos os
    # envelopes lidos no ciclo virem `indisponivel` é equivalente, sem
    # reclassificar exceção nenhuma aqui (D-D continua valendo: a
    # classificação mora só na fronteira). Ver docstring do módulo.
    """
    return bool(envelopes) and all(e.estado == EstadoEnvelope.INDISPONIVEL for e in envelopes)


def _motivo_hostil_de_sessao(
    envelope_namespaces: Envelope, envelopes_objetos: list[Envelope], namespace_selecionado: str | None
) -> str | None:
    """O motivo do banner de "tela inteira indisponível", ou `None` quando a
    sessão não está nesse estado.

    Dois casos levam a essa leitura: (1) a própria leitura de namespaces —
    de escopo de cluster, tentada mesmo sem namespace selecionado — veio
    `indisponivel`, o que por si só já significa sessão inteira comprometida
    (não há como haver namespace selecionado se a lista nunca chegou); ou
    (2) há namespace selecionado e todos os seis tipos de escopo de
    namespace vieram `indisponivel` no mesmo ciclo. Sem o primeiro caso, uma
    sessão que falha antes de qualquer namespace existir nunca dispararia o
    banner, porque os seis envelopes de objeto ficariam nos valores
    iniciais (`vazio`), não `indisponivel` — eles nunca chegam a ser lidos."""
    if envelope_namespaces.estado == EstadoEnvelope.INDISPONIVEL:
        return envelope_namespaces.motivo
    if namespace_selecionado and _todos_indisponiveis(envelopes_objetos):
        return envelopes_objetos[0].motivo
    return None


# ---------------------------------------------------------------------------
# A aplicação
# ---------------------------------------------------------------------------


class PainelClusterApp(App[None]):
    """A tela do `painel-cluster` (Requirement "interface-de-terminal").

    Recebe uma `Sessao` já conectada (produzida por `cliente.conectar()`, no
    ponto de entrada) e, opcionalmente, uma `Leituras` para testes. Nunca
    troca de contexto — a `Sessao` é fixa pela vida inteira do processo
    (Requirement "Contexto corrente e somente ele").
    """

    CSS = """
    #cabecalho {
        dock: top;
        height: 2;
    }
    #destino {
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    #status {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    #erro-interno {
        dock: bottom;
        height: auto;
        color: $error;
        padding: 0 1;
    }
    #erro-interno:disabled {
        display: none;
    }
    #corpo {
        height: 1fr;
    }
    #coluna-namespaces {
        width: 28;
        border: solid $primary;
    }
    #coluna-objetos {
        width: 1fr;
        border: solid $primary;
    }
    .titulo-secao {
        text-style: bold;
        background: $boost;
        padding: 0 1;
    }
    .mensagem-estado {
        color: $text-muted;
        padding: 0 1;
    }
    .mensagem-estado:disabled {
        display: none;
    }
    DataTable:disabled {
        display: none;
    }
    ListView:disabled {
        display: none;
    }
    """

    BINDINGS = [
        # priority=True: sem isso, o binding padrao "tab" -> foco seguinte
        # que Screen ja registra (screen.py) venceria por estar mais perto
        # do widget focado na resolucao por DOM, e o Tab nunca chegaria a
        # este action — descoberto rodando o smoke test deste grupo, nao
        # documentado em lugar nenhum do Textual que a spec cite.
        Binding("tab", "alternar_foco", "alternar foco", show=True, priority=True),
        Binding("slash", "focar_busca", "busca", show=True),
        Binding("escape", "limpar_busca", "limpar busca", show=True),
        Binding("r", "atualizar_agora", "atualizar", show=True),
        Binding("q", "sair", "sair", show=True),
    ]

    namespaces: reactive[tuple[str, ...]] = reactive(tuple, always_update=True)
    namespace_selecionado: reactive[str | None] = reactive(None)
    busca: reactive[str] = reactive("")
    momento_leitura: reactive[datetime | None] = reactive(None)
    momento_leitura_namespaces: reactive[datetime | None] = reactive(None)

    def __init__(
        self,
        sessao: Sessao,
        leituras: Leituras | None = None,
        intervalo_objetos: float = 10.0,
        intervalo_namespaces: float = 60.0,
    ) -> None:
        super().__init__()
        self._sessao = sessao
        self._destino: Destino = sessao.destino
        self._leituras = leituras or Leituras.padrao()
        self._intervalo_objetos = intervalo_objetos
        self._intervalo_namespaces = intervalo_namespaces
        self._envelope_namespaces: Envelope = _ENVELOPE_VAZIO_INICIAL
        self._envelopes = _ENVELOPES_INICIAIS
        self._erro_interno: str | None = None

    # ------------------------------------------------------------ compose

    def compose(self) -> ComposeResult:
        with Vertical(id="cabecalho"):
            yield Static(self._texto_destino(), id="destino")
            yield Static("", id="status")
        with Horizontal(id="corpo"):
            with Vertical(id="coluna-namespaces"):
                yield Static("Namespaces", classes="titulo-secao")
                yield Static("", id="mensagem-namespaces", classes="mensagem-estado")
                yield ListView(id="lista-namespaces")
            with VerticalScroll(id="coluna-objetos"):
                yield Input(
                    placeholder="busca por nome (Esc limpa)",
                    id="busca",
                )
                yield Static("Pods", classes="titulo-secao")
                yield Static("", id="mensagem-pods", classes="mensagem-estado")
                yield DataTable(id="tabela-pods")
                yield Static(
                    "Controladores (Deployments/StatefulSets)", classes="titulo-secao"
                )
                yield Static(
                    "", id="mensagem-controladores", classes="mensagem-estado"
                )
                yield DataTable(id="tabela-controladores")
                yield Static("Services", classes="titulo-secao")
                yield Static("", id="mensagem-services", classes="mensagem-estado")
                yield DataTable(id="tabela-services")
                yield Static("Eventos (última hora)", classes="titulo-secao")
                yield Static("", id="mensagem-eventos", classes="mensagem-estado")
                yield DataTable(id="tabela-eventos")
        yield Static("", id="erro-interno", disabled=True)

    def _texto_destino(self) -> str:
        return f"contexto: {self._destino.contexto}    servidor: {self._destino.servidor}"

    # -------------------------------------------------------------- mount

    async def on_mount(self) -> None:
        self._preparar_tabelas()
        await self._carregar_namespaces()
        if self.namespace_selecionado:
            await self._carregar_objetos()
        self._renderizar_tudo()
        self.set_interval(self._intervalo_objetos, self._ciclo_objetos)
        self.set_interval(self._intervalo_namespaces, self._ciclo_namespaces)
        self.set_interval(1, self._atualizar_relogio)

    def _preparar_tabelas(self) -> None:
        colunas = {
            "tabela-pods": (
                "nome",
                "estado",
                "prontos",
                "reinícios",
                "motivo",
                "sonda",
                "idade",
                "por quê",
            ),
            "tabela-controladores": ("tipo", "nome", "prontos", "condição", "por quê"),
            "tabela-services": ("nome", "tipo", "portas", "endereços", "por quê"),
            "tabela-eventos": (
                "tipo",
                "motivo",
                "objeto",
                "repetições",
                "quando",
                "mensagem",
            ),
        }
        for id_tabela, cols in colunas.items():
            tabela = self.query_one(f"#{id_tabela}", DataTable)
            tabela.cursor_type = "row"
            tabela.zebra_stripes = True
            tabela.add_columns(*cols)

    # ------------------------------------------------------ ciclos de leitura

    async def _ciclo_objetos(self) -> None:
        await self._carregar_objetos()
        self._renderizar_tudo()

    async def _ciclo_namespaces(self) -> None:
        await self._carregar_namespaces()
        self._renderizar_tudo()

    async def _carregar_namespaces(self) -> None:
        try:
            envelope = await asyncio.to_thread(self._leituras.namespaces, self._sessao)
        except Exception as exc:  # nenhum rastreamento de pilha chega ao terminal
            self._erro_interno = f"falha interna ao ler namespaces: {exc!r}"
            return
        self._erro_interno = None
        self._envelope_namespaces = envelope
        nomes = sorted(
            modelo.normalizar(item.get("metadata"), {}).get("name")
            for item in envelope.itens
        )
        self.namespaces = tuple(n for n in nomes if n)
        self.momento_leitura_namespaces = datetime.now(timezone.utc)
        if self.namespace_selecionado is None and self.namespaces:
            # DECISÃO: nenhum artefato diz qual namespace fica selecionado
            # no primeiro desenho da tela. Sem seleção nenhuma não há
            # retrato — a primeira ordem alfabética é a escolha mais neutra
            # disponível, e é a mesma ordem em que a lista já é exibida.
            self.namespace_selecionado = self.namespaces[0]

    async def _carregar_objetos(self) -> None:
        ns = self.namespace_selecionado
        if not ns:
            return
        try:
            pods = await asyncio.to_thread(self._leituras.pods, self._sessao, ns)
            deployments = await asyncio.to_thread(
                self._leituras.deployments, self._sessao, ns
            )
            statefulsets = await asyncio.to_thread(
                self._leituras.statefulsets, self._sessao, ns
            )
            services = await asyncio.to_thread(self._leituras.services, self._sessao, ns)
            endpointslices = await asyncio.to_thread(
                self._leituras.endpointslices, self._sessao, ns
            )
            eventos = await asyncio.to_thread(self._leituras.eventos, self._sessao, ns)
        except Exception as exc:  # nenhum rastreamento de pilha chega ao terminal
            self._erro_interno = f"falha interna ao ler objetos: {exc!r}"
            return
        self._erro_interno = None
        self._envelopes = _EnvelopesObjetos(
            pods=pods,
            deployments=deployments,
            statefulsets=statefulsets,
            services=services,
            endpointslices=endpointslices,
            eventos=eventos,
        )
        self.momento_leitura = datetime.now(timezone.utc)

    # ------------------------------------------------------------ desenho

    def _renderizar_tudo(self) -> None:
        try:
            self._renderizar_namespaces()
            self._renderizar_pods()
            self._renderizar_controladores()
            self._renderizar_services()
            self._renderizar_eventos()
            self._renderizar_status()
        except Exception as exc:  # invariante: nenhuma falha esvazia a tela
            self._erro_interno = f"falha interna ao desenhar a tela: {exc!r}"
        self._renderizar_erro_interno()

    def _renderizar_erro_interno(self) -> None:
        widget = self.query_one("#erro-interno", Static)
        if self._erro_interno:
            widget.update(f"⚠ {self._erro_interno}")
            widget.disabled = False
        else:
            widget.update("")
            widget.disabled = True

    def _renderizar_status(self) -> None:
        agora = datetime.now(timezone.utc)
        partes = []
        if self.momento_leitura:
            partes.append(f"objetos: atualizado há {formatar_duracao(agora - self.momento_leitura)}")
        if self.momento_leitura_namespaces:
            partes.append(
                f"namespaces: atualizado há {formatar_duracao(agora - self.momento_leitura_namespaces)}"
            )
        if self.namespace_selecionado:
            partes.insert(0, f"namespace: {self.namespace_selecionado}")
        if self.busca:
            partes.append(f"busca: {self.busca!r}")

        envelopes_objetos = [
            self._envelopes.pods,
            self._envelopes.deployments,
            self._envelopes.statefulsets,
            self._envelopes.services,
            self._envelopes.endpointslices,
            self._envelopes.eventos,
        ]
        texto = "  |  ".join(partes)
        motivo_hostil = _motivo_hostil_de_sessao(
            self._envelope_namespaces, envelopes_objetos, self.namespace_selecionado
        )
        if motivo_hostil is not None:
            texto = f"⚠ TELA EM ESTADO DE INDISPONIBILIDADE — {motivo_hostil}    ({texto})"
        self.query_one("#status", Static).update(texto)

    def _renderizar_namespaces(self) -> None:
        mensagem = self.query_one("#mensagem-namespaces", Static)
        lista = self.query_one("#lista-namespaces", ListView)
        texto_estado = texto_estado_envelope("namespaces", self._envelope_namespaces)
        if texto_estado is not None and not self.namespaces:
            mensagem.update(texto_estado)
            mensagem.disabled = False
            lista.disabled = True
            return
        mensagem.disabled = True
        lista.disabled = False
        nomes_atuais = [str(item.name) for item in lista.query(ListItem)]
        if nomes_atuais != list(self.namespaces):
            selecionado_anterior = self.namespace_selecionado
            lista.clear()
            for nome in self.namespaces:
                lista.append(ListItem(Label(nome), name=nome))
            if selecionado_anterior in self.namespaces:
                lista.index = list(self.namespaces).index(selecionado_anterior)

    def _combina_texto(self, texto: str) -> bool:
        return not self.busca or self.busca.lower() in texto.lower()

    def _eventos_por_objeto_na_janela(self, agora: datetime) -> dict:
        if self._envelopes.eventos.estado != EstadoEnvelope.OK:
            return {}
        na_janela = modelo.eventos_na_janela(list(self._envelopes.eventos.itens), agora)
        return modelo.eventos_warning_por_objeto(na_janela)

    def _renderizar_pods(self) -> None:
        envelope = self._envelopes.pods
        mensagem = self.query_one("#mensagem-pods", Static)
        tabela = self.query_one("#tabela-pods", DataTable)
        texto_estado = texto_estado_envelope("pods", envelope)
        if texto_estado is not None:
            mensagem.update(texto_estado)
            mensagem.disabled = False
            tabela.disabled = True
            return

        agora = datetime.now(timezone.utc)
        eventos_por_objeto = self._eventos_por_objeto_na_janela(agora)
        pods = [modelo.interpretar_pod(p) for p in envelope.itens]
        pods = [
            modelo.com_criterio_de_eventos(pod, "Pod", eventos_por_objeto) for pod in pods
        ]
        idades = {
            modelo.normalizar(p.get("metadata"), {}).get("name"): idade_pod(p, agora)
            for p in envelope.itens
        }
        pods = [p for p in pods if self._combina_texto(p.nome or "")]
        pods = modelo.ordenar_por_anormalidade(pods)

        mensagem.disabled = True
        tabela.disabled = False
        tabela.clear()
        for pod in pods:
            tabela.add_row(
                pod.nome,
                pod.estado,
                f"{pod.prontos}/{pod.total_containers}",
                str(pod.reinicios),
                texto_motivo_pod(pod.motivo),
                texto_sonda(pod.sonda),
                idades.get(pod.nome, "—"),
                texto_criterios(pod.criterios),
            )

    def _renderizar_controladores(self) -> None:
        env_dep = self._envelopes.deployments
        env_sts = self._envelopes.statefulsets
        mensagem = self.query_one("#mensagem-controladores", Static)
        tabela = self.query_one("#tabela-controladores", DataTable)

        # DECISÃO: Deployment e StatefulSet são dois envelopes independentes
        # desenhados no mesmo painel (D4). A spec nunca cobre o caso dos dois
        # estarem em estados diferentes. Aqui: qualquer um que tenha itens
        # contribui linhas; qualquer um que não esteja "ok" acrescenta uma
        # nota de estado — o painel só fica vazio se os dois estiverem sem
        # itens, e só mostra "sem permissão"/"indisponível" puro se nenhum
        # dos dois tiver dado nenhum para mostrar. Isso estende a mesma regra
        # do Requirement "Cada estado do envelope tem desenho próprio" para
        # dois tipos compartilhando um painel, em vez de escolher um dos dois
        # arbitrariamente como "o" estado do painel.
        notas = []
        texto_dep = texto_estado_envelope("deployments", env_dep)
        texto_sts = texto_estado_envelope("statefulsets", env_sts)
        if texto_dep is not None:
            notas.append(f"deployments: {texto_dep}")
        if texto_sts is not None:
            notas.append(f"statefulsets: {texto_sts}")

        agora = datetime.now(timezone.utc)
        eventos_por_objeto = self._eventos_por_objeto_na_janela(agora)

        controladores = []
        if env_dep.estado == EstadoEnvelope.OK:
            controladores += [
                modelo.com_criterio_de_eventos(
                    modelo.interpretar_controlador(d, "Deployment"),
                    "Deployment",
                    eventos_por_objeto,
                )
                for d in env_dep.itens
            ]
        if env_sts.estado == EstadoEnvelope.OK:
            controladores += [
                modelo.com_criterio_de_eventos(
                    modelo.interpretar_controlador(s, "StatefulSet"),
                    "StatefulSet",
                    eventos_por_objeto,
                )
                for s in env_sts.itens
            ]

        controladores = [c for c in controladores if self._combina_texto(c.nome or "")]
        controladores = modelo.ordenar_por_anormalidade(controladores)

        if not controladores:
            mensagem.update(" ; ".join(notas) if notas else "nenhum objeto neste namespace")
            mensagem.disabled = False
            tabela.disabled = True
            return

        mensagem.disabled = bool(not notas)
        if notas:
            mensagem.update(" ; ".join(notas))
        tabela.disabled = False
        tabela.clear()
        for c in controladores:
            tabela.add_row(
                c.tipo,
                c.nome,
                f"{c.prontos}/{c.desejados}",
                texto_condicao(c.condicao_available),
                texto_criterios(c.criterios),
            )

    def _renderizar_services(self) -> None:
        env_svc = self._envelopes.services
        env_slices = self._envelopes.endpointslices
        mensagem = self.query_one("#mensagem-services", Static)
        tabela = self.query_one("#tabela-services", DataTable)

        texto_estado = texto_estado_envelope("services", env_svc)
        if texto_estado is not None:
            mensagem.update(texto_estado)
            mensagem.disabled = False
            tabela.disabled = True
            return

        # DECISÃO: o painel de Services é dirigido pelo envelope `services`
        # (mesma regra dos demais painéis de tipo único). O envelope
        # `endpointslices` é uma fonte subordinada — enriquece a coluna de
        # endereços de cada linha, não decide se o painel aparece. Quando
        # `endpointslices` não está ok/vazio (negado ou indisponível),
        # nenhuma linha afirma "sem endereço": a spec (D9, Requirement "A
        # tela relata, e não afirma saúde") proíbe exatamente essa afirmação
        # não sustentada, então a coluna mostra que o dado de endereço está
        # indisponível, com o motivo, em vez de um estado dos três que
        # `01-comportamento.md` define para quando a leitura teve sucesso.
        if env_slices.estado in (EstadoEnvelope.OK, EstadoEnvelope.VAZIO):
            agregados = modelo.agregar_enderecos_por_service(list(env_slices.itens))
            motivo_indisponibilidade = None
        else:
            agregados = {}
            motivo_indisponibilidade = env_slices.motivo or "sem dado de endereço"

        agora = datetime.now(timezone.utc)
        eventos_por_objeto = self._eventos_por_objeto_na_janela(agora)

        linhas = []
        for svc in env_svc.itens:
            nome = modelo.normalizar(svc.get("metadata"), {}).get("name")
            spec = modelo.normalizar(svc.get("spec"), {})
            fatias = agregados.get(nome, [])
            exibido = modelo.interpretar_service(svc, fatias)
            if motivo_indisponibilidade is not None:
                # Sem dado de endereço confiável, o critério de "sem
                # endereço" (peso 4) não pode ser afirmado — seria opinar
                # além do que a API sustentou nesta leitura.
                exibido = dataclasses.replace(exibido, criterios=())
            exibido = modelo.com_criterio_de_eventos(exibido, "Service", eventos_por_objeto)
            if not self._combina_texto(nome or ""):
                continue
            linhas.append((exibido, spec))

        linhas_ordenadas = modelo.ordenar_por_anormalidade([e for e, _ in linhas])
        specs_por_nome = {e.nome: s for e, s in linhas}

        if not linhas_ordenadas:
            mensagem.update("nenhum objeto neste namespace")
            mensagem.disabled = False
            tabela.disabled = True
            return

        mensagem.disabled = True
        tabela.disabled = False
        tabela.clear()
        for exibido in linhas_ordenadas:
            spec = specs_por_nome.get(exibido.nome, {})
            tabela.add_row(
                exibido.nome,
                spec.get("type") or "—",
                texto_portas_service(spec),
                texto_enderecos_service(
                    exibido.prontos, exibido.total_enderecos, motivo_indisponibilidade
                ),
                texto_criterios(exibido.criterios),
            )

    def _renderizar_eventos(self) -> None:
        envelope = self._envelopes.eventos
        mensagem = self.query_one("#mensagem-eventos", Static)
        tabela = self.query_one("#tabela-eventos", DataTable)
        texto_estado = texto_estado_envelope("eventos", envelope)
        if texto_estado is not None:
            mensagem.update(texto_estado)
            mensagem.disabled = False
            tabela.disabled = True
            return

        agora = datetime.now(timezone.utc)
        eventos = modelo.eventos_exibidos(list(envelope.itens), agora)
        # DECISÃO: a spec descreve busca por "objetos", e um evento não tem
        # nome próprio — o análogo mais próximo é o nome do objeto envolvido
        # (`involvedObject.name`), que é também o campo que conecta um
        # evento a uma linha de pod/controlador/service em outro painel.
        eventos = [e for e in eventos if self._combina_texto(e.objeto_nome or "")]

        if not eventos:
            mensagem.update("nenhum objeto neste namespace")
            mensagem.disabled = False
            tabela.disabled = True
            return

        mensagem.disabled = True
        tabela.disabled = False
        tabela.clear()
        for evento in eventos:
            tipo_texto = "⚠ Warning" if evento.tipo == "Warning" else (evento.tipo or "—")
            objeto_texto = f"{evento.objeto_kind or '?'}/{evento.objeto_nome or '?'}"
            tabela.add_row(
                tipo_texto,
                evento.motivo or "—",
                objeto_texto,
                str(evento.repeticoes),
                evento.quando or "—",
                evento.mensagem or "—",
            )

    def _atualizar_relogio(self) -> None:
        """Faz só a idade do dado avançar a cada segundo, sem reler nada —
        Requirement "Atualização periódica com a idade do dado visível",
        cenário "A idade do dado aparece"."""
        self._renderizar_status()

    # ------------------------------------------------------------- eventos

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id != "lista-namespaces" or event.item is None:
            return
        novo = event.item.name
        if novo and novo != self.namespace_selecionado:
            self.namespace_selecionado = novo
            self.run_worker(self._trocar_namespace(), exclusive=True, group="troca-ns")

    async def _trocar_namespace(self) -> None:
        await self._carregar_objetos()
        self._renderizar_tudo()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "busca":
            self.busca = event.value

    def watch_busca(self) -> None:
        # A busca filtra o que já está lido — não dispara nova leitura de
        # rede (Requirement "Busca por nome" não pede isso, e recarregar a
        # cada tecla digitada seria custo sem benefício, dado que a D3 já
        # escopa a leitura ao namespace selecionado).
        if self.is_mounted:
            self._renderizar_tudo()

    # ------------------------------------------------------------- ações

    def action_alternar_foco(self) -> None:
        lista_ns = self.query_one("#lista-namespaces", ListView)
        if self.focused is lista_ns:
            self.query_one("#tabela-pods", DataTable).focus()
        else:
            # DECISÃO: a spec descreve um alternador de dois estados (Tab
            # "alterna o foco entre a lista de namespaces e o painel de
            # objetos"), mas a tela tem quatro painéis de objeto empilhados,
            # não um só. Sem uma tecla própria para circular entre eles
            # (não está na tabela de teclas), Tab sempre volta para a lista
            # de namespaces a partir de qualquer um dos quatro, e sempre
            # avança para o primeiro painel de objetos (Pods) a partir da
            # lista de namespaces — um alternador de dois estados de
            # verdade, só que com um destino fixo do lado dos objetos.
            # Quem quiser o painel de Controladores/Services/Eventos chega
            # lá pelo mouse ou, futuramente, por uma tecla dedicada que a
            # spec não pede nesta fatia.
            lista_ns.focus()

    def action_focar_busca(self) -> None:
        self.query_one("#busca", Input).focus()

    def action_limpar_busca(self) -> None:
        campo = self.query_one("#busca", Input)
        campo.value = ""
        self.busca = ""

    def action_atualizar_agora(self) -> None:
        self.run_worker(self._atualizar_agora(), exclusive=True, group="atualizar-agora")

    async def _atualizar_agora(self) -> None:
        await self._carregar_namespaces()
        await self._carregar_objetos()
        self._renderizar_tudo()

    def action_sair(self) -> None:
        self.exit()

