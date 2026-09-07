# Grupo 10 — validação contra o cluster real

Feita por quem **não** escreveu spec nem código deste ticket — só leu os artefatos
e rodou contra `kind-metacortex-lab` (servidor v1.31.0). Nenhum objeto do cluster
foi criado, alterado ou apagado; a única escrita em disco foi um kubeconfig e um
certificado **fora do repositório**, em `/tmp/painel-cluster-validacao/`.

Ponto de partida conferido antes de qualquer critério:

```bash
./.venv/bin/pytest -q
# 85 passed in 7.05s   -> grupo10-suite-baseline.stdout.txt / .rc.txt
```

## Metodologia

A tela é uma aplicação Textual. Em vez de operar um terminal interativo (que não
versiona nem diffa), toda captura usou o mesmo mecanismo que `tests/test_tela.py`
já usa para as próprias asserções: `App.run_test()` (modo headless do Textual) com
uma **`Sessao` real**, produzida por `painel_cluster.cliente.conectar()` — ou seja,
toda leitura passou pelo código de produção inalterado, contra a API de verdade.
Isso não é simulação: é a mesma técnica que valida a suíte, aplicada ao cluster
real em vez de fixtures.

`capturar_texto()` reaproveita a lógica documentada em `tests/test_tela.py`
(`App.export_screenshot()`, trocando a exportação SVG por
`rich.console.Console.export_text()`), porque **saída de tela em texto versiona e
diffa**, e captura de imagem não.

Dois scripts, gravados aqui por transparência e reprodutibilidade — não fazem
parte do pacote `painel_cluster`, não são importados por ele, e não alteram nada
no cluster:

- `script-validar-criterios-de-aceite.py` — sobe `PainelClusterApp` com uma sessão
  real, navega (setas, `/`, `Esc`, `r`, `q`) e captura texto. Usado nos critérios
  1, 2, 3, 5, 6, 7 (tela), 8 (tela) e 9.
- `script-validar-codigo-de-saida.py` — roda o **binário instalado de verdade**
  (`.venv/bin/painel-cluster`) dentro de um pseudo-terminal (`pty` da stdlib),
  envia `q` e lê o código de saída do processo real. Usado nos critérios 7 e 8
  para confirmar o código de saída do processo, não só o estado da tela.

### RBAC e credenciais usadas

Os dois `ServiceAccount` já estavam aplicados (`rbac/platform-ro.yaml`,
`rbac/platform-ro-sem-events.yaml`). Nenhum objeto do cluster foi criado por esta
validação — só tokens de curta duração e um kubeconfig de teste, tudo em
`/tmp/painel-cluster-validacao/`, nunca em `~/.kube/config`:

```bash
TMP=/tmp/painel-cluster-validacao
cp ~/.kube/config "$TMP/kubeconfig"          # copia, nunca o arquivo real
TOKEN=$(kubectl create token platform-ro -n kube-system --duration=3h)
kubectl --kubeconfig="$TMP/kubeconfig" config set-credentials platform-ro --token="$TOKEN"
kubectl --kubeconfig="$TMP/kubeconfig" config set-context platform-ro \
  --cluster=kind-metacortex-lab --user=platform-ro
# mesma receita para platform-ro-sem-events
```

O certificado de cliente vencido foi gerado exatamente pelo cabeçalho de
`verificacoes/verificar-hipotese-d2.py`, também em `/tmp/painel-cluster-validacao/`
— a chave da CA (`ca.key`) nunca saiu de `/tmp` e não foi commitada:

```bash
docker cp metacortex-lab-control-plane:/etc/kubernetes/pki/ca.crt /tmp/painel-cluster-validacao/
docker cp metacortex-lab-control-plane:/etc/kubernetes/pki/ca.key /tmp/painel-cluster-validacao/
openssl genrsa -out cliente-vencido.key 2048
openssl req -new -key cliente-vencido.key -out cliente-vencido.csr -subj "/CN=platform-ro/O=metacortex"
openssl ca -batch -config ca.cnf -keyfile ca.key -cert ca.crt \
    -in cliente-vencido.csr -out cliente-vencido.crt \
    -startdate 200101000000Z -enddate 200102000000Z -notext
```

Reconferido contra `verificar-hipotese-d2.py` antes de usar em qualquer critério —
o certificado ainda produz `UnauthorizedException`, `.status = 401` (ver
`criterio7-hipotese-d2-rerun.stdout.txt`), reproduzindo exatamente o que
`hipotese-d2-excecoes.md` já tinha medido.

