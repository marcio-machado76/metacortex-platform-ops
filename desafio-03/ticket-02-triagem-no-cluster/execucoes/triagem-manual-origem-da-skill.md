# Triagem manual dos três chamados — o fluxo do qual a skill nasceu

Executado em 2026-09-06 contra o cluster `kind-metacortex-lab`, com os três
ambientes do enunciado aplicados e assentados. Ferramenta: `kubectl` direto,
sem skill e sem método escrito — é a triagem "por onde der" que a Trinity quer
padronizar. A saída bruta de cada um está em `chamado-N-triagem-manual.txt`.

O objetivo aqui não era achar a causa depressa. Era **registrar em que ordem eu
olhei**, o que cada passo descartou e qual passo revelou a causa — porque é isso
que vira método, e não o resultado.

---

## Chamado 1 — nyx-prod, "a API reinicia sozinha"

| Passo | O que mostrou | O que isso descartou |
|---|---|---|
| 1. `get pods` | `OOMKilled` e `Running`, 3 reinícios cada, 62s de vida | não é agendamento, não é imagem |
| 2. estado do container | `exitCode: 137`, `reason: OOMKilled` em `state` **e** em `lastState` | não é falha da aplicação: é o kernel matando |
| 3. limites declarados | `limits.memory: 24Mi` | — |
| 4. eventos | `BackOff` repetido; nenhum evento diz "OOM" | os eventos confirmam o ciclo, não a causa |
| 5. o banco ao lado | `nyx-postgres` pronto, 0 reinícios | a dependência não é o problema |

**Causa: limite de memória incompatível com o consumo real da aplicação.** O
kube-news é Node com Express; `24Mi` não sustenta o runtime. O corte de custo
apertou o namespace inteiro sem olhar consumo, e este workload não cabe.

**Onde a causa apareceu:** no passo 2, no campo `lastState.terminated.reason`.
Não nos eventos, e não nos logs — o processo é morto pelo cgroup, então ele não
escreve nada antes de morrer. Quem começa por `logs` neste chamado não encontra
nada e conclui errado.

Detalhe que a triagem precisa saber ler: o objeto `Endpoints` deste Service
**tem** o campo, com os endereços em `notReadyAddresses`. Serviço sem tráfego
com o campo presente é um problema diferente de serviço sem tráfego com o campo
ausente — compare com o Chamado 3.

---

## Chamado 2 — orion-stg, "a loja parou depois de uma publicação"

| Passo | O que mostrou | O que isso descartou |
|---|---|---|
| 1. `get pods` | 3 pods em `ErrImagePull`, **0 reinícios** | não é crash: o container nunca chegou a rodar |
| 2. estado do container | `docker.io/fabricioveronez/fake-shop:v1.14.2: not found` | — |
| 3. `get deploy` | `readyReplicas` **ausente**, `unavailableReplicas: 3`, `Available=False (MinimumReplicasUnavailable)` | — |
| 4. eventos | `ImagePullBackOff`, `Back-off pulling image` | confirma o ciclo |
| 5. o banco ao lado | `orion-postgres` pronto | a dependência não é o problema |

**Causa: a tag anunciada no release não existe no registry.** Consultando as 18
tags publicadas de `fabricioveronez/fake-shop`, existem `v1`, `v14`, `v26` — e
nenhuma `v1.14.2`. O deploy foi aplicado, o ReplicaSet novo foi criado, e ele
nunca conseguiu produzir um pod. Por isso "o pod nunca trocou": os antigos
seguem servindo enquanto o rollout não avança.

**Onde a causa apareceu:** no passo 2, na mensagem do `state.waiting`. Zero
reinícios é o sinal que separa este chamado do Chamado 1 — mesmo sintoma
declarado, camada completamente diferente.

---

## Chamado 3 — nyx-stg, "503 para quem chama de fora"

| Passo | O que mostrou | O que isso descartou |
|---|---|---|
| 1. `get pods` | 2/2 `Running`, ambos `ready=true` | não é o container |
| 2. `get deploy` | 2 desejadas, 2 prontas, 2 disponíveis | não é o rollout |
| 3. eventos | nenhum `Warning` | não há nada errado a reportar |
| 4. `get endpoints` | o objeto existe e **não traz a chave `subsets`** | — |
| 5. cruzamento | seletor `app: nyx-api` × rótulo do pod `app: nyxapi` | — |

**Causa: o seletor do Service não casa com os rótulos do pod.** Um hífen. O
Service foi criado sem uma linha de reclamação, nenhum pod casa com ele, e a
lista de endereços fica vazia — quem chama de fora recebe 503 porque não há para
onde encaminhar.

**Onde a causa apareceu:** só no passo 5, cruzando dois objetos. Nenhuma das
quatro fontes anteriores — pods, deployment, eventos, logs — menciona o problema,
porque do ponto de vista delas não há problema nenhum. É o chamado que prova que
aprofundar numa fonte só não resolve: tem que cruzar.

Dois detalhes de leitura da API:

- O `Endpoints` **não vem com `subsets: []`**. A chave simplesmente não aparece.
  Código que espera lista vazia quebra aqui.
- O `EndpointSlice` equivalente traz `endpoints: null`. Mesma informação, forma
  diferente — e é ele que sobrevive à aposentadoria do `Endpoints`.

**Ruído que a triagem tem que ignorar:** um dos dois pods tem 1 reinício. Ele
subiu antes do `nyx-postgres` ficar pronto, não resolveu o DNS e saiu; o backoff
seguinte funcionou. É reinício legítimo e não tem relação com o 503. Perseguir
esse reinício é o caminho errado mais convidativo deste chamado.

---

## O que este fluxo ensinou, e que vira método

1. **O sintoma declarado não diz a camada.** Os três chegam como "o cliente diz
   que está fora do ar" e vêm de container, registry e metadado.
2. **Contagem de reinícios é o primeiro divisor.** Reinício > 0 aponta para o
   container; reinício = 0 com pod não pronto aponta para antes do container —
   imagem, agendamento, volume.
3. **Tudo saudável e mesmo assim inacessível é a assinatura do Chamado 3.** Se
   pods, deployment e eventos estão limpos, a causa está em metadado, e o único
   jeito de vê-la é cruzar Service × rótulos de pod.
4. **Evento confirma ciclo, raramente revela causa.** Nos três, o evento disse
   "isto está se repetindo" e nunca "por causa disto".
5. **Log só serve quando o processo escreveu antes de morrer.** No Chamado 1 ele
   é inútil por construção — quem começa por log perde tempo.
6. **Sempre existe coisa funcionando ao lado.** Nos três, o Postgres do cliente
   estava de pé. Verificar a dependência cedo descarta uma hipótese inteira por
   um comando.
7. **Ausência de campo ≠ campo vazio.** `readyReplicas` ausente no Chamado 2 e
   `subsets` ausente no Chamado 3 são dados, não erros de leitura.
8. **Onde parar.** Nos três, identificada a causa, a triagem acabou. Nenhuma
   correção foi aplicada — e o Chamado 1 é tentador, porque a correção é uma
   linha.
