# Decisões dos manifests do encontros-tech (helio-prod)

Nove decisões que o padrão não toma sozinho. Cada uma traz o que foi escolhido, o
porquê, e o que foi descartado. O projeto não versiona manifesto nenhum e também
não versiona Dockerfile — o que precisou ser lido no código para decidir está
citado em cada seção, com arquivo e linha.

Commit lido do `workloads/encontros-tech`: `0f5bbad86f7e576cd9d64189c581ecee20f547df`
(branch `padrao`, conforme `insumos/workloads.md`). Onde a decisão dependeu de
histórico anterior a esse commit, isso está dito explicitamente — não é leitura do
estado atual do repositório, é leitura do `git log`.

---

## 1. Não existe imagem para subir — o Dockerfile foi removido no próprio commit lido

Este é o achado mais caro desta tarefa. `git log --oneline` em
`workloads/encontros-tech` mostra:

```
0f5bbad Removendo Docker
1c0388e feat: adiciona estrutura inicial do projeto Encontros Tech
```

O commit que o Ticket manda ler **é** o commit que apagou `Dockerfile`,
`docker-compose.yml` e `.dockerignore`. Isso só apareceu fazendo
`git fetch --unshallow` (o clone raso `--depth 1` documentado em
`insumos/workloads.md` esconde o commit anterior) e depois
`git diff 1c0388e 0f5bbad`.

**Consequência prática:** não existe, hoje, nenhuma definição de build no
repositório do cliente. `registry.metacortex.io/helio/encontros-tech:v1`, usado no
Deployment, é um **placeholder** — não há pipeline publicando essa imagem. Isso não
é um problema que manifesto resolve; é um bloqueio anterior ao deploy que precisa
voltar para o time do Helio ou para quem tirou o Dockerfile do ar.

**Por que ainda assim dá para escrever o manifesto:** o Dockerfile removido ficou
recuperável no histórico, e ele responde três perguntas que, de outra forma,
teriam ficado sem resposta:

