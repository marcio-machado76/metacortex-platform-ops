# coleta-de-inventario Specification

## Purpose
Obter o retrato real de uma VM do parque através de uma sessão SSH somente-leitura,
sem instalar agente e sem alterar nada no host, registrando explicitamente o que
não pôde ser observado em vez de omitir ou presumir.

## Requirements

### Requirement: Conexão autenticada com identidade do host verificada

A ferramenta SHALL conectar-se ao host usando endereço, usuário e chave privada
informados, e SHALL recusar host cuja identidade não conste na base de hosts
conhecidos, a menos que a aceitação de host desconhecido tenha sido pedida
explicitamente.

#### Scenario: Host conhecido

- **WHEN** a identidade do host confere com a base de hosts conhecidos
- **THEN** a sessão é estabelecida e a coleta prossegue

#### Scenario: Host desconhecido sem autorização explícita

- **WHEN** a identidade do host não consta na base de hosts conhecidos e a
  aceitação explícita não foi pedida
- **THEN** a coleta é recusada com mensagem dizendo que a identidade não pôde ser
  verificada, e nenhum comando é executado no host

#### Scenario: Host desconhecido com autorização explícita

- **WHEN** a aceitação de host desconhecido foi pedida explicitamente
- **THEN** a coleta prossegue e o resultado registra que a identidade do host não
  foi verificada

### Requirement: Retrato do host

A ferramenta SHALL registrar, para o host coletado: endereço usado na conexão,
nome que o próprio host reporta e instante da coleta; distribuição e versão do
sistema operacional; versão do kernel em execução; unidades ativas distinguindo
serviço de socket; se há swap habilitado e o seu tamanho; portas em escuta com
número, protocolo, endereço de vínculo e processo dono; chaves SSH autorizadas com
a sua identificação e o arquivo de origem; configuração efetiva de login de root; e
se o relógio está sincronizado e por qual mecanismo.

#### Scenario: Unidade ativada por socket

- **WHEN** uma unidade está ativa na forma de socket e não de serviço
- **THEN** o inventário registra o nome completo da unidade e o seu tipo, de modo
  que socket e serviço sejam distinguíveis

#### Scenario: Porta vinculada a endereço de loopback

- **WHEN** um processo escuta em endereço de loopback
- **THEN** a porta aparece no inventário com o seu endereço de vínculo, como
  qualquer outra

#### Scenario: Escopo da leitura de chaves autorizadas

- **WHEN** existem arquivos de chaves autorizadas que a coleta não consegue ler
- **THEN** o inventário registra as chaves lidas com o seu arquivo de origem, e o
  resultado permite distinguir leitura completa de leitura parcial

### Requirement: Dado não coletável é registrado como desconhecido

A ferramenta SHALL registrar como desconhecido todo campo que não pôde ser
observado, e SHALL NOT presumir valor, omitir o campo ou interromper a coleta por
causa dele.

#### Scenario: Dado que exige privilégio

- **WHEN** um dado só pode ser lido com privilégio que o usuário da coleta não tem
- **THEN** o campo correspondente é registrado como desconhecido e a coleta
  prossegue para os demais campos

#### Scenario: Recurso inexistente no host

- **WHEN** o host não dispõe do recurso necessário para observar um dado
- **THEN** o campo correspondente é registrado como desconhecido, distinguível do
  caso em que o recurso existe e o dado é ausente

### Requirement: A coleta não altera o host

A ferramenta SHALL executar apenas operações de leitura no host. Ela SHALL NOT
instalar, escrever, remover, corrigir ou reiniciar qualquer coisa do outro lado da
conexão.

#### Scenario: Estado do host após a coleta

- **WHEN** uma coleta é executada contra um host
- **THEN** o host permanece no mesmo estado em que estava antes dela

### Requirement: Retratos repetidos são idênticos

Duas coletas consecutivas contra um host inalterado SHALL produzir inventários
iguais, exceto pelo instante da coleta.

#### Scenario: Duas coletas seguidas

- **WHEN** duas coletas são executadas em sequência contra o mesmo host inalterado
- **THEN** a única diferença entre os dois inventários é o instante da coleta

#### Scenario: Ordenação de listas

- **WHEN** o host reporta listas cuja ordem não é garantida entre execuções
- **THEN** o inventário apresenta essas listas em ordem estável

### Requirement: A chave privada não vaza

A chave privada SHALL ser tratada como credencial. Ela SHALL NOT aparecer em
nenhuma saída, registro de execução ou mensagem de erro.

#### Scenario: Falha de autenticação

- **WHEN** a chave é recusada pelo host
- **THEN** a mensagem de erro informa que a autenticação falhou sem conter o
  conteúdo da chave