Ao final da validação, `~/.kube/config` foi conferido e está **intocado** —
contexto corrente ainda `kind-metacortex-lab`, sem os contextos de teste. Nenhum
contexto precisou ser restaurado porque nenhum foi trocado no arquivo real; toda
a manipulação de contexto aconteceu só na cópia em `/tmp`.

---

## Critério 1 — Retrato do namespace saudável — **FALHOU** (parcialmente)

> `nyx-dev`: Deployment `nyx-api` em `1/1`, StatefulSet `nyx-postgres` em `1/1`,
> os dois Services com endereço pronto, e **nenhum objeto marcado como anormal**.

Comando:
```bash
kubectl --kubeconfig=/tmp/painel-cluster-validacao/kubeconfig config use-context kind-metacortex-lab
./.venv/bin/python script-validar-criterios-de-aceite.py dev /tmp/painel-cluster-validacao/kubeconfig
```
Saída: `criterio1-nyx-dev.stdout.txt`.

Três das quatro partes passam:

| Parte do critério | Medido |
|---|---|
| Deployment `nyx-api` `1/1` | `Deployment nyx-api 1/1 Available=True —` |
| StatefulSet `nyx-postgres` `1/1` | `StatefulSet nyx-postgres 1/1 — —` |
| dois Services com endereço | `nyx-api 1 prontos`, `nyx-postgres 1 prontos` |

A quarta não:

```
nyx-api-77bb84897f-nlfcb   Running  1/1  2  —  ✓  8h50m  ⚠ reinícios: 2
```

O pod `nyx-api` do `nyx-dev` tem `restartCount: 2` e a tela marca a linha como
anormal (`⚠ reinícios: 2`), porque o critério de peso 3 de `01-comportamento.md`
é literalmente "reinícios maiores que zero", sem janela de tempo nem
prescrição — ao contrário dos eventos, que têm janela de 1h, o critério de
reinícios não decai. **Isso não é bug do código**: é exatamente o que a spec
manda desenhar, e `tests/test_contencao.py`/`test_modelo.py` não têm como pegar
isso porque é um fato do cluster, não do código.

O fato em si já estava documentado **antes** de `01-comportamento.md` ser escrito:
`evidencias/preparacao-do-cluster.md` (do mesmo commit `56008ac`, anterior a
`3a5b830` que introduziu `01-comportamento.md`) registra, na seção "Achado 2",
que o `nyx-api` do `nyx-dev` (kube-news) reiniciou duas vezes por
`ECONNREFUSED` contra o Postgres ainda subindo, e "se cura sozinha" — a mesma
`restartCount: 2` medida agora, 8h50m depois, imutável enquanto o pod não for
recriado.

**Veredito:** o critério de aceite 1, como está escrito, contradiz um fato do
próprio fixture que o ticket criou para representá-lo. A tela está correta pelo
padrão que a spec define; a spec descreveu um "namespace saudável" sem reconciliar
com o estado que ela mesma já sabia que o `nyx-dev` teria. Caixa **não marcada**
em `tasks.md` — a verificação rodou e não confirma "nenhum objeto anormal".

---

## Critério 2 — Retrato dos três chamados — **PASSOU**

> `nyx-prod` mostra `0/2` com `CrashLoopBackOff` e `OOMKilled`; `orion-stg` mostra
> `0/3` sem `readyReplicas`; `nyx-stg` mostra pods `2/2` e o Service `nyx-api`
> **sem endereço**.

Comandos e saídas:
```bash
./.venv/bin/python script-validar-criterios-de-aceite.py prod ...kubeconfig   # criterio2-nyx-prod.stdout.txt
./.venv/bin/python script-validar-criterios-de-aceite.py orion-stg ...kubeconfig  # criterio2-orion-stg.stdout.txt
./.venv/bin/python script-validar-criterios-de-aceite.py stg ...kubeconfig    # criterio2-nyx-stg.stdout.txt
```

Medido:

```
nyx-prod:   nyx-api-79c5f4d8d7-2w5kd  CrashLoopBackOff  0/1  235  CrashLoopBackOff (causa: OOMKilled)
            Deployment nyx-api  0/2  Available=False  ⚠ 0/2 prontos
orion-stg:  Deployment orion-web  0/3  Available=False  ⚠ 0/3 prontos
nyx-stg:    nyx-api-5cd5cdbf9d-*  Running 1/1 (x2, dois pods = "2/2" agregado)
            Service nyx-api  ⚠ sem endereço
```

