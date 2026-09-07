# Relatório de Triagem — kube-news (nyx-stg) respondendo 503

**Cluster:** kind-metacortex-lab
**Namespace afetado:** nyx-stg
**Sintoma relatado:** chamadas externas ao kube-news retornam 503; a aplicação "parece de pé".

## Causa raiz

**Mismatch de selector/label entre o Service `nyx-api` e os Pods do Deployment `nyx-api` no namespace `nyx-stg`.**

- O `Service nyx-api` foi criado com `selector: app=nyx-api` (com hífen).
- O `Deployment nyx-api` gera Pods com o label `app=nyxapi` (sem hífen), pois esse é o `matchLabels`/label do template de Pod do Deployment.
- Como o selector do Service não bate com nenhum label de Pod, o Service **não tem nenhum Endpoint associado**.
- Resultado: qualquer requisição roteada através do Service `nyx-api` não tem para onde ser encaminhada, e o componente que recebe o tráfego externo (proxy/ingress/gateway na frente do Service) devolve **503 Service Unavailable** ao cliente — mesmo com os Pods da aplicação saudáveis e prontos.

Isso explica exatamente o relato do cliente: a aplicação "parece de pé" (os Pods estão `Running`, `Ready 1/1`, passando nos probes de liveness/readiness), mas ninguém consegue ser roteado até ela porque o Service que a expõe está "vazio" por causa do mismatch de labels.

## Evidências coletadas (somente leitura, nenhuma alteração feita no cluster)

1. Pods do `nyx-api` em `nyx-stg` estão saudáveis:
   ```
   NAME                       READY   STATUS    RESTARTS   AGE
   nyx-api-5cd5cdbf9d-5qf22   1/1     Running   0          23m
   nyx-api-5cd5cdbf9d-8ppxv   1/1     Running   1 (23m ago) 23m
   ```
   Ambos com `Ready: True`, condições `Initialized/ContainersReady/PodScheduled = True`, sem erros nos `Events`.

2. Labels reais dos Pods (herdados do template do Deployment):
   ```
   app=nyxapi,pod-template-hash=5cd5cdbf9d
   ```

3. Selector configurado no Service (via `kubectl.kubernetes.io/last-applied-configuration`, aplicado manualmente com `kubectl apply`):
   ```
   spec.selector: {"app":"nyx-api"}
   ```

4. Endpoints do Service confirmam a ausência de backends:
   ```
   NAME      ENDPOINTS   AGE
   nyx-api   <none>      23m
   ```
   (Compare com `nyx-postgres`, que está saudável: `nyx-postgres  10.244.0.11:5432  23m`).

5. Comparação com o namespace `nyx-prod` (mesmo app, ambiente diferente) confirma qual é o padrão correto: lá o Service usa `selector: app=nyx-api` e os Pods também têm o label `app=nyx-api` (com hífen) — ou seja, a convenção correta do time é `app=nyx-api`. O Deployment de `nyx-stg` foi criado/alterado com o label divergente `app=nyxapi`.
   > Observação à parte: em `nyx-prod` os Pods do `nyx-api` estão em `CrashLoopBackOff` — é um problema distinto, não relacionado a este chamado (que é especificamente sobre `nyx-stg`), e não foi aprofundado aqui.

6. Não há Ingress, Gateway/HTTPRoute nem Service do tipo NodePort/LoadBalancer no cluster apontando para `nyx-stg` além do Service `nyx-api` (ClusterIP, porta 80 → targetPort 8080). Ou seja, o único caminho de tráfego para a aplicação depende inteiramente desse Service — e ele está sem Endpoints.

## Por que isso gera 503 e não 404/timeout

Quando um Service não possui nenhum Endpoint, o componente de rede que depende dele (kube-proxy/iptables, ou um proxy/gateway na frente que consulta os Endpoints) não tem um destino válido para encaminhar a conexão. O comportamento típico nesse cenário é a rejeição imediata da conexão/requisição com **503 Service Unavailable**, em vez de um erro de aplicação — o que é coerente com "a aplicação parece de pé" (os pods realmente estão saudáveis) mas ninguém de fora consegue ser roteado até eles.

## Recomendação (não executada — apenas leitura neste chamado)

Alinhar o label do Pod template do Deployment `nyx-api` em `nyx-stg` com o selector do Service (ou vice-versa), padronizando para `app=nyx-api` (mesmo padrão usado — na definição do Service — em `nyx-prod`). Após a correção, validar que `kubectl get endpoints nyx-api -n nyx-stg` passa a listar os IPs dos dois Pods do `nyx-api`.

Nenhum comando de escrita (`apply`, `edit`, `patch`, `delete`, `scale`, `rollout`, `restart`, `cordon`, `label`) foi executado durante esta triagem, conforme restrição do laboratório.
