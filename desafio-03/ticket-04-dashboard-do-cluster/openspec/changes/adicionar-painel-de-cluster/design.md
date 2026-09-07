## Context

Ver `proposal.md` para a motivação. As onze decisões técnicas, com as alternativas
descartadas e o que se ganha e se perde em cada caminho, estão em
`../../../docs/02-decisoes-tecnicas.md`; este documento não as repete, e sim
descreve a arquitetura que elas produzem.

Três restrições moldam o desenho:

1. **A garantia de só-leitura precisa estar visível**, e não pode depender de quem
   revisa lembrar dela.
2. **Três formas de ausência** — chave ausente, valor nulo, coleção vazia —
   aparecem em posições diferentes das respostas da API, e uma delas foi cometida
   por engano dentro da verificação feita para demonstrá-la.
3. **Falha parcial é o caso normal**, não a exceção: permissão negada para um tipo
   enquanto os outros funcionam é o comportamento de um contexto de leitura
   restrita.

## Goals / Non-Goals

**Goals:**

- Que a parte difícil de acertar — a interpretação dos campos — seja testável sem
  cluster nenhum.
- Que tudo que pode mudar debaixo do projeto fique confinado num módulo só.
- Que a garantia de só-leitura tenha três camadas independentes, e que a falha de
  uma não derrube as outras.

**Non-Goals:**

- Abstrair o cliente de Kubernetes atrás de uma interface genérica que permita
  trocar de implementação. A fronteira existe para conter mudança, não para
  suportar duas implementações.
- Desenho de tela que sobreviva a redimensionamento arbitrário de terminal na
  primeira fatia.

## Decisions

### D-A · Duas metades: quem fala com a rede e quem interpreta

O código se divide em **um módulo que faz rede e nada mais** e **funções puras que
interpretam**. A fronteira é o envelope: o módulo de leitura devolve envelopes com
JSON cru dentro; nenhuma interpretação acontece lá.

**Alternativa descartada — interpretar no momento da leitura**, devolvendo objetos
já prontos para a tela. Ganharia um passo a menos. Perderia o que importa: a
interpretação passaria a exigir cluster para ser testada, e é justamente ela que
concentra as armadilhas do ticket.

É o mesmo desenho do Ticket 03, e pelo mesmo motivo. Lá, separar coleta de
avaliação tornou a idempotência do julgamento provável em CI, sem host. Aqui,
separar leitura de interpretação torna as três formas de ausência prováveis sem
apiserver.

### D-B · As fixtures de teste são capturas do cluster real

Os testes da camada de interpretação rodam sobre JSON **capturado do
`kind-metacortex-lab`**, não sobre JSON escrito à mão: o pod do `nyx-prod` com
`CrashLoopBackOff` e `OOMKilled`, o Deployment do `orion-stg` sem
`readyReplicas`, o `Endpoints` do `nyx-stg` sem `subsets` e a fatia equivalente com
`endpoints` nulo, e um evento com `series` ausente.

**Alternativa descartada — fixtures escritas à mão.** Seriam mais curtas e mais
legíveis. Perderiam a única propriedade que interessa: JSON escrito à mão contém a
forma que quem escreveu **acredita** que a API devolve, e a hipótese errada sobre
`series` prova que essa crença falha exatamente nos pontos que o ticket planta.

As capturas ficam em `tests/fixtures/`, com o comando que as reproduz registrado ao
lado.

### D-C · O envelope é um tipo, não uma convenção

`ok`, `vazio`, `negado` e `indisponível` são um tipo de dado explícito, com o JSON
cru quando há dado e o motivo quando não há. A camada de tela recebe envelope,
nunca lista.

**Alternativa descartada — devolver lista e sinalizar falha por exceção.** Ganharia
código mais direto no caminho feliz. Perderia o requisito central: quem desenha
precisa distinguir "não há objetos" de "não posso ver os objetos", e exceção não
carrega essa diferença até a tela sem alguém escrever o `try` no lugar certo.

