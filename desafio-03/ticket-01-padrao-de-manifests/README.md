# Ticket 01 — O padrão do Seraph que ninguém abre

O padrão de manifests da Metacortex existe, está escrito, e é justamente esse o problema:
uma página de wiki é boa para guardar decisão e péssima para conferir regra a regra no meio
de uma tarefa. Este ticket a transforma em procedimento.

## A lista de entrega, item a item

| O que o ticket pede | Onde está |
|---|---|
| **A skill completa** (corpo, script e arquivo de apoio) | [`skill/`](skill/) — `SKILL.md`, `scripts/conferir-padrao.py`, `references/` |
| **A origem dela** (de qual fluxo nasceu, por qual caminho, com qual ferramenta) | [`origem-da-skill.md`](origem-da-skill.md) |
| **A saída real das duas execuções** | [`execucoes/`](execucoes/) — manifests gerados e a conferência do manifesto barrado |
| **A curadoria** (onde passa a linha, o que não foi empacotado, quais permissões a skill pede) | [`curadoria-das-regras.md`](curadoria-das-regras.md) e a seção final do `SKILL.md` |

## O que fundamenta a curadoria

A divisão entre Trivy, script e instrução **foi medida, não suposta** — o ticket exige isso
com essas palavras. Em [`baseline-trivy/`](baseline-trivy/) está a saída bruta e a leitura:

```
trivy config no manifesto barrado  →  18 achados
mapeados de volta ao padrão        →  4 das 19 regras
trivy fs --scanners secret         →  não vê a senha em env.value
```

Três violações reais presentes naquele manifesto passam batido pelas duas varreduras:
`1.1` (nome fora do kebab-case), `1.4` (seletor órfão) e `3.3` — a regra classificada como
**proibida**, a mais grave do padrão.

E o Trivy anda para o lado errado numa quarta: o `KSV-0125` acusa `registry.metacortex.io`
como registry não confiável, ou seja, marca quem **cumpriu** a regra 3.7.

## As duas execuções

**Modo escrita** rodou no `encontros-tech` (`execucoes/manifests-helio-prod/`) — projeto que
nem eu nem a skill tínhamos aberto, de propósito: repetir o fake-shop provaria apenas que a
skill reproduz o que já sabia.

**Modo conferência** rodou no manifesto barrado
([`execucoes/conferencia-manifesto-barrado.md`](execucoes/conferencia-manifesto-barrado.md)),
e produziu o achado mais valioso do ticket: o manifesto injeta `DATABASE_URL`, e o kube-news
**nunca lê essa variável**. Corrigir só a regra 3.3 deixaria o manifesto conforme e quebrado
ao mesmo tempo — defeito invisível ao YAML e às duas ferramentas.

## O fluxo rodado à mão, do qual a skill nasceu

- [`execucoes/leitura-do-fake-shop.md`](execucoes/leitura-do-fake-shop.md) — o que só se sabe
  abrindo o projeto: porta, rotas, o que a aplicação escreve em disco, nomes das variáveis
- [`execucoes/manifests-orion-prod/`](execucoes/manifests-orion-prod/) — os manifests escritos
  à mão, com [`DECISOES.md`](DECISOES.md) registrando as dez decisões que o padrão não toma
- [`insumos/`](insumos/) — o padrão, o manifesto barrado e os commits exatos dos projetos lidos

## O teste que separa conferidor de conferidor quebrado

```bash
python3 skill/scripts/conferir-padrao.py insumos/manifesto-barrado-nyx.yaml   # 10 erros, saída 1
python3 skill/scripts/conferir-padrao.py execucoes/manifests-orion-prod/      # 0 erros, saída 0
trivy config execucoes/manifests-orion-prod/                                  # 5 achados, todos catalogados
```

Conferidor que nunca reprova é indistinguível de conferidor quebrado.
