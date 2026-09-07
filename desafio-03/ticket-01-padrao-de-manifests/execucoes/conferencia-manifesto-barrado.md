# Conferência — manifesto barrado do nyx (kube-news)

- **Manifesto avaliado:** `insumos/manifesto-barrado-nyx.yaml` (não alterado)
- **Projeto que ele empacota:** `workloads/kube-news` (Node.js/Express + Sequelize/Postgres)
- **Padrão:** revisão 2026-07-29, 19 regras (ver `skill/references/padrao-resumido.md`)
- **Método:** `skill/scripts/conferir-padrao.py` + `trivy config` + leitura do projeto,
  conforme `SKILL.md`. Saída bruta completa dos comandos em
  `conferencia-manifesto-barrado-saida-bruta.txt`, no mesmo diretório.
- **Resultado geral:** manifesto reprovado. 10 ERROs de regra obrigatória/proibida
  pelo script + 18 achados do Trivy (17 reais, 1 falso positivo documentado) + 6
  pontos que só apareceram lendo o código do kube-news, incluindo um que impede a
  aplicação de conectar no banco mesmo que toda a segurança seja corrigida.

---

## 1. O que a varredura determinística acusou (`trivy config`)

Comando: `trivy config --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL insumos/manifesto-barrado-nyx.yaml`
Resultado: 18 achados (`Failures: 18`), todos no objeto `Deployment/NyxAPI`. Eles colapsam
em três regras reais e uma leitura invertida, exatamente como o SKILL.md descreve.

### Regra 3.1 — proibido usar tag `:latest`
- **KSV-0013** (MEDIUM): container `api` deveria especificar uma tag de imagem.
- Imagem no manifesto: `registry.metacortex.io/nyx/api:latest`. **ERRO.**

### Regra 2.1 — obrigatório `requests`/`limits` de CPU e memória
- **KSV-0011** (LOW): falta `resources.limits.cpu`
- **KSV-0015** (LOW): falta `resources.requests.cpu`
- **KSV-0016** (LOW): falta `resources.requests.memory`
- **KSV-0018** (LOW): falta `resources.limits.memory`
- Nenhum bloco `resources` existe no container. **ERRO** (o Trivy só confere presença;
  o valor 1,5x–2x é julgamento de projeto — ver seção 3).

### Regra 3.2 — obrigatório `securityContext` completo (pod + container)
- **KSV-0118** (HIGH, x2 — pod e container): sem `securityContext`, container roda com
  contexto padrão (permite privilégio de root).
- **KSV-0014** (HIGH): falta `readOnlyRootFilesystem: true`.
- **KSV-0012** (MEDIUM): falta `runAsNonRoot: true`.
- **KSV-0001** (MEDIUM): falta `allowPrivilegeEscalation: false`.
- **KSV-0003 / KSV-0004 / KSV-0106** (LOW): falta `capabilities.drop: [ALL]`.
- **KSV-0020 / KSV-0021** (LOW): falta `runAsUser`/`runAsGroup` > 10000.
- **KSV-0030 / KSV-0104** (LOW/MEDIUM): falta `seccompProfile.type: RuntimeDefault`
  — esta é a **lacuna conhecida nº 1** do padrão (não está escrita na 3.2, mas sem
  ela o Pod Security `restricted` recusa o pod na admissão; SKILL.md manda incluir
  mesmo assim).
- Todos **ERRO** — o bloco `securityContext` está inteiramente ausente, tanto em
  nível de pod quanto de container.

### Falso positivo documentado — não é achado de 3.7
- **KSV-0125** (MEDIUM): "Container api ... uses an image from an untrusted
  registry", apontando `registry.metacortex.io`.
- Este check (`KSV-0125`) avalia a regra **ao contrário**: `registry.metacortex.io`
  é exatamente o registry exigido pela 3.7, e a imagem está corretamente prefixada
  com ele (`registry.metacortex.io/nyx/api:latest`). **Descartar este achado.** A
  3.7 está, na verdade, **conforme** neste manifesto (confirmado também pelo script,
  seção 2, que não a acusou).