Confirmado por fora, direto na API, que `orion-stg`/`orion-web` realmente não tem
`readyReplicas` na resposta (a tela nunca precisa mostrar a ausência da chave —
só o resultado normalizado — então isto foi checado à parte):

```bash
kubectl get --raw "/apis/apps/v1/namespaces/orion-stg/deployments/orion-web" \
  | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)['status'].keys()))"
# ['conditions', 'observedGeneration', 'replicas', 'unavailableReplicas', 'updatedReplicas']
```

**Nota:** o estado atual do pod em `orion-stg` é `ImagePullBackOff`, não a falha de
migração (`0/1` sem evento) que `docs/preparacao-do-cluster.md` descreveu. A
imagem `fabricioveronez/fake-shop:v1.14.2` (o chamado original do Ticket 02, não
o workload do Ticket 04) não está mais disponível no nó — provável efeito de
reinício do control-plane do `kind` desde a captura original. Isso **não afeta**
o critério 2, que só exige `0/3` sem `readyReplicas` — ambos continuam
verdadeiros, e é o motivo de estar `0/3`, não o valor, que mudou.

Caixa **marcada**.

---

## Critério 3 — Réplica única ao lado de duas — **PASSOU**

> `nyx-dev` em `1/1` e `orion-prod` em `2/2` aparecem com o mesmo formato de
> coluna, sem que o denominador diferente mude a leitura.

Comando: `./.venv/bin/python script-validar-criterios-de-aceite.py orion-prod ...kubeconfig`
Saída: `criterio3-orion-prod.stdout.txt` (comparar com `criterio1-nyx-dev.stdout.txt`).

```
nyx-dev:     Deployment nyx-api    1/1   Available=True   —
orion-prod:  Deployment orion-web  2/2   Available=True   —
             StatefulSet orion-postgres  1/1  —  —
```

Mesmo formato de coluna (`N/M`) nos dois, e `orion-prod` está limpo (zero
reinícios nos três pods, nenhum critério de anormalidade) — o que também mostra
que o achado do Critério 1 é específico do `nyx-dev`, não um problema geral da
coluna. Caixa **marcada**.

---

## Critério 4 — StatefulSet sem condição — **PASSOU**

> `nyx-postgres` aparece com prontos sobre desejados e sem coluna de condição, e
> isso não é exibido como problema.

Já capturado em `criterio1-nyx-dev.stdout.txt` e reforçado em
`criterio3-orion-prod.stdout.txt`:

```
StatefulSet  nyx-postgres    1/1  —  —
StatefulSet  orion-postgres  1/1  —  —
```

Coluna "condição" mostra `—` (ausência, não falha) e coluna "por quê" também `—`
(nenhum critério de anormalidade aplicado). Confirmado por fora que a chave
`conditions` realmente não existe na resposta:

```bash
kubectl get --raw "/apis/apps/v1/namespaces/nyx-dev/statefulsets/nyx-postgres" \
  | python3 -c "import json,sys; print(sorted(json.load(sys.stdin)['status'].keys()))"
# ['availableReplicas', 'collisionCount', 'currentReplicas', 'currentRevision',
#  'observedGeneration', 'readyReplicas', 'replicas', 'updateRevision', 'updatedReplicas']
# ('conditions' ausente)
```

Caixa **marcada**.

---

## Critério 5 — Ausência de sonda — **PASSOU**

> `orion-web` do `orion-stg` aparece com `readiness: —`; `nyx-api` do `nyx-dev`
> aparece com `readiness: ✓`.

(A coluna na tela chama-se "sonda", não "readiness" — mesmo conceito, nome
diferente do texto do critério; ver `docs/01-comportamento.md`.)

```
orion-stg (criterio2-orion-stg.stdout.txt): orion-web-*   sonda = —
nyx-dev   (criterio1-nyx-dev.stdout.txt):    nyx-api-*     sonda = ✓
```

