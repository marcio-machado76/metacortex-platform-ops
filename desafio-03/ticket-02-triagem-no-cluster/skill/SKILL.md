---
name: triagem-de-cluster
description: >-
  Método de triagem para descobrir a causa de um workload com problema num cluster
  Kubernetes já em execução — pod que reinicia, que não sobe, deployment parado em
  0/N, Service que não entrega tráfego, aplicação que responde 503 ou que "está fora
  do ar". Use sempre que alguém relatar sintoma de cluster, mesmo sem usar a palavra
  triagem e mesmo quando o pedido parecer só um olhar rápido ("dá uma olhada nesse
  deployment", "por que isso está 0/3", "o service do nyx não tem endpoint", "o
  cliente diz que caiu"). Ela diz por onde começar, em que ordem descer as camadas,
  quando cruzar duas fontes e quando parar. Lê o cluster e nunca escreve — não
  aplica, não escala, não reinicia, não corrige. NÃO use para revisar manifesto
  antes de subir nem para conferir se um YAML segue o padrão da casa: isso é outra
  skill, e o critério é o objeto já estar rodando no cluster.
---

# Triagem de cluster

O alcance ao cluster já existe: as ferramentas de leitura do servidor MCP de
Kubernetes chegam em qualquer namespace do parque. O que falta é método — sem ele,
cada pessoa começa por onde está acostumada, e a triagem vira folclore de plantão.

Este método existe porque três chamados com o mesmo sintoma declarado — "o cliente
diz que está fora do ar" — tinham causa em três camadas diferentes: uma no
container, uma no registry, uma em metadado que nenhuma das duas primeiras revela.

## O limite, antes de tudo

**Triagem lê. Nunca escreve.** Nenhuma correção é aplicada no cluster por
iniciativa própria — nem quando a correção é óbvia, nem quando é uma linha, nem
quando o agente tem permissão para isso.

A razão não é timidez. Quem pede triagem está perguntando *o que houve*, e a
resposta a essa pergunta é informação, não ação. Aplicar a correção junto rouba de
quem opera a decisão de quando e como corrigir — e num parque com dezenas de
clusters, "óbvio" costuma esbarrar em algo que a triagem não vê: uma janela de
mudança, um cliente em contrato, um rollback em curso.

Ao terminar, entregue a causa e, se for útil, **descreva** a correção. Nunca a
execute.

## Passo 0 — Enquadrar antes de olhar

Antes do primeiro comando, fixe três coisas: **namespace**, **objeto** e **o que a
pessoa diz que está acontecendo**. Se algum estiver faltando, pergunte — um comando
disparado no namespace errado gera meia hora de conclusão sobre o workload errado.

Há um caso em que perguntar é obrigatório: pedidos como *"esse manifesto não sobe
no cluster"* não dizem se o objeto **já existe** no cluster. Se já existe e está com
problema, é triagem; se ainda vai subir, ou se o apiserver o está rejeitando, o
assunto é conformidade de manifesto e não é aqui. Você vai conseguir escolher um
dos dois de forma plausível sem perguntar — e plausível não é correto. Uma frase de
pergunta custa menos que uma triagem inteira na camada errada.

O sintoma declarado não diz a camada, mas diz por onde é mais barato começar:

| O que a pessoa diz | Comece por | Por quê |
|---|---|---|
| "reinicia sozinho", "CrashLoopBackOff" | estado do container: `state` **e** `lastState` | o motivo da morte anterior fica em `lastState`, não em `state` |
| "não sobe", "fica 0/N", "Pending" | `state.waiting.reason` + eventos | container que nunca rodou não tem `lastState` nem log |
| "parou depois do deploy" | rollout do Deployment + `state.waiting` | o objeto pode estar íntegro e o ReplicaSet novo travado |
| "está de pé e ninguém acessa", "503", "timeout" | Service × rótulos dos pods | as camadas de baixo estão todas limpas |
| "está lento" | fora do escopo desta triagem | latência não é falha; peça métrica, não estado |

## As camadas, e o que cada uma responde

Desça nesta ordem. Cada camada responde uma pergunta diferente, e subir de novo
depois de descer é sinal de que uma resposta foi lida como se fosse outra.

1. **Objeto de carga** (Deployment, StatefulSet, DaemonSet) — *quantas réplicas
   deveriam existir e quantas existem?* Aqui se separa "o rollout não anda" de "o
   rollout terminou e o problema é outro".
2. **Pod** — *ele foi agendado, e está pronto?* Fase e prontidão. Cuidado: a fase
   engana. Um pod em `CrashLoopBackOff` continua com fase `Running` — o estado de
   falha vive no container, não no pod.
3. **Container** — *o que aconteceu com o processo?* `state`, `lastState`,
   `exitCode`, `restartCount`. **É aqui que a maior parte das causas aparece.**
4. **Eventos do namespace** — *isto está se repetindo?* Eventos confirmam ciclo;
   raramente revelam causa. Um `BackOff` diz que o kubelet está desistindo, não por
   quê.
5. **Metadado e rede** — *o tráfego tem para onde ir?* Service, seletor,
   EndpointSlice. Esta camada é invisível para as quatro anteriores: quando o
   problema mora aqui, tudo acima aparece perfeitamente saudável.

**E, em paralelo à camada 1, verifique a dependência ao lado.** Todo workload do
parque vem em par com seu banco. Um comando confirmando que o Postgres do cliente
está pronto descarta uma hipótese inteira — e nos três chamados de referência ele
estava de pé, o que significa que quem gasta a triagem investigando o banco perde
o tempo todo.

## A bifurcação que decide o resto

Antes de qualquer aprofundamento, leia `restartCount`. Ele parte a árvore em duas:

- **`restartCount > 0`** — o container rodou e morreu. A causa está *no container*:
  memória, exceção na aplicação, dependência que falhou na subida. Vá para
  `lastState.terminated`: `reason` e `exitCode` costumam encerrar o assunto.
- **`restartCount == 0` com pod não pronto** — o container nunca rodou. A causa
  está *antes* dele: imagem, agendamento, volume, permissão. Vá para
  `state.waiting.reason` e `state.waiting.message`.

Dois chamados podem ter o mesmo texto de abertura e cair em lados opostos daqui. É
a leitura mais barata do método e a que mais evita trabalho perdido.

## Quando cruzar em vez de aprofundar

Aprofundar é olhar mais fundo na mesma fonte; cruzar é comparar duas fontes que
sozinhas não acusam nada. **Cruze quando as camadas 1 a 4 estiverem limpas e o
sintoma persistir.** Isso não é um beco sem saída — é a assinatura de um problema
de metadado, e o único jeito de vê-lo é comparar objetos:

- **Service que não entrega tráfego** → compare `spec.selector` do Service com
  `metadata.labels` dos pods do namespace. Divergência de um caractere basta, e
  ninguém reclama: o Service é criado sem erro e nasce sem destino.
- **Pod que não agenda** → compare `nodeSelector`, tolerations e afinidades do pod
  com os rótulos e taints dos nós.
- **Variável que "não chega"** → compare o nome da chave no ConfigMap ou Secret com
  o nome referenciado no container.

O padrão é sempre o mesmo: **algo que declara** contra **algo que é declarado**.
Quando o Kubernetes não valida esse par, ele aceita calado, e só o cruzamento acusa.

## Quando parar

**Identificada a causa, a triagem acabou.** Causa identificada é aquela que explica
o sintoma inteiro e que você consegue apontar num campo concreto — não uma hipótese
plausível.

Sinais de que já passou da hora de parar:

- você está listando o que *poderia* ser, em vez de mostrar o que *é*;
- está investigando um segundo achado que não explica o sintoma relatado;
- está começando a redigir a correção como se fosse aplicá-la.

O último merece atenção. Chamado com causa clara e correção de uma linha é
exatamente onde a mão escorrega. Descreva a correção; não a execute.

**Ruído é esperado.** Nem todo achado é a causa. Um pod com 1 reinício por não ter
resolvido o DNS do banco na primeira subida se recupera sozinho e não tem relação
com um Service sem endpoint. Antes de perseguir um achado, pergunte: *isto explica
o sintoma que a pessoa relatou?* Se não explica, mencione de passagem e siga.

## O relatório

Entregue nesta forma. Ela é curta de propósito: quem lê está no meio de um plantão.

```
## Chamado: <namespace>/<objeto> — "<sintoma declarado>"

**Causa:** <uma frase, apontando o campo concreto que a evidencia>

**Evidência:**
<o trecho de saída que fecha o diagnóstico, cru, sem parafrasear>

**Como cheguei:**
<as fontes consultadas na ordem, e o que cada uma descartou>

**O que está saudável ao lado:**
<o que foi verificado e não é o problema — evita a próxima pessoa repetir>

**Correção sugerida (não aplicada):**
<o que precisa mudar, e onde>
```

A seção "o que está saudável ao lado" parece supérflua e não é: sem ela, a próxima
pessoa a olhar o chamado refaz a mesma eliminação.

## Armadilhas de leitura

Três erros de interpretação custam mais tempo que qualquer comando faltante. Estão
detalhados em `references/leitura-da-api.md` — leia esse arquivo quando a saída da
API não bater com o que você espera:

- **Ausência de campo não é campo vazio.** `subsets` some inteiro quando não há
  endereço; `readyReplicas` some quando nenhuma réplica está pronta.
- **Log só existe se o processo escreveu antes de morrer.** Container morto pelo
  cgroup não escreve nada — começar por log ali não retorna nada e induz a conclusão
  errada.
- **Evento é resumo com prazo de validade.** Ele expira e é agregado por contagem;
  ausência de evento não é ausência de problema.

Para as assinaturas já catalogadas — que sintoma corresponde a que causa, e qual
campo fecha o diagnóstico — consulte `references/assinaturas.md`.

## Por que esta skill não traz script

Todo script que consultasse o cluster precisaria de credencial própria e rodaria
fora do servidor MCP — ou seja, fora da garantia de somente-leitura que o servidor
oferece por não expor ferramenta de escrita. A garantia deixaria de ser estrutural e
viraria promessa de quem escreveu o script.

O que esta skill empacota é método, e método não precisa de credencial.
