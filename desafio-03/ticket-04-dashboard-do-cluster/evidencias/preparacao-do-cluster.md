# Preparação do cluster para o Ticket 04

O enunciado exige workload de verdade na tela: pelo menos dois dos três projetos,
em namespaces separados, com os manifests que a skill do Ticket 01 gerou. Este
documento registra como o cluster chegou ao estado que o dashboard vai ler, e os
dois achados que a subida produziu.

Inventário cru em `cluster-preparado.txt`.

## O que subiu

| Namespace | Projeto | Objetos | Estado |
|---|---|---|---|
| `nyx-dev` | kube-news | Deployment `nyx-api` (1 réplica) + StatefulSet `nyx-postgres` | saudável |
| `orion-prod` | fake-shop | Deployment `orion-web` (2 réplicas + PDB) + StatefulSet `orion-postgres` | saudável |

Os três namespaces do Ticket 02 continuam no ar e **não foram tocados** — são o
lado patológico da amostra.

## A amostra que o dashboard vai ver

```
nyx-dev      deployment/nyx-api          1/1     saudavel, replica unica
nyx-prod     deployment/nyx-api          0/2     CrashLoopBackOff, OOMKilled
nyx-stg      deployment/nyx-api          2/2     pods ok, Service sem endpoint
orion-prod   deployment/orion-web        2/2     saudavel, duas replicas + PDB
orion-stg    deployment/orion-web        0/3     ImagePullBackOff
nyx-dev      statefulset/nyx-postgres    1/1
orion-prod   statefulset/orion-postgres  1/1
```

Três coisas que esta amostra destrava e a anterior não tinha:

1. **Existem StatefulSets.** Antes não havia nenhum no cluster — os três chamados
   do Ticket 02 usam Deployment até para o postgres. A D4 inclui StatefulSet na
   primeira fatia, e agora há resposta real da API para especificar em cima.
2. **Existe workload saudável.** A D7 ordena por anormalidade; sem o lado normal,
   a ordenação não teria contra o que se medir.
3. **`nyx-api` existe em três ambientes, em três estados diferentes.** Filtro por
   namespace e busca por nome passam a ter o que distinguir de verdade.

## Como as imagens entraram sem registry

A regra 3.7 exige `registry.metacortex.io`, que não existe. A tag local resolve,
porque o kubelet não vai à rede quando a tag não é `:latest`:

```bash
docker tag postgres:16-alpine registry.metacortex.io/nyx/postgres:16-alpine
kind load docker-image registry.metacortex.io/nyx/postgres:16-alpine --name metacortex-lab
```

`registry.metacortex.io/nyx/api:2.9.1` já estava no nó, carregada pelo Ticket 02.

Os Secrets `nyx-db` e `orion-db` são criados por linha de comando, não versionados
— é a decisão da skill do Ticket 01 sobre não deixar esqueleto de Secret no Git.

## Achado 1 — o fake-shop também está sem Dockerfile

O `estado-da-entrega.md` dizia para usar kube-news e fake-shop porque o
`encontros-tech` teve o Dockerfile removido. **O fake-shop também teve.** O clone
está em `a3fa74f`, cujo título é literalmente `Delete src/Dockerfile`, e o clone é
raso — só esse commit.

Isso não apareceu no Ticket 01 porque lá o projeto foi **lido**, nunca construído.

Resolvido recuperando o histórico e construindo sem tocar no clone:

```bash
git fetch --unshallow
git show 15f8d9d:src/Dockerfile | docker build -f- -t registry.metacortex.io/orion/web:v14 src/
```

O Dockerfile recuperado não declara `USER`, então a imagem rodaria como root. O
`runAsUser: 10001` do manifesto cobre isso — a regra 3.2 é cumprida pelo
manifesto, não pela imagem.

## Achado 2 — a lacuna 2 do padrão tem duas formas, e a segunda é pior

A skill do Ticket 01 registra como lacuna conhecida que **nada no padrão trata de
dependência que falha na inicialização**. Os dois projetos exibiram a lacuna, de
jeitos opostos.

**kube-news — falha ruidosa, que se cura sozinha.**

```
lastState.terminated: reason="Error", exitCode=1
  original: Error: connect ECONNREFUSED 10.96.197.236:5432
restartCount: 2, depois estabilizou
```

`seque.sync()` rejeita, ninguém trata, o processo morre. O Kubernetes reinicia, e
na terceira tentativa o banco está no ar. Ruim de olhar, mas converge.

**fake-shop — falha silenciosa, que não se cura nunca.**

O `src/entrypoint.sh` é:

```bash
#!/bin/bash
python -m flask db upgrade
python -m gunicorn --bind 0.0.0.0:5000 index:app
```

**Sem `set -e`.** Com o banco ainda subindo, o `flask db upgrade` falha, o script
continua, e o gunicorn sobe contra um banco sem tabela. O resultado:

```
orion-web-774b495bc5-8g4d9   0/1   Running   restarts: 0   5m
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable)
  relation "products" does not exist
```

Pod `Running`, zero reinícios, zero eventos de falha, e **nunca fica pronto** —
porque nada reexecuta a migração. Só a readiness denuncia, e ela denuncia porque o
alvo escolhido no Ticket 01 foi `/`, que toca o banco. Com a readiness apontada
para `/metrics`, este pod estaria marcado como pronto e serviria erro.

Resolvido com `kubectl rollout restart` depois do banco pronto. Fica registrado
porque é material direto para o Ticket 04: **é o caso em que `phase: Running` e
`restartCount: 0` não dizem nada, e só o par prontos-sobre-desejados denuncia.**
Um dashboard que mostrasse só fase e reinícios pintaria este pod de saudável.
