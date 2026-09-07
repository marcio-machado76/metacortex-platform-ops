# Comportamento — dashboard do cluster

O que a ferramenta faz, campo a campo, antes de existir código. As decisões que
sustentam este documento estão em `00-brainstorm.md`; a justificativa estendida de
cada uma vai para `02-decisoes-tecnicas.md`.

Toda forma de dado citada aqui foi medida contra o `kind-metacortex-lab`
(servidor v1.31.0) e tem comando que a reproduz, registrado em `evidencias/`.

## Escopo

Encurtar os primeiros dez minutos de um chamado: mostrar numa tela o retrato de um
namespace que hoje se monta com seis a dez `kubectl`. **Não substitui o terminal.**

**Dentro:** namespaces do cluster; pods com estado, reinícios e motivo em falha;
Deployments e StatefulSets com prontos sobre desejados; Services e se têm endereço;
eventos recentes do namespace selecionado; filtro por namespace e busca por nome.

**Fora, e declarado:** observar mudanças por watch, multicluster, logs, `describe`,
visualização de YAML, nós, métricas, DaemonSet, Job e CronJob.

O StatefulSet entra porque o enunciado diz "no mínimo" ao listar o conteúdo da
tela — o acréscimo é autorizado pelo texto, não pela conveniência. DaemonSet fica
fora: no parque de laboratório só existem os do `kube-system`.

## Interface

Aplicação de terminal, um único comando, sem argumento obrigatório:

```
painel-cluster
```

Ela lê o contexto **corrente** do kubeconfig no momento em que sobe, e só ele. Não
há seletor de cluster, não há troca de destino sem sair. Quem quiser outro cluster
troca o contexto por fora.

O contexto e o endereço do servidor ficam visíveis no topo da tela, permanentemente.
Uma ferramenta que lê o contexto corrente sem dizer qual é permite que alguém tire
conclusão sobre produção olhando homologação.

| Tecla | Efeito |
|---|---|
| `Tab` | alterna o foco entre a lista de namespaces e o painel de objetos |
| `↑` `↓` | move a seleção no painel focado |
| `/` | busca por nome; filtra por substring dentro do namespace selecionado |
| `Esc` | limpa a busca |
| `r` | atualiza agora, sem esperar o intervalo |
| `q` | sai |

A busca por nome é substring simples, sem expressão regular, e casa contra o nome
do objeto. Um cluster do parque tem centenas de objetos, e rolar a lista não é
funcionalidade.

## O que a tela mostra

### Namespaces

Lista de `metadata.name`, ordenada alfabeticamente, com o namespace selecionado em
destaque. É a única leitura de escopo de cluster; todo o resto é do namespace
selecionado.

### Pods

| Coluna | Origem | Regra |
|---|---|---|
| nome | `metadata.name` | |
| estado | ver abaixo | nunca é só `status.phase` |
| prontos | contagem de `status.containerStatuses[].ready` sobre o total | `2/2`, `0/1` |
| reinícios | soma de `restartCount` | |
| motivo | `state.waiting.reason` e `lastState.terminated.reason` | ver abaixo |
| idade | `metadata.creationTimestamp` | |

**O estado não é a fase.** Três correções que a fase sozinha não dá:

1. **`Terminating` não é fase.** Um pod em remoção continua com
   `status.phase: Running` e se distingue por ter `metadata.deletionTimestamp`.
   Foi observado durante o rollout do `orion-web`: dois pods `Terminating` e dois
   `Running`, todos com a mesma fase.
2. **`CrashLoopBackOff` não é fase.** Vive em
   `containerStatuses[].state.waiting.reason`, com a fase ainda em `Running`.
3. **Pronto não é fase.** O `orion-web` ficou `Running` com `restartCount: 0` e
   `0/1` pronto por cinco minutos, sem um único evento de falha.

**O motivo tem duas metades, e a útil é a segunda.** Medido no `nyx-prod`:

```
state    : waiting.reason  = CrashLoopBackOff
lastState: terminated.reason = OOMKilled, exitCode 137
```

`state` diz o quê — está reiniciando; `lastState` diz o porquê — foi morto por
memória. A tela mostra os dois, nessa ordem, porque quem tria já sabe que está
reiniciando.

### Deployments e StatefulSets

Os dois aparecem no mesmo painel, com a mesma coluna de prontos sobre desejados —
e **não compartilham vocabulário de status**. Medido:

| | Deployment | StatefulSet |
|---|---|---|
| `spec.replicas` | presente | presente |
| `status.readyReplicas` | presente quando > 0 | presente quando > 0 |
| `status.conditions` | `Available`, `Progressing` | **chave ausente** |
| exclusivos | — | `currentReplicas`, `currentRevision`, `updateRevision` |

