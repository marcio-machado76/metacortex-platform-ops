## Chamado: orion-stg/orion-web (imagem fake-shop) — "subimos a versao nova do fake-shop no orion-stg e a loja parou. o deploy foi aplicado mas o pod nunca trocou"

**Causa:** a tag de imagem anunciada no release, `fabricioveronez/fake-shop:v1.14.2`, não existe no registry — o runtime não consegue resolver a referência, e o ReplicaSet novo (`orion-web-556748f4f8`) nunca produz um pod pronto.

**Evidência:**
```
Warning  Failed     kubelet   Failed to pull image "fabricioveronez/fake-shop:v1.14.2":
rpc error: code = NotFound desc = failed to pull and unpack image
"docker.io/fabricioveronez/fake-shop:v1.14.2":
failed to resolve reference "docker.io/fabricioveronez/fake-shop:v1.14.2":
docker.io/fabricioveronez/fake-shop:v1.14.2: not found
```
```
containerStatuses[0]:
  restartCount: 0
  state.waiting.reason:  ImagePullBackOff
  state.waiting.message: Back-off pulling image "fabricioveronez/fake-shop:v1.14.2"
  lastState: {}   # nunca houve execução anterior
```
```
Deployment orion-web:
  Replicas: 3 desired | 3 updated | 3 total | 0 available | 3 unavailable
  Conditions:
    Available    False  MinimumReplicasUnavailable
    Progressing  False  ProgressDeadlineExceeded
```

**Como cheguei:**
1. Enquadramento: namespace `orion-stg`, objeto `Deployment/orion-web` (imagem `fake-shop`), sintoma "parou depois do deploy" → comecei pelo rollout do Deployment e por `state.waiting` dos pods novos, conforme o método.
2. Camada 1 (objeto de carga): `kubectl get deploy orion-web -n orion-stg` mostra `0/3` prontos; `describe` confirma `Available=False (MinimumReplicasUnavailable)` e `Progressing=False (ProgressDeadlineExceeded)` — o rollout começou e travou. `NewReplicaSet: orion-web-556748f4f8 (3/3 replicas created)` — o ReplicaSet novo existe e criou os 3 pods, mas nenhum ficou pronto. Isso descarta "o rollout não anda por falta de objeto" e aponta para os pods do RS novo (assinatura C do catálogo).
3. Camada 2/3 (pod/container): os 3 pods estão em `ImagePullBackOff`. Antes de aprofundar, li `restartCount`: é `0` em todos, e não há `lastState` — o container nunca rodou. Isso descarta hipótese de crash/OOM e direciona para `state.waiting.reason`/`state.waiting.message`, que trazem `ImagePullBackOff` e a mensagem crua do containerd confirmando "tag not found".
4. Camada 4 (eventos do namespace): eventos repetidos de `Failed`/`ErrImagePull`/`BackOff` para os 3 pods, com `BackOff` acumulando dezenas de ocorrências — confirmam ciclo, mas quem fecha o diagnóstico é a mensagem de `state.waiting`, não o evento.
5. Dependência ao lado: `orion-postgres` está `1/1 Running`, 0 reinícios — o banco do par está saudável e não é a causa.

**O que está saudável ao lado:**
- `orion-postgres` (Deployment e pod): `1/1` pronto, 0 reinícios, imagem `postgres:16-alpine` puxada com sucesso.
- Agendamento dos 3 pods `orion-web`: todos foram agendados normalmente no nó (`Scheduled` com sucesso) — não é problema de nó, taint ou recurso.
- `Service/orion-web` e `Service/orion-postgres` existem e resolvem para os respectivos ClusterIP — não há indício de problema de seletor/metadado; o tráfego não chega porque não há pod pronto para receber, não porque falte destino cadastrado.
- Não houve envolvimento de ConfigMap/Secret (variáveis de ambiente do container são literais no manifesto) — descarta `CreateContainerConfigError`.

**Correção sugerida (não aplicada):**
Confirmar no registry (`docker.io/fabricioveronez/fake-shop`) qual é a tag correta publicada para esta versão — `v1.14.2` não existe — e ajustar `spec.template.spec.containers[].image` do Deployment `orion-web` no manifesto de origem para a tag válida (ou repadronizar o pipeline de release para não publicar uma tag inexistente antes do deploy). Depois de corrigir a imagem, um novo rollout deve substituir o ReplicaSet `orion-web-556748f4f8` sem necessidade de nenhuma outra ação manual.
