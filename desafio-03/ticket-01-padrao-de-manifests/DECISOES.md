# Decisões dos manifests do fake-shop (orion-prod)

Dez decisões que o padrão não toma por você. Cada uma traz o que foi escolhido, o
porquê, e o que foi descartado — porque quem pegar esses manifests daqui a um ano
vai perguntar, e o commit não responde.

A leitura do projeto que sustenta várias delas está em
`execucoes/leitura-do-fake-shop.md`.

---

## 1. As probes, sem endpoint de saúde (regra 2.2)

**Escolhido:** liveness em `/metrics`, readiness em `/`.

O fake-shop não tem `/health` nem `/ready`, mas tem `/metrics`, registrado por
`GunicornPrometheusMetrics` e servido pela própria aplicação — e ele **não toca o
banco**. A raiz toca: `Product.query.all()`.

Isso dá exatamente a separação que a 2.2 cobra. Liveness responde "o processo está
servindo HTTP" sem o banco no caminho; readiness responde "posso receber tráfego",
e para uma loja isso inclui o banco.

**Descartado — as duas em `/`:** é o erro que a própria regra descreve. Banco lento
derruba a liveness, o container reinicia, e reinício não conserta banco.

**Descartado — as duas em `/metrics`:** sai mais barato e cega a readiness. Com o
banco fora, o pod continuaria recebendo tráfego para devolver erro.

**Custo aceito:** a readiness executa uma consulta ao catálogo a cada 15s. Com
catálogo grande isso pesa, e a mitigação é `periodSeconds`, não trocar o alvo.

## 2. A migração que roda no start (o padrão não cobre)

`src/entrypoint.sh` roda `python -m flask db upgrade` antes do gunicorn. Com a
regra 2.3 exigindo duas réplicas em prod, **duas migrações partem juntas**.

**Escolhido:** manter o entrypoint da imagem e cobrir a janela com `startupProbe`
(`failureThreshold: 60`, `periodSeconds: 5` — até cinco minutos), para que a
migração não seja confundida com aplicação morta.

**Descartado — initContainer com a migração:** parece mais limpo e não resolve o
problema real: o initContainer roda uma vez **por pod**, então duas réplicas
continuam migrando em paralelo. E exigiria sobrescrever o `command` do container
da aplicação, o que não é seguro aqui: **o fake-shop não versiona Dockerfile**, e
sem ele não dá para saber o `WORKDIR` da imagem. Trocar o entrypoint por um
palpite quebra o pod de um jeito que só aparece em execução.

**Descartado — Job de migração antes do rollout:** é a resposta correta em teoria e
exige ordenação entre o Job e o Deployment que nem o padrão nem o Construct
descrevem. Fora do escopo de um manifesto.

**Risco que fica declarado:** Alembic dentro do Postgres serializa pela linha de
`alembic_version`, então na prática a segunda migração normalmente vira no-op. Não
é garantia para DDL. E se o banco ainda não estiver pronto, o entrypoint falha e o
container sai — o pod reinicia até o banco subir, exibindo CrashLoop que não é
defeito de manifesto. **O padrão não tem regra sobre dependência que falha na
inicialização, e deveria ter.**

## 3. Os valores de requests e limits (regra 2.1)

**Escolhido:** `requests 100m/192Mi`, `limits 500m/384Mi`, **declarados como
estimativa**.

A regra da casa é limite de memória entre 1,5x e 2x o consumo em regime, e consumo
em regime não está no YAML nem no código. O que dá para saber lendo o projeto:
Flask 3 + SQLAlchemy 2 + gunicorn, um processo Python por worker. O ponto de
partida é o porte do stack, não uma medição.

**O que isso significa na prática:** este é o único número destes manifests que
precisa ser corrigido depois de observar o workload rodando. Está marcado como tal
no comentário do arquivo, e não como se fosse fato.

**Contraste que motiva o cuidado:** o Chamado 1 do Ticket 02 é um `limits.memory:
24Mi` aplicado sem olhar consumo. O erro não foi o número — foi tratá-lo como
decisão fechada.

## 4. `automountServiceAccountToken: false` (regra 3.4)

A regra é condicional: vale "quando não fala com a API". **Verificado, não
suposto** — `src/requirements.txt` não traz `kubernetes`, `openshift` nem
equivalente; as 22 dependências são Flask, SQLAlchemy, Alembic, gunicorn,
prometheus e utilitários. A aplicação não conversa com o apiserver.

Declarado em dois lugares: na ServiceAccount e no pod. O do pod é o que vale;
o da ServiceAccount protege quem esquecer no pod.

