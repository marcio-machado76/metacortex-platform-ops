# Ticket 03 — O Roster que ninguém consegue manter

Ferramenta que roda na estação de quem opera, entra por SSH numa VM do parque, levanta o
retrato real daquele host e o compara com o padrão declarado — apontando cada desvio, sua
gravidade, e o que **não pôde ser verificado**.

Este é o primeiro projeto do desafio, e ele não começou no editor de código.

## A lista de entrega, item a item

| O que o ticket pede | Onde está |
|---|---|
| **Os documentos de spec** | [`docs/00-brainstorm.md`](docs/00-brainstorm.md), [`01-comportamento.md`](docs/01-comportamento.md), [`02-decisoes-tecnicas.md`](docs/02-decisoes-tecnicas.md) |
| **Os artefatos do OpenSpec** (proposta, tarefas, specs, arquivado) | [`openspec/`](openspec/) — arquivado em `changes/archive/2026-09-06-adicionar-inventario-de-vm/` |
| **O código** | [`src/inventario_vm/`](src/inventario_vm/) e [`tests/`](tests/) |
| **A evidência de execução real** | [`evidencias/`](evidencias/) — 25 arquivos, saídas cruas |
| **A curadoria** (onde o documento precisou ser corrigido, o que o agente entendeu diferente) | [`docs/03-divergencias-da-implementacao.md`](docs/03-divergencias-da-implementacao.md) |

## O arco, na ordem em que aconteceu

```
brainstorm → documentos de spec → ciclo do OpenSpec → implementação → validação
```

O histórico prova a ordem: **o primeiro commit do ticket não tem uma linha de código.**

A implementação foi conduzida por agentes em **contexto frio**, que não participaram da
especificação — de propósito. Se um agente que não sabe o que estava na minha cabeça
consegue implementar a partir dos artefatos, a especificação está completa; onde ele trava,
o buraco fica visível.

## Rodando

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/inventario-vm --host <endereço> --usuario <nome> --chave <caminho>
.venv/bin/python -m pytest -q          # 104 testes, nenhum toca rede
```

Códigos de saída: `0` conforme · `1` desvio · `2` inalcançável · `3` erro interno.

O laboratório que serve de alvo está em [`infra/`](infra/) — duas EC2, uma dentro do
baseline e outra com um desvio de cada severidade. É **efêmero por decisão**: sobe para a
validação e desce em seguida.

## A decisão que pagou

Separar **coleta** de **julgamento**: o avaliador é função pura de `(inventário, baseline)`.
Isso tornou as onze regras testáveis sobre inventários escritos à mão, sem host — e o
avaliador foi construído **antes** do coletor por causa disso.

Dois bugs só apareceram porque havia teste:

- `ipaddress.ip_address("0.0.0.0").is_private` é **`True`** em Python, porque `0.0.0.0/8` é
  faixa reservada. A primeira versão classificava o *bind* coringa como rede interna — uma
  porta aberta para o mundo sairia **conforme** nas duas regras que o baseline marca como
  **críticas**.
- O `ss` anota loopback com sufixo de interface (`127.0.0.53%lo`), que quebra a análise.

## A ferramenta violava o próprio invariante

Declarada somente-leitura, ela **ativava um serviço no host que auditava**:

```
antes de qualquer coleta      : systemd-timedated.service  inactive
imediatamente após uma coleta : systemd-timedated.service  active
```

O `timedatectl` fala com o `systemd-timedated` por D-Bus, e o systemd o ativa sob demanda.
Nenhum teste pegaria — só apareceu contra VM real. Corrigido no **código**, não na
especificação, e a saída fácil (afrouxar o critério para valer só sobre vereditos, já que
nenhum veredito mudava) foi descartada explicitamente.

Fica o limite honesto: **observar não é gratuito**.
