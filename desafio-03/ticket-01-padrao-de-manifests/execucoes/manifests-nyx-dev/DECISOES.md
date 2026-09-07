# Decisões — manifests do kube-news em `nyx-dev`

Execução da skill `padrao-de-manifests` em **modo escrita**, para o Ticket 04.
O que o padrão fecha não está aqui; aqui está o que ele deixou em aberto e
precisou de julgamento.

A leitura do projeto que sustenta estas decisões está em
`../leitura-do-kube-news.md`. Conferência gravada em
`../conferencia-nyx-dev-script.txt` e `../conferencia-nyx-dev-trivy.txt`.

---

## 1 · Ambiente `dev`: três regras não se aplicam, e isso tem efeito colateral

A regra 2.3 exige `replicas >= 2` **em prod**, e o texto diz que em `dev` e `stg`
uma réplica é aceitável. A 2.4 é "obrigatório em prod". A 2.5 pede PDB para
workload de prod com mais de uma réplica.

Em `nyx-dev`, nenhuma das três se aplica. O conjunto sai com `replicas: 1`, sem
bloco `strategy` e sem PodDisruptionBudget.

**O efeito colateral vale ser dito, porque é o tipo de coisa que passa por
descuido quando não está escrita:** este conjunto **exercita menos regras do
padrão** que o do `orion-prod`. Quem usar os dois como amostra de cobertura da
skill precisa saber que a amostra de dev é mais rasa por construção, não por
falha do conferidor.

E há uma consequência que não é sobre o padrão, e sim sobre o cluster: com este
conjunto no ar, o parque passa a ter um Deployment de **réplica única** ao lado
de um de **duas**. Isso é insumo direto para o Ticket 04 — a coluna "prontos
sobre desejados" ganha dois denominadores diferentes, e a D7 (ordenar por
anormalidade) passa a ter os dois lados para comparar em vez de só o patológico.

Nota de contraste: o `orion-postgres` carrega anotação de exceção à 2.3, com
motivo, aprovador e prazo. O `nyx-postgres` **não carrega**, e não é esquecimento:
em dev não há regra a excetuar, e anotação de exceção sem regra violada seria
ruído — declararia um desvio que não existe.

## 2 · A readiness não aponta para `/ready`

A decisão mais importante do conjunto, e a que mais parece errada de relance.

O kube-news expõe `/health` **e** `/ready`, com os nomes exatos que a regra 2.2
sugere. A escolha óbvia seria casar um com cada probe. Ela é errada.

`/ready` não checa dependência nenhuma: compara `readTime` com o relógio, e
`readTime` só muda quando alguém chama `PUT /unreadyfor/:seconds`. É gancho de
simulação de falha, não checagem. Uma readiness apontada para lá responderia
"pronto" com o banco desligado — e o Service mandaria tráfego para um pod que só
sabe devolver erro.

| Probe | Alvo | Por quê |
|---|---|---|
| `livenessProbe` | `/health` | devolve `os.hostname()`, não toca o banco. Banco lento não pode virar reinício, porque reinício não conserta banco |
| `readinessProbe` | `/` | `Post.findAll()` — exercita a dependência sem a qual a aplicação não serve |
| `startupProbe` | `/` | ver decisão 3 |

O custo da readiness em `/` é uma consulta a cada checagem. A mitigação é
`periodSeconds: 15`, não trocar o alvo por um que não detecta nada.

Detalhe que confirma a escolha da liveness: `healthMid` é registrado antes do
roteador, então `PUT /unhealth` derruba **todas** as rotas, `/health` inclusive.
O gancho de "processo morto" funciona como se espera de uma liveness.

## 3 · `startupProbe` em `/`, e o que ela não resolve

`models.initDatabase()` dispara `seque.sync({alter: true})` e **não é aguardado**;
`app.listen(8080)` roda na linha seguinte. A porta abre antes de o schema existir.

A `startupProbe` em `/` com `failureThreshold: 60` e `periodSeconds: 5` cobre até
cinco minutos de banco subindo, sem a liveness matar o container no meio.

**O que ela não resolve, e o padrão não tem resposta para isso:** com o banco
ausente, a rejeição de `sync()` não é tratada e o processo morre por *unhandled
rejection* antes de qualquer probe rodar. É a lacuna 2 listada na própria skill —
"nada trata de dependência que falha na inicialização" — e fica registrada em vez
de disfarçada.

## 4 · `automountServiceAccountToken: false`, verificado

`src/package.json` declara `express`, `ejs`, `body-parser`, `pg`, `pg-hstore`,
`sequelize`, `prom-client` e `express-prom-bundle`. Nenhum cliente de Kubernetes.
A 3.4 se aplica. Declarado em dois lugares — na ServiceAccount e no pod — porque o
do pod é o que vale e o da conta protege quem esquecer.

## 5 · Recursos: estimativa declarada, não medida

`requests: {cpu: 100m, memory: 128Mi}` · `limits: {cpu: 500m, memory: 256Mi}`.

Node em processo único por réplica, sem worker. A regra da casa é limite de
memória entre 1,5x e 2x o consumo em regime, e **consumo em regime não está no
repositório**. Este é o único número do manifesto que se espera corrigir depois de
observar o workload rodando; tratá-lo como decisão fechada é como se produz
reinício por OOM.

## 6 · `readOnlyRootFilesystem: true` sem nenhum `emptyDir`

