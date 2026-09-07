# A skill melhora o resultado ou só custa token?

Três chamados, cada um rodado duas vezes em sessão limpa: uma com a skill
`triagem-de-cluster` e uma sem nenhuma skill. Mesmo prompt, mesmo cluster, mesmo
modelo. Saídas em `iteration-1/eval-*/`, com `timing.json` e `grading.json` por
rodada.

**Ressalvas que mudam a leitura destes números, e por isso vêm antes deles:**

1. **As rodadas foram em Sonnet, não no modelo da sessão.** As primeiras seis, em
   Opus, morreram por limite de sessão. O ganho medido é o ganho *naquele* modelo.
2. **A garantia de somente-leitura não foi medida aqui.** As duas arms receberam do
   harness a instrução de não escrever no cluster, para preservar o laboratório.
   Quem impede a escrita na operação real é o servidor MCP em
   `ALLOW_ONLY_READONLY_TOOLS`, não esta medição.
3. **Três casos, uma rodada cada.** Suficiente para ver forma; insuficiente para
   afirmar significância.

## Os números

| | com skill | sem skill | delta |
|---|---:|---:|---:|
| Asserções atendidas | **18/18** (100%) | 17/18 (94,4%) | +1 |
| Causa correta | 3/3 | 3/3 | 0 |
| Tokens (média) | 51.010 | 43.947 | **+16,1%** |
| Tempo (média) | 80,4 s | 79,0 s | +1,8% |
| Chamadas de ferramenta (média) | 9,7 | 6,7 | +45% |
| Relatório (linhas, média) | 55 | 83 | −34% |

## A resposta honesta: nos três casos, a skill não decidiu o diagnóstico

**As duas arms chegaram à causa certa nos três chamados.** Um modelo capaz, com
`kubectl` e um sintoma bem formulado, resolve OOM, tag inexistente e seletor
divergente sem método escrito. Quem esperava que a skill fosse a diferença entre
achar e não achar não vai encontrar isso aqui.

Vale registrar por quê: os três chamados são *bem-postos*. O sintoma vem com
namespace, o defeito é único, e o cluster está no estado do incidente. Triagem real
raramente chega assim.

## O que a skill comprou, então

**Disciplina de escopo.** A diferença aparece nas bordas, e são as bordas que
custam caro no plantão:

- No Chamado 2, a rodada sem skill recomendou "adicionar validação de existência de
  imagem no pipeline de CI/CD". É um bom conselho e não é triagem — o método diz
  que identificada a causa o trabalho acabou.
- No Chamado 3, a rodada sem skill foi olhar o `nyx-prod` para comparar convenção
  de rótulo. `nyx-prod` é *outro chamado*, com outro defeito, e dali ela concluiu
  qual seria "a convenção correta" a partir de uma amostra de um.

**Raciocínio explícito em vez de resultado.** A única asserção que separou as duas
foi a do Chamado 2: a rodada sem skill concluiu direto do `ImagePullBackOff`, sem
passar por `restartCount == 0`. Chegou ao mesmo lugar — mas perdeu o divisor que
separa "container que nunca rodou" de "container que rodou e morreu". Num chamado
menos evidente, é esse divisor que evita começar pelo log de um container que nunca
escreveu nada.

**Ruído nomeado como ruído.** No Chamado 3 há um pod com um reinício isolado, sem
relação com o 503. A rodada com skill o encontrou e o classificou explicitamente
como ruído; a rodada sem skill não o mencionou. As duas acertaram — mas só uma
deixou registrado que aquilo foi visto e descartado, que é o que impede a próxima
pessoa de persegui-lo.

**Menos texto para dizer o mesmo.** Relatórios 34% mais curtos, com formato fixo.
A rodada sem skill do Chamado 1 gastou 124 linhas e ainda assim afirmou que o
kube-news é "uma aplicação Go/HTTP" — ele é Node com Express. Detalhe inventado que
não mudou o diagnóstico, mas que num relatório de plantão vira folclore.

**Rastro de eliminação.** A seção "o que está saudável ao lado" aparece nas três
rodadas com skill por construção. Sem ela, a próxima pessoa a olhar o chamado
refaz a mesma eliminação.

## O custo

**+16% de tokens** — o preço de carregar a skill e consultar as referências. O
tempo praticamente não muda (+1,8%, dentro do ruído), e as chamadas de ferramenta
sobem 45% porque o método manda verificar coisas que a curiosidade não verificaria.

## Veredito

Nestes três casos, contra um modelo capaz, **a skill não paga o token pelo
diagnóstico — paga pela forma**. O que ela entrega é consistência entre pessoas e
entre chamados: mesmo formato, mesmo rastro, mesmo limite de escopo, independente
de quem está de plantão.

Isso é exatamente o que a Trinity pediu. O pedido não foi "descubram mais rápido",
foi "parem de variar por pessoa antes que vire folclore de plantão". Para esse
pedido, 16% de token é barato.

Onde eu esperaria ver ganho de diagnóstico, e que estes três casos não testam:
chamado com sintoma mal formulado, chamado com dois defeitos simultâneos, e
plantonista novo — que é o caso que motivou o ticket.
