## Purpose

A fronteira entre o painel e o apiserver: resolve o contexto corrente do
kubeconfig, lê os tipos de recurso que a tela usa sem nunca escrever, e entrega
cada tipo num envelope que carrega tanto o dado quanto o motivo de não haver dado.

## ADDED Requirements

### Requirement: Contexto corrente e somente ele

O sistema SHALL resolver o destino a partir do contexto corrente do kubeconfig no
momento em que sobe, e MUST NOT oferecer qualquer forma de trocar de contexto ou
de cluster durante a execução.

#### Scenario: O contexto corrente é o destino

- **WHEN** o kubeconfig tem vários contextos e um deles é o corrente
- **THEN** todas as leituras vão para o cluster daquele contexto
- **AND** nenhuma leitura vai para qualquer outro cluster declarado no kubeconfig

#### Scenario: Não existe kubeconfig legível

- **WHEN** não há kubeconfig acessível, ou o contexto corrente não existe nele
- **THEN** o sistema encerra com código de saída 2 e uma mensagem que nomeia a causa
- **AND** não apresenta rastreamento de pilha

### Requirement: Somente leitura

O sistema MUST NOT executar qualquer operação de escrita contra o apiserver. Isso
inclui criar, alterar, remover, escalar, drenar, anotar e rotular, em qualquer
caminho de código.

#### Scenario: Uma sessão inteira sob credencial restrita

- **WHEN** o painel roda por uma sessão completa sob uma credencial que só concede
  os verbos de leitura dos tipos que a tela usa
- **THEN** nenhuma requisição é recusada por falta de permissão
- **AND** o registro de auditoria do apiserver não contém verbo de escrita vindo do painel

### Requirement: Tipos lidos

O sistema SHALL ler namespaces em escopo de cluster, e pods, Deployments,
StatefulSets, Services, fatias de endereço de Service e eventos no escopo do
namespace selecionado.

#### Scenario: A leitura de namespace é a única de escopo de cluster

- **WHEN** um namespace está selecionado
- **THEN** os seis tipos restantes são lidos apenas naquele namespace
- **AND** a lista de namespaces é a única leitura que abrange o cluster inteiro

### Requirement: Envelope por tipo de recurso

Cada tipo de recurso SHALL ser lido de forma independente e SHALL produzir um
envelope com exatamente um de quatro estados: `ok`, `vazio`, `negado` ou
`indisponível`. A falha na leitura de um tipo MUST NOT impedir a entrega dos
demais.

#### Scenario: Permissão negada em um tipo, com os outros acessíveis

- **WHEN** a credencial não tem permissão para ler eventos, mas tem para os demais tipos
- **THEN** o envelope de eventos volta como `negado`
- **AND** os envelopes de pods, Deployments, StatefulSets e Services voltam como `ok` com seus itens

#### Scenario: Namespace sem objetos de um tipo

- **WHEN** a leitura de um tipo é bem-sucedida e não devolve item nenhum
- **THEN** o envelope volta como `vazio`
- **AND** `vazio` é distinguível de `negado` e de `indisponível`

### Requirement: Classificação dos ambientes hostis

O sistema SHALL distinguir credencial recusada, permissão negada e cluster
inalcançável, e MUST NOT depender do texto de mensagens de erro para fazê-lo.

#### Scenario: Credencial recusada

- **WHEN** a credencial do contexto corrente é inválida ou está vencida
- **THEN** o sistema classifica a falha como credencial recusada
- **AND** aplica essa classificação a todos os tipos

#### Scenario: Cluster que não responde

- **WHEN** o endereço do apiserver não aceita conexão
- **THEN** o sistema classifica a falha como cluster indisponível
- **AND** o sistema não encerra com código de saída diferente de zero por causa disso

#### Scenario: A causa da recusa de credencial não é afirmada

- **WHEN** a credencial é recusada
- **THEN** o sistema relata que a credencial foi recusada
- **AND** MUST NOT afirmar que ela está expirada, porque credencial vencida e
  credencial inválida chegam de forma indistinguível

### Requirement: A leitura não interpreta

O sistema SHALL entregar, dentro do envelope, a resposta da API como ela veio, e
MUST NOT normalizar, derivar nem reclassificar campo algum nesta camada.

#### Scenario: A resposta chega intacta

- **WHEN** a leitura de um tipo é bem-sucedida
- **THEN** o envelope carrega a resposta com as mesmas chaves que a API devolveu
- **AND** chave ausente e chave com valor nulo continuam distinguíveis dentro dele

<!-- Corrigido durante a implementação. Esta capacidade trazia os requisitos de
     normalização de ausente/nulo/vazio e de distinção entre zero afirmado e nada
     afirmado. Os dois são interpretação, e a decisão D-A do design.md diz que
     nenhuma interpretação acontece na camada de leitura. Estavam na capacidade
     errada e foram movidos para retrato-do-namespace. No lugar deles ficou o
     requisito acima, que é o que esta camada de fato deve garantir: entregar a
     resposta sem tocá-la. -->