Afirmação sobre o projeto, não esquecimento. O kube-news não escreve em disco:
`express.static` só lê, não há log em arquivo, e o `prom-client` em processo único
mantém as métricas em memória — não existe `PROMETHEUS_MULTIPROC_DIR`, que foi
exatamente o que obrigou dois `emptyDir` no fake-shop.

É a diferença mais visível entre este conjunto e o do `orion-prod`, e ela vem do
código. Fica como hipótese a ser derrubada pela execução: se o pod escrever em
algum lugar, aparece na primeira subida.

## 7 · Porta 8080, fixa no código

`app.listen(8080)` — número literal. A aplicação não lê porta de variável de
ambiente. O `containerPort` acompanha, o Service publica 80 e encaminha por
**nome** de porta, não por número.

## 8 · Não existe `DATABASE_URL`

As seis variáveis são `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT` e `DB_SSL_REQUIRE`. Confirma por outro caminho o achado da conferência
do Ticket 01: o manifesto barrado injetava `DATABASE_URL`, que esta aplicação
nunca lê — corrigir só a 3.3 daquele manifesto o deixaria conforme e quebrado.

A senha default `Pg#123` está no código-fonte. É problema do projeto, não do
manifesto; injetar `DB_PASSWORD` por `secretKeyRef` faz o default nunca ser usado.

## 9 · `terminationGracePeriodSeconds: 30` mantido por falta de dado

O padrão de 30s foi mantido para a aplicação, e elevado para 60s no banco. Quanto
o kube-news demora para drenar e se trata SIGTERM depende de carga real, que não
existe aqui. Mantido, e **declarado que foi mantido por falta de dado** — quem
observar o workload em uso decide.

## 10 · O componente se chama `nyx-api`, reaproveitando o nome do Ticket 02

Mesmo produto (`nyx`), mesmo componente, ambiente diferente. Os chamados do
Ticket 02 já usam `nyx-api` em `nyx-prod` e `nyx-stg`.

Manter o nome é o comportamento realista de um parque — e, para o Ticket 04, é
melhor de propósito: o mesmo componente passa a existir em três ambientes, em três
estados distintos (saudável em dev, `CrashLoopBackOff` em prod, Service sem
endpoint em stg). Filtro por namespace e busca por nome passam a ter o que
distinguir.

## 11 · O Secret não é versionado

`nyx-db`, com as chaves `username` e `password`, precisa existir em `nyx-dev`
antes do apply. Ele **não** está neste diretório, por decisão da skill: versionar
um Secret, mesmo com placeholder, cria o arquivo que alguém preenche com a
credencial real no dia em que tiver pressa.

```bash
kubectl create secret generic nyx-db -n nyx-dev \
  --from-literal=username=kubedevnews \
  --from-literal=password=<senha>
```

## 12 · Os cinco achados do Trivy, e por que nenhum é defeito

O conferidor da skill fecha em **8 objetos · 0 erro · 0 aviso · 0 exceção**. O
Trivy aponta cinco, e os cinco têm a **mesma forma** dos do `orion-prod`, que já
passaram por revisão no Ticket 01:

| Achado | Onde | Leitura |
|---|---|---|
| `KSV-0125` ×2 | os dois containers | acusa `registry.metacortex.io` de registry não confiável — **avalia a 3.7 ao contrário e acusa quem acertou** |
| `KSV-01010` | ConfigMap `nyx-api` | acusa `DB_PORT: "5432"` de conteúdo sensível — o falso positivo já catalogado |
| `KSV-0020`, `KSV-0021` | `nyx-postgres` | pedem UID e GID acima de 10000; o `70` é o dono dos arquivos do banco na imagem alpine. A 3.2 exige **não rodar como root**, e isso está atendido |

Que o conjunto novo produza exatamente a mesma assinatura de achados do conjunto
já revisado é resultado, não coincidência: mostra que os falsos positivos são da
ferramenta e do padrão, não do manifesto.

---

## Confirmação pela execução

O conjunto foi aplicado no `kind-metacortex-lab`. Duas decisões deixaram de ser
argumento e viraram observação.

**A decisão 3 se confirmou na primeira subida.** O `nyx-api` reiniciou duas vezes
antes de estabilizar, e o motivo é exatamente o previsto:

```
lastState.terminated: reason="Error", exitCode=1
log do container anterior:
  original: Error: connect ECONNREFUSED 10.96.197.236:5432
  Node.js v22.23.2
```

Sem o banco no ar, `seque.sync()` rejeita, ninguém trata, e o processo morre —
antes de a `startupProbe` ter o que checar. A `startupProbe` cobre banco **lento**;
não cobre banco **ausente**. A lacuna 2 do padrão não é teórica.

**A decisão 6 se sustentou.** `readOnlyRootFilesystem: true` sem nenhum `emptyDir`,
e o pod ficou `1/1 Running`. A hipótese de que o kube-news não escreve em disco
não foi derrubada pela execução.

**E a prontidão prova o alvo da readiness.** O pod só chega a `1/1` quando `/`
responde 200, e `/` faz `Post.findAll()`. Ou seja: o `Ready` deste pod significa
mesmo "o banco responde" — diferente do que significaria com a probe apontada
para `/ready`, que responderia 200 com o banco desligado.

```
NAME                       READY   STATUS    RESTARTS
nyx-api-77bb84897f-nlfcb   1/1     Running   2
nyx-postgres-0             1/1     Running   0

nyx-api      -> [['10.244.0.16']]
nyx-postgres -> [['10.244.0.18']]
```
