# O que aconteceu com as duas skills durante o Ticket 04

Entregável do ticket. Ele pede **quatro** coisas, e a quarta é a que costuma ser
esquecida: quais skills dispararam sozinhas, quais tiveram que ser chamadas na mão,
quais apareceram onde não deviam, **e o que acabou sendo reexplicado ao agente
repetidamente mesmo tendo as duas instaladas**.

Registrado na ordem em que aconteceu, do que veio antes do ticket ao fim da
validação.

---

## Antes do ticket começar

**O servidor MCP estava explicitamente desabilitado.**

A `triagem-de-cluster` depende do servidor MCP de Kubernetes, declarado no
`.mcp.json` do escopo do projeto. Quem registra se ele foi autorizado nesta máquina
é o `.claude/settings.local.json`, e lá ele estava recusado — por um "não" num
diálogo de aprovação, em alguma sessão anterior.

O sintoma engana: `claude mcp list` responde **"No MCP servers configured"**, que se
lê como "não há MCP" e não como "o MCP foi recusado". A skill teria falhado, ou
caído silenciosamente para `kubectl` direto, sem que o motivo aparecesse.

É o tipo exato de coisa que o ticket manda capturar: **ferramenta ausente por um
motivo que não aparece no lugar onde a falha se manifesta.**

E há um segundo tempo nisso: as sessões anteriores foram abertas no diretório
**acima** do repositório. Efeito colateral que ninguém percebeu na hora — as duas
skills entregues nunca estiveram em escopo, e os procedimentos do OpenSpec tiveram
que ser lidos e seguidos à mão em vez de invocados.

---

## 1 · Quais dispararam sozinhas

### `padrao-de-manifests`, em modo escrita — o único disparo positivo

Aconteceu ao gerar os manifests do kube-news para o `nyx-dev`. O pedido era
"escrever manifesto novo para um projeto", que é o gatilho declarado dela, e ela
entrou sem ser nomeada.

O disparo mudou o resultado, e dá para dizer exatamente onde: **a skill manda
começar pelo projeto, não pelo YAML.** Foi lendo `src/system-life.js` que apareceu
a armadilha do kube-news — ele expõe `/health` **e** `/ready`, com os nomes exatos
que a regra 2.2 sugere, e `/ready` não checa nada. Sem esse passo, a readiness teria
ido para `/ready` por parecer óbvio, e o pod responderia "pronto" com o banco
desligado.

Isso se pagou uma hora depois, **no outro projeto**: o `orion-web` subiu contra um
banco sem tabela e ficou `Running` com zero reinícios, e só a readiness denunciou —
porque o alvo escolhido no Ticket 01 foi `/`, que toca o banco.

### `brainstorm`

Entrou por descrição, sem ser nomeada, quando a conversa passou a ser sobre
amadurecer a ideia do dashboard. Comportamento correto.

---

## 2 · Quais tiveram que ser chamadas na mão

### As três do fluxo git

`gerar-branch`, `preparar-stage` e `gerar-commit` foram invocadas porque a
convenção do repositório nomeia o fluxo, não porque o pedido as descreveu. O pedido
era "commite".

Um atrito registrado: a `gerar-commit` manda *"mostre a mensagem e confirme antes de
commitar"*. Como a autorização já tinha vindo no mesmo pedido, a mensagem foi
mostrada e o commit feito no mesmo passo. É desvio da letra da skill, com motivo —
mas é desvio, e fica registrado como tal em vez de disfarçado.

### `openspec-propose`

Disparo parcial, e vale a honestidade: o pedido dizia "segue para o ciclo do
OpenSpec". Isso nomeia o **procedimento**, não a skill — a escolha entre as seis do
OpenSpec foi feita por descrição.

O que importa aqui é o contraste com as sessões anteriores: **foi a primeira vez
neste desafio que o procedimento do OpenSpec foi invocado em vez de lido e seguido
à mão.** A diferença não veio da skill ter melhorado; veio da sessão ter sido aberta
na raiz do repositório.

---

## 3 · Quais apareceram onde não deviam

**Nenhuma.** Zero disparo indevido no ticket inteiro. Mas dois casos merecem ser
escritos, porque o não-disparo aqui é resultado e não ausência de resultado.

### A `triagem-de-cluster` não disparou, e era o candidato óbvio

**Isto foi registrado como hipótese no começo do brainstorm, antes de se saber o
resultado** — o que faz dele medição e não observação conveniente.

