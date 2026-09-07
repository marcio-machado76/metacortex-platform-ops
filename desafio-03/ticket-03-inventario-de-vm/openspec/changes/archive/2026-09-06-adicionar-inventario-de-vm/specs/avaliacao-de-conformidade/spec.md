## Purpose

Julgar um inventário contra o padrão declarado do parque, produzindo uma entrada
por regra com veredito, severidade e motivo — sem acessar rede, de modo que o
julgamento possa ser verificado sobre inventários gravados.

## ADDED Requirements

### Requirement: Uma entrada por regra do baseline

A avaliação SHALL produzir exatamente uma entrada para cada regra declarada no
baseline, contendo qual regra, o que o baseline esperava, o que foi encontrado no
host e o veredito.

#### Scenario: Cobertura completa

- **WHEN** um inventário é avaliado contra um baseline
- **THEN** a quantidade de entradas de conformidade é igual à quantidade de regras
  do baseline

### Requirement: Três vereditos possíveis

O veredito SHALL ser um entre `conforme`, `desvio` e `nao_verificado`. Uma entrada
com veredito `desvio` SHALL carregar a severidade que o baseline atribui àquela
regra; uma entrada com veredito `nao_verificado` SHALL carregar o motivo.

#### Scenario: Regra atendida

- **WHEN** o inventário demonstra que o host atende a regra
- **THEN** o veredito é `conforme`

#### Scenario: Regra violada

- **WHEN** o inventário demonstra que o host não atende a regra
- **THEN** o veredito é `desvio` e a entrada traz a severidade declarada pelo
  baseline para aquela regra

#### Scenario: Regra que não pôde ser verificada

- **WHEN** o inventário registra como desconhecido o dado de que a regra depende
- **THEN** o veredito é `nao_verificado`, distinto de `conforme`, e a entrada traz
  o motivo pelo qual não foi possível verificar

### Requirement: Prova positiva de violação prevalece sobre leitura incompleta

Quando parte da evidência é desconhecida mas o que foi observado já demonstra
violação, o veredito SHALL ser `desvio`. O veredito SHALL ser `nao_verificado`
apenas quando a parte desconhecida é o que impede a conclusão.

#### Scenario: Evidência parcial já suficiente para reprovar

- **WHEN** uma parte da evidência é ilegível e a parte legível já demonstra
  violação da regra
- **THEN** o veredito é `desvio`

#### Scenario: Evidência parcial insuficiente para concluir

- **WHEN** toda a evidência legível está de acordo com a regra e alguma parte
  permanece ilegível
- **THEN** o veredito é `nao_verificado`, com motivo indicando a leitura incompleta

### Requirement: Recurso ausente é desvio, não falta de verificação

A ausência de um recurso que o baseline exige SHALL produzir veredito `desvio`. O
veredito `nao_verificado` SHALL ser reservado aos casos em que a observação não foi
possível.

#### Scenario: Serviço exigido não está ativo

- **WHEN** o baseline exige um serviço ativo e o inventário mostra que ele não está
- **THEN** o veredito é `desvio`, e não `nao_verificado`

### Requirement: Unidade ativa por socket satisfaz a exigência de unidade ativa

Quando o baseline nomeia uma unidade sem qualificar o tipo, a exigência SHALL ser
considerada atendida se a unidade estiver ativa como serviço ou como socket, e o
resultado SHALL indicar qual das duas formas foi encontrada. Quando o baseline
nomeia a unidade com o tipo, a correspondência SHALL ser exata.

#### Scenario: Unidade exigida ativa apenas como socket

- **WHEN** o baseline exige uma unidade sem qualificar o tipo e o inventário a
  mostra ativa como socket
- **THEN** o veredito é `conforme` e o resultado indica que ela está ativa na forma
  de socket

#### Scenario: Unidade proibida nomeada com o tipo

- **WHEN** o baseline proíbe uma unidade nomeando o seu tipo e o inventário mostra
  essa unidade ativa
- **THEN** o veredito é `desvio`

### Requirement: Classificação de endereço de escuta

A avaliação SHALL classificar cada porta em escuta como pública, de rede interna ou
de loopback, conforme o endereço a que está vinculada. Porta em loopback SHALL NOT
produzir desvio.

#### Scenario: Porta pública fora do permitido

- **WHEN** uma porta está vinculada a endereço público e não consta entre as
  publicamente permitidas
- **THEN** o veredito da regra correspondente é `desvio`

#### Scenario: Porta restrita à rede interna exposta publicamente

- **WHEN** uma porta que deveria ficar restrita à rede interna está vinculada a
  endereço público
- **THEN** o veredito da regra correspondente é `desvio`

#### Scenario: Porta em loopback

- **WHEN** uma porta está vinculada a endereço de loopback
- **THEN** ela não produz desvio em nenhuma das regras de porta

#### Scenario: Porta restrita que não está em escuta

- **WHEN** uma porta que deveria ficar restrita à rede interna não está em escuta
  em endereço nenhum
- **THEN** a regra correspondente é `conforme`

### Requirement: Regra desconhecida não é silenciada

Uma regra presente no baseline que a ferramenta não sabe avaliar SHALL receber
veredito `nao_verificado`, com motivo indicando que a versão da ferramenta não a
implementa. A ferramenta SHALL avisar quando a versão do baseline for posterior à
que ela conhece, e SHALL prosseguir com a avaliação.

#### Scenario: Baseline com regra não implementada

- **WHEN** o baseline declara uma regra que a ferramenta não sabe avaliar
- **THEN** a entrada correspondente tem veredito `nao_verificado` com motivo
  explícito, e a regra não é contada como conforme

### Requirement: A avaliação não depende de rede

A avaliação SHALL ser determinada exclusivamente pelo par inventário e baseline.
Avaliar o mesmo inventário contra o mesmo baseline SHALL produzir sempre o mesmo
resultado.

#### Scenario: Avaliação repetida sobre inventário gravado

- **WHEN** o mesmo inventário é avaliado repetidamente contra o mesmo baseline
- **THEN** o resultado é idêntico em todas as execuções, sem qualquer acesso ao
  host