Confirmado por fora:
```bash
kubectl -n orion-stg get deploy orion-web -o jsonpath='{.spec.template.spec.containers[0].readinessProbe}'
# (vazio)
kubectl -n nyx-dev get deploy nyx-api -o jsonpath='{.spec.template.spec.containers[0].readinessProbe}'
# {"failureThreshold":3,"httpGet":{"path":"/","port":"http","scheme":"HTTP"}, ...}
```
Caixa **marcada**.

---

## Critério 6 — Permissão parcial — **PASSOU**

> Com `platform-ro-sem-events`, o painel de eventos diz "sem permissão" e pods,
> controladores e services continuam preenchidos.

Comando:
```bash
kubectl --kubeconfig=/tmp/painel-cluster-validacao/kubeconfig config use-context platform-ro-sem-events
./.venv/bin/python script-validar-criterios-de-aceite.py sem-events ...kubeconfig
```
Saída: `criterio6-platform-ro-sem-events.stdout.txt`.

```
contexto: platform-ro-sem-events
Pods:          nyx-api-79c5f4d8d7-2w5kd  CrashLoopBackOff ...  (preenchido)
Controladores: Deployment nyx-api 0/2 ...                       (preenchido)
Services:      nyx-api  0 de 2 prontos                          (preenchido)
Eventos:       sem permissão para ler eventos                   (negado, isolado)
```
Caixa **marcada**.

---

## Critério 7 — Credencial recusada — **PASSOU**

> Com certificado vencido, a tela mostra o estado de credencial, o contexto e o
> servidor, sem traceback.

Duas verificações independentes:

**(a) Tela, via harness headless**, comando:
```bash
kubectl --kubeconfig=/tmp/painel-cluster-validacao/kubeconfig config use-context cert-vencido
./.venv/bin/python script-validar-criterios-de-aceite.py cert-vencido ...kubeconfig
```
Saída: `criterio7-cert-vencido-tela.stdout.txt`.
```
contexto: cert-vencido    servidor: https://127.0.0.1:34969
⚠ TELA EM ESTADO DE INDISPONIBILIDADE — credencial recusada    (...)
```
Zero ocorrências de `Traceback` (`grep -c Traceback` = 0).

**(b) Binário instalado de verdade, via pty**, comando:
```bash
./.venv/bin/painel-cluster   # KUBECONFIG apontado para o contexto cert-vencido
# ... espera, envia 'q' ...
```
(rodado por `script-validar-codigo-de-saida.py`, saída em
`criterio7-cert-vencido-binario-real.stdout.txt`):
```
codigo de saida: 0
contem 'Traceback'? False
```
Contexto e servidor visíveis na captura raw ANSI (`⚠ TELA EM ESTADO DE
INDISPONIBILIDADE — credencial recusada`).

Reconfirmado que o certificado ainda produz 401 (`UnauthorizedException`),
igual ao que `hipotese-d2-excecoes.md` mediu (`criterio7-hipotese-d2-rerun.stdout.txt`).

**Observação, não é falha:** o texto do painel individual (não o banner do
topo) usa o prefixo genérico "cluster não respondeu — credencial recusada" —
herdado de `texto_estado_envelope()`, que prefixa todo estado `indisponivel`
da mesma forma, mesmo quando a causa é credencial e não transporte. O banner de
topo (`⚠ TELA EM ESTADO DE INDISPONIBILIDADE — credencial recusada`) é quem
carrega a distinção exigida pelo critério, e o critério só exige que "a tela
mostra o estado de credencial" — o que ela mostra, ali. Fica registrado porque
pode confundir quem lê só o painel individual.

Caixa **marcada**.

---

## Critério 8 — Cluster inalcançável — **PASSOU**

> Com o apiserver inacessível, a tela mostra o estado de indisponível e o
> endereço tentado, e não sai com código diferente de zero.

**(a) Tela**, contexto apontando para `https://127.0.0.1:1` (porta fechada em
loopback — recusa de conexão real, sem precisar derrubar o cluster de verdade,
que é read-only por definição e não deve ser tocado):
```bash
kubectl --kubeconfig=/tmp/painel-cluster-validacao/kubeconfig config use-context endereco-morto
./.venv/bin/python script-validar-criterios-de-aceite.py endereco-morto ...kubeconfig
```
Saída: `criterio8-endereco-morto-tela.stdout.txt`:
```
contexto: endereco-morto    servidor: https://127.0.0.1:1
⚠ TELA EM ESTADO DE INDISPONIBILIDADE — cluster nao respondeu em https://127.0.0.1:1
```