Consequência para a tela: **a coluna de prontos sobre desejados é a única fonte
comum aos dois.** A condição `Available` só é lida para Deployment, e quando
existe. Um StatefulSet nunca exibe coluna de condição, e isso é ausência de dado,
não estado ruim.

`status.readyReplicas` some quando nenhuma réplica está pronta — foi medido no
`orion-web` do `orion-stg`, cujo status traz `['conditions', 'observedGeneration',
'replicas', 'unavailableReplicas', 'updatedReplicas']` e nada mais. A tela mostra
`0/3`, e mostra porque normaliza a ausência, não porque testa a chave.

### Services e endereços

| Coluna | Origem |
|---|---|
| nome, tipo, portas | `Service.spec` |
| endereços | `EndpointSlice`, agregados pelo rótulo `kubernetes.io/service-name` |

O `EndpointSlice` carrega `conditions.ready` por endereço, então a tela distingue
três estados que o objeto `Endpoints` embaralharia:

| Exibido | Condição |
|---|---|
| `3 prontos` | há endereços, todos com `ready: true` |
| `2 de 3 prontos` | há endereços, nem todos prontos |
| **`sem endereço`** | não há endereço nenhum |

Um Service sem endereço é sempre destacado, mesmo com todos os pods do namespace
saudáveis: é o defeito mais silencioso do parque, e o Chamado 3 do Ticket 02
existe para provar isso.

**A ausência tem três formas, e nenhuma delas se testa por presença de chave.**
Medido no mesmo Service sem endereço:

```
Endpoints/nyx-api     : chave 'subsets'   AUSENTE
EndpointSlice do mesmo: chave 'endpoints' PRESENTE, valor null
```

A normalização é `obj.get(campo) or []`, aplicada **no ponto em que o campo é lido
pela camada de interpretação** — não na camada que fala com a API, que entrega a
resposta como ela veio. Nenhum ponto do código pergunta se a chave existe para
decidir estado.
<!-- Corrigido durante a implementação. A redação anterior dizia "na fronteira de
     leitura", o que colidia com a decisão D-A do design: a camada que fala com a
     API não interpreta nada. "Fronteira de leitura" queria dizer o primeiro ponto
     que lê o campo, e foi lido como o módulo de rede. -->

### Eventos

Do namespace selecionado, pela API `core/v1`.

| Coluna | Origem |
|---|---|
| tipo | `type` — `Normal` ou `Warning` |
| motivo | `reason` |
| objeto | `involvedObject.kind` e `.name` |
| repetições | `count` |
| quando | `lastTimestamp` |
| mensagem | `message` |

Ordenados por `lastTimestamp` decrescente, porque **a API não devolve ordenado**.
Eventos de tipo `Warning` são destacados.

"Recente" é definido como janela deslizante de **1 hora** sobre `lastTimestamp`.

O número não é arbitrário: o apiserver descarta eventos mais velhos que o seu
`--event-ttl`, e neste cluster a flag **não é declarada**, o que faz valer o
default de 1 hora do `kube-apiserver`. A janela da tela coincide de propósito com
o que o cluster guarda — esticá-la não traria evento nenhum a mais.

```bash
kubectl get pod kube-apiserver-metacortex-lab-control-plane -n kube-system \
  -o jsonpath='{.spec.containers[0].command}' | tr ' ' '\n' | grep event-ttl
# (vazio: flag nao declarada)
```

Num cluster com `--event-ttl` maior, a janela da tela passa a ser um recorte do que
o cluster tem. Nos dois casos a tela **não afirma** que aquilo é tudo o que
aconteceu.

Quando `lastTimestamp` vier ausente ou nulo, a tela usa `eventTime`. Medido no
`nyx-dev`: os eventos de `core/v1` chegam com `firstTimestamp` preenchido e
`eventTime: null` — mais uma vez a mesma ausência, num terceiro campo.

## O envelope por tipo de recurso

Cada tipo é lido de forma independente e devolve um envelope com **um** destes
quatro estados. A tela desenha os quatro; nenhum deles é exceção que sobe.

| Estado | Quando | O que a tela mostra |
|---|---|---|
| `ok` | leitura bem-sucedida, com itens | os itens |
| `vazio` | leitura bem-sucedida, sem itens | "nenhum objeto neste namespace" |
| `negado` | `ForbiddenException` (403) | "sem permissão para ler <tipo>" no lugar daquele painel, com os outros intactos |
| `indisponível` | falha de transporte | "cluster não respondeu" naquele painel |