## 5. O que entra no seletor (regra 1.4)

**Escolhido:** só `app.kubernetes.io/name` e `app.kubernetes.io/instance`.

O seletor de um Deployment é imutável depois de criado. Colocar nele um rótulo cujo
valor muda com o tempo obriga a apagar e recriar o objeto no dia da troca — e
`managed-by` é o caso óbvio, porque o próprio padrão lista três valores possíveis
(`platform | argocd | helm`), ou seja, prevê a troca.

Os quatro rótulos continuam no template do pod, como a 1.3 exige. O que muda é
quais deles o seletor carrega.

## 6. Pod Security no Namespace (além do padrão)

O Namespace leva `pod-security.kubernetes.io/enforce: restricted`. Isso **não é
regra do padrão** — é o que faz o cluster recusar, na admissão, o pod que violaria
a 3.2.

Não é acrescentar regra: é aplicar uma que já existe. Regra escrita e regra
aplicada são coisas diferentes, e a segunda não depende de ninguém rodar a
varredura.

## 7. `seccompProfile`, que a regra 3.2 não lista

A 3.2 enumera cinco campos e `seccompProfile` não está entre eles. Sem ele, o pod é
**recusado na admissão** em namespace `restricted`, e o Trivy cobra por dois checks
(KSV-0030, KSV-0104).

Ou seja: seguir a 3.2 ao pé da letra produz manifesto que o cluster não aceita e que
nasce com dois achados abertos na varredura que a mesma Segurança & Compliance
opera. Incluído com `RuntimeDefault`. **É lacuna do padrão, e vale corrigir o
texto da regra.**

## 8. `terminationGracePeriodSeconds` (regra 2.6)

**Escolhido:** 30s na aplicação (o padrão), 60s no banco.

A 2.6 pede um valor compatível com o tempo de drenagem, e isso não se lê no código
com confiança — depende de carga real. Mantido no padrão para a aplicação, com o
registro de que é o valor não decidido, e elevado no Postgres, onde o desligamento
limpo notoriamente não cabe em 30s.

**Esta é a única regra do padrão que continua dependendo de operação, e não de
leitura.**

## 9. O banco com uma réplica em prod (exceção à regra 2.3)

A 2.3 exige duas réplicas em prod sem qualificar o tipo de carga. Para um banco de
escrita única a regra não tem como ser cumprida no espírito: a segunda réplica com
volume próprio não produz disponibilidade, produz um segundo banco divergindo do
primeiro.

A seção Exceções do padrão exige, para desvio de regra obrigatória, aprovação
escrita e prazo de validade. Os dois estão nas anotações do StatefulSet
(`metacortex.io/excecao-*`), no próprio objeto — não num PR que ninguém acha depois.

**Lacuna do padrão:** ele não tem vocabulário para carga com estado. A 1.3 nem
lista StatefulSet entre os objetos que carregam os quatro rótulos.

## 10. `runAsUser` diferente do exemplo (regra 3.2)

A aplicação usa 10001, o do exemplo. O Postgres usa **70**, que é o dono dos
arquivos do banco na imagem alpine — com 10001 ele não sobe.

O que a regra exige de fato é `runAsNonRoot: true`, e isso está atendido nos dois. O
número do exemplo é ilustração, não piso. O Trivy discorda e acusa `KSV-0020` e
`KSV-0021` ("runs with UID/GID <= 10000") no banco.

---

# O que o Trivy diz sobre estes manifests

De **18 achados** no manifesto barrado para **5** nestes. Os cinco são conhecidos e
nenhum é desvio do padrão:

| Achado | Ocorrências | O que é |
|---|---|---|
| KSV-0125 untrusted registry | 2 | acusa `registry.metacortex.io`, que é o que a regra 3.7 **exige** |
| KSV-0020 / KSV-0021 UID/GID ≤ 10000 | 2 | o UID 70 do Postgres, decisão 10 |
| KSV-01010 ConfigMap com conteúdo sensível | 1 | acusa **`DB_PORT: "5432"`** |

O último merece registro, porque fecha um argumento. Colocado ao lado da medição do
manifesto barrado, o resultado é este:

- a **senha real** do banco, em `env.value`, passa limpa pelo `trivy config` **e**
  pelo `trivy fs --scanners secret`;
- o **número da porta** do banco, num ConfigMap, é acusado como conteúdo sensível.

A heurística de segredo da ferramenta erra nos dois sentidos. É por isso que a
regra 3.3 — a única classificada como **proibida** entre as três de segurança —
fica com a skill, e não com a varredura.