**(b) Código de saída, no binário real, via pty** —
`criterio8-endereco-morto-binario-real.stdout.txt`:
```
codigo de saida: 0
contem 'Traceback'? False
```
A idade do dado avança sozinha no terminal real ("...atualizado há 1s", "...2s",
"...3s", "...4s") até o `q` ser enviado — prova de que a aplicação **continua
tentando**, como o invariante exige, em vez de travar ou sair.

Caixa **marcada**.

---

## Critério 9 — Busca e filtro — **PASSOU**

> Com `nyx-prod` selecionado e `postgres` digitado, a tela mostra só os objetos
> cujo nome contém `postgres`.

Comando: `./.venv/bin/python script-validar-criterios-de-aceite.py busca ...kubeconfig`
Saída: `criterio9-busca-postgres.stdout.txt` — três capturas (antes, durante,
depois do `Esc`).

Antes: `nyx-api-*` (CrashLoopBackOff) e `nyx-postgres-*` visíveis nos quatro
painéis. Depois de `/postgres`: só `nyx-postgres-5877b89bf8-5g58h` (pod),
`Deployment nyx-postgres` e `Service nyx-postgres` — `nyx-api` desaparece dos
quatro painéis, inclusive Controladores e Services. Depois do `Esc`:
`app.busca == ''` e `orion-web`/`nyx-api` voltam a aparecer.

Caixa **marcada**.

---

## Critério 10 — Só leitura, provada por fora — **NÃO VERIFICÁVEL como escrito**

> Rodando sob `platform-ro`, a sessão inteira de uso não produz nenhuma negativa
> de RBAC — **porque a aplicação nunca tenta escrever**.

A tarefa 10.10 manda checar isso **no registro de auditoria do apiserver**. Esse
registro não existe neste ambiente:

```bash
kubectl get pod kube-apiserver-metacortex-lab-control-plane -n kube-system \
  -o jsonpath='{.spec.containers[0].command}' | grep -i audit
# nenhuma saida — nenhuma flag --audit-log-* declarada
```
(`criterio10-apiserver-sem-auditoria.txt`; conferido também que não existe
`/var/log/kubernetes/audit*.log` no container e que a palavra "audit" não
aparece nos logs do apiserver.)

Como o aviso do pedido antecipava: **não vou inventar o resultado, nem habilitar
auditoria no cluster** (seria escrita em configuração de infraestrutura, fora do
escopo de só-leitura desta validação, e alteraria o cluster que devo só ler).

### O que rodei em vez disso, e por quê é uma prova equivalente

Duas verificações que juntas sustentam a mesma afirmação por outro caminho —
"nenhuma negativa de RBAC porque nenhuma escrita é tentada":

**(1) Sessão completa sob `platform-ro`, rodando de verdade.** Cinco trocas de
namespace, busca, `Esc`, `r`, `q` — nenhuma exceção, nenhum erro interno:
```bash
kubectl --kubeconfig=/tmp/painel-cluster-validacao/kubeconfig config use-context platform-ro
./.venv/bin/python script-validar-criterios-de-aceite.py platform-ro-sessao ...kubeconfig
```
Saída: `criterio10-sessao-platform-ro.stdout.txt` — os cinco namespaces lidos, a
busca aplicada, o `r` executado e "sessao encerrada por 'q', sem excecao". Isto
prova que a sessão **funciona inteira** sob `platform-ro` sem tropeçar em nada —
mas sozinho não prova ausência de tentativa de escrita (poderia ter tentado e
sido negada em silêncio, sem que a UI reagisse de forma visível).

**(2) Prova de que escrita nunca é tentada, por dois ângulos independentes:**

- **Estático, no código**: `tests/test_contencao.py` (grupo 8, já parte da
  suíte) falha se qualquer verbo de escrita aparecer em `src/`, ou se qualquer
  módulo fora de `cliente.py` importar o cliente do Kubernetes. Rodado de novo,
  isolado, agora:
  ```bash
  ./.venv/bin/pytest tests/test_contencao.py -v
  # 3 passed
  ```
  (não gravado em arquivo à parte — está dentro da suíte de 85, já coberta por
  `grupo10-suite-baseline.stdout.txt`).

