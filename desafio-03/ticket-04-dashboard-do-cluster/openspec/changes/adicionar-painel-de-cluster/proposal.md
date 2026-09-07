## Why

Toda triagem no parque começa igual: alguém abre o terminal e roda de seis a dez
`kubectl` para montar na cabeça o retrato de um namespace. Esse retrato é sempre o
mesmo — pods e seus estados, controladores e quantas réplicas estão prontas,
Services e se eles têm para onde mandar tráfego, eventos recentes — e reconstruí-lo
à mão a cada chamado gasta os primeiros dez minutos de todos eles.

O `painel-cluster` põe esse retrato numa tela. Não substitui o terminal: encurta a
abertura do chamado.

A oportunidade é agora porque o cluster do parque já tem os dois lados da amostra
no ar — workload saudável e os três chamados patológicos do Ticket 02 — e porque as
decisões técnicas já foram tomadas e medidas contra ele, em `docs/00-brainstorm.md`,
`docs/01-comportamento.md` e `docs/02-decisoes-tecnicas.md`.

## What Changes

- Aplicação de terminal em Python com Textual, empacotada como `painel-cluster`,
  que sobe contra o **contexto corrente** do kubeconfig e só ele.
- Leitura da API pelo cliente oficial `kubernetes` com `_preload_content=False`,
  confinada a um **único módulo** — nenhum outro importa `kubernetes` nem
  `urllib3`.
- Sete tipos de recurso lidos por `LIST`, cada um num **envelope independente** com
  quatro estados possíveis: `ok`, `vazio`, `negado`, `indisponível`. São seis no
  escopo do namespace selecionado mais os namespaces, que é a única leitura de
  escopo de cluster — e que passa pelo mesmo envelope que os outros.
  <!-- Corrigido durante a implementação: a primeira versão dizia "seis tipos" e
       esquecia que a lista de namespaces também é lida por LIST e também precisa
       de envelope. A spec e as tarefas já diziam sete. -->
- Tela com lista de namespaces, painéis de pods, controladores, services e eventos,
  filtro por namespace, busca por nome e ordenação por anormalidade **com o critério
  visível**.
- Atualização em intervalo fixo escopado ao namespace selecionado, com a idade do
  dado sempre na tela.
- Dois perfis RBAC versionados em `rbac/`, já aplicados: `platform-ro` como jeito
  documentado de rodar, `platform-ro-sem-events` como cenário de evidência.
- **Nenhuma operação de escrita, em nenhum caminho de código.** A garantia é
  aplicada em três camadas: ponto único de acesso, teste automatizado e RBAC.

Não é mudança incompatível: o projeto não existia.

## Capabilities

### New Capabilities

- `leitura-do-cluster`: a fronteira com o apiserver — resolução do contexto
  corrente, leitura somente-leitura dos sete tipos, o envelope de quatro estados
  por tipo, a classificação dos três ambientes hostis por tipo de exceção, e a
  normalização de campo ausente, nulo e vazio.
- `retrato-do-namespace`: o modelo exibível derivado do que foi lido — estado de
  pod que não é a fase, motivo de falha em duas metades, prontos sobre desejados
  para Deployment e StatefulSet, endereços de Service em três estados, eventos
  recentes, e a ordenação por anormalidade com o critério que a justifica.
- `interface-de-terminal`: a tela e a interação — os painéis, o filtro por
  namespace, a busca por nome, as teclas, a atualização em intervalo fixo com a
  idade do dado, e como cada estado do envelope é desenhado.

### Modified Capabilities

Nenhuma. Não existem specs em `openspec/specs/` nesta raiz.

## Impact

**Código novo**, todo dentro de `desafio-03/ticket-04-dashboard-do-cluster/`:
`src/` com os módulos, `tests/` com a suíte, `pyproject.toml` para o comando
`painel-cluster`, `requirements.txt` com a versão do cliente fixada.

**Dependências:** `kubernetes` (cliente oficial) e `textual`, ambos em versão
fixada. `urllib3` entra como dependência transitiva e é tratado como tal — a
exceção de transporte vem dele, e isso está registrado na D8.

**Nada fora do ticket é alterado.** Os manifests do Ticket 01 e os perfis RBAC já
estão no repositório e aplicados; o cluster não precisa de mudança para a
implementação começar.

**Fora do escopo, e declarado:** watch, multicluster, logs, `describe`,
visualização de YAML, nós, métricas, DaemonSet, Job e CronJob.
