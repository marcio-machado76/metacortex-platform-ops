# Origem da skill — de qual fluxo ela nasceu

O desafio tem uma regra que vale do começo ao fim: *"toda skill nasce de um fluxo que
você rodou, não de um chute"*. Este documento responde as três perguntas que a lista de
entrega faz — **de qual fluxo**, **por qual caminho** e **com qual ferramenta**.

## Linhagem: o desafio anterior

A skill não nasceu do zero. O padrão de manifests da Metacortex já tinha sido enfrentado
no desafio anterior desta pós, cuja entrega está em
<https://github.com/marcio-machado76/metacortex-padrao-manifests> (commit `5f65997`).

Aquele repositório transformou a página de wiki em três ambientes conformes, um
verificador e um relatório de oito pontos em que o padrão não produz o resultado que
promete. Ele não era uma skill — era um repositório de manifests com CI.

**A decisão foi usá-lo como origem declarada, não como base a ser reembalada.** O que veio
de lá foi o método e a linhagem; o que foi refeito aqui, do zero, foi tudo o que a lista de
entrega pede: a medição na versão desta máquina, o modo de escrita (que não existia lá), a
skill em si e as duas execuções.

## O caminho, na ordem em que aconteceu

A ordem importa mais que o conteúdo, porque é ela que separa skill destilada de skill
inventada. O histórico do repositório confirma a sequência.

**1 · Medir antes de escrever qualquer linha.** O ticket é explícito: descobrir quanto o
Trivy já pega *"rodando, não supondo"*, e isso *"vem antes de escrever qualquer script"*.
Rodamos `trivy config` no manifesto barrado — 18 achados, que ao serem mapeados de volta
colapsam em **quatro das 19 regras**. E testamos a hipótese natural sobre a regra mais
grave: `trivy fs --scanners secret` **não vê** a senha em `env.value`.

Saída bruta em `baseline-trivy/`, leitura em `baseline-trivy/cobertura-medida.md`.

**2 · Classificar as 19 regras.** Só com a medição na mão dava para dividir entre o que é
do Trivy, o que vira script, o que exige ler o projeto e o que não entra. Está em
`curadoria-das-regras.md`, e é onde apareceu o achado que justifica a skill existir além do
verificador do desafio anterior: **cinco regras deixam de ser "revisão humana"** quando
quem confere é um agente que tem o repositório do projeto à mão.

**3 · Rodar o fluxo à mão, nos dois modos.** Antes de existir skill:

- **Modo escrita** — abrimos o fake-shop e extraímos o que o YAML não conta
  (`execucoes/leitura-do-fake-shop.md`), e escrevemos os manifests de `orion-prod` à mão,
  registrando as dez decisões que o padrão não toma sozinho (`DECISOES.md`).
- **Modo conferência** — rodamos o Trivy nos manifests produzidos: de 18 achados para 5,
  todos conhecidos e nenhum sendo desvio do padrão.

**4 · Só então destilar.** Com o fluxo rodado e documentado, a skill foi produzida com a
skill **`skill-creator`**, que é a ferramenta da casa para isso. O que era mecânico virou
`scripts/conferir-padrao.py`; o que exige ler o projeto virou instrução no corpo e em
`references/regras-que-exigem-o-projeto.md`; o que não aprova nem reprova manifesto — o
Bloco 4 inteiro — ficou de fora.

**5 · Testar o conferidor nos dois sentidos.** Conferidor que nunca reprova é
indistinguível de conferidor quebrado. No manifesto barrado: 10 erros, saída 1, pegando as
três regras que o Trivy não vê (`1.1`, `1.4` e `3.3`). Nos manifests conformes: 0 erros, 0
avisos, saída 0, com a exceção do banco reconhecida.

**6 · Executar em sessão limpa.** As duas execuções da lista de entrega foram feitas por
agentes em **contexto frio**, que não participaram de nada acima e trabalharam só a partir
da skill. O modo de escrita rodou no `encontros-tech` de propósito — projeto que nem eu nem
a skill tinham aberto —, porque repetir o fake-shop provaria só que a skill reproduz o que
já sabia.

**7 · Corrigir a skill com o que a execução expôs.** O agente versionou um objeto `Secret`
com valor de placeholder. Não é vazamento e não fere a letra da regra 3.3 — mas o
`SKILL.md` mandava "referenciar um Secret" sem dizer que o objeto não entra no
repositório. A lacuna era da skill, e o texto foi corrigido. **O manifesto gerado ficou
como saiu**, porque ele é a evidência.

## As ferramentas

| Ferramenta | Para quê |
|---|---|
| `trivy` 0.74.0 | a medição do passo 1, que definiu o escopo do script |
| `skill-creator` | produzir a skill a partir do fluxo já rodado |
| subagentes em contexto frio | as duas execuções da entrega, sem contaminação de contexto |
| `kubectl --dry-run=client` | validar o esquema dos manifests escritos à mão |

## O que a ordem prova

O histórico registra a medição do Trivy e a curadoria **antes** do primeiro commit de
skill, e as execuções **depois**. Se a ordem fosse outra — script primeiro, medição depois
—, a skill teria reimplementado o que já vinha pronto e continuado devendo o que é da
Metacortex e não do Kubernetes, que é exatamente o que o ticket existe para evitar.