**Regra 3.6** (proibido `hostNetwork`/`hostPID`/`privileged`) não aparece na lista —
o manifesto não usa nenhum desses campos, então está conforme por omissão.

---

## 2. O que o script da skill acusou (`scripts/conferir-padrao.py`)

Comando: `python3 skill/scripts/conferir-padrao.py insumos/manifesto-barrado-nyx.yaml`
Resultado: `10 erro(s) · 3 aviso(s) · 0 excecao(oes)`, código de saída 1 (reprova).

| Regra | Nível | Onde | Achado |
|---|---|---|---|
| **1.1** | ERRO | Deployment | nome `NyxAPI` fora do kebab-case (tem maiúsculas) |
| **1.3** | ERRO | Deployment (metadata) | faltam os 4 rótulos `app.kubernetes.io/{name,instance,part-of,managed-by}` |
| **1.3** | ERRO | Deployment (template do pod) | os mesmos 4 rótulos faltam também no template |
| **1.3** | ERRO | Service | os mesmos 4 rótulos faltam no Service |
| **1.4** | ERRO | Service `nyx-api` | seletor `{app: nyx-api}` não casa com o rótulo do pod (`app: nyxapi`, sem hífen) — Service sobe sem reclamar e nasce **sem endpoint** |
| **2.2** | ERRO | container `api` | faltam as duas probes (`readinessProbe` e `livenessProbe`) |
| **2.3** | ERRO | Deployment | `replicas: 1` em `nyx-prod` (ambiente prod); mínimo é 2 |
| **2.4** | ERRO | Deployment | sem `strategy.rollingUpdate` com `maxUnavailable: 0` em prod |
| **3.3** | ERRO | container `api`, env `DATABASE_URL` | credencial embutida na URL de conexão (`postgres://nyx:s3nh4-do-banco@...`) — heurística de credencial-em-URL |
| **3.4** | ERRO | Deployment (pod) | `automountServiceAccountToken` não está `false` |
| **1.5** | AVISO | Deployment e Service | sem anotação `metacortex.io/owner` |
| **3.5** | AVISO | Deployment | usa a ServiceAccount `default` do namespace |

Regras do escopo do script que **não** dispararam (conformes): **1.2** (namespace
`nyx-prod` no formato correto), **1.6** (nome de container `api` não está na lista
de nomes genéricos do script), **2.5** (não avaliável isoladamente — só um objeto
Deployment no arquivo, sem contexto de PDB a cruzar), **3.7** (imagem já está sob
`registry.metacortex.io`, conforme).

---

## 3. O que só apareceu lendo o projeto `workloads/kube-news`

Esta é a parte que nem o script nem o Trivy sabem responder — e onde apareceu o
achado mais sério de todos.

### 3.1 — Achado crítico: a variável de ambiente do manifesto não existe no código (fora das 19 regras, mas inviabiliza o deploy)

Lendo `src/models/post.js`, a conexão com o banco é montada por Sequelize a partir
de **seis variáveis individuais**:

```js
const DB_DATABASE = process.env.DB_DATABASE || "kubedevnews";
const DB_USERNAME = process.env.DB_USERNAME || "kubedevnews";
const DB_PASSWORD = process.env.DB_PASSWORD || "Pg#123";
const DB_HOST = process.env.DB_HOST || "localhost";
const DB_PORT = parseInt(process.env.DB_PORT, 10) || 5432;
const DB_SSL_REQUIRE = strToBool(process.env.DB_SSL_REQUIRE) || false;
```