A separação por tipo é o que atende ao ambiente hostil que o enunciado chama de
mais interessante. Está medido: com o contexto `platform-ro-sem-events`, no mesmo
cliente e na mesma sessão, `events` devolveu 403 e `pods` devolveu três itens.

## O que a tela afirma, e o que ela não afirma

**Ela relata o vocabulário da API.** `Running`, `CrashLoopBackOff`, `OOMKilled`,
`0/3`, `sem endereço`. Não existe coluna "saudável", "OK" nem semáforo de saúde.

O motivo está medido: o `orion-web` do `orion-stg` **não tem probe nenhuma**, e o
`Ready` dele significa apenas "o processo subiu". Uma coluna de saúde mentiria com
autoridade.

**Ela mostra a ausência de probe.** Coluna própria, por container, lida de
`spec.containers[].readinessProbe`. É fato da API, não juízo, e vem de graça no
Pod que a tela já lista.

| Exibido | Significado |
|---|---|
| `readiness: —` | sem `readinessProbe`; o `Ready` deste container vale "o processo subiu" |
| `readiness: ✓` | há probe; o `Ready` reflete o que a probe checa |

Num pod com mais de um container, a coluna mostra a contagem — `readiness: 1/2` —
porque o `Ready` do pod é o E lógico dos containers, e a ausência de probe não é.

**Ela ordena por anormalidade, e mostra o critério.** Ordenar é opinar sobre onde
olhar primeiro, não sobre saúde. Os critérios, todos dados da API, aparecem numa
coluna "por quê":

| Peso | Critério |
|---|---|
| 1 | prontos menores que desejados |
| 2 | `reason` de falha em `state.waiting` |
| 3 | reinícios maiores que zero |
| 4 | Service sem endereço |
| 5 | eventos `Warning` na janela |

Objetos sem nenhum critério aparecem depois, na ordem alfabética. Quem discordar da
ordem vê o motivo dela na própria linha.

## Atualização

Consulta em **intervalo fixo**, escopada ao namespace selecionado. `r` força uma
consulta imediata.

| O que | Intervalo |
|---|---|
| objetos do namespace selecionado | 10s |
| lista de namespaces | 60s |

O escopo por namespace é o que torna o intervalo barato: um `LIST` por tipo sobre
um namespace, e não sobre o cluster. A lista de namespaces é a única leitura
cluster-wide, e quase não muda.

A tela mostra **a idade do dado** — "atualizado há 4s" — porque um painel que se
atualiza sozinho sem dizer quando induz a confiar em número velho.

Watch está fora da primeira fatia. O contexto `platform-ro` não concede o verbo
`watch`, então a decisão é aplicada pelo cluster e não só pelo documento.

## Ambientes hostis

Os três se separam por **tipo de exceção**, sem ler mensagem. Medido:

| Ambiente | Como chega | O que a tela faz |
|---|---|---|
| Permissão negada num tipo | `ForbiddenException`, 403 | envelope `negado` só naquele painel |
| Credencial recusada | `UnauthorizedException`, 401 | tela inteira em estado de credencial, com o contexto e o servidor visíveis |
| Cluster não responde | `urllib3.exceptions.MaxRetryError` | tela inteira em estado de indisponível, com o endereço tentado |

**A tela não afirma "credencial expirada".** Foi medido que certificado de cliente
vencido e token inválido produzem o mesmo 401, com o mesmo corpo. As duas pedem a
mesma ação de quem opera, e a tela diz o que sabe: a credencial foi recusada.

Em nenhum dos três casos a tela fica em branco, e em nenhum deles um traceback
chega ao terminal.

## Códigos de saída

| Código | Quando |
|---|---|
| 0 | saída normal, pelo `q` |
| 1 | erro de uso — argumento inválido |
| 2 | não há kubeconfig legível, ou o contexto corrente não existe |

**Cluster inalcançável não é código de saída diferente de zero.** A aplicação
sobe, mostra o estado de indisponível e continua tentando; sair com erro seria
exatamente a tela em branco que o enunciado recusa. O código 2 cobre só o caso em
que não há sequer o que tentar.

## Invariantes

1. **Só lê.** Nenhuma operação de escrita, em nenhum caminho de código. Um único
   módulo fala com a API; nenhum outro importa `kubernetes` nem `urllib3`. O
   contexto recomendado de execução não concede verbo de escrita, e nega `secrets`.
2. **Contexto corrente e só ele.** A aplicação nunca troca de contexto, nem lê
   outro que não o corrente no momento em que subiu.
3. **Nenhuma afirmação que a API não sustente.** A tela não deriva saúde. Ordena,
   destaca e mostra o critério.