### D-D · A classificação de falha acontece na fronteira, e só lá

O mapeamento de exceção para estado de envelope vive no módulo de leitura:

| Exceção | Envelope |
|---|---|
| falha de autorização em um tipo | `negado`, só naquele tipo |
| falha de autenticação | `indisponível` por credencial, em todos os tipos |
| falha de transporte | `indisponível` por cluster, em todos os tipos |

**Alternativa descartada — classificar na tela.** Espalharia conhecimento de
biblioteca por toda a camada de apresentação, que é exatamente o que a fronteira
existe para impedir.

A terceira linha vem de uma **dependência transitiva**, não da biblioteca escolhida.
Isso é motivo suficiente para a classificação estar aqui: é o único lugar do
projeto que tem licença para conhecê-la.

### D-E · A garantia de só-leitura em três camadas independentes

| Camada | O que prova | Falha se |
|---|---|---|
| Fronteira única | nenhum outro módulo importa o cliente nem o transporte | alguém adiciona o import |
| Teste automatizado | nenhum verbo de escrita e nenhum import fora da fronteira | o teste roda em CI |
| RBAC do contexto recomendado | o cluster recusa o que o código venha a tentar | independe do repositório |

**Alternativa descartada — uma camada só.** Cada uma cobre o que as outras não
cobrem: o teste prova o que o código faz hoje, o RBAC recusa o que ele venha a
fazer amanhã, e a fronteira é o que torna as duas primeiras verificáveis num só
lugar.

O teste da segunda camada é o mesmo que protege a fronteira de contenção — verbo de
escrita e import indevido são a mesma verificação, sobre a mesma regra.

### D-F · A ordenação é derivada, mas o critério é dado

Cada objeto exibido carrega a lista de critérios que satisfez. A ordenação usa essa
lista; a tela a exibe. Nenhum critério é calculado a partir de outro critério.

**Alternativa descartada — um escore numérico de severidade.** Ordenaria melhor em
casos ambíguos. Perderia a auditabilidade: um número não diz o que o produziu, e a
tela passaria a afirmar algo que a API não devolve.

## Risks / Trade-offs

- **`_preload_content` é API com sublinhado e pode sumir numa versão maior do
  cliente** → versão fixada em `requirements.txt`, uso restrito à fronteira, e um
  teste que falha se a leitura deixar de preservar a distinção entre chave ausente
  e valor nulo. O teste denuncia a quebra antes de a tela mentir.
- **A exceção de transporte vem de dependência transitiva** → capturada só na
  fronteira, e o teste de import impede que qualquer outro módulo passe a
  depender dela.
- **Testes de tela por captura de texto quebram com mudança cosmética** → poucos,
  e apontados aos estados que importam: os quatro do envelope e os três ambientes
  hostis. Layout não vira teste.
- **A camada de interpretação pode ganhar regra que a API não sustenta** → toda
  saída dela precisa apontar para o campo lido que a originou; critério sem campo
  de origem não passa na revisão.
- **As fixtures capturadas envelhecem com o cluster** → o comando que as reproduz
  fica junto, e a captura é refeita quando o cenário mudar. Fixture que não se sabe
  reproduzir é fixture escrita à mão com passos extras.

## Migration Plan

Projeto novo; não há migração nem rollback de dado.

A instalação exige dois passos além do pacote, e os dois já estão no repositório:
aplicar `rbac/platform-ro.yaml` e apontar o kubeconfig para um contexto que use
aquela ServiceAccount. O README do ticket documenta os dois, e o
`platform-ro-sem-events.yaml` fica ao lado, marcado como cenário de evidência e não
como forma de rodar.

## Open Questions

- **Largura mínima de terminal** em que a tela continua legível. Não muda spec,
  desenho nem divisão de tarefas; resolve-se ao desenhar os painéis.
- **Se a idade do dado aparece por painel ou uma vez para a tela inteira.** Depende
  de como os painéis ficam dispostos, e as duas formas atendem ao requisito.