Busquei `DATABASE_URL` em todo `src/` (`grep -rn "DATABASE_URL" src/`) e **não há
nenhuma ocorrência** — a aplicação nunca lê essa variável. O manifesto barrado
define `DATABASE_URL` como uma URL de conexão única, que é a variável errada:
mesmo corrigindo a 3.3 (movendo o valor para um `Secret` via `secretKeyRef`), se o
nome da variável continuar sendo `DATABASE_URL` a aplicação vai ignorá-la
silenciosamente, cair nos valores-padrão (`DB_HOST=localhost`, `DB_PASSWORD=Pg#123`,
banco `kubedevnews`) e nunca alcançar `pg.nyx-prod.svc`. O pod provavelmente sobe
"saudável" pelas probes (quando existirem) e falha de forma silenciosa ou tenta
conectar a um Postgres inexistente dentro do próprio pod.
**Correção:** substituir a variável única por seis `env` (ou `envFrom`), casando
exatamente os nomes acima, com `DB_PASSWORD` vindo de `secretKeyRef` (resolve 3.3
de verdade) e as demais como valor literal ou ConfigMap.
Não amarrei isto a nenhuma das 19 regras porque não é isso que elas descrevem — é
um defeito funcional que o padrão não cobre, mas que teria passado batido numa
conferência que só olhasse o YAML e as duas ferramentas.

### 3.2 — Regra 2.2: para onde as probes devem apontar

`src/system-life.js` expõe:
- `GET /health` — responde `{state: 'up', machine: hostname}` sem tocar o banco.
  **Bom alvo de liveness.**
- `GET /ready` — compara um timestamp em memória (`isRead()`), também **sem tocar
  o banco**; é o endpoint que o próprio README descreve como "verifica se a
  aplicação está pronta para receber tráfego". É o melhor candidato a
  **readiness** disponível no projeto, mas registro a ressalva: ele não exercita
  de fato a dependência do Postgres (não é uma query real), então uma falha de
  conectividade com o banco não derruba o `/ready` — a app pode ser marcada
  "pronta" e ainda assim falhar ao servir `/` ou `/post/:id` (que chamam
  `models.Post.findAll`/`findByPk`).
- `src/models/post.js` roda `seque.sync({ alter: true })` de forma não tratada
  (sem `.catch`) em `models.initDatabase()`, chamada antes de `app.listen(8080)`.
  Isso é a **lacuna conhecida nº 2** do padrão (dependência que falha na
  inicialização): se o Postgres não estiver acessível na subida, isso pode gerar
  rejeição de promise não tratada e crash antes de qualquer probe rodar — CrashLoop
  que não é defeito de manifesto, mas que uma `startupProbe` com janela folgada
  ajuda a não mascarar como falha de liveness.
- **Recomendação:** `livenessProbe` em `/health`, `readinessProbe` em `/ready`
  (com a ressalva acima documentada no PR), e considerar `startupProbe` dado o
  `sync` no boot.

### 3.3 — Regra 3.2: o que a aplicação escreve em disco

Busquei por escrita em disco em `src/` (`fs.`, `writeFile`, `/tmp`, `multer`,
`upload`) e **não encontrei nenhuma**. A aplicação serve estático via
`express.static('static')` (leitura, não escrita) e usa `express-prom-bundle` sem
modo multiprocesso (`collectDefaultMetrics: {}` simples, sem diretório de métrica
compartilhado). **Conclusão:** não é necessário nenhum `emptyDir` extra para
`readOnlyRootFilesystem: true` funcionar — a app não escreve fora do que o próprio
Node já resolve em memória. Único ponto de atenção: `console.log` em
`src/models/post.js:31` e `src/server.js:57` vai para stdout, não para arquivo,
então não interfere.

Quanto à divisão do `securityContext` (a própria SKILL avisa que o padrão não
deixa isso claro): `runAsNonRoot`, `runAsUser`, `runAsGroup`, `fsGroup` e
`seccompProfile` vão no pod; `allowPrivilegeEscalation`, `readOnlyRootFilesystem` e
`capabilities.drop` vão no container. A imagem é `registry.metacortex.io/nyx/api`
(terceiro/próprio, não inspecionei o Dockerfile — não está no repositório clonado)
— `runAsUser` exato precisa ser confirmado contra o UID de dono dos arquivos da
imagem; o que a regra exige de fato é `runAsNonRoot: true`.