- **RBAC do próprio cluster, testado por fora**: se o código tentasse escrever
  apesar do que o teste estático garante, o cluster recusaria — e isso é
  verificável sem habilitar nada:
  ```bash
  for verbo in create update patch delete deletecollection watch; do
    for recurso in pods deployments statefulsets services events namespaces endpointslices secrets; do
      kubectl auth can-i "$verbo" "$recurso" \
        --as=system:serviceaccount:kube-system:platform-ro -A
    done
  done
  ```
  Saída completa em `criterio10-auth-can-i.txt`: **48 combinações de verbo de
  escrita/`watch` × recurso, todas `no`** — incluindo `secrets`, que nem está na
  `ClusterRole`. Os únicos `yes` são `get`/`list` nos sete tipos.

**Conclusão sobre o critério 10:** a garantia de só-leitura está provada, mas por
uma composição diferente da que a tarefa 10.10 pede ao pé da letra (registro de
auditoria). O que é logicamente equivalente ao que o registro de auditoria
proveria é: (a) nenhuma escrita existe no código-fonte que roda [prova estática],
(b) se existisse, o cluster a recusaria [prova de RBAC], e (c) a sessão completa
sob `platform-ro` rodou sem incidente [prova funcional]. O registro de auditoria
teria provado só o item (c) por um caminho diferente — nenhuma tentativa de
escrita *observada pelo apiserver* — e é estritamente mais fraco do que (a)+(b)
juntos, que provam que a tentativa **não pode ter acontecido**, não só que não
foi vista.

Caixa **não marcada** — a tarefa, como redigida ("no registro de auditoria"), não
é verificável neste `kind`. As três provas alternativas rodaram e estão
registradas; quem revisar decide se aceita a composição como equivalente.

---

## Resumo — o que ficou marcado em `tasks.md`

| Tarefa | Critério | Resultado | Caixa |
|---|---|---|---|
| 10.1 | 1 | Falhou (reinícios) | não marcada |
| 10.2 | 2 | Passou | marcada |
| 10.3 | 3 | Passou | marcada |
| 10.4 | 4 | Passou | marcada |
| 10.5 | 5 | Passou | marcada |
| 10.6 | 6 | Passou | marcada |
| 10.7 | 7 | Passou | marcada |
| 10.8 | 8 | Passou | marcada |
| 10.9 | 9 | Passou | marcada |
| 10.10 | 10 | Não verificável como escrito | não marcada |
| 10.11 | evidências | Feito (este arquivo + os `.stdout.txt`/`.txt` ao lado) | marcada |

## O que a spec/tarefas não respondiam, e o que decidi

1. **Como capturar a tela contra o cluster real, sem terminal interativo.**
   Nenhum artefato do grupo 10 diz como. Reaproveitei a técnica de
   `tests/test_tela.py` (`App.run_test` + `capturar_texto()`), trocando as
   `Leituras` fabricadas por uma `Sessao` real de `cliente.conectar()`. Decisão:
   é a mesma camada de teste que o próprio projeto já confia, aplicada ao cluster
   de verdade em vez de fixture — não é uma técnica nova, é a existente com a
   fonte de dados trocada.
2. **Como provar o código de saída do critério 8, e não só o estado da tela.**
   O harness headless não passa pelo `SystemExit` real de `cli.py`. Escrevi um
   segundo script que roda o binário instalado dentro de um `pty`, envia `q` e lê
   o `returncode` do processo de verdade.
3. **Onde gerar o certificado vencido e os contextos de RBAC**, sem tocar no
   kubeconfig real. Decisão: cópia do kubeconfig em `/tmp`, nunca
   `~/.kube/config`; contextos adicionados só na cópia; `endereco-morto` como
   cluster novo (`https://127.0.0.1:1`) para não precisar desligar o cluster de
   verdade, que este ticket só pode ler.
4. **Tarefa 10.10 não verificável como escrita** — coberto na seção do critério
   10, com a alternativa proposta e rodada.

## Reprodutibilidade

Todos os comandos acima assumem `cwd` = raiz deste ticket
(`desafio-03/ticket-04-dashboard-do-cluster/`) e um `/tmp/painel-cluster-validacao/`
já preparado (kubeconfig de teste + certificado vencido) pelos passos da seção
"RBAC e credenciais usadas". Os dois scripts em `evidencias/script-*.py` esperam
`kubeconfig` como segundo argumento e o caminho absoluto do repositório embutido
(ajustar `REPO = Path(...)` no topo de `script-validar-criterios-de-aceite.py` se
rodar em outra máquina).
