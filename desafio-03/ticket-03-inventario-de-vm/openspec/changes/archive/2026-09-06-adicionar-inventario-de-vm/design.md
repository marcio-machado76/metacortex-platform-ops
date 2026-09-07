## Context

A motivação está em `proposal.md`. O comportamento observável e os critérios de
aceite estão em `docs/01-comportamento.md`; as dez decisões técnicas, com as
alternativas descartadas, estão em `docs/02-decisoes-tecnicas.md`. Este documento
não repete nenhum dos dois — ele cobre a arquitetura interna, que é o que aqueles
não fixam.

Restrições que moldam o desenho:

- A ferramenta roda na estação de quem opera. Não há agente nos hosts e não haverá.
- O usuário da coleta é comum, sem privilégio. Parte do baseline é ilegível para
  ele, e isso é o caso normal, não a exceção.
- Dois invariantes não negociáveis: só leitura, e a chave privada não vaza.
- O critério de aceite mais difícil de demonstrar é o de repetibilidade.

## Goals / Non-Goals

**Goals**

- Tornar o julgamento verificável sem host, para que a repetibilidade do veredito
  seja demonstrada em teste automatizado.
- Isolar tudo que depende de rede num único ponto, de modo que o resto seja
  testável com dado gravado.
- Fazer com que dado ausente atravesse o sistema como valor, e não como exceção.

**Non-Goals**

- Abstrair sobre múltiplos sistemas operacionais. O baseline diz `ubuntu`; o
  coletor assume Linux com gerenciador de serviços systemd e falha de forma
  legível fora disso.
- Suportar coleta paralela de frota, transporte alternativo ao SSH ou persistência
  de histórico.
- Otimizar tempo de coleta. O gargalo é a rede, e a ferramenta faz uma ida só.

## Decisions

### Quatro módulos, com a rede confinada em um

```
cli          → argumentos, orquestração, código de saída
coletor      → ÚNICO módulo que fala com a rede; devolve um inventário
avaliador    → função pura (inventário, baseline) → conformidade
relatorio    → serializa o mesmo dado em JSON e em Markdown
```

O avaliador e o relatório não conhecem SSH e não importam Paramiko. Consequência
prática: a suíte de testes exercita as regras de conformidade sobre inventários
gravados em arquivo, sem host, sem rede e sem espera — e é isso que torna o
critério de repetibilidade demonstrável em CI, não só na VM.

**Alternativa descartada:** um módulo único que coleta e julga em passada única.
Menos código, e faria a suíte inteira depender de um host de laboratório de pé.

### O inventário é um dado, não um objeto vivo

O coletor devolve uma estrutura simples, serializável, com campo desconhecido
representado por nulo. Ela é o contrato entre o coletor e todo o resto, e é o que
os testes gravam como fixture.

Isso obriga a decisão sobre ausência a ser tomada uma vez, no coletor, em vez de
espalhada por cada regra. O avaliador recebe "não sei" como valor e o traduz em
veredito — ele nunca precisa perguntar se a coleta funcionou.

### Um script composto com marcadores

A sessão executa um único script que emite blocos delimitados, um por grupo de
dados. O motivo está em `docs/02-decisoes-tecnicas.md`, decisão D5: aproximar
`coletado_em` de um instante real em vez de uma janela de vários segundos.

O protocolo entre o script e o analisador é a parte frágil e precisa ser explícita:

- cada bloco abre com um marcador próprio numa linha só;
- bloco cujo comando falhou sai **vazio**, não ausente — o script não interrompe;
- bloco ausente na saída, bloco vazio e bloco em formato não reconhecido levam o
  campo correspondente a nulo, com motivos distintos;
- o script não escreve nada em disco no host e não depende de nada além do que
  vem na instalação padrão.

**Alternativa descartada:** transferir um script para o host e executá-lo de lá.
Seria escrita no host, o que viola o primeiro invariante.

### Registro de regras indexado pelo caminho do baseline

Cada regra do baseline (`swap.habilitado`, `portas_em_escuta.publicas_permitidas`,
…) tem uma função de avaliação registrada sob o seu caminho. O avaliador percorre
as regras **declaradas no arquivo**, não uma lista fixa no código.

Isso dá de graça o comportamento exigido para regra desconhecida: caminho sem
função registrada vira `nao_verificado` com motivo, em vez de ser ignorado em
silêncio.

**Alternativa descartada:** um motor genérico que interpreta o baseline sem
código por regra. As onze regras têm formas incompatíveis — comparação de versão,
pertinência em lista, classificação de endereço, correspondência de sufixo em nome
de unidade. Um motor genérico o bastante para todas seria mais difícil de ler que
onze funções pequenas.

### Falhas de rede viram um tipo próprio antes de virar código de saída

O coletor traduz as exceções do transporte em uma falha de alcance com mensagem
pronta para leitura. A CLI mapeia essa falha para o código de saída; nenhum rastro
de pilha chega ao terminal.

A separação importa porque a mensagem precisa distinguir três causas com a mesma
consequência — endereço errado, credencial recusada e SSH fora do ar — e essa
distinção existe no transporte, não na CLI.

## Risks / Trade-offs

| Risco | Mitigação |
|---|---|
| O script composto quebra em host com saída inesperada e derruba vários campos de uma vez | Blocos independentes: falha de um bloco não afeta os outros, e o campo vira nulo com motivo em vez de erro |
| `nao_verificado` vira tapete: a ferramenta reporta muita coisa como não verificada e ninguém percebe | O resumo conta os três vereditos separadamente e as duas saídas têm seção própria para não verificado; a contagem total é conferida contra o número de regras |
| Recusar host desconhecido por padrão atrapalha o primeiro contato com VM recém-provisionada | Opção explícita de aceitação, que registra na saída que a identidade não foi verificada |
| A comparação de versão erra em formatos que não previmos (kernel com sufixo de distribuição, versão com letra) | Componentes numéricos iniciais, com teste sobre os formatos reais das duas VMs de laboratório e sobre formatos anômalos |
| Um erro de digitação no comando ser lido como host fora do ar | O comportamento padrão do analisador de argumentos é sobrescrito para o código de erro interno — ver D7 |
| A suíte passar com dado gravado e a coleta real divergir | As fixtures são geradas a partir de execuções reais contra as duas VMs, e a validação final roda contra elas |

## Migration Plan

Não há migração. A ferramenta é nova, não substitui nada automaticamente e não
escreve em lugar nenhum. O Roster manual continua existindo até que alguém decida
aposentá-lo, e essa decisão não é desta entrega.

Reversão é apagar o diretório: não há estado, serviço nem agente instalado.

## Open Questions

Nenhuma que altere as specs, a abordagem ou a divisão de tarefas. As duas dúvidas
que surgiram no amadurecimento foram resolvidas em
`docs/02-decisoes-tecnicas.md`: a política de identidade de host (D3) e a
classificação de endereço de escuta (D8).