O assunto do Ticket 04 *é* pod reiniciando, deployment em 0/N e Service sem
endereço. São as frases-gatilho da skill, e elas apareceram dezenas de vezes na
conversa, nos documentos e nas evidências. Ela nunca entrou.

O critério dela é o objeto **já estar rodando e apresentando problema**, como
chamado. Aqui os mesmos objetos foram lidos como **dado de projeto**: fonte de
fixture, amostra de validação, exemplo de forma de campo. A distinção que a
descrição da skill faz — triagem contra construção de ferramenta — se sustentou sob
a pressão de um ticket inteiro cheio de vocabulário dela.

### A `padrao-de-manifests` não disparou durante o brainstorm, e também está certo

Os manifests do `orion-prod` foram lidos, e as regras 1.2 e 3.7 entraram na
discussão de nome. Ela não entrou.

O gatilho dela é escrever manifesto novo ou conferir manifesto existente. **Ler
manifesto para decidir arquitetura de outra coisa não é nem um nem outro.** Ela
entrou depois, quando o pedido virou escrever de fato — o que mostra que o
discriminador é a ação pedida, não o vocabulário presente.

### Uma ferramenta em escopo que nunca foi usada

Com a sessão aberta na raiz, as ferramentas `mcp__kubernetes__*` estavam
disponíveis em modo somente-leitura. **Nenhuma foi usada.** Todo acesso ao cluster
foi por `kubectl` no shell.

Não é defeito, é sintoma do tipo de trabalho: quase toda leitura precisou ser
canalizada para `python3` ou `grep` — comparar chaves de topo entre dois objetos,
contar eventos com `series` preenchido, extrair o `command` do apiserver. As
ferramentas MCP entregam o objeto; o que o ticket exigiu foi **inspecionar a forma
do objeto**, e para isso o shell é o instrumento.

---

## 4 · O que foi reexplicado repetidamente, mesmo com as duas skills instaladas

A pergunta mais reveladora das quatro, e a resposta é incômoda.

Quatro ondas de implementação rodaram em contexto frio. **Cinco regras tiveram que
ser escritas à mão em todos os quatro prompts**, palavra por palavra:

| Regra reexplicada | Onde ela mora hoje |
|---|---|
| Nada afirmado sem ser rodado | `estado-da-entrega.md`, fora do repositório |
| Caixa marcada significa verificado, não escrito | idem |
| Implementação por agente em contexto frio, a partir só dos artefatos | idem |
| Não conserte artefato de spec por conta própria — reporte | idem |
| Não invente requisito que a spec não tem, e não afrouxe critério para acomodar defeito | idem |

**Nenhuma delas está em skill nenhuma.** As duas entregues cobrem método de
**domínio** — o padrão de manifests e a triagem de cluster. O que precisou ser
repetido quatro vezes foi método de **trabalho**, e para isso não existe skill.

Some-se que elas vivem num documento de continuidade que é externo à entrega e
descartável quando o desafio fechar. Duas consequências práticas:

- cada onda custou um prompt longo, e a diferença entre elas não era o escopo, era o
  preâmbulo repetido;
- se uma dessas regras faltasse num prompt, a onda ainda entregaria — e entregaria
  pior, sem que o defeito fosse óbvio. A quarta onda mostra isso pelo avesso: a
  regra "não conserte, reporte" é o que fez o critério de aceite falho **aparecer**
  em vez de ser silenciosamente contornado.

**O que isso sugere, e que não é decisão deste ticket:** a skill que faltou nunca
foi de domínio. Era uma de método de entrega — o que significa caixa marcada, o que
significa contexto frio, o que se faz ao encontrar documento errado. É exatamente o
argumento do Tema 2 do enunciado, chegando pelo avesso: descobri o que deveria ter
sido empacotado por ter reescrito à mão quatro vezes.

---

## Resumo

| Pergunta do ticket | Resposta |
|---|---|
| Dispararam sozinhas | `padrao-de-manifests` em modo escrita, e a `brainstorm` |
| Chamadas na mão | as três do fluxo git; a `openspec-propose` por descrição, com o procedimento nomeado no pedido |
| Apareceram onde não deviam | nenhuma, em nenhum momento |
| Reexplicado repetidamente | as cinco regras de método de trabalho, em todos os quatro prompts de implementação — nenhuma delas coberta por skill |

E a entrada que antecede tudo: a skill mais bem escrita do mundo não dispara se o
servidor de que ela depende foi recusado numa sessão anterior e o sintoma disso é
uma mensagem que diz outra coisa.
