## Purpose

Apresentar o mesmo dado em dois formatos com públicos diferentes — um consumido por
máquina e outro lido por pessoa no meio de um plantão — e terminar com um código de
saída que sirva de porta em pipeline.

## ADDED Requirements

### Requirement: Saída em JSON para consumo automático

A ferramenta SHALL produzir uma saída em JSON contendo a identificação do host, o
inventário, a lista de conformidade e o resumo.

#### Scenario: Estrutura da saída

- **WHEN** uma coleta é concluída
- **THEN** a saída em JSON traz identificação do host, inventário, uma entrada de
  conformidade por regra e o resumo

#### Scenario: Campo desconhecido no inventário

- **WHEN** um campo do inventário não pôde ser observado
- **THEN** ele aparece na saída em JSON com valor nulo, e não ausente nem com valor
  presumido

### Requirement: Saída em Markdown para leitura humana

A ferramenta SHALL produzir uma saída em Markdown, a partir do mesmo dado,
apresentando os desvios ordenados por severidade, o que não pôde ser verificado com
o respectivo motivo, e o que está conforme.

#### Scenario: Host com desvios

- **WHEN** o host apresenta desvios
- **THEN** a saída em Markdown lista cada desvio com severidade, regra, o que era
  esperado e o que foi encontrado, começando pelos de maior severidade

#### Scenario: Host sem nada a reportar em uma seção

- **WHEN** não há entradas para uma das seções
- **THEN** aquela seção não é apresentada

### Requirement: Resumo por veredito e por severidade

A saída SHALL trazer a contagem de regras por veredito, e a contagem de desvios por
severidade. A soma das contagens por veredito SHALL ser igual à quantidade de
regras do baseline.

#### Scenario: Contagem consistente

- **WHEN** uma avaliação é concluída
- **THEN** as contagens de conforme, desvio e não verificado somam a quantidade de
  regras do baseline, e a contagem por severidade considera apenas os desvios

### Requirement: Código de saída utilizável em pipeline

A ferramenta SHALL terminar com código distinto para cada desfecho: host sem
desvio, host com ao menos um desvio, host inalcançável e erro interno. Host
inalcançável SHALL NOT terminar com o mesmo código de host conforme. A presença de
regras não verificadas SHALL NOT alterar o código de saída.

#### Scenario: Host conforme

- **WHEN** a coleta conclui e nenhuma regra recebe veredito de desvio
- **THEN** a ferramenta termina com o código reservado a host conforme

#### Scenario: Host com desvio

- **WHEN** a coleta conclui e ao menos uma regra recebe veredito de desvio
- **THEN** a ferramenta termina com o código reservado a host com desvio

#### Scenario: Host conforme com regras não verificadas

- **WHEN** a coleta conclui sem desvios mas com regras não verificadas
- **THEN** a ferramenta termina com o código reservado a host conforme, e as regras
  não verificadas aparecem nas duas saídas e no resumo

#### Scenario: Argumento inválido

- **WHEN** a ferramenta é invocada com argumento inválido
- **THEN** ela termina com o código reservado a erro interno, distinto do código de
  host inalcançável

### Requirement: Falha de alcance é reportada de forma legível

Quando o host não pode ser alcançado, a ferramenta SHALL informar o que houve em
mensagem legível e SHALL NOT exibir rastro de pilha. O resultado SHALL NOT ser
confundível com o de um host conforme.

#### Scenario: Endereço sem serviço SSH respondendo

- **WHEN** o endereço informado não responde na porta de SSH
- **THEN** a ferramenta informa que o host está inalcançável, sem rastro de pilha, e
  termina com o código reservado a host inalcançável

#### Scenario: Credencial recusada

- **WHEN** o host responde mas recusa a credencial
- **THEN** a ferramenta informa que a autenticação falhou, sem rastro de pilha e sem
  expor a chave, e termina com o código reservado a host inalcançável
