## Purpose

A tela de terminal por onde quem opera lê o retrato de um namespace: como os
painéis se organizam, como se filtra e se busca, com que frequência o dado se
renova, e como cada forma de falha é desenhada sem deixar a tela em branco.

## ADDED Requirements

### Requirement: O destino fica visível o tempo todo

O sistema SHALL exibir permanentemente o nome do contexto corrente e o endereço do
servidor a que está conectado.

#### Scenario: Destino visível também em falha

- **WHEN** o cluster está inalcançável ou a credencial foi recusada
- **THEN** o contexto e o endereço do servidor continuam visíveis na tela

### Requirement: Seleção de namespace

O sistema SHALL exibir a lista de namespaces do cluster e SHALL permitir selecionar
um, restringindo todos os demais painéis ao namespace selecionado.

#### Scenario: Trocar de namespace troca o retrato

- **WHEN** quem opera seleciona outro namespace
- **THEN** todos os painéis passam a mostrar objetos daquele namespace

### Requirement: Busca por nome

O sistema SHALL permitir filtrar os objetos exibidos por trecho do nome, dentro do
namespace selecionado.

#### Scenario: Busca por trecho

- **WHEN** quem opera digita um trecho na busca
- **THEN** cada painel passa a mostrar apenas os objetos cujo nome contém aquele trecho

#### Scenario: Limpar a busca

- **WHEN** quem opera limpa a busca
- **THEN** todos os objetos do namespace selecionado voltam a aparecer

### Requirement: Atualização periódica com a idade do dado visível

O sistema SHALL renovar os dados do namespace selecionado em intervalo fixo, SHALL
permitir uma renovação imediata sob comando, e SHALL exibir há quanto tempo o dado
mostrado foi obtido.

#### Scenario: A idade do dado aparece

- **WHEN** a tela está exibindo dados
- **THEN** ela mostra há quanto tempo aqueles dados foram lidos

#### Scenario: Renovação sob comando

- **WHEN** quem opera pede a renovação
- **THEN** o sistema lê o cluster imediatamente, sem esperar o próximo intervalo

#### Scenario: A lista de namespaces renova em ritmo próprio

- **WHEN** o painel está aberto
- **THEN** a lista de namespaces é renovada com intervalo maior que o dos objetos do
  namespace selecionado

### Requirement: Cada estado do envelope tem desenho próprio

O sistema SHALL desenhar os quatro estados de envelope de forma distinguível, e
MUST NOT apresentar ausência de permissão ou indisponibilidade como lista vazia.

#### Scenario: Painel sem permissão

- **WHEN** o envelope de um tipo está no estado negado
- **THEN** o painel daquele tipo informa que falta permissão para lê-lo
- **AND** os demais painéis continuam exibindo seus objetos

#### Scenario: Painel sem objetos

- **WHEN** o envelope de um tipo está no estado vazio
- **THEN** o painel informa que não há objetos daquele tipo no namespace

### Requirement: Nenhuma falha esvazia a tela

O sistema MUST NOT apresentar tela em branco nem deixar rastreamento de pilha
chegar ao terminal, em nenhuma das formas de falha previstas.

#### Scenario: Cluster inalcançável

- **WHEN** o apiserver não aceita conexão
- **THEN** a tela informa que o cluster não respondeu e mostra o endereço tentado
- **AND** o sistema continua tentando nos intervalos seguintes

#### Scenario: Credencial recusada

- **WHEN** a credencial do contexto corrente é recusada
- **THEN** a tela informa que a credencial foi recusada, com contexto e servidor visíveis

### Requirement: Códigos de saída

O sistema SHALL encerrar com código 0 em saída normal, 1 em erro de uso e 2 quando
não houver kubeconfig legível ou contexto corrente válido. Ambiente hostil alcançado
em execução MUST NOT produzir código de saída diferente de zero.

#### Scenario: Cluster inalcançável não é erro de execução

- **WHEN** o painel roda uma sessão inteira contra um cluster que não responde e
  quem opera encerra normalmente
- **THEN** o código de saída é 0

#### Scenario: Contexto corrente inexistente

- **WHEN** não há contexto corrente utilizável no kubeconfig
- **THEN** o sistema encerra com código 2 antes de desenhar a tela
