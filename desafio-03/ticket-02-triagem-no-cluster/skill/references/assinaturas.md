# Assinaturas — sintoma, evidência e causa

Catálogo do que já foi visto no parque. Consulte quando quiser confirmar uma
assinatura ou quando o sintoma não se encaixar de imediato em nenhuma camada.

Cada entrada tem a mesma forma: **como aparece**, **o campo que fecha o
diagnóstico**, e **o que costuma ser a causa**. A ordem é a frequência com que
elas aparecem, não a gravidade.

## Índice

- A. Container que reinicia
- B. Container que nunca roda
- C. Rollout que não avança
- D. Tudo saudável e ninguém acessa
- E. Pod que não é agendado

---

## A. Container que reinicia

**Como aparece:** `restartCount > 0`, fase `Running`, prontidão `false`,
eventos `BackOff` com contagem crescente.

**O campo que fecha:** `lastState.terminated.reason` e `exitCode`.

| `reason` / `exitCode` | Causa provável | Confirmação |
|---|---|---|
| `OOMKilled` / 137 | limite de memória abaixo do consumo real | compare com `resources.limits.memory` |
| `Error` / 1 | exceção na aplicação | log da instância anterior |
| `Completed` / 0 | processo termina achando que acabou | comando da imagem |

**Caso de referência — nyx-prod.** Dois pods, três reinícios cada em 62 segundos,
`exitCode: 137` e `reason: OOMKilled` tanto em `state` quanto em `lastState`. O
Deployment declarava `limits.memory: 24Mi` para uma aplicação Node com Express,
que não sustenta o runtime nesse teto. Origem: um corte de custo aplicado ao
namespace inteiro sem olhar consumo real.

Aqui o log é inútil por construção: o processo é morto pelo cgroup e não escreve
nada. Quem começa por log não encontra e conclui errado.

**Ruído frequente:** um único reinício, logo após a criação do pod, em que a
aplicação não resolveu o DNS do banco antes de ele ficar pronto. O DNS de um
Service só publica endereço de pod pronto; a aplicação tenta, falha e sai, e o
backoff seguinte funciona. Isso não é a causa de nada — é o custo de a aplicação
não repetir a tentativa na subida.

## B. Container que nunca roda

**Como aparece:** `restartCount == 0`, pod não pronto, `state.waiting` preenchido.
Não existe `lastState`.

**O campo que fecha:** `state.waiting.reason` e, principalmente,
`state.waiting.message`, que traz o erro cru do runtime.

| `reason` | Causa provável |
|---|---|
| `ErrImagePull` / `ImagePullBackOff` | tag inexistente, registry inacessível, credencial ausente |
| `CreateContainerConfigError` | ConfigMap ou Secret referenciado que não existe |
| `CreateContainerError` | comando ou ponto de montagem inválido |

**Caso de referência — orion-stg.** Três pods em `ErrImagePull`, zero reinícios, e
a mensagem crua encerrando o assunto:

```
failed to resolve reference "docker.io/fabricioveronez/fake-shop:v1.14.2":
docker.io/fabricioveronez/fake-shop:v1.14.2: not found
```

A tag anunciada no release não existe no registry. O ReplicaSet novo foi criado e
nunca produziu um pod — por isso "o pod nunca trocou": os antigos seguem servindo
enquanto o rollout não avança.

Quando a mensagem indicar tag inexistente, vale conferir quais tags o repositório
de fato publica antes de concluir. A diferença entre "a tag não existe" e "não
consigo autenticar no registry" muda quem resolve o chamado.

## C. Rollout que não avança

**Como aparece:** o Deployment tem réplicas desejadas, `readyReplicas` **ausente**
ou menor que o desejado, e `Available=False` com `MinimumReplicasUnavailable`.

**O campo que fecha:** `status.conditions` do Deployment, cruzado com o `state` dos
pods do ReplicaSet novo.

`Progressing=True` com `ReplicaSetUpdated` diz que o rollout começou; combinado com
`Available=False`, diz que ele começou e não terminou. A causa está nos pods novos,
sempre — o rollout é sintoma, não causa. Desça para a assinatura A ou B.

## D. Tudo saudável e ninguém acessa

**Como aparece:** pods `Running` e prontos, Deployment com as réplicas desejadas
disponíveis, **nenhum evento `Warning`**, e mesmo assim quem chama de fora recebe
503 ou timeout.

**O campo que fecha:** o objeto `Endpoints` do Service **sem a chave `subsets`**,
ou o `EndpointSlice` com `endpoints: null`.

**A causa é sempre um par que não casa.** Compare, nesta ordem:

1. `spec.selector` do Service × `metadata.labels` dos pods do namespace
2. `spec.ports[].targetPort` do Service × `containerPort` do container
3. o namespace do Service × o namespace dos pods

**Caso de referência — nyx-stg.** Duas réplicas prontas, deployment completo,
nenhum evento. O Service selecionava `app: nyx-api` e os pods carregavam
`app: nyxapi`. Um hífen. O Service foi criado sem uma linha de reclamação e nasceu
sem destino.

Esta é a assinatura que prova por que aprofundar numa fonte só não resolve:
nenhuma das quatro camadas anteriores menciona o problema, porque do ponto de vista
delas não há problema nenhum.

**Atenção ao caso vizinho:** se `subsets` **existe** e traz `notReadyAddresses`, o
seletor casou e os pods é que não estão prontos. Isso é assinatura A ou B
disfarçada de problema de rede — não perca tempo comparando rótulos.

## E. Pod que não é agendado

**Como aparece:** fase `Pending`, sem `nodeName`, evento `FailedScheduling`.

**O campo que fecha:** a mensagem do evento `FailedScheduling`, que enumera por que
cada nó foi recusado.

Causas usuais: `requests` maiores que a capacidade livre, `nodeSelector` ou
afinidade sem nó correspondente, taint sem toleration, ou PVC que não vincula.
Todas se confirmam cruzando a especificação do pod com os rótulos, taints e
capacidade dos nós.
