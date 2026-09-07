# Fixtures — capturas do `kind-metacortex-lab`

Nenhum JSON deste diretório foi escrito à mão (D-B do `design.md`). Todos vêm
do cliente oficial `kubernetes`, com `_preload_content=False` — a mesma forma
que `cliente.py` usa em produção — e não do `kubectl -o json`, porque o
`kubectl` omite `managedFields` na exibição por padrão e o cliente cru não
omite; capturar pelo mesmo caminho que o código usa é o que a D-B pede.

Servidor: `kind-metacortex-lab`, v1.31.0. Cliente `kubernetes` 36.0.3, Python
3.10.12. Reproduz tudo de uma vez com:

```bash
cd desafio-03/ticket-04-dashboard-do-cluster
./.venv/bin/python - <<'EOF'
import json
from kubernetes import client, config

config.load_kube_config()
with client.ApiClient() as api:
    core, apps, disc = client.CoreV1Api(api), client.AppsV1Api(api), client.DiscoveryV1Api(api)
    capturas = [
        ("pods-nyx-prod.json", core.list_namespaced_pod, "nyx-prod"),
        ("deployments-orion-stg.json", apps.list_namespaced_deployment, "orion-stg"),
        ("statefulsets-nyx-dev.json", apps.list_namespaced_stateful_set, "nyx-dev"),
        ("endpoints-nyx-stg.json", core.list_namespaced_endpoints, "nyx-stg"),
        ("endpointslices-nyx-stg.json", disc.list_namespaced_endpoint_slice, "nyx-stg"),
        ("events-nyx-prod.json", core.list_namespaced_event, "nyx-prod"),
        ("deployments-nyx-dev.json", apps.list_namespaced_deployment, "nyx-dev"),
        ("deployments-orion-prod.json", apps.list_namespaced_deployment, "orion-prod"),
    ]
    for nome_arquivo, fn, namespace in capturas:
        bruto = json.loads(fn(namespace, _preload_content=False).data)
        with open(f"tests/fixtures/{nome_arquivo}", "w") as f:
            json.dump(bruto, f, indent=2, sort_keys=True)
            f.write("\n")
EOF
```

Ou por tipo, com `kubectl get --raw` (equivalente ao que o cliente chama por
baixo — útil para conferir uma fixture isolada; note que `kubectl get -o json`
comum não serve, pelo motivo acima):

| Arquivo | Comando | O que prova |
|---|---|---|
| `pods-nyx-prod.json` | `kubectl get --raw /api/v1/namespaces/nyx-prod/pods` | pod `nyx-api` com `state.waiting.reason=CrashLoopBackOff` e `lastState.terminated.reason=OOMKilled` |
| `deployments-orion-stg.json` | `kubectl get --raw /apis/apps/v1/namespaces/orion-stg/deployments` | Deployment `orion-web` sem a chave `readyReplicas` no status |
| `statefulsets-nyx-dev.json` | `kubectl get --raw /apis/apps/v1/namespaces/nyx-dev/statefulsets` | StatefulSet `nyx-postgres` sem a chave `conditions` no status |
| `endpoints-nyx-stg.json` | `kubectl get --raw /api/v1/namespaces/nyx-stg/endpoints` | `Endpoints/nyx-api` sem a chave `subsets` |
| `endpointslices-nyx-stg.json` | `kubectl get --raw /apis/discovery.k8s.io/v1/namespaces/nyx-stg/endpointslices` | fatia de `nyx-api` com a chave `endpoints` presente e valor `null` |
| `events-nyx-prod.json` | `kubectl get --raw /api/v1/namespaces/nyx-prod/events` | eventos com `count` e `lastTimestamp` preenchidos, `series` ausente |
| `deployments-nyx-dev.json` | `kubectl get --raw /apis/apps/v1/namespaces/nyx-dev/deployments` | amostra saudável de réplica única — `nyx-api`, `readyReplicas` presente |
| `deployments-orion-prod.json` | `kubectl get --raw /apis/apps/v1/namespaces/orion-prod/deployments` | amostra saudável de duas réplicas — `orion-web`, `readyReplicas` presente |

## Nota sobre reprodutibilidade

Os números mudam a cada captura — `restartCount`, `count` de evento,
`resourceVersion`, idades. O que se mantém, e é o que os testes de
interpretação (fora do escopo deste commit) devem checar, é a **forma**:
quais chaves existem, quais estão ausentes, e o vocabulário dos `reason`.
Quando o cenário do cluster mudar, refaça a captura em vez de editar o JSON
à mão — fixture que não se sabe reproduzir é fixture escrita à mão com passos
extras (D-B, `design.md`).
