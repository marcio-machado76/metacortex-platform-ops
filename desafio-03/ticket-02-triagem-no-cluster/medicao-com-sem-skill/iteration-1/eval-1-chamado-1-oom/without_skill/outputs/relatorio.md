# Relatório de Triagem — Incidente Nyx API (nyx-prod)

## Resumo executivo

A API de produção do cliente **nyx** está em **CrashLoopBackOff** contínuo porque o
container está sendo **OOMKilled (Exit Code 137)** repetidamente. A causa raiz é um
**limite de memória (`memory: 24Mi`) configurado no Deployment `nyx-api` muito abaixo
do necessário** para a aplicação rodar — o container é morto pelo kernel assim que
ultrapassa esse teto, o kubelet reinicia, e o ciclo se repete infinitamente. Não há
falta de recursos no nó nem problema no banco de dados; o problema está isolado na
especificação de recursos do próprio Deployment.

## Evidências coletadas (comandos somente leitura)

### 1. Estado dos pods
```
NAME                            READY   STATUS             RESTARTS      AGE
nyx-api-79c5f4d8d7-2w5kd        0/1     CrashLoopBackOff   9 (87s ago)   23m
nyx-api-79c5f4d8d7-hkw2t        0/1     CrashLoopBackOff   9 (94s ago)   23m
nyx-postgres-5877b89bf8-5g58h   1/1     Running            0             23m
```
As duas réplicas da API (`nyx-api`) estão em `CrashLoopBackOff` com 9 reinícios em
~23 minutos de vida. O banco (`nyx-postgres`) está saudável, com 0 reinícios.

### 2. `kubectl describe pod` — causa do término
Em ambos os pods da API:
```
State:          Waiting
  Reason:       CrashLoopBackOff
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
Restart Count:  9
Limits:
  cpu:     200m
  memory:  24Mi
Requests:
  cpu:      50m
  memory:   16Mi
```
`Reason: OOMKilled` + `Exit Code: 137` é a assinatura clássica de estouro do limite
de memória do cgroup — o kernel mata o processo, não é um crash da aplicação em si.

Eventos do pod confirmam o padrão cíclico:
```
Warning  BackOff  3m1s (x96 over 22m)  kubelet  Back-off restarting failed container api ...
```
(96 ocorrências de back-off em 22 minutos — reinícios constantes, exatamente o
sintoma relatado pelo cliente: "a API fica caindo sozinha").

### 3. Deployment (`nyx-api`) — configuração de recursos
```yaml
resources:
  limits:
    cpu: 200m
    memory: 24Mi
  requests:
    cpu: 50m
    memory: 16Mi
```
Um limite de **24Mi de memória** é extremamente baixo para uma aplicação web
(a imagem é `fabricioveronez/kube-news:v1`, uma aplicação Go/HTTP com conexão a
banco Postgres). Esse patamar é insuficiente até para a inicialização do runtime
e das bibliotecas HTTP/DB, resultando em OOM quase imediato após o start.

Status do Deployment confirma a indisponibilidade:
```
message: Deployment does not have minimum availability.
reason: MinimumReplicasUnavailable
...
message: ReplicaSet "nyx-api-79c5f4d8d7" has timed out progressing.
reason: ProgressDeadlineExceeded
```

### 4. Descartando outras causas

- **Nó sem recursos?** Não. `kubectl describe node` mostra
  `Allocatable memory: 15726832Ki` (~15 GB livres) e `cpu: 16` — o nó tem folga
  enorme de memória. O problema é o *limite do container*, não a capacidade do nó.
- **Métricas de uso:** `kubectl top pods/nodes` não disponível (metrics-server não
  instalado neste cluster de laboratório), então o uso real de memória não pôde ser
  lido diretamente — mas o evento `OOMKilled` já é prova suficiente e definitiva da
  causa.
- **ResourceQuota/LimitRange no namespace:** `kubectl get resourcequota,limitrange -n
  nyx-prod` retornou vazio — o limite de 24Mi não foi imposto por uma política de
  namespace, foi definido diretamente no manifesto do Deployment (visível também na
  anotação `kubectl.kubernetes.io/last-applied-configuration`).
- **Banco de dados (`nyx-postgres`):** logs mostram inicialização normal, criação do
  banco `kubedevnews`, sem erros, e pod `Running` com 0 restarts. **Não é causa do
  incidente.**
- **Logs da aplicação:** `kubectl logs` (atual e `--previous`) retornaram vazios —
  consistente com um processo morto por OOM antes de conseguir emitir/flush de logs
  relevantes no stdout.
- **Probes:** existe `readinessProbe` em `/ready:8080` com `initialDelaySeconds: 10`,
  mas isso não é a causa raiz: mesmo que a probe falhasse, o efeito seria pod
  "NotReady", não `OOMKilled`. O evento explícito de OOM já isola a causa.

## Causa raiz

**Memory limit subdimensionado no Deployment `nyx-api` (`limits.memory: 24Mi`,
`requests.memory: 16Mi`).** A aplicação precisa de mais memória do que isso para
iniciar e operar; o kernel do container mata o processo (OOM) segundos após o start,
o kubelet reinicia o container, ele estoura o limite de novo, e assim
indefinidamente — gerando o padrão de "queda sozinha" percebido pelo cliente.

## Impacto atual

- 2/2 réplicas da API em `nyx-prod` fora do ar (`0/1 Ready`), serviço `nyx-api`
  (ClusterIP, porta 80) sem backends saudáveis para atender requisições.
- Indisponibilidade total da API para o cliente nyx desde a criação do Deployment
  (23+ minutos), com ~9 reinícios por pod e back-off crescente (o intervalo entre
  tentativas aumenta, piorando a percepção de instabilidade).

## Recomendação (não aplicada — ambiente é somente leitura)

- Aumentar `resources.limits.memory` (e `requests.memory` proporcionalmente) do
  container `api` no Deployment `nyx-api` para um valor compatível com o footprint
  real da aplicação (sugestão inicial: testar com algo como `128Mi`/`256Mi` de
  limite e ajustar via observação de uso real com metrics-server/VPA, em vez de
  fixar um valor arbitrário).
- Após corrigir o limite, validar reinícios, prontidão (`/ready`) e ausência de
  novos eventos `OOMKilled`.
- Nenhuma alteração foi feita neste cluster (laboratório preservado no estado do
  incidente, conforme restrição).
