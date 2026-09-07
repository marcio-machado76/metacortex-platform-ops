## Purpose

O modelo exibível de um namespace: transforma o que foi lido do cluster nas linhas
que a tela mostra, sem afirmar nada que a API não sustente e sem esconder o critério
que ordena o que aparece primeiro.

## ADDED Requirements

### Requirement: O estado de um pod não é a sua fase

O sistema SHALL derivar o estado exibido de um pod da fase, da marca de remoção e
do estado dos seus containers, e MUST NOT exibir a fase sozinha como estado.

#### Scenario: Pod em remoção

- **WHEN** um pod tem marca de remoção e sua fase ainda é `Running`
- **THEN** o estado exibido é `Terminating`

#### Scenario: Pod reiniciando em laço

- **WHEN** a fase de um pod é `Running` e o container está aguardando com motivo
  `CrashLoopBackOff`
- **THEN** o estado exibido é `CrashLoopBackOff`

#### Scenario: Pod que subiu mas não está pronto

- **WHEN** a fase de um pod é `Running`, ele não reiniciou nenhuma vez e nenhum dos
  seus containers está pronto
- **THEN** a tela mostra o estado `Running` e a contagem de prontos `0/1`
- **AND** o pod é marcado como anormal pela contagem de prontos

### Requirement: O motivo de uma falha tem duas metades

Para container em falha, o sistema SHALL exibir tanto o motivo do estado corrente
quanto o motivo do encerramento anterior, quando ambos existirem.

#### Scenario: Laço de reinício por falta de memória

- **WHEN** o estado corrente do container tem motivo `CrashLoopBackOff` e o
  encerramento anterior tem motivo `OOMKilled`
- **THEN** a tela mostra os dois motivos
- **AND** o motivo do encerramento anterior é apresentado como a causa

### Requirement: Prontos sobre desejados para Deployment e StatefulSet

O sistema SHALL exibir Deployments e StatefulSets no mesmo painel, com a mesma
contagem de réplicas prontas sobre réplicas desejadas.

#### Scenario: Nenhuma réplica pronta

- **WHEN** um Deployment deseja três réplicas e nenhuma está pronta
- **THEN** a tela mostra `0/3`

#### Scenario: Réplica única ao lado de duas

- **WHEN** um namespace tem um controlador de uma réplica e outro namespace tem um
  de duas, ambos com todas prontas
- **THEN** os dois aparecem com o mesmo formato de coluna, `1/1` e `2/2`

### Requirement: Condição de controlador só existe onde a API a fornece

O sistema SHALL exibir condição de controlador apenas para os tipos em que a API a
fornece, e MUST NOT apresentar a ausência dessa informação como estado ruim.

#### Scenario: StatefulSet não tem condição

- **WHEN** um StatefulSet está com todas as réplicas prontas e seu status não traz
  condições
- **THEN** a linha do StatefulSet não exibe coluna de condição
- **AND** ele não é marcado como anormal por esse motivo

### Requirement: Um Service tem três estados de endereço

O sistema SHALL derivar o estado de endereços de um Service das fatias de endereço
associadas a ele, distinguindo três casos: sem endereço, com endereços nem todos
prontos, e com todos os endereços prontos.

#### Scenario: Service cujo seletor não casa com pod nenhum

- **WHEN** um Service não tem nenhum endereço associado
- **THEN** a tela mostra `sem endereço`
- **AND** o Service é marcado como anormal, ainda que todos os pods do namespace estejam prontos

#### Scenario: Endereços presentes, nem todos prontos

- **WHEN** um Service tem três endereços e dois estão prontos
- **THEN** a tela mostra `2 de 3 prontos`

### Requirement: Eventos recentes do namespace selecionado

O sistema SHALL exibir os eventos do namespace selecionado ocorridos na última
hora, ordenados do mais recente para o mais antigo, com tipo, motivo, objeto
envolvido, número de repetições e instante da última ocorrência.

#### Scenario: A ordenação não vem da API

- **WHEN** os eventos são lidos
- **THEN** o sistema os ordena por instante da última ocorrência antes de exibir

#### Scenario: A tela não afirma completude

- **WHEN** a lista de eventos é exibida
- **THEN** ela não é apresentada como o registro completo do que aconteceu no namespace

### Requirement: Ausência de sonda de prontidão é exibida como fato

O sistema SHALL indicar, por container, quando não existe sonda de prontidão
declarada, para que quem lê possa interpretar o estado de pronto daquele container.

#### Scenario: Container sem sonda de prontidão

- **WHEN** um container não declara sonda de prontidão
- **THEN** a tela indica a ausência da sonda naquela linha

#### Scenario: Pod com mais de um container

- **WHEN** um pod tem dois containers e apenas um declara sonda de prontidão
- **THEN** a tela indica a contagem `1/2`
- **AND** MUST NOT reduzir a informação a um único sim ou não para o pod inteiro

### Requirement: A tela relata, e não afirma saúde

O sistema SHALL usar o vocabulário que a API devolve, e MUST NOT apresentar
qualquer juízo de saúde — coluna, rótulo ou sinal — que não seja um dado lido do
cluster.

#### Scenario: Objeto pronto sem sonda que o sustente

- **WHEN** um container está pronto e não declara sonda de prontidão
- **THEN** a tela mostra que ele está pronto e que não há sonda
- **AND** MUST NOT afirmar que o objeto está saudável

### Requirement: Ordenação por anormalidade com o critério visível

O sistema SHALL ordenar os objetos de cada painel colocando primeiro os que
satisfazem algum critério de anormalidade, e SHALL exibir, em cada objeto assim
ordenado, qual critério o colocou ali. Os critérios MUST ser dados lidos do
cluster.

#### Scenario: Objeto anormal aparece primeiro, com o motivo

- **WHEN** um painel contém objetos anormais e objetos sem nenhum critério satisfeito
- **THEN** os anormais aparecem primeiro
- **AND** cada um deles exibe o critério que o classificou
- **AND** os demais aparecem depois, em ordem alfabética

#### Scenario: A ordem é auditável

- **WHEN** alguém discorda da ordem apresentada
- **THEN** o critério exibido em cada linha permite conferir a classificação contra
  o dado lido do cluster
