## Chamado: nyx-stg/nyx-api (kube-news) — "responde 503 pra quem chama de fora, aplicação parece de pé"

**Causa:** o Service `nyx-api` seleciona `app=nyx-api`, mas os pods do Deployment carregam o rótulo `app=nyxapi` — um hífen de diferença. O Service nasce sem nenhum endpoint e não tem para onde mandar o tráfego.

**Evidência:**
```
$ kubectl describe svc nyx-api -n nyx-stg
Selector:                 app=nyx-api
...
Endpoints:                

$ kubectl get pods -n nyx-stg --show-labels
NAME                            LABELS
nyx-api-5cd5cdbf9d-5qf22        app=nyxapi,pod-template-hash=5cd5cdbf9d
nyx-api-5cd5cdbf9d-8ppxv        app=nyxapi,pod-template-hash=5cd5cdbf9d

$ kubectl get endpoints nyx-api -n nyx-stg -o yaml
apiVersion: v1
kind: Endpoints
metadata:
  name: nyx-api
  namespace: nyx-stg
# chave "subsets" ausente

$ kubectl get endpointslices -n nyx-stg -l kubernetes.io/service-name=nyx-api -o yaml
endpoints: null
ports: null
```

**Como cheguei:**
1. `kubectl get all -n nyx-stg -o wide` — Deployment `nyx-api` 2/2 prontos e disponíveis, sem indício de rollout travado ou pod não pronto. Descartou as camadas de objeto de carga e pod.
2. `kubectl get deployment nyx-api -o json` (`.status`) — `Available=True` (`MinimumReplicasAvailable`), `readyReplicas: 2`. Deployment íntegro.
3. Container status dos dois pods — `restartCount: 0` e `restartCount: 1`; o segundo com `lastState.terminated.reason: Error, exitCode: 1` ocorrido no mesmo segundo da subida (19:07:12), seguido de `running` estável. Padrão de ruído catalogado (tentativa de conexão ao banco antes de o Postgres/DNS estar pronto), não se repete e não corresponde ao sintoma relatado (503 constante, não instabilidade intermitente).
4. `kubectl get events -n nyx-stg` — nenhum evento `Warning`; apenas eventos `Normal` de criação/pull/start. Confirma que, do ponto de vista das camadas 1 a 4, está tudo saudável — assinatura clássica de problema de metadado.
5. Dependência ao lado: `nyx-postgres` com 1/1 pronto e `Available=True`. Banco descartado como causa.
6. Como as camadas 1-4 estavam limpas e o sintoma persistia, cruzei `spec.selector` do Service com `metadata.labels` dos pods (`kubectl describe svc nyx-api` + `kubectl get pods --show-labels`): `app=nyx-api` × `app=nyxapi`. Divergência de um hífen.
7. Confirmação final em `Endpoints`/`EndpointSlice`: `subsets` ausente no primeiro, `endpoints: null` e `ports: null` no segundo — Service sem nenhum destino, o que explica o 503 fim-a-fim (proxy/ingress recebe a chamada, encaminha ao Service, e o Service não tem endereço para entregar).
8. Também conferi `targetPort` do Service (`8080`) contra `containerPort` dos pods (`8080`) — batem; não é problema de porta.

**O que está saudável ao lado:**
- Deployment `nyx-api`: 2/2 réplicas prontas e disponíveis, rollout concluído (`NewReplicaSetAvailable`).
- Pods: `Running`, `ready: true`, imagem `fabricioveronez/kube-news:v1` puxada com sucesso nos dois.
- Dependência `nyx-postgres`: 1/1 pronto, `Available=True`, sem reinícios.
- Nenhum evento `Warning`/`BackOff` no namespace.
- Portas batendo: `Service.spec.ports[].targetPort=8080` = `containerPort=8080` dos pods.
- O único reinício observado (`exitCode 1`, um pod, uma vez, no instante da subida) é ruído já catalogado (tentativa de conexão a dependência antes dela publicar endereço) — não explica um 503 persistente e não deve ser perseguido.

**Correção sugerida (não aplicada):**
Alinhar o rótulo. Duas opções, a decidir por quem opera:
- Ajustar `spec.selector.app` do Service `nyx-api` de `nyx-api` para `nyxapi`, para casar com o rótulo atual dos pods; ou
- Ajustar `spec.template.metadata.labels.app` do Deployment `nyx-api` (e o `spec.selector.matchLabels` do próprio Deployment, hoje `app=nyxapi`) de `nyxapi` para `nyx-api`, para casar com o Service — isso implica um rollout do Deployment.
Nenhuma alteração foi aplicada no cluster.
