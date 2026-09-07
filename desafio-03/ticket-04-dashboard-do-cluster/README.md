# painel-cluster

Retrato de um namespace do cluster corrente do kubeconfig — pods com estado e
motivo de falha, Deployments e StatefulSets com prontos sobre desejados,
Services e se têm endereço, eventos recentes — numa tela de terminal.

**Não substitui o terminal.** Encurta os primeiros dez minutos de um chamado,
que hoje se montam com seis a dez `kubectl`. O comportamento completo, campo a
campo, está em `docs/01-comportamento.md`; as decisões técnicas, em
`docs/02-decisoes-tecnicas.md`.

## Instalação

Requer Python 3.10 ou mais novo e acesso a um kubeconfig com um contexto
corrente definido.

```bash
cd desafio-03/ticket-04-dashboard-do-cluster
python3 -m venv .venv
./.venv/bin/pip install -e .
```

Isto instala o cliente `kubernetes` e o `textual` nas versões fixadas em
`pyproject.toml`/`requirements.txt`, e expõe o comando `painel-cluster`:

```bash
./.venv/bin/painel-cluster --help
```

## Antes do primeiro uso: RBAC

O painel só lê. Antes de rodar contra um cluster de verdade, aplique o perfil
de permissão de leitura:

```bash
kubectl apply -f rbac/platform-ro.yaml
```

Isto cria uma `ServiceAccount` chamada `platform-ro` em `kube-system`, com uma
`ClusterRole` que concede `get`/`list` só nos sete tipos que a tela usa
(namespaces, pods, services, events, deployments, statefulsets,
endpointslices) — nunca `secrets`, nunca verbo de escrita, nunca `watch`. É o
**jeito documentado** de rodar o painel.

Existe um segundo perfil, `rbac/platform-ro-sem-events.yaml`: idêntico ao
primeiro, menos a permissão de ler `events`. **Não é o jeito recomendado de
rodar** — os eventos do namespace selecionado são requisito explícito da
tela, e um contexto que os nega entrega um painel incompleto. Ele existe só
para reproduzir o cenário de permissão parcial (critério de aceite 6:
com esse contexto, o painel de eventos mostra "sem permissão" e os demais
painéis continuam preenchidos) — útil para conferir a garantia de só-leitura
por fora do código, não para uso do dia a dia.

### Criando um contexto de kubeconfig para o `platform-ro`

O painel lê sempre o **contexto corrente** do kubeconfig, e nunca troca de
contexto sozinho. Para apontar esse contexto para a `ServiceAccount`
`platform-ro`, gere um token de curta duração e registre um contexto que o
use (troque `kind-metacortex-lab` pelo nome do cluster de destino):

```bash
TOKEN=$(kubectl create token platform-ro -n kube-system --duration=24h)
kubectl config set-credentials platform-ro --token="$TOKEN"
kubectl config set-context platform-ro \
  --cluster=kind-metacortex-lab --user=platform-ro
kubectl config use-context platform-ro
```

O token expira depois de `--duration`; repita o `kubectl create token` e o
`set-credentials` para renová-lo. Para voltar ao contexto anterior (por
exemplo, o de administrador), use `kubectl config use-context <nome>`.

O mesmo procedimento, trocando `platform-ro` por `platform-ro-sem-events`,
reproduz o cenário de permissão parcial.

## Rodando

```bash
./.venv/bin/painel-cluster
```

Sem argumento obrigatório. A tela sobe contra o contexto corrente do
kubeconfig no momento em que é chamada — não há seletor de cluster nem de
contexto dentro do painel; quem quiser outro cluster troca o contexto por
fora (`kubectl config use-context ...`) e sobe o painel de novo.

`--kubeconfig CAMINHO` aponta para um kubeconfig específico, em vez da
resolução normal do cliente (`KUBECONFIG`, ou `~/.kube/config`). Em qualquer
caso, é sempre o contexto **corrente** daquele arquivo que a tela lê.

### Teclas

| Tecla | Efeito |
|---|---|
| `Tab` | alterna o foco entre a lista de namespaces e o painel de objetos |
| `↑` `↓` | move a seleção no painel focado |
| `/` | busca por nome — filtra por substring dentro do namespace selecionado |
| `Esc` | limpa a busca |
| `r` | atualiza agora, sem esperar o intervalo |
| `q` | sai |

### Códigos de saída

| Código | Quando |
|---|---|
| 0 | saída normal, pelo `q` |
| 1 | erro de uso — argumento inválido |
| 2 | não há kubeconfig legível, ou o contexto corrente não existe |

Cluster inalcançável **não** é código de saída diferente de zero: a tela
sobe, mostra o estado de indisponível com o endereço tentado, e continua
tentando nos próximos ciclos.

## Rodando os testes

```bash
./.venv/bin/pip install pytest pytest-socket PyYAML  # ferramentas de teste, não de execução
./.venv/bin/pytest
```

Para conferir que a suíte não depende de rede (o transporte é sempre
simulado — ver `docs/03-divergencias-da-implementacao.md`):

```bash
./.venv/bin/pytest --disable-socket --allow-unix-socket
```

(`--allow-unix-socket` é sobre IPC local do processo — o self-pipe que o
próprio laço de eventos do Python abre — não sobre rede; uma conexão de rede
de verdade continua bloqueada com a flag presente. Ver comentário em
`pytest.ini`.)

## Estrutura

```
src/painel_cluster/
  cliente.py   fronteira de leitura — único módulo que importa `kubernetes`/`urllib3`
  modelo.py    interpretação pura do JSON cru — sem rede, sem cluster
  tela.py      interface de terminal (Textual)
  cli.py       ponto de entrada `painel-cluster`
rbac/          os dois perfis de permissão de leitura
tests/         suíte de testes, com fixtures capturadas do cluster real
docs/          comportamento e decisões técnicas
openspec/      especificação formal (proposal, design, specs, tasks)
```

## Garantia de só-leitura

Três camadas independentes, nenhuma delas sozinha:

1. **Fronteira única.** Só `cliente.py` importa `kubernetes`/`urllib3`; nenhum
   outro módulo do pacote pode.
2. **Teste automatizado.** `tests/test_contencao.py` falha se aparecer verbo
   de escrita em `src/`, ou se algum módulo fora de `cliente.py` importar o
   cliente/transporte.
3. **RBAC do contexto recomendado.** `platform-ro` não concede verbo de
   escrita, nem `watch`, nem `secrets` — o cluster recusa o que o código
   venha a tentar, independente do repositório.
