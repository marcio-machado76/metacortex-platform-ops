# Ticket 02 — Triagem no cluster

O alcance ao cluster já existe. O que faltava era método: o Dozer começa pelos eventos, o
Tank pelos logs, e quem entrou mês passado começa por onde der. Este ticket padroniza isso
antes que vire folclore de plantão.

## A lista de entrega, item a item

| O que o ticket pede | Onde está |
|---|---|
| **A skill** | [`skill/`](skill/) — `SKILL.md` e duas referências |
| **A origem dela** | [`execucoes/triagem-manual-origem-da-skill.md`](execucoes/triagem-manual-origem-da-skill.md) |
| **A saída real da triagem dos três chamados, com a causa de cada um** | [`execucoes/`](execucoes/) — saída bruta por chamado |
| **O resultado da matriz de roteamento** | [`matriz-roteamento/matriz.md`](matriz-roteamento/matriz.md) |
| **A comparação com e sem skill** | [`medicao-com-sem-skill/comparacao.md`](medicao-com-sem-skill/comparacao.md) |
| **A curadoria** (o que o método fixou, o que ficou com o agente, como se garante que não escreve) | seção final do `SKILL.md` e [`mcp/README.md`](mcp/README.md) |

## As três causas, em três camadas diferentes

Os três chamados chegam com o mesmo texto — *"o cliente diz que está fora do ar"*:

| Chamado | Causa | Onde apareceu |
|---|---|---|
| 1 · `nyx-prod` | `limits.memory: 24Mi` abaixo do runtime → `OOMKilled`, `exitCode 137` | `lastState.terminated` |
| 2 · `orion-stg` | a tag `v1.14.2` não existe no registry | `state.waiting.message` |
| 3 · `nyx-stg` | Service seleciona `app: nyx-api`, pods têm `app: nyxapi` | **só cruzando** dois objetos |

O terceiro é o que justifica o método: pods, deployment, eventos e logs estão todos limpos.
Nenhuma fonte isolada acusa — só o cruzamento.

Os ambientes estão em [`ambientes/`](ambientes/) e sobem com `kubectl apply -f`.

## Como se garante que a skill não escreve

Não é promessa de texto. O enunciado descreve o servidor MCP "em modo não-destrutivo", mas
essa flag **mantém `kubectl_apply` e `kubectl_scale` disponíveis**. O invariante do ticket é
mais forte — *"nunca escreve, nem quando o agente tem permissão"* —, então o servidor roda
com `ALLOW_ONLY_READONLY_TOOLS`. A configuração e o raciocínio estão em
[`mcp/`](mcp/).

**A skill também não traz script**, e isso é curadoria: qualquer script com acesso ao cluster
carregaria credencial própria e ficaria fora da garantia estrutural do servidor.

## A skill melhora o resultado ou só custa token?

A resposta medida é desconfortável e está publicada assim mesmo:

```
com skill   18/18 asserções   3/3 causas corretas   51.010 tokens
sem skill   17/18 asserções   3/3 causas corretas   43.947 tokens  (+16% para a skill)
```

**As duas arms acertaram os três diagnósticos.** A skill não paga o token pelo diagnóstico —
paga pela forma: disciplina de escopo, ruído nomeado como ruído, rastro de eliminação. Que é
exatamente o que foi pedido: *"parem de variar por pessoa"*, não "descubram mais rápido".

## A matriz de roteamento

Dez frases, dez sessões limpas: **8 limpas, 0 disparo errado, 2 ambíguas**. O único erro foi
do instrumento — `--max-turns 1` media o primeiro passo e não o roteamento, e três frases
gastavam esse passo procurando de que manifesto a pessoa falava.

Nenhuma descrição foi ajustada: não houve disparo errado que justificasse. As duas skills
ganharam uma linha sobre o que fazer quando o pedido não diz se o objeto já está no cluster —
que é o fato que desempata e que as frases ambíguas não trazem.