```dockerfile
FROM python
WORKDIR /app
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

- porta 8000 (bate com o default de `src/core/settings.py`, `PORT=8000`);
- **4 workers do gunicorn por réplica**, não 1 — isso muda o dimensionamento de
  recursos (decisão 3);
- a imagem não define `USER`: roda como root por padrão (decisão 2).

**Descartado — sobrescrever `command`/`args` no Deployment com este `CMD`
recuperado:** o Dockerfile não existe mais no commit corrente, e uma imagem nova
pode ser publicada com outro `WORKDIR`, outro módulo de entrada ou outro número de
workers sem que ninguém atualize este manifesto. Sobrescrever a partir de um
histórico apagado é fixar um contrato que o próprio projeto já abandonou. O
Deployment não declara `command`: a imagem publicada é quem manda. O CMD
recuperado serviu só para dimensionar porta e recursos, não para virar campo do
YAML.

## 2. `runAsUser: 10001` é um palpite não verificado (regra 3.2)

O Dockerfile recuperado não tem `USER`: a imagem `FROM python` roda como root, e
os arquivos de `/app` são copiados por `COPY . .` rodando como root — dono
provavelmente UID 0, permissão default do `COPY`.

**Escolhido:** manter `runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`
— o mesmo padrão de exemplo usado no manifesto do ticket anterior (orion-prod),
por consistência do parque.

**Risco aceito e não verificável sem a imagem:** se os arquivos copiados não
tiverem permissão de leitura para "outros" (cenário incomum com `COPY` padrão, mas
não impossível), o processo sob UID 10001 falha ao importar `main.py` e o pod
crasha na inicialização — um sintoma que só aparece em execução, não na revisão do
YAML. **Recomendação:** validar este manifesto contra a imagem real em staging
antes do primeiro apply em produção; se falhar, o UID exigido pela imagem
substitui 10001 aqui (o que a regra exige de fato é `runAsNonRoot: true`, não o
número 10001 — mesmo raciocínio da decisão 10 do ticket orion-prod, onde o
Postgres exigiu UID 70).

## 3. Recursos dimensionados para 4 processos por réplica, não 1 (regra 2.1)

**Escolhido:** `requests: {cpu: 200m, memory: 384Mi}`,
`limits: {cpu: 1, memory: 640Mi}`, declarados como estimativa.

A regra da casa é limite de memória entre 1,5x e 2x o consumo em regime (640/384 ≈
1,67x, dentro da faixa), e consumo em regime não está no repositório — não tem como
estar, é medição de produção rodando. O que dá para saber lendo o projeto: o
Dockerfile removido usava `gunicorn -w 4`, ou seja, **quatro processos Python por
réplica** (Flask + SQLAlchemy + pydantic + prometheus_client cada), não um
processo único como um app FastAPI/uvicorn de worker só. Dimensionar para 1
processo aqui produziria OOMKill no primeiro pico de tráfego.

**O que isso significa na prática:** este é o número que mais precisa de correção
depois de observar o workload rodando — e também o que mais depende de uma
suposição (o `-w 4` de uma imagem que talvez nem exista mais do jeito que foi
lida). Está marcado como estimativa no comentário do Deployment, não como fato.

## 4. `automountServiceAccountToken: false` (regra 3.4)

**Verificado, não suposto** — `src/requirements.txt` lista 16 dependências (Flask,
gunicorn, prometheus-flask-exporter, Jinja2, psycopg2-binary, pydantic,
pydantic-settings, python-dotenv, PyYAML, SQLAlchemy, pytest, Werkzeug,
prometheus-client e afins). Nenhuma é cliente de Kubernetes. A aplicação não fala
com o apiserver.

Declarado em dois lugares — ServiceAccount e pod — o do pod é o que vale, o da
ServiceAccount protege quem esquecer no pod.

## 5. As probes, sem endpoint de saúde dedicado (regra 2.2)

**Escolhido:** liveness em `/metrics`, readiness em `/api/events/?limit=1`.

`src/routers/page_router.py` e `src/routers/api_router.py` não registram `/health`
nem `/ready`. Mas `src/main.py` registra `PrometheusMetrics(app)` sem `path`
customizado — o default da biblioteca (confirmado lendo
`prometheus_flask_exporter/__init__.py`, parâmetro `path='/metrics'`) é servido
pela própria aplicação e **não toca o banco**: o handler só lê o `CollectorRegistry`
em memória (ou os arquivos do multiprocess dir, quando configurado — nunca faz
`SELECT`).

Toda rota de página e de API deste app, por outro lado, abre sessão de banco:
`src/routers/page_router.py` (`list_events_page`, `event_detail_page`,
`edit_event_page`) e `src/routers/api_router.py` (`read_events`,
`get_event_by_token`) chamam `event_service` dentro de `with get_db() as db:`. Não
existe rota "leve" que exercite o Postgres sem ser uma consulta real.

**Escolhido para readiness:** `GET /api/events/?limit=1` — existe
(`api_router.read_events`), toca o banco (`event_service.get_events`), e o
parâmetro `limit` (já suportado pela função) reduz o custo da consulta a cada
checagem.

**Descartado — as duas em `/metrics`:** sai mais barato e cega a readiness. Sem o
banco no caminho, o pod continuaria recebendo tráfego que devolveria erro 500 em
toda página.

**Descartado — as duas em `/` ou em `/api/events/`:** é o erro que a própria regra
descreve. Banco lento derruba a liveness, o container reinicia, e reinício não
conserta banco.

**Custo aceito:** a readiness executa uma consulta ao Postgres a cada 15s por
réplica (2 réplicas × 4 workers cada não somam: só o worker que responde à
requisição de probe consulta). A mitigação é `periodSeconds`, não trocar o alvo.

## 6. `DATABASE_URL` inteira no Secret, não decomposta (regra 3.3)

`src/core/settings.py` lê uma única variável, `DATABASE_URL`, já com usuário e
senha embutidos na URL (`postgresql://usuario:senha@host:porta/banco`). Diferente
do fake-shop do ticket anterior (que lia `DB_HOST`, `DB_USER`, `DB_PASSWORD`,
`DB_NAME`, `DB_PORT` separados), o encontros-tech **não tem** como receber host e
porta por uma variável não sensível e senha por outra — é tudo uma string.

**Escolhido:** a `DATABASE_URL` completa vai para o Secret `helio-web-db`,
referenciada por `secretKeyRef` no Deployment. Nada de host/porta/nome do banco
sobra para o ConfigMap, porque não tem como extrair essas partes sem reescrever a
forma como a aplicação lê configuração — e reescrever código não é escopo deste
ticket.

