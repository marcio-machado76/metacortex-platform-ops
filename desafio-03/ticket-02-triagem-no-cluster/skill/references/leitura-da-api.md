# Leitura da API — onde a saída engana

Consulte quando a resposta da API não bater com o que você espera, ou antes de
concluir que "não tem nada ali".

## Índice

1. Ausência de campo não é campo vazio
2. A fase do pod não é o estado do container
3. `state` × `lastState`
4. Códigos de saída que aparecem no parque
5. Eventos: o que eles são e o que não são
6. Quando o log não existe
7. `Endpoints` e `EndpointSlice`

---

## 1. Ausência de campo não é campo vazio

A API do Kubernetes **omite** campo sem valor em vez de devolvê-lo vazio. Quem
espera lista vazia lê ausência como erro de consulta, e quem trata ausência como
zero relata número errado.

Um Service sem nenhum pod casando com o seletor:

```yaml
apiVersion: v1
kind: Endpoints
metadata:
  name: nyx-api
  namespace: nyx-stg
# nao existe a chave subsets
```

Não é `subsets: []`. A chave some.

Um Deployment sem nenhuma réplica pronta:

```json
{"spec": {"replicas": 3},
 "status": {"replicas": 3, "unavailableReplicas": 3,
            "conditions": [{"type": "Available", "status": "False",
                            "reason": "MinimumReplicasUnavailable"}]}}
```

Não há `readyReplicas: 0` — não há `readyReplicas`. Ao relatar, diga "nenhuma
réplica pronta", não "0 prontas de 3", porque a segunda forma sugere um campo que
você leu e não leu.

**Distinção que importa na triagem:** um Service *pode* ter `subsets` presente e
mesmo assim não entregar tráfego, quando os endereços estão em
`notReadyAddresses` — pods casaram com o seletor mas nenhum está pronto. Isso é
problema de container, não de seletor. Campo ausente aponta para metadado; campo
presente com endereços não prontos aponta para as camadas de baixo.

## 2. A fase do pod não é o estado do container

Um pod cujo container está em `CrashLoopBackOff` continua com `status.phase:
Running`. A fase descreve o pod; a falha vive em `status.containerStatuses[]`.

Confiar na fase produz o relatório mais enganoso possível: "o pod está Running"
enquanto ele reinicia a cada trinta segundos.

## 3. `state` × `lastState`

- `state` — o que o container está fazendo **agora**: `running`, `waiting` ou
  `terminated`.
- `lastState` — como a encarnação **anterior** terminou.

Num container que reinicia, o motivo costuma estar em `lastState.terminated`,
porque no instante da consulta ele já voltou a rodar. Ler só `state` num pod que
acabou de reiniciar mostra `running` e esconde a causa.

```json
"state":     {"running": {"startedAt": "..."}},
"lastState": {"terminated": {"reason": "OOMKilled", "exitCode": 137}}
```

Container que **nunca** rodou não tem `lastState`. A informação está em
`state.waiting.reason` e, mais útil, em `state.waiting.message`, que costuma
trazer o erro cru do runtime.

## 4. Códigos de saída que aparecem no parque

| `exitCode` | O que significa | Onde procurar a seguir |
|---|---|---|
| 137 | SIGKILL — quase sempre o cgroup matando por memória | `reason: OOMKilled` e `resources.limits.memory` |
| 143 | SIGTERM — encerramento pedido; normal em rollout | nada, se acompanha rollout |
| 1 | erro genérico da aplicação | log do container |
| 0 com reinício | processo terminou achando que acabou | comando da imagem, `restartPolicy` |

## 5. Eventos: o que eles são e o que não são

Eventos **confirmam ciclo**: dizem que algo se repete e há quanto tempo. Eles
raramente dizem por quê. `BackOff` informa que o kubelet está desistindo de
reiniciar, não o motivo da morte.

Duas propriedades que mudam a leitura:

- **Expiram.** O padrão do cluster é uma hora. Um problema de ontem não tem
  evento hoje — ausência de evento não é ausência de problema.
- **São agregados por contagem.** Um evento com `count: 21` é uma linha, não 21.
  O `count` alto é o dado mais útil: ele mede insistência.

E eventos não vivem dentro do objeto a que se referem: são objetos próprios, que
apontam para o alvo por `involvedObject`. Para achá-los, filtre pelo nome do
objeto, não espere encontrá-los no `describe` de outro.

## 6. Quando o log não existe

O log só tem conteúdo se o processo escreveu antes de morrer. Ele **não** ajuda
quando:

- o container foi morto pelo cgroup (`OOMKilled`) — o processo não é avisado;
- o container nunca rodou (`ErrImagePull`, `CreateContainerConfigError`) — não há
  processo;
- o container já reiniciou — aí o log é da instância nova. Para ver a que morreu,
  peça o log da instância anterior (`--previous`).

Começar a triagem pelo log é hábito comum e custa caro justamente nos casos em
que ele está vazio por construção.

## 7. `Endpoints` e `EndpointSlice`

Os dois carregam a mesma informação: quais endereços um Service alcança.
`Endpoints` é o objeto antigo e está a caminho da aposentadoria; `EndpointSlice` é
o sucessor e é o que as ferramentas novas leem.

Para triagem manual, `Endpoints` é o caminho mais curto. Para qualquer coisa que
vá durar, prefira `EndpointSlice`, filtrando pelo rótulo
`kubernetes.io/service-name=<nome-do-service>`.

As duas formas de "sem endereço" também diferem: em `Endpoints` a chave `subsets`
some; em `EndpointSlice` o campo `endpoints` vem `null`.