4. **Ausência nunca vira erro nem afirmação falsa.** Campo ausente, nulo e vazio
   são normalizados na fronteira de leitura; "o control plane ainda não falou" é
   estado derivado da comparação entre `status.observedGeneration` e
   `metadata.generation` — nunca da forma do JSON.
   <!-- Corrigido durante a implementação. A primeira versão nomeava três sinais:
        observedGeneration, condições e idade. Dois deles não servem: condições não
        existem em StatefulSet, e nenhum documento fixou limiar de idade. Nomear
        três quando só um é utilizável era sobre-especificação. -->
5. **Nenhuma falha esvazia a tela.** Falha de um tipo de recurso afeta o painel
   daquele tipo e mais nada.

## Critérios de aceite

1. **Retrato do namespace saudável.** Com `nyx-dev` selecionado, a tela mostra o
   Deployment `nyx-api` em `1/1`, o StatefulSet `nyx-postgres` em `1/1`, os dois
   Services com endereço pronto, e a única marca de anormalidade é o
   `reinícios: 2` do pod `nyx-api`.
   <!-- Corrigido depois da validação. A redação original exigia "nenhum objeto
        marcado como anormal", e isso já era falso quando foi escrita: o
        restartCount: 2 daquele pod está registrado em
        evidencias/preparacao-do-cluster.md desde o commit 56008ac, e este
        documento só passou a existir no commit seguinte. A tela faz o que a spec
        manda; o critério é que contradizia um fato do próprio repositório. A
        limitação de desenho que isso expõe está em 03-divergencias, item 27. -->
2. **Retrato dos três chamados.** `nyx-prod` mostra `0/2` com `CrashLoopBackOff` e
   `OOMKilled`; `orion-stg` mostra `0/3` sem `readyReplicas`; `nyx-stg` mostra
   pods `2/2` e o Service `nyx-api` **sem endereço**.
3. **Réplica única ao lado de duas.** `nyx-dev` em `1/1` e `orion-prod` em `2/2`
   aparecem com o mesmo formato de coluna, sem que o denominador diferente mude a
   leitura.
4. **StatefulSet sem condição.** O `nyx-postgres` aparece com prontos sobre
   desejados e sem coluna de condição, e isso não é exibido como problema.
5. **Ausência de probe.** O `orion-web` do `orion-stg` aparece com
   `readiness: —`; o `nyx-api` do `nyx-dev` aparece com `readiness: ✓`.
6. **Permissão parcial.** Com o contexto `platform-ro-sem-events`, o painel de
   eventos diz "sem permissão" e os painéis de pods, controladores e services
   continuam preenchidos.
7. **Credencial recusada.** Com certificado vencido, a tela mostra o estado de
   credencial, o contexto e o servidor, sem traceback.
8. **Cluster inalcançável.** Com o apiserver inacessível, a tela mostra o estado de
   indisponível e o endereço tentado, e não sai com código diferente de zero.
9. **Busca e filtro.** Com `nyx-prod` selecionado e `postgres` digitado na busca, a
   tela mostra só os objetos cujo nome contém `postgres`.
10. **Só leitura, provada por fora.** Rodando sob `platform-ro`, a sessão inteira
    de uso não produz nenhuma negativa de RBAC — porque a aplicação nunca tenta
    escrever.

## Pontos que este documento fecha

O `00-brainstorm.md` deixou sete pontos em aberto. Este documento resolve quatro:

| Ponto | Resolução |
|---|---|
| Definição de "eventos recentes" | janela de 1h sobre `lastTimestamp`, ordenação client-side, TTL do apiserver medido |
| Intervalo concreto de atualização | 10s no namespace selecionado, 60s na lista de namespaces |
| Ausência de probe em pod multi-container | contagem por container — `readiness: 1/2` |
| Nome do comando empacotado | `painel-cluster` |

Os outros três continuam abertos por motivo próprio: o layout da tela é detalhe de
implementação e será resolvido no código; a hipótese da D2 já foi medida e fechada
em `evidencias/hipotese-d2-excecoes.md`; e a fabricação da credencial vencida
também, no cenário 6 do mesmo script.

Um ponto novo, que só apareceu ao escrever esta spec e vale registrar antes da
implementação: **Deployment e StatefulSet não compartilham vocabulário de status.**
O StatefulSet não traz a chave `conditions`, então a coluna de condição existe para
um e não para o outro. A D4 incluiu StatefulSet na primeira fatia sabendo do custo
de "mais um tipo no mesmo envelope"; o custo real é um pouco maior — é mais um
tipo **com forma de status própria**. Não muda a decisão: a coluna de prontos sobre
desejados, que é a que o enunciado exige, é comum aos dois.
