# O que só se sabe abrindo o kube-news

Commit lido: `aab9356`. Nada abaixo está no manifesto de ninguém — tudo sai do
projeto, e é por isso que estas regras do padrão viram **instrução** e não script.

## Porta

`src/server.js`, última linha executável:

```js
app.listen(8080);
```

**Número fixo no código.** A aplicação não lê porta de variável de ambiente —
diferente de quase tudo que se empacota. `containerPort: 8080`, e mudar a porta
exige mudar a imagem.

## Endpoints — e a decisão da regra 2.2 é uma armadilha

`src/server.js` e `src/system-life.js` registram:

| Rota | Toca o banco? | O que faz |
|---|---|---|
| `GET /` | **sim** | `Post.findAll()` e renderiza o índice |
| `GET /post/:id` | sim | `Post.findByPk()` |
| `POST /post`, `POST /api/post` | sim | `Post.create()` |
| `GET /post` | não | renderiza o formulário vazio |
| `GET /health` | **não** | devolve `{state: 'up', machine: os.hostname()}` |
| `GET /ready` | **não** | compara dois timestamps |
| `PUT /unhealth` | não | passa a responder 500 em **tudo** |
| `PUT /unreadyfor/:seconds` | não | faz `/ready` responder 500 por N segundos |
| `GET /metrics` | não | `express-prom-bundle` |

**A armadilha:** o projeto tem `/health` **e** `/ready`, com os nomes exatos que
uma leitura apressada procura. Casar `livenessProbe` com `/health` e
`readinessProbe` com `/ready` parece a escolha óbvia — e é errada.

`/ready` não checa nada. Ele compara `readTime` com o relógio, e `readTime` só
muda quando alguém chama `PUT /unreadyfor/:seconds`. É **gancho de simulação de
falha**, feito para exercícios de aula, não checagem de dependência. Uma readiness
apontada para lá responde "pronto" com o banco desligado.

Quem exercita a dependência é `/`, que faz `Post.findAll()`.

Detalhe de ordem que confirma a escolha da liveness: `healthMid` é registrado
**antes** do roteador, então `PUT /unhealth` derruba todas as rotas, `/health`
inclusive. É exatamente o que se quer de uma liveness — o gancho existe para
simular processo morto.

## Variáveis de ambiente

`src/models/post.js`, com os nomes exatos e os defaults:

```js
const DB_DATABASE = process.env.DB_DATABASE || "kubedevnews";
const DB_USERNAME = process.env.DB_USERNAME || "kubedevnews";
const DB_PASSWORD = process.env.DB_PASSWORD || "Pg#123";
const DB_HOST     = process.env.DB_HOST     || "localhost";
const DB_PORT     = parseInt(process.env.DB_PORT, 10) || 5432;
const DB_SSL_REQUIRE = strToBool(process.env.DB_SSL_REQUIRE) || false;
```

São seis, e **`DATABASE_URL` não é uma delas**. Isso confirma, num segundo
commit e por outro caminho, o achado da conferência do Ticket 01: o manifesto
barrado do nyx injetava `DATABASE_URL`, que esta aplicação nunca lê. Corrigir só
a regra 3.3 daquele manifesto o deixaria conforme e quebrado.

Duas consequências para o manifesto:

- `DB_SSL_REQUIRE` passa por `strToBool`, que compara com a string `"true"`.
  Qualquer outro valor desliga o SSL. No ConfigMap vai `"false"`, explícito.
- A senha default está **no código-fonte**. É problema do projeto, não do
  manifesto; o manifesto cumpre a 3.3 injetando `DB_PASSWORD` por `secretKeyRef`,
  o que faz o default nunca ser usado.

## O que a aplicação escreve em disco

**Nada.** E isso é afirmação, não omissão:

- `express.static('static')` só lê;
- `prom-client` com `collectDefaultMetrics` em processo único mantém as métricas
  **em memória** — não há `PROMETHEUS_MULTIPROC_DIR`, que foi justamente o que
  obrigou dois `emptyDir` no fake-shop;
- não há log em arquivo, upload, cache nem sessão em disco.

Por isso o Deployment sai com `readOnlyRootFilesystem: true` e **sem
`volumeMounts`**. É a diferença mais visível entre este conjunto e o do
`orion-prod`, e ela vem do projeto.

## Se fala com o apiserver

Dependências declaradas em `src/package.json`: `express`, `ejs`, `body-parser`,
`pg`, `pg-hstore`, `sequelize`, `prom-client`, `express-prom-bundle`. **Nenhum
cliente de Kubernetes.** A 3.4 se aplica: `automountServiceAccountToken: false`,
na ServiceAccount e no pod.

## O que roda antes do processo principal

```js
models.initDatabase();   // seque.sync({ alter: true })
app.listen(8080);
```

`initDatabase()` dispara a sincronização de schema e **não é aguardado**. O
`listen` acontece imediatamente, então a porta abre antes de o schema existir.

Isso é a **lacuna 2 do padrão**, que a skill manda registrar em vez de fingir que
o documento respondeu: nada no padrão trata de dependência que falha na
inicialização. Aqui a rejeição de `sync()` não é tratada — sem banco alcançável,
o processo morre por *unhandled rejection* antes de qualquer probe rodar. Probe
não resolve, porque o processo já não existe.

O que dá para fazer no manifesto é cobrir a janela em que o banco ainda está
subindo: `startupProbe` em `/`, com folga. O que o manifesto **não** resolve é
banco ausente.
