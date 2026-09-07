# As 19 regras, em uma linha cada

Destilação operacional do padrão, **não** uma cópia dele. A fonte de verdade é a
página do wiki, revisão 2026-07-29; em caso de divergência, vale ela.

Pesos: **obrigatório** barra sem discussão · **recomendado** aceita exceção
justificada no PR · **proibido** não tem exceção para workload de cliente.

## Bloco 1 — Identidade e nomenclatura

| # | Peso | Regra | Quem confere |
|---|---|---|---|
| 1.1 | obrigatório | nome em kebab-case: minúsculo, hífen, sem camelCase/underscore/ponto | script |
| 1.2 | obrigatório | namespace `<cliente>-<ambiente>`, ambiente em `dev`/`stg`/`prod` | script |
| 1.3 | obrigatório | os quatro rótulos `app.kubernetes.io/{name,instance,part-of,managed-by}` em todo objeto **e** no template do pod | script |
| 1.4 | obrigatório | seletor do Service e `matchLabels` idênticos aos rótulos do pod | script (cruzamento) |
| 1.5 | recomendado | `metacortex.io/owner`, e `metacortex.io/runbook` quando existir | script (aviso) |
| 1.6 | recomendado | nome do container = o componente, não `app`/`main`/`container` | script avisa · projeto decide |

## Bloco 2 — Resiliência

| # | Peso | Regra | Quem confere |
|---|---|---|---|
| 2.1 | obrigatório | `requests` e `limits` de CPU e memória; memória entre 1,5x e 2x o consumo em regime | Trivy (presença) · projeto (valor) |
| 2.2 | obrigatório | as duas probes, apontando para endpoints que a aplicação expõe; liveness não pode depender do banco | script (presença) · projeto (alvo) |
| 2.3 | obrigatório | `replicas >= 2` em prod; uma réplica é aceitável em dev e stg | script |
| 2.4 | obrigatório em prod | `RollingUpdate` com `maxUnavailable: 0` e `maxSurge: 1` | script |
| 2.5 | recomendado | PDB com `minAvailable: 1` em prod com mais de uma réplica | script (aviso) |
| 2.6 | recomendado | `terminationGracePeriodSeconds` compatível com a drenagem | ninguém — decisão de operação |

## Bloco 3 — Segurança

| # | Peso | Regra | Quem confere |
|---|---|---|---|
| 3.1 | **proibido** | tag `:latest`; sempre tag imutável ou digest | Trivy |
| 3.2 | obrigatório | `securityContext` completo, dividido entre nível de pod e de container | Trivy (presença) · projeto (o que escreve em disco) |
| 3.3 | **proibido** | segredo em texto puro em `env.value`, ConfigMap ou comentário | script (heurística) · leitura decide |
| 3.4 | obrigatório | `automountServiceAccountToken: false` quando não fala com a API | script (campo) · projeto (a condicional) |
| 3.5 | recomendado | ServiceAccount dedicada, com RBAC mínimo ou nenhum | script (aviso) |
| 3.6 | **proibido** | `hostNetwork`, `hostPID`, `privileged` | Trivy |
| 3.7 | obrigatório | toda imagem em `registry.metacortex.io` | script |

**A 3.7 não vai para o Trivy de propósito:** o check KSV-0125 marca o domínio do
parque como registry não confiável, ou seja, acusa quem cumpriu a regra.

## Bloco 4 — fora do escopo

Oito verbetes de vocabulário (Pod, ReplicaSet, Deployment, Service,
`port` × `targetPort`, Endpoints, ConfigMap e Secret, probes), escritos para quem
está chegando na plataforma. Nenhum aprova ou reprova manifesto. Um terço da
página, zero regra.

## Lacunas conhecidas do padrão

- `seccompProfile` falta na 3.2, e sem ele o Pod Security `restricted` recusa o pod
- nada trata de dependência que falha na inicialização
- nenhum vocabulário para carga com estado: a 1.3 não lista StatefulSet e a 2.3 não
  qualifica o tipo de carga