### 3.4 — Regra 3.4: a aplicação fala com o apiserver?

Busquei cliente de Kubernetes nas dependências (`grep -i "kubernetes\|k8s"` em
`package.json` e `package-lock.json`) — **nenhuma ocorrência**. As dependências são
`express`, `body-parser`, `ejs`, `sequelize`, `pg`, `pg-hstore`, `prom-client`,
`express-prom-bundle`: nenhuma delas fala com o apiserver.
**Conclusão:** declarar `automountServiceAccountToken: false` tanto na
ServiceAccount dedicada quanto no pod (o do pod é o que vale).

### 3.5 — Regra 1.6: nome do componente

O container já se chama `api` (não está na lista de nomes genéricos do script, por
isso não foi avisado). Ressalva de leitura: o `kube-news` não é só uma API — serve
páginas HTML renderizadas via EJS (`/`, `/post`, `/post/:id`) além da rota
`POST /api/post`. Um nome como `web` ou `portal` descreveria melhor o papel do
container do que `api`. Não é ERRO nem AVISO de ferramenta — é uma decisão de
nomenclatura que cabe ao time do nyx; registro como observação.

### 3.6 — Regra 2.1: porte de recurso (só o ponto de partida, não o valor final)

O projeto é um processo Node.js único (sem cluster mode), Express + Sequelize +
`prom-client` com métricas default. Não há indicação de workers pesados nem
processamento assíncrono paralelo. Ponto de partida típico para esse porte:
`requests` em torno de `100m` CPU / `128Mi` memória e `limits` de `500m` CPU /
`256Mi` memória (memória do limite entre 1,5x–2x o consumo em regime, conforme a
2.1) — **isto é estimativa**, não medição; precisa ser corrigido depois de
observar o workload rodando em `nyx-prod`.

### 3.7 — Regra 2.6: tempo de drenagem

Nenhum tratamento de `SIGTERM` foi encontrado em `server.js` (sem `process.on`).
Não há dado no repositório sobre quanto tempo uma requisição em andamento leva
para finalizar. **Recomendação:** manter `terminationGracePeriodSeconds: 30`
(padrão), e declarar no PR que foi mantido por falta de dado — não é uma decisão
fechada.

---

## 4. Resumo por peso (para o time discutir com o padrão aberto ao lado)

| Peso | Regras com achado | Bloqueiam? |
|---|---|---|
| obrigatório | 1.1, 1.3, 2.1, 2.2, 2.3, 2.4, 3.2, 3.4 | sim — ERRO, barram sem discussão |
| proibido | 3.1 (tag `:latest`), 3.3 (segredo em `env.value`) | sim — proibido não tem exceção para workload de cliente |
| recomendado | 1.5, 3.5 | não bloqueiam, mas exigem justificativa no PR se não corrigidos |
| conforme | 1.2, 1.6 (ferramenta), 3.6, 3.7 | — |
| falso positivo a descartar | KSV-0125 (leitura invertida da 3.7 pelo Trivy) | não conta |
| fora das 19 regras, mas crítico | env var `DATABASE_URL` inexistente no código | sim, na prática — app nunca conecta no banco real |

O manifesto precisa ser reescrito com: nome em kebab-case, os 4 rótulos padrão em
todos os objetos e no template do pod, rótulos do Service casando com os do pod
(`app.kubernetes.io/name`, não `app: nyx-api`), `replicas: 2`, estratégia
`RollingUpdate`/`maxUnavailable: 0`/`maxSurge: 1`, `resources` com
`requests`/`limits`, `securityContext` completo em pod e container (incluindo
`seccompProfile: RuntimeDefault`), as seis variáveis de banco corretas com a senha
via `secretKeyRef`, tag de imagem imutável (não `:latest`),
`automountServiceAccountToken: false` + ServiceAccount dedicada, probes em
`/health` (liveness) e `/ready` (readiness) com `startupProbe` para o `sync` do
boot, `metacortex.io/owner` e `terminationGracePeriodSeconds: 30` documentado.
