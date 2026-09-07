# Relatório de Triagem — fake-shop (orion-stg)

## Chamado
"Subimos a versão nova do fake-shop no orion-stg e a loja parou. O deploy foi aplicado mas o pod nunca trocou."

## Diagnóstico (TL;DR)
A imagem informada no Deployment — `fabricioveronez/fake-shop:v1.14.2` — **não existe** no Docker Hub. Os pods novos ficam em `ImagePullBackOff` e nunca conseguem subir/ficar `Ready`. Como o Deployment usa `RollingUpdate`, o Kubernetes exige que os pods novos fiquem prontos antes de encerrar os antigos — só que, neste caso, **este Deployment foi criado com essa imagem desde a revisão 1** (não havia uma ReplicaSet/versão anterior saudável para onde o rollout pudesse voltar). Resultado: 0 de 3 réplicas disponíveis, o Service `orion-web` ficou sem endpoints, e a loja está fora do ar.

## Evidências coletadas (somente leitura, contexto `kind-metacortex-lab`)

### 1. Estado do Deployment
```
NAME             READY   UP-TO-DATE   AVAILABLE   IMAGES
orion-web        0/3     3            0           fabricioveronez/fake-shop:v1.14.2
```
- `Replicas: 3 desired | 3 updated | 3 total | 0 available | 3 unavailable`
- `Conditions: Available=False (MinimumReplicasUnavailable)`, `Progressing=False (ProgressDeadlineExceeded)`
- `deployment.kubernetes.io/revision: 1` e `OldReplicaSets: <none>` — ou seja, não existe uma ReplicaSet antiga saudável em paralelo; a única ReplicaSet (`orion-web-556748f4f8`) é a nova, e é ela que está quebrada.
- `rollout status`: `error: deployment "orion-web" exceeded its progress deadline`

### 2. Pods
```
NAME                              READY   STATUS             RESTARTS
orion-web-556748f4f8-6dxbk        0/1     ImagePullBackOff   0
orion-web-556748f4f8-fqtnb        0/1     ImagePullBackOff   0
orion-web-556748f4f8-ww7km        0/1     ImagePullBackOff   0
```

### 3. Eventos (kubelet / replicaset)
```
Warning  Failed   pod/orion-web-556748f4f8-*  Failed to pull image "fabricioveronez/fake-shop:v1.14.2":
  rpc error: code = NotFound desc = failed to pull and unpack image
  "docker.io/fabricioveronez/fake-shop:v1.14.2": failed to resolve reference
  "docker.io/fabricioveronez/fake-shop:v1.14.2": docker.io/fabricioveronez/fake-shop:v1.14.2: not found
Warning  Failed   Error: ErrImagePull
Warning  Failed   Error: ImagePullBackOff
Normal   BackOff  Back-off pulling image "fabricioveronez/fake-shop:v1.14.2"  (x85 over 23m)
```

### 4. Confirmação de que a tag não existe no registro
Consulta somente-leitura ao Docker Hub (`fabricioveronez/fake-shop`) mostra as tags realmente publicadas:
```
1, latest, v1, v2, v6, v7, v8, v9, v11, v12, v13, v14, v15, v16, v17, v19, v20, v26
```
Não existe nenhuma tag `v1.14.2` (o repositório nem segue esse padrão semver — as tags são `vN` inteiras). A tag usada no manifesto está incorreta/inexistente — provavelmente um erro de digitação (ex.: confundida com `v14`, ou com uma tag de outro repositório/produto).

### 5. Impacto no serviço
```
NAME                       ENDPOINTS          
endpoints/orion-web        (vazio)
```
O Service `orion-web` está sem nenhum endpoint saudável — não há nenhum pod `Ready` por trás dele, confirmando a percepção do cliente de que "a loja parou".

O banco (`orion-postgres`) está saudável e não é a causa (`1/1 Running`, endpoint ativo em `10.244.0.10:5432`).

## Causa raiz
**Tag de imagem inexistente no registro** (`fabricioveronez/fake-shop:v1.14.2`) informada no manifesto do Deployment `orion-web`. O `kubelet` não consegue puxar a imagem (`NotFound` no `docker.io`), os pods da nova ReplicaSet nunca saem de `ImagePullBackOff`/ficam `Ready`, e por isso o rollout trava e "o pod nunca troca" — na prática, não havia uma versão anterior saudável para a qual o tráfego pudesse continuar sendo servido durante o rollout, então o serviço caiu por completo (0 endpoints).

## Recomendação (não executada — laboratório é somente leitura)
1. Corrigir a tag da imagem no manifesto do Deployment `orion-web` para uma tag existente e validada no registro (ex.: `v14` ou a tag correta pretendida pelo time de aplicação — confirmar com quem gerou o release).
2. Reaplicar o manifesto corrigido (`kubectl apply`) para que o Deployment crie uma nova ReplicaSet com a imagem válida.
3. Acompanhar `kubectl rollout status deploy/orion-web -n orion-stg` até `3/3` `Ready`/`Available`.
4. Validar os endpoints do Service `orion-web` voltando a listar os IPs dos pods.
5. Sugestão de prevenção: adicionar validação de existência da imagem/tag no pipeline de CI/CD antes do `apply` (ex.: `docker manifest inspect` ou `crane digest`) para evitar deploys com tags inexistentes chegando ao cluster.

---
*Relatório gerado via comandos somente-leitura (`kubectl get/describe/rollout status`, consulta pública ao Docker Hub). Nenhuma alteração foi feita no cluster `kind-metacortex-lab`.*
