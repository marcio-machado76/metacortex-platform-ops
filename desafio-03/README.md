# Desafio 03 — O parque da Metacortex

Quatro tickets: dois pedem skills que empacotem o método de operação da casa, dois pedem
projetos entregues por inteiro. Duas regras valem do começo ao fim — **toda skill nasce de
um fluxo que foi rodado**, e **nenhum dos dois projetos começa pelo código**.

| Ticket | Entrega | Pasta |
|---|---|---|
| 01 | Skill do padrão de manifests | [`ticket-01-padrao-de-manifests/`](ticket-01-padrao-de-manifests/) |
| 02 | Skill de triagem no cluster | [`ticket-02-triagem-no-cluster/`](ticket-02-triagem-no-cluster/) |
| 03 | Ferramenta de inventário e drift de VM | [`ticket-03-inventario-de-vm/`](ticket-03-inventario-de-vm/) |
| 04 | Dashboard do cluster | [`ticket-04-dashboard-do-cluster/`](ticket-04-dashboard-do-cluster/) |

Cada pasta tem um `README.md` que cruza a lista "Entregue" do ticket com o arquivo que
contém cada item.

## O histórico é parte da entrega

Os commits estão na ordem em que o trabalho aconteceu, e nos dois projetos **o primeiro
commit não tem uma linha de código**. Isso não é estilo: é a prova de que o arco foi
percorrido na ordem que o desafio exige, e é o que um squash teria apagado.

No Ticket 01, a medição do Trivy e a curadoria das regras estão commitadas **antes** do
primeiro commit de skill. Na ordem inversa, a skill teria reimplementado o que já vinha
pronto.

## Os quatro tickets são um sistema só

O que mais rendeu não foi nenhum ticket isolado, e sim onde eles se tocam:

**A regra 1.4 atravessa três.** O padrão diz que o seletor do Service tem que casar com os
rótulos do pod. No Ticket 02 ela é o Chamado 3 — um hífen de diferença, e o Service nasce
sem destino. No Ticket 04 ela decide como a tela distingue *"sem endereço"* de *"tem
endereço, nenhum pronto"*, o que só o `EndpointSlice` sabe responder.

**A decisão de probe do Ticket 01 pagou no Ticket 04.** A readiness do kube-news foi
apontada para `/` e não para `/ready`, porque o `/ready` do projeto só compara timestamps e
responderia "pronto" com o banco desligado. Meses depois — dois tickets depois — foi a
única coisa que denunciou um pod do fake-shop `Running`, com zero reinícios e zero eventos,
servindo erro.

**"Quem impede é a ferramenta, não a instrução" aparece três vezes.** No Ticket 02 é o
servidor MCP em `ALLOW_ONLY_READONLY_TOOLS`. No Ticket 03 é o usuário de coleta sem `sudo`.
No Ticket 04 é o RBAC que nega todo verbo de escrita — e que, por não conceder `watch`, faz
o próprio cluster recusar a alternativa que a decisão descartou.

**"Não sei" é dado, não erro.** O Ticket 03 inventou o veredito `nao_verificado` porque
reportar como conforme seria mentira. O Ticket 04 herdou a forma num envelope de quatro
estados, e é o que faz a tela degradar por construção quando falta permissão para um tipo
de recurso.

## O que foi deliberadamente deixado de fora

O desafio premia tanto o que se cobre quanto o que se recusa cobrir:

- **O Bloco 4 do padrão** — oito verbetes de vocabulário, zero regra. Um terço da página.
- **Reimplementar o Trivy** — as quatro regras que ele já cobre não foram reescritas.
- **Script na skill de triagem** — script com acesso ao cluster carregaria credencial
  própria e ficaria fora da garantia do servidor.
- **`watch` no dashboard** — o eixo de carga favorece o watch; o que decide é a manutenção
  de uma máquina de resync que um time de infra herda e não mexe.

## Onde os erros ficaram registrados

Nenhum documento foi reescrito como se sempre tivesse estado certo. As correções estão
marcadas como correções, com o motivo:

- `ticket-03-.../docs/01-comportamento.md` — quatro pontos que não sobreviveram ao contato
  com o código, dois deles contratos entre módulos
- `ticket-03-.../docs/03-divergencias-da-implementacao.md` — o que o agente entendeu
  diferente do que foi escrito
- `ticket-04-.../docs/03-divergencias-da-implementacao.md` — um critério de aceite que já
  era falso quando foi escrito, com a ordem dos commits provando que não é trave movida
  depois do resultado

## Instalação das skills

As duas skills são versionadas em `ticket-01-.../skill/` e `ticket-02-.../skill/`. Para
usá-las, aponte o escopo de projeto do agente para elas:

```bash
mkdir -p .claude/skills
ln -s ../../desafio-03/ticket-01-padrao-de-manifests/skill .claude/skills/padrao-de-manifests
ln -s ../../desafio-03/ticket-02-triagem-no-cluster/skill  .claude/skills/triagem-de-cluster
```

`.claude/` e o `.mcp.json` da raiz ficam fora do versionamento — são estado de instalação.
A cópia canônica do `.mcp.json` é versionada em `ticket-02-.../mcp/`.

O OpenSpec tem uma raiz por projeto, dentro da pasta do ticket: os comandos rodam **de
dentro dela**, e da raiz do repositório respondem que não há raiz — comportamento esperado.