**O valor no Secret é um placeholder** (`postgresql://CHANGEME:CHANGEME@CHANGEME:5432/CHANGEME`),
não uma credencial real. Isso está marcado em comentário no próprio arquivo. O
valor de produção precisa entrar pelo pipeline de segredo da casa antes do apply —
nunca commitado neste repositório de manifests.

## 7. Sem `metacortex.io/runbook` (regra 1.5)

O ticket anterior (orion-prod) incluiu essa anotação apontando para uma URL de
wiki. Aqui, não: este é o primeiro deploy do encontros-tech em produção — não pode
existir runbook operacional para um workload que ainda não rodou. Incluir uma URL
inventada seria pior do que omitir a anotação: um link morto no manifesto engana
quem for atrás dele às três da manhã. A anotação `metacortex.io/owner` continua
presente (é a que o script cobra com AVISO se faltar); `runbook` fica de fora até
existir de fato.

## 8. Pod Security no Namespace, além do padrão (mesma decisão do orion-prod)

O Namespace leva `pod-security.kubernetes.io/enforce: restricted`. Não é regra do
padrão — é o que faz o cluster recusar, na admissão, o pod que violaria a 3.2
(inclusive a falta do `seccompProfile`, que a 3.2 não lista mas que o Pod Security
`restricted` exige — lacuna conhecida da skill). Reaplicar aqui a mesma decisão
já tomada e registrada no ticket orion-prod, para manter o parque consistente.

## 9. `terminationGracePeriodSeconds: 30` mantido (regra 2.6)

Nenhum código do encontros-tech trata `SIGTERM` explicitamente (sem handler
customizado em `main.py`), e o Flask/gunicorn de request-resposta simples deste
app não sugere operação de longa duração que precise de janela maior — mas isso é
inferência sobre ausência de handler, não medição de drenagem real. Mantido em
30s, o padrão, com o registro de que é o único número deste manifesto que continua
dependendo de operação, não de leitura de código.

---

## O que o Trivy e o script acusaram, e por que fica assim

Saída completa em `validacao.txt`. Resultado: **0 erros e 0 avisos** no
`conferir-padrao.py` (7 objetos), e **2 achados MEDIUM** no `trivy config` — os
dois já descritos como falso positivo conhecido na própria skill:

| Achado | Onde | Por que é aceitável |
|---|---|---|
| KSV-0125 "untrusted registry" | `10-web-deployment.yaml`, imagem `registry.metacortex.io/...` | É a regra 3.7 avaliada ao contrário: o check do Trivy não conhece o registry do parque e marca qualquer domínio fora da lista dele como não confiável. Cumprir a 3.7 (usar `registry.metacortex.io`) **é o que produz** este achado. Documentado em `SKILL.md`, seção "A divisão do trabalho". |
| KSV-01010 "ConfigMap stores sensitive contents" em `LOG_LEVEL`/`PORT` | `02-configmap-web.yaml` | A heurística de segredo do Trivy erra para o lado da suspeita: nem nível de log nem número de porta são credencial. É o mesmo padrão do achado sobre `DB_PORT` registrado no `DECISOES.md` do ticket orion-prod — a regra 3.3 fica com o script/leitura humana exatamente por isso (ela erra nos dois sentidos, e o script tem heurística própria, mais estreita, que não dispara aqui: nem `LOG_LEVEL` nem `PORT` casam com `NOME_SENSIVEL`). Nenhuma correção necessária. |

Nenhum dos dois achados corresponde a exceção formal (`metacortex.io/excecao-*`)
porque nenhum dos dois é desvio de regra — são limite conhecido da ferramenta, não
do manifesto.

## Ordem dos arquivos

```
00-namespace.yaml          namespace
01-serviceaccount-web.yaml contas
02-configmap-web.yaml      configuração (não sensível)
03-secret-web-db.yaml      configuração (sensível)
10-web-deployment.yaml     workload
11-web-pdb.yaml            resiliência do workload
12-web-service.yaml        exposição
```

`kubectl apply -f desafio-03/ticket-01-padrao-de-manifests/execucoes/manifests-helio-prod/`
aplica na ordem correta sem ajuda — exceto pela imagem placeholder (decisão 1) e
pelo Secret placeholder (decisão 6), que bloqueiam deliberadamente um apply real
até alguém substituir os dois valores.
