# Desafio 03 — O parque da Metacortex

Entrega dos quatro tickets. Cada pasta e autocontida: skill, insumos, codigo,
documentos de spec e evidencia de execucao real do ticket correspondente.

| Ticket | Entrega | Pasta |
|---|---|---|
| 01 | Skill do padrao de manifests | [`ticket-01-padrao-de-manifests/`](ticket-01-padrao-de-manifests/) |
| 02 | Skill de triagem no cluster | [`ticket-02-triagem-no-cluster/`](ticket-02-triagem-no-cluster/) |
| 03 | Ferramenta de inventario e drift de VM | [`ticket-03-inventario-de-vm/`](ticket-03-inventario-de-vm/) |
| 04 | Dashboard do cluster | [`ticket-04-dashboard-do-cluster/`](ticket-04-dashboard-do-cluster/) |

## Duas regras que atravessam a entrega

1. **Toda skill nasce de um fluxo que foi rodado**, nao de um chute. A origem de
   cada skill esta registrada na pasta do seu ticket.
2. **Nenhum dos dois projetos comeca pelo codigo.** O arco e
   `brainstorm -> documentos de spec -> ciclo do OpenSpec -> implementacao -> validacao`.

## Ambiente local

O repositorio e a raiz do projeto do agente. Na raiz existem, **fora do
versionamento**:

| Caminho | O que e |
|---|---|
| `.mcp.json` | symlink para `ticket-02-triagem-no-cluster/mcp/.mcp.json` |
| `.claude/skills/` | skills instaladas: as do fluxo de trabalho, as do OpenSpec e, quando existirem, as dos Tickets 01 e 02 |
| `.claude/commands/opsx/` | comandos do OpenSpec |
| `workloads/` | clones do kube-news, fake-shop e encontros-tech, so para leitura (commits registrados em `ticket-01-.../insumos/workloads.md`) |

### OpenSpec

Cada projeto tem a sua propria raiz OpenSpec, dentro da pasta do ticket, para
que os artefatos do ciclo fiquem junto do resto da entrega daquele ticket. O CLI
resolve a raiz a partir do diretorio corrente, entao os comandos do OpenSpec
precisam rodar de dentro da pasta do ticket:

```bash
cd desafio-03/ticket-03-inventario-de-vm   # ou ticket-04-dashboard-do-cluster
openspec list
```

Rodar da raiz do repositorio devolve "No OpenSpec root found" — e o
comportamento esperado, nao um erro de configuracao.

## Instalacao das skills

As skills sao versionadas em `ticket-01-.../skill/` e `ticket-02-.../skill/`.
Para usa-las, aponte o escopo de projeto do agente para elas:

```bash
mkdir -p .claude/skills
ln -s ../../desafio-03/ticket-01-padrao-de-manifests/skill .claude/skills/<nome-da-skill>
ln -s ../../desafio-03/ticket-02-triagem-no-cluster/skill  .claude/skills/<nome-da-skill>
```

`.claude/` e `.mcp.json` ficam na raiz do repositorio mas fora do versionamento:
sao estado de instalacao, nao artefato. A copia canonica do `.mcp.json`
usado no Ticket 02 esta em `ticket-02-triagem-no-cluster/mcp/`.
