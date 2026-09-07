"""Camada de interpretação (D-A do `design.md`).

Transforma o JSON cru que vem dentro do `Envelope` de `cliente.py` no retrato
exibível de um namespace. Este módulo:

  - não faz rede;
  - não importa `kubernetes` nem `urllib3` (D8: só `cliente.py` tem essa
    licença);
  - é testável inteiramente com dicionários e listas, sem cluster e sem
    fixture nenhuma no caso geral — as fixtures em `tests/fixtures/` servem
    para provar que a forma que se assume aqui é a forma que o cluster real
    devolve, não para exercitar cada ramo de código.

Escopo deste arquivo (grupos 4, 5 e 6 do `tasks.md`): interpretação de pods,
de controladores (Deployment e StatefulSet) e de Services, mais eventos e a
ordenação por anormalidade. A montagem da tela (grupo 7 em diante) não mora
aqui.

## A armadilha central (D9, `docs/02-decisoes-tecnicas.md`)

Campo ausente, campo com valor `null` e coleção vazia são a mesma leitura de
fato, e nenhuma função abaixo decide estado perguntando se uma chave existe
(`"campo" in objeto`). Toda leitura passa por `normalizar()`, que usa o único
padrão que colapsa as três formas de ausência sem testar presença de chave:
`valor or padrao`. Isso funciona porque o padrão escolhido para cada campo já
é a própria forma vazia esperada (`[]` para coleção, `0` para contagem, `{}`
para objeto aninhado) — normalizar um valor que já está no padrão é um no-op.

A única exceção deliberada é `metadata.deletionTimestamp`: ali a presença do
campo *é* o próprio fato que se quer ler (o pod foi marcado para remoção), não
uma armadilha de ausente-contra-vazio — por isso o código testa a
truthiness do valor lido por `.get()`, nunca `"deletionTimestamp" in metadata`.

## Zero afirmado contra nada ainda afirmado (D9, requisito "Condição de
controlador só existe onde a API a fornece" combinado com a tarefa 5.5)

`readyReplicas` ausente normaliza para `0`, e `0` é um fato exibível — mas
"zero pronto" não é o mesmo que "degradado". Um controlador cujo
`observedGeneration` ainda não alcançou `metadata.generation` é um
controlador que o control plane ainda não terminou de avaliar; tratá-lo como
anormal pintaria de degradado algo que acabou de ser criado. Ver
`controlador_ainda_nao_avaliado()` para a decisão registrada sobre qual dos
três sinais que `01-comportamento.md` cita (`observedGeneration`, condições,
idade) este código usa como decisivo.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
from typing import Any

__all__ = [
    "normalizar",
    "Criterio",
    # pods
    "MotivoFalha",
    "Sonda",
    "PodExibido",
    "estado_pod",
    "prontos_pod",
    "reinicios_pod",
    "motivo_falha_pod",
    "sonda_prontidao_pod",
    "interpretar_pod",
    # controladores
    "Condicao",
    "ControladorExibido",
    "controlador_ainda_nao_avaliado",
    "interpretar_controlador",
    # services
    "SEM_ENDERECO",
    "PARCIAL",
    "COMPLETO",
    "ServiceExibido",
    "agregar_enderecos_por_service",
    "enderecos_de_service",
    "estado_enderecos",
    "interpretar_service",
    # eventos
    "EventoExibido",
    "instante_evento",
    "eventos_na_janela",
    "ordenar_eventos",
    "interpretar_evento",
    "eventos_exibidos",
    # ordenação por anormalidade
    "eventos_warning_por_objeto",
    "com_criterio_de_eventos",
    "ordenar_por_anormalidade",
]


def normalizar(valor: Any, padrao: Any) -> Any:
    """O único ponto de normalização do projeto (D9).

    `obj.get(campo) or padrao` colapsa chave ausente, valor `None` e coleção
    vazia na mesma forma — o próprio `padrao`. Nenhuma chamada em todo este
    módulo testa `"campo" in objeto` para decidir se um dado existe; todas
    passam pelo `.get()` seguido desta função.
    """
    return valor or padrao


# --------------------------------------------------------------------------
# Critério de anormalidade — comum a pods, controladores, Services e eventos.
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Criterio:
    """Um critério de anormalidade satisfeito por um objeto (D-F do
    `design.md`; Requirement "Ordenação por anormalidade com o critério
    visível").

    `peso` é a ordem de prioridade da tabela de `01-comportamento.md` (1 a
    5, menor é mais urgente). `motivo` é o texto que a tela mostra na coluna
    "por quê". `campo` é o campo lido da API que originou o critério — nunca
    um critério deriva de outro critério, sempre do dado cru.
    """

    peso: int
    motivo: str
    campo: str


# --------------------------------------------------------------------------
# Grupo 4 — interpretação de pods
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MotivoFalha:
    """As duas metades do motivo de falha de um container (Requirement "O
    motivo de uma falha tem duas metades"). `atual` é o que está acontecendo
    agora (`state.waiting.reason`); `causa` é o que aconteceu antes
    (`lastState.terminated.reason`), apresentado como a causa do motivo
    atual. Os dois são `None` quando o container não está em falha."""

    atual: str | None
    causa: str | None


@dataclasses.dataclass(frozen=True)
class Sonda:
    """Quantos containers do pod declaram sonda de prontidão, sobre o total
    (Requirement "Ausência de sonda de prontidão é exibida como fato"). A
    tela decide como desenhar isso (`—`, `✓`, `1/2`); aqui só a contagem."""

    com_sonda: int
    total: int


@dataclasses.dataclass(frozen=True)
class PodExibido:
    """O retrato interpretado de um pod, pronto para a tela ordenar e
    desenhar."""

    nome: str
    estado: str
    prontos: int
    total_containers: int
    reinicios: int
    motivo: MotivoFalha
    sonda: Sonda
    criterios: tuple[Criterio, ...] = ()


def estado_pod(pod: dict) -> str:
    """O estado exibido de um pod (Requirement "O estado de um pod não é a
    sua fase").

    Ordem de decisão, e por quê:

    1. `metadata.deletionTimestamp` presente → `"Terminating"`, **mesmo que**
       algum container esteja em `waiting` — o pod está saindo, e isso é a
       informação mais urgente independente do que os containers fazem
       enquanto o kubelet os desliga. A spec não cobre o caso dos dois
       sinais presentes ao mesmo tempo; esta prioridade é uma decisão deste
       código, não um requisito medido.
    2. Algum `containerStatuses[].state.waiting.reason` presente →
       esse motivo (`CrashLoopBackOff`, `ImagePullBackOff` etc.), no lugar da
       fase. A spec só exemplifica com `CrashLoopBackOff`; este código
       generaliza para qualquer motivo de espera, porque a regra que o texto
       descreve — "vive em waiting.reason, com a fase ainda em Running" — não
       é específica daquele motivo. Com mais de um container em espera, o
       primeiro da lista vence; a spec não cobre múltiplos motivos
       simultâneos.
    3. Nenhum dos dois → a fase, sem tradução.
    """
    metadata = normalizar(pod.get("metadata"), {})
    status = normalizar(pod.get("status"), {})

    if metadata.get("deletionTimestamp"):
        return "Terminating"

    for cs in normalizar(status.get("containerStatuses"), []):
        estado_container = normalizar(cs.get("state"), {})
        aguardando = normalizar(estado_container.get("waiting"), {})
        motivo = aguardando.get("reason")
        if motivo:
            return motivo

    return status.get("phase") or "Desconhecido"


def prontos_pod(pod: dict) -> tuple[int, int]:
    """Contagem de containers prontos sobre o total (coluna "prontos" da
    tabela de Pods).

    O total vem de `status.containerStatuses` quando presente — é a fonte que
    a spec cita (`status.containerStatuses[].ready`). Quando o pod ainda não
    tem status de container nenhum (por exemplo, antes de ser agendado), o
    total recua para `spec.containers`, para que a contagem seja `0/N` e não
    `0/0` — decisão deste código; a spec não cobre pod sem
    `containerStatuses`.
    """
    status = normalizar(pod.get("status"), {})
    containers_status = normalizar(status.get("containerStatuses"), [])

    if containers_status:
        total = len(containers_status)
        prontos = sum(1 for cs in containers_status if normalizar(cs.get("ready"), False))
        return prontos, total

    spec = normalizar(pod.get("spec"), {})
    containers_spec = normalizar(spec.get("containers"), [])
    return 0, len(containers_spec)


def reinicios_pod(pod: dict) -> int:
    """Soma de `restartCount` de todos os containers do pod."""
    status = normalizar(pod.get("status"), {})
    return sum(
        normalizar(cs.get("restartCount"), 0)
        for cs in normalizar(status.get("containerStatuses"), [])
    )


def motivo_falha_pod(pod: dict) -> MotivoFalha:
    """As duas metades do motivo, do primeiro container em `waiting` (o
    mesmo container que decide `estado_pod` quando o motivo vem daí)."""
    status = normalizar(pod.get("status"), {})
    for cs in normalizar(status.get("containerStatuses"), []):
        estado_container = normalizar(cs.get("state"), {})
        aguardando = normalizar(estado_container.get("waiting"), {})
        atual = aguardando.get("reason")
        if atual:
            estado_anterior = normalizar(cs.get("lastState"), {})
            terminado = normalizar(estado_anterior.get("terminated"), {})
            causa = terminado.get("reason")
            return MotivoFalha(atual=atual, causa=causa)
    return MotivoFalha(atual=None, causa=None)


def sonda_prontidao_pod(pod: dict) -> Sonda:
    """Quantos containers declaram `readinessProbe`, sobre o total de
    containers de `spec.containers` — é fato de especificação, não de
    runtime, e por isso não depende de `containerStatuses`."""
    spec = normalizar(pod.get("spec"), {})
    containers = normalizar(spec.get("containers"), [])
    total = len(containers)
    com_sonda = sum(1 for c in containers if c.get("readinessProbe"))
    return Sonda(com_sonda=com_sonda, total=total)


def interpretar_pod(pod: dict) -> PodExibido:
    """Junta as funções acima e calcula os critérios de anormalidade que
    nascem do próprio pod (pesos 1, 2 e 3 da tabela de
    `01-comportamento.md`; o peso 4 é de Service e o peso 5, de eventos, é
    aplicado depois por `com_criterio_de_eventos`)."""
    nome = normalizar(pod.get("metadata"), {}).get("name")
    prontos, total = prontos_pod(pod)
    reinicios = reinicios_pod(pod)
    motivo = motivo_falha_pod(pod)

    criterios: list[Criterio] = []
    if prontos < total:
        criterios.append(
            Criterio(
                peso=1,
                motivo=f"{prontos}/{total} containers prontos",
                campo="status.containerStatuses[].ready",
            )
        )
    if motivo.atual:
        criterios.append(
            Criterio(
                peso=2,
                motivo=f"em espera: {motivo.atual}",
                campo="status.containerStatuses[].state.waiting.reason",
            )
        )
    if reinicios > 0:
        criterios.append(
            Criterio(
                peso=3,
                motivo=f"reinícios: {reinicios}",
                campo="status.containerStatuses[].restartCount",
            )
        )

    return PodExibido(
        nome=nome,
        estado=estado_pod(pod),
        prontos=prontos,
        total_containers=total,
        reinicios=reinicios,
        motivo=motivo,
        sonda=sonda_prontidao_pod(pod),
        criterios=tuple(criterios),
    )


# --------------------------------------------------------------------------
# Grupo 5 — interpretação de controladores (Deployment, StatefulSet) e
# Services
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Condicao:
    """Uma condição de controlador, no vocabulário cru da API (`status` é a
    string `"True"`/`"False"`/`"Unknown"` que a API manda, não um bool)."""

    tipo: str
    status: str


@dataclasses.dataclass(frozen=True)
class ControladorExibido:
    """O retrato interpretado de um Deployment ou StatefulSet."""

    nome: str
    tipo: str  # "Deployment" ou "StatefulSet" — igual ao Kind da API
    prontos: int
    desejados: int
    condicao_available: Condicao | None
    criterios: tuple[Criterio, ...] = ()


def controlador_ainda_nao_avaliado(objeto: dict) -> bool:
    """Distingue "o control plane afirmou zero" de "o control plane ainda
    não avaliou este objeto" (D9; Requirement "Condição de controlador só
    existe onde a API a fornece" e tarefa 5.5).

    **Decisão registrada, porque a spec cita três sinais e não diz como
    combiná-los.** `01-comportamento.md` e a tarefa 5.5 mencionam
    `observedGeneration`, condições e idade como as três fontes da
    distinção, mas nenhum artefato dá um algoritmo. Este código usa
    `status.observedGeneration` comparado a `metadata.generation` como sinal
    decisivo — é o mesmo par de campos que `kubectl rollout status` usa para
    a mesma pergunta, e está sempre presente (ou ausente de forma
    informativa) tanto em Deployment quanto em StatefulSet, ao contrário de
    "condições" (que o StatefulSet não tem) e de "idade" (que exigiria um
    limiar arbitrário não especificado em lugar nenhum). Um controlador é
    "ainda não avaliado" quando `observedGeneration` está ausente, ou é menor
    que `metadata.generation`.
    """
    status = normalizar(objeto.get("status"), {})
    metadata = normalizar(objeto.get("metadata"), {})
    generation = metadata.get("generation")
    observado = status.get("observedGeneration")

    if observado is None:
        return True
    if generation is not None and observado < generation:
        return True
    return False


def interpretar_controlador(objeto: dict, tipo: str) -> ControladorExibido:
    """Interpreta um Deployment ou StatefulSet (`tipo` é o Kind exato,
    `"Deployment"` ou `"StatefulSet"` — o chamador sabe qual API leu, e não
    há como adivinhar isso a partir do JSON sozinho).

    A condição `Available` é procurada em `status.conditions` normalizado
    para `[]`, sem nenhum `if tipo == "StatefulSet"`: um StatefulSet não tem
    a chave `conditions`, então a lista normalizada vem vazia e a busca não
    encontra nada — `condicao_available` sai `None` pela própria forma dos
    dados, não por um desvio de código que testa o tipo (Requirement
    "Condição de controlador só existe onde a API a fornece").
    """
    metadata = normalizar(objeto.get("metadata"), {})
    spec = normalizar(objeto.get("spec"), {})
    status = normalizar(objeto.get("status"), {})

    nome = metadata.get("name")
    desejados = normalizar(spec.get("replicas"), 0)
    prontos = normalizar(status.get("readyReplicas"), 0)

    condicao_available: Condicao | None = None
    for condicao in normalizar(status.get("conditions"), []):
        if condicao.get("type") == "Available":
            condicao_available = Condicao(tipo="Available", status=condicao.get("status"))
            break

    criterios: list[Criterio] = []
    if prontos < desejados and not controlador_ainda_nao_avaliado(objeto):
        criterios.append(
            Criterio(
                peso=1,
                motivo=f"{prontos}/{desejados} prontos",
                campo="status.readyReplicas",
            )
        )

    return ControladorExibido(
        nome=nome,
        tipo=tipo,
        prontos=prontos,
        desejados=desejados,
        condicao_available=condicao_available,
        criterios=tuple(criterios),
    )


SEM_ENDERECO = "sem_endereco"
PARCIAL = "parcial"
COMPLETO = "completo"


@dataclasses.dataclass(frozen=True)
class ServiceExibido:
    """O retrato interpretado de um Service, já com os endereços de todas as
    suas fatias de `EndpointSlice` agregados."""

    nome: str
    prontos: int
    total_enderecos: int
    criterios: tuple[Criterio, ...] = ()


def agregar_enderecos_por_service(fatias: list[dict]) -> dict[str, list[dict]]:
    """Agrupa fatias de `EndpointSlice` pelo rótulo
    `kubernetes.io/service-name` (D5). Um Service mapeia para N fatias; esta
    função é o passo de agregação que a D5 registra como custo aceito de
    trocar `Endpoints` por `EndpointSlice`."""
    agrupado: dict[str, list[dict]] = {}
    for fatia in fatias:
        metadata = normalizar(fatia.get("metadata"), {})
        rotulos = normalizar(metadata.get("labels"), {})
        nome_service = rotulos.get("kubernetes.io/service-name")
        if nome_service is None:
            continue
        agrupado.setdefault(nome_service, []).append(fatia)
    return agrupado


def enderecos_de_service(fatias_do_service: list[dict]) -> tuple[int, int]:
    """Devolve `(prontos, total)` juntando os endereços de todas as fatias de
    um Service (Requirement "Um Service tem três estados de endereço").

    As duas formas de ausência que a D9 mede no mesmo Service —
    `Endpoints.subsets` ausente e `EndpointSlice.endpoints` presente com
    valor `null` — convergem aqui na mesma leitura, porque as duas passam
    por `normalizar(..., [])` e nenhuma é testada por `in`.
    """
    total = 0
    prontos = 0
    for fatia in fatias_do_service:
        enderecos = normalizar(fatia.get("endpoints"), [])
        for endereco in enderecos:
            total += 1
            condicoes = normalizar(endereco.get("conditions"), {})
            if normalizar(condicoes.get("ready"), False):
                prontos += 1
    return prontos, total


def estado_enderecos(prontos: int, total: int) -> str:
    """Os três estados de endereço de um Service (Requirement "Um Service
    tem três estados de endereço"). A tela escolhe o texto final (`"sem
    endereço"`, `"2 de 3 prontos"`, `"3 prontos"`); aqui só a classificação."""
    if total == 0:
        return SEM_ENDERECO
    if prontos == total:
        return COMPLETO
    return PARCIAL


def interpretar_service(objeto: dict, fatias_do_service: list[dict]) -> ServiceExibido:
    """Interpreta um Service já com as fatias do seu grupo (o resultado de
    `agregar_enderecos_por_service()` para o nome deste Service).

    Um Service sem endereço é sempre marcado anormal (peso 4), mesmo que
    todos os pods do namespace estejam prontos — este código não olha pods
    nenhum para decidir isso; é uma função só dos próprios endereços
    (Requirement "Um Service tem três estados de endereço", cenário "Service
    cujo seletor não casa com pod nenhum")."""
    nome = normalizar(objeto.get("metadata"), {}).get("name")
    prontos, total = enderecos_de_service(fatias_do_service)

    criterios: list[Criterio] = []
    if estado_enderecos(prontos, total) == SEM_ENDERECO:
        criterios.append(
            Criterio(peso=4, motivo="sem endereço", campo="EndpointSlice.endpoints")
        )

    return ServiceExibido(
        nome=nome,
        prontos=prontos,
        total_enderecos=total,
        criterios=tuple(criterios),
    )


# --------------------------------------------------------------------------
# Grupo 6 — eventos e ordenação
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class EventoExibido:
    """O retrato interpretado de um evento, nas colunas que
    `01-comportamento.md` pede."""

    tipo: str | None
    motivo: str | None
    objeto_kind: str | None
    objeto_nome: str | None
    repeticoes: int
    quando: str | None
    mensagem: str | None


def instante_evento(evento: dict) -> str | None:
    """O instante que ordena e filtra um evento: `lastTimestamp`, com recuo
    para `eventTime` quando o primeiro vier ausente ou nulo (Requirement
    "Eventos recentes do namespace selecionado"; medido em `nyx-dev`:
    `firstTimestamp` preenchido e `eventTime: null` no mesmo evento — mais
    uma vez a mesma ausência, num terceiro campo, que este código não testa
    por `in`)."""
    return evento.get("lastTimestamp") or evento.get("eventTime")


def _instante_como_data(valor: str) -> datetime:
    """Converte o timestamp da API (`...Z`, RFC 3339) para `datetime`
    ciente de fuso. `datetime.fromisoformat` do Python 3.10 não aceita o
    sufixo `Z` diretamente — só `+00:00` — daí a troca."""
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def eventos_na_janela(
    itens: list[dict],
    agora: datetime,
    janela: timedelta = timedelta(hours=1),
) -> list[dict]:
    """Filtra eventos cujo instante (`instante_evento`) cai dentro da janela
    deslizante de uma hora terminada em `agora` (Requirement "Eventos
    recentes do namespace selecionado").

    `agora` é parâmetro, não `datetime.now()` interno: a interpretação é uma
    função pura (D-A do `design.md`), e o horário de agora é decisão de quem
    chama (a tela, no grupo 7), não deste módulo — é o que torna este filtro
    testável com uma fixture capturada num instante fixo do passado, sem que
    o teste dependa de que horas são agora de verdade.

    **Decisão registrada, porque a spec não cobre o caso:** um evento sem
    `lastTimestamp` e sem `eventTime` — as duas ausentes ou nulas ao mesmo
    tempo — é excluído da janela, porque não há como avaliar "recente" sobre
    um instante que não existe, e afirmar que ele está dentro da janela seria
    exatamente o tipo de afirmação que a API não sustenta.
    """
    limite = agora - janela
    resultado = []
    for evento in itens:
        instante = instante_evento(evento)
        if not instante:
            continue
        if _instante_como_data(instante) >= limite:
            resultado.append(evento)
    return resultado


def ordenar_eventos(itens: list[dict]) -> list[dict]:
    """Ordena eventos do mais recente para o mais antigo por
    `instante_evento` (Requirement "Eventos recentes do namespace
    selecionado", cenário "A ordenação não vem da API"). A ordem de entrada
    não influencia a saída — a API não devolve ordenado, e este é o único
    lugar do projeto que ordena eventos."""
    return sorted(
        itens,
        key=lambda evento: _instante_como_data(instante_evento(evento)),
        reverse=True,
    )


def interpretar_evento(evento: dict) -> EventoExibido:
    """Traduz um evento cru nas colunas que a tela mostra."""
    envolvido = normalizar(evento.get("involvedObject"), {})
    return EventoExibido(
        tipo=evento.get("type"),
        motivo=evento.get("reason"),
        objeto_kind=envolvido.get("kind"),
        objeto_nome=envolvido.get("name"),
        repeticoes=normalizar(evento.get("count"), 0),
        quando=instante_evento(evento),
        mensagem=evento.get("message"),
    )


def eventos_exibidos(
    itens: list[dict],
    agora: datetime,
    janela: timedelta = timedelta(hours=1),
) -> list[EventoExibido]:
    """Composição das três funções acima: filtra pela janela, ordena do mais
    recente ao mais antigo, e interpreta cada evento. É o que o grupo 7 vai
    chamar para desenhar o painel de eventos; nenhum código de tela mora
    aqui."""
    itens_na_janela = eventos_na_janela(itens, agora, janela)
    itens_ordenados = ordenar_eventos(itens_na_janela)
    return [interpretar_evento(evento) for evento in itens_ordenados]


# --------------------------------------------------------------------------
# Ordenação por anormalidade (Requirement "Ordenação por anormalidade com o
# critério visível") — genérica sobre qualquer objeto exibido que tenha
# `.nome` e `.criterios`, então serve para PodExibido, ControladorExibido e
# ServiceExibido sem repetir a lógica de ordenação três vezes.
# --------------------------------------------------------------------------


def eventos_warning_por_objeto(
    eventos: list[dict],
) -> dict[tuple[str | None, str | None], list[dict]]:
    """Agrupa eventos `Warning` por `(involvedObject.kind,
    involvedObject.name)` — a chave que o critério de peso 5 usa para achar
    a qual pod, controlador ou Service um evento se refere.

    Pressupõe que `eventos` já vem do namespace selecionado (D3/D8: toda
    leitura de tipo é escopada a um namespace), então `kind` + `nome` basta
    para casar sem ambiguidade — não é preciso carregar `namespace` junto."""
    agrupado: dict[tuple[str | None, str | None], list[dict]] = {}
    for evento in eventos:
        if evento.get("type") != "Warning":
            continue
        envolvido = normalizar(evento.get("involvedObject"), {})
        kind = envolvido.get("kind")
        nome = envolvido.get("name")
        if kind is None or nome is None:
            continue
        agrupado.setdefault((kind, nome), []).append(evento)
    return agrupado


def com_criterio_de_eventos(
    objeto: Any,
    kind: str,
    eventos_por_objeto: dict[tuple[str | None, str | None], list[dict]],
):
    """Devolve `objeto` com o critério de peso 5 acrescentado, se algum
    evento `Warning` na janela o referenciar. `objeto` é qualquer dataclass
    com `.nome` e `.criterios` (`PodExibido`, `ControladorExibido` ou
    `ServiceExibido`) — a função é genérica porque a correlação por
    `(kind, nome)` não muda entre os três tipos."""
    eventos = eventos_por_objeto.get((kind, objeto.nome), [])
    if not eventos:
        return objeto
    motivos = sorted({evento.get("reason") for evento in eventos if evento.get("reason")})
    criterio = Criterio(
        peso=5,
        motivo=f"evento Warning: {', '.join(motivos)}" if motivos else "evento Warning",
        campo="Event.type/involvedObject",
    )
    return dataclasses.replace(objeto, criterios=objeto.criterios + (criterio,))


def ordenar_por_anormalidade(objetos: list[Any]) -> list[Any]:
    """Ordena qualquer lista de objetos com `.nome` e `.criterios`
    (Requirement "Ordenação por anormalidade com o critério visível"):
    primeiro os que satisfazem algum critério, depois os demais em ordem
    alfabética pura.

    **Decisão registrada, porque a spec não define a ordem relativa entre
    vários objetos anormais.** O requisito só diz "os anormais aparecem
    primeiro" e "os demais depois, em ordem alfabética" — não diz como
    ordenar os anormais entre si. Este código usa `(peso mínimo satisfeito,
    nome)`: o objeto cujo critério mais urgente (menor peso) é mais grave
    aparece antes, e o nome desempata. Isso é auditável do mesmo jeito que o
    resto da ordenação — o peso mínimo é um dos critérios já exibidos na
    linha, não um número novo inventado para ordenar.
    """
    anomalos = [objeto for objeto in objetos if objeto.criterios]
    normais = [objeto for objeto in objetos if not objeto.criterios]
    anomalos.sort(key=lambda objeto: (min(c.peso for c in objeto.criterios), objeto.nome))
    normais.sort(key=lambda objeto: objeto.nome)
    return anomalos + normais
