# Decisões técnicas

O enunciado nomeia cinco decisões que o dashboard não carrega sozinho — linguagem
e stack, como falar com a API, como atualizar a tela, quanto entra na primeira
fatia, e `Endpoints` contra `EndpointSlice`. Elas estão aqui, cada uma com pelo
menos duas alternativas descartadas e o que se ganha e se perde em cada caminho.

As outras seis apareceram durante o amadurecimento e valem pelo mesmo motivo: quem
pegar este código daqui a um ano vai perguntar por quê, e o commit não responde.

Onde a decisão se apoia em medição, o comando que a reproduz está no
`00-brainstorm.md` ou em `evidencias/`. Onde ela se apoia em julgamento, o
julgamento está escrito.

---

## D1 · Linguagem e stack: Python com Textual

**Escolhido:** Python 3 com Textual, aplicação de terminal, empacotada como
`painel-cluster`.

**Descartado — Go com TUI.** Entrega binário único sem runtime na estação, e o
`client-go` é o cliente de referência do ecossistema: tipagem melhor, informers
prontos, semântica de erro superior à de qualquer outra linguagem. **Ganha** em
distribuição e em qualidade de biblioteca. **Perde** em duas frentes: seria a
segunda linguagem do repositório, que já tem Python no conferidor do Ticket 01 e na
ferramenta do Ticket 03, mais Terraform na infraestrutura; e o argumento de
distribuição vale menos do que parece aqui, porque **a ferramenta roda na estação
de quem opera, não numa frota**. Para um time de infraestrutura que já mantém
Python, o custo de manutenção supera o ganho de execução.

**Descartado — web local, FastAPI servindo HTML.** **Ganha** layout livre, e
qualquer pessoa sabe abrir um navegador. **Perde** por dois motivos, e o segundo só
apareceu na conversa: sobe um servidor HTTP na estação de quem opera com a
credencial de produção atrás dele — superfície nova para uma ferramenta cujo
invariante é só ler; e a evidência de execução vira PNG. **Snapshot de TUI é
texto: versiona e diffa em PR.** Screenshot de web ninguém revisa.

**Descartado — TypeScript com React.** **Ganha** a melhor interface possível dos
três. **Perde** aderência ao time que vai manter, acrescenta uma cadeia de build
inteira e seria a terceira linguagem do repositório. O consumidor desta tela é
infraestrutura, não produto.

**Custo aceito:** Textual é uma dependência a mais, e ninguém "abre no navegador"
para mostrar a alguém de fora. Mitigado por versão fixada em `requirements.txt` e
um único ponto de entrada.

O argumento decisivo não é técnico, é do enunciado: *"Não é substituir o terminal;
é encurtar os primeiros dez minutos de todo chamado."* A ferramenta vive **ao
lado** do terminal, e o k9s é a prova de que essa é a forma nativa do problema.

## D2 · Acesso à API: cliente oficial com `_preload_content=False`

**Escolhido:** o cliente oficial `kubernetes`, versão fixada, com
`_preload_content=False` para receber o JSON cru.

**Descartado — `kubectl` como subprocesso.** **Ganha** o máximo: zero dependência
além de um binário que todo mundo do time já tem, JSON com a forma original de
graça, e autenticação cem por cento resolvida, incluindo *exec plugins* de nuvem.
**Perde** exatamente onde o enunciado aperta: classificar erro vira regex em
mensagem de erro humana, em inglês, escrita para pessoa e não para máquina.
Distinguir *"403 em `events`, os outros tipos ok"* de *"cluster não responde"*
passaria a depender de texto que muda entre versões do `kubectl`. Perde também em
latência, com um processo por consulta.

**Descartado — HTTP direto contra o apiserver.** **Ganha** controle total do
formato e o código de status puro, que é o sinal mais limpo possível para a
degradação graciosa. **Perde** no que não é o problema do projeto: reimplementar o
carregamento do kubeconfig — contextos, certificado de cliente, CA, tokens e, o
que mata de vez, *exec credential plugins*. O kubeconfig do enunciado usa
certificado, mas um parque real tem `aws eks get-token`.

**Descartado — o mesmo cliente oficial, com os modelos tipados.** **Ganha**
ergonomia, autocompletar e atributos em vez de chaves de dicionário. **Perde** a
distinção que o ticket planta: campo ausente e campo nulo viram o mesmo `None`.
Medido:

```
Endpoints/nyx-api  tipado : .subsets   = None
EndpointSlice      tipado : .endpoints = None
```

**Custo aceito:** `_preload_content` é API com sublinhado — convenção de privado.
Nada garante que sobreviva a uma versão maior do cliente. O risco fica contido no
ponto único de acesso da D8, e a versão fica fixada.

**Uma correção ao argumento original.** Durante o brainstorm foi dito que esta
seria a única combinação a atender aos dois requisitos difíceis ao mesmo tempo. A
medição estreitou isso: o modelo tipado levanta a **mesma** exceção com o **mesmo**
`.status`. O tratamento de erro sai de graça nos dois modos. **O modo cru compra
uma coisa, não duas** — a forma do JSON. A escolha não muda; a justificativa fica
mais honesta.

## D3 · Atualização da tela: intervalo fixo escopado ao namespace

**Escolhido:** consulta a cada 10s sobre o namespace selecionado, 60s sobre a lista
de namespaces, mais atualização manual por tecla.

**Descartado — observar mudanças por watch.** **Ganha** os dois eixos que mais
parecem importar: é **mais barato** para o apiserver em regime, porque mantém uma
conexão por tipo e recebe só deltas em vez de reserializar a lista inteira a cada
ciclo; e o atraso cai para quase zero. **Perde** no eixo que decide: complexidade
de manutenção. Watch exige reconexão, tratamento de `410 Gone`, resync, bookmarks e
casamento do fluxo com o `LIST` inicial. É uma máquina de estados, e quem herda
este código é um time de infraestrutura que mexe nele duas vezes por ano.

Vale dizer o que **não** é argumento aqui, porque é o folclore mais comum sobre o
assunto: *watch não é caro para o apiserver.* Escrever o contrário seria repetir
crença em vez de pesar os três eixos que o enunciado pede.

**Descartado — consultar só sob demanda.** **Ganha** a menor carga possível e o
menor código possível. **Perde** o que faz a coisa ser um painel: a tela mente
desde o instante seguinte à consulta, e quem está triando não sabe se está olhando
o cluster ou uma fotografia de três minutos atrás.

**Custo aceito:** até 10s de atraso, e um `LIST` por tipo por ciclo. O escopo por
namespace é o que torna esse custo pequeno — e ele já era requisito, porque a tela
tem filtro por namespace. Mitigação parcial contra o engano: a tela mostra a idade
do dado.

Um efeito colateral que virou garantia: **o contexto `platform-ro` não concede o
verbo `watch`.** Trocar intervalo fixo por watch sem reabrir esta decisão não
depende de alguém lembrar — o apiserver recusa.

## D4 · Primeira fatia: o mínimo do enunciado, mais StatefulSet

**Escolhido:** namespaces, pods, Deployments, **StatefulSets**, Services com
endereços, e eventos do namespace selecionado. Filtro por namespace e busca por
nome.

**Descartado — o mínimo literal, sem StatefulSet.** **Ganha** uma superfície a
menos para especificar, testar e manter. **Perde** contra o cluster de validação:
o postgres do fake-shop é StatefulSet, então metade do workload que subimos para
provar a ferramenta apareceria como pods órfãos, sem linha de controlador. O texto
do enunciado autoriza o acréscimo ao dizer *"o que precisa aparecer na tela, **no
mínimo**"* — e é esse apoio textual que separa escopo justificado de inchaço.

**Descartado — incluir DaemonSet, Job, CronJob, nós e logs.** **Ganha** uma
ferramenta que responde mais perguntas sem sair dela. **Perde** o próprio motivo de
existir desta decisão: é exatamente o inchaço que transforma ferramenta interna em
coisa que ninguém termina. E o apoio textual não existe para eles — no laboratório,
DaemonSet só aparece no `kube-system`, que não é workload de cliente.

**Custo aceito, e maior do que parecia na hora de decidir.** A conta feita foi "mais
um tipo no mesmo envelope". Ao escrever o `01-comportamento.md` a medição mostrou
que é **mais um tipo com forma de status própria**: o StatefulSet não traz a chave
`status.conditions`, enquanto o Deployment traz `Available` e `Progressing`.

```
deploy status: [availableReplicas, conditions, observedGeneration, readyReplicas, replicas, updatedReplicas]
sts    status: [availableReplicas, collisionCount, currentReplicas, currentRevision,
                observedGeneration, readyReplicas, replicas, updateRevision, updatedReplicas]
sts    conditions: <CHAVE AUSENTE>
```

A decisão se mantém, porque a coluna que o enunciado exige — prontos sobre
desejados — é comum aos dois. O que muda é que a coluna de condição existe para um
e não para o outro, e isso precisa aparecer como ausência de dado e não como estado
ruim.

## D5 · Endereços: `EndpointSlice`

**Escolhido:** `EndpointSlice`, agregado pelo rótulo `kubernetes.io/service-name`.

**Descartado — `Endpoints`.** **Ganha** simplicidade real: relação um-para-um com
o Service, nome igual ao do Service, e é a forma que o próprio enunciado mostra no
exemplo. **Perde** por dois motivos, e o segundo importa mais que o primeiro. O
primeiro é a aposentadoria que o enunciado menciona. O segundo é informação: o
`Endpoints` separa endereços prontos de não prontos por listas irmãs dentro de
`subsets`, enquanto o `EndpointSlice` carrega `conditions.ready` **por endereço** —
o que deixa a tela distinguir *"nenhum endereço"* de *"tem endereço, nenhum
pronto"*. No cluster de validação esses dois são chamados diferentes.

**Descartado — ler os dois e cruzar.** **Ganha** robustez contra cluster antigo em
que o `EndpointSlice` não exista. **Perde** duas coisas caras para uma primeira
fatia: duas fontes de verdade para o mesmo fato, e o dobro de `LIST` por ciclo.
A primeira fatia roda contra clusters conhecidos.

**Custo aceito:** um Service mapeia para **N** slices, não uma, então há um passo
de agregação por rótulo que o `Endpoints` não exigiria. E a forma de "vazio" muda:
o `Endpoints` omite a chave, o `EndpointSlice` manda `null` — resolvido pela D9.

## D6 · Eventos: `core/v1`

**Escolhido:** a API `core/v1`.

**Descartado — `events.k8s.io/v1`.** **Ganha** ser a API mais nova, com o mesmo
argumento de durabilidade que fez o `EndpointSlice` vencer na D5. **Perde** na
medição, e perde feio: ela marca como *deprecated* exatamente os quatro campos que
uma triagem usa.

| `core/v1` | `events.k8s.io/v1` |
|---|---|
| `message` | `note` |
| `involvedObject` | `regarding` |
| `count` | **`deprecatedCount`** |
| `firstTimestamp` / `lastTimestamp` | **`deprecatedFirstTimestamp`** / **`deprecatedLastTimestamp`** |

O substituto declarado de `count` é `series`, e a medição fecha o caso: nos três
eventos do `nyx-prod`, `series` está **ausente**, `deprecatedCount` está preenchido
(105, 2429 e 2420), e `reportingController` é `kubelet` nos três. **O kubelet ainda
escreve pelo caminho da `core/v1`** — ou seja, os eventos que mais importam numa
triagem são precisamente os que chegam sem o campo novo. Ler pela API nova hoje
significa ler o campo desencorajado ou perder a contagem.

**Descartado — ler as duas e mesclar.** **Ganha** cobertura de qualquer escritor de
evento. **Perde** por ser a mesma coisa duas vezes: são os mesmos objetos servidos
por duas portas, então mesclar duplicaria linha na tela e exigiria deduplicação por
identidade — trabalho para não ganhar informação.

**Custo aceito:** se a `core/v1` entrar em trilha de remoção, isto vira dívida. A
troca acontece num único lugar, que é a fronteira da D8.

**O par D5/D6 é o resultado mais interessante do ticket.** Duas decisões com a
mesma forma — API antiga contra API nova — e respostas opostas, no mesmo projeto e
na mesma semana. *"Prefira a API mais nova"* não é princípio; é heurística que se
verifica caso a caso. Essa é a "consequência de durabilidade" que o enunciado manda
pesar.

## D7 · A tela relata, ordena, e mostra a ausência de probe

**Escolhido:** vocabulário da API na tela, ordenação por anormalidade com o critério
visível, e uma coluna que mostra quando o container não tem `readinessProbe`.

**Descartado — uma coluna de severidade derivada.** **Ganha** leitura instantânea:
verde, amarelo, vermelho, e quem abre a tela sabe onde olhar em dois segundos.
**Perde** a única coisa que a ferramenta tem de valor, que é ser confiável sobre o
que afirma. O `orion-web` do `orion-stg` **não tem probe nenhuma**, então o `Ready`
dele significa apenas "o processo subiu". Uma coluna dizendo "saudável" ali estaria
errada, e estaria errada com autoridade.

**Descartado — relatar e nada mais, sem ordenação.** **Ganha** neutralidade
absoluta: a tela é um espelho da API e não opina em nada. **Perde** o objetivo
declarado do ticket. Um painel que lista trezentos objetos em ordem alfabética não
encurta dez minutos de chamado; empurra o trabalho de volta para quem abriu.

**A distinção que destravou a decisão:** ordenar não é opinar sobre saúde, é opinar
sobre **onde olhar primeiro**. E o que torna isso honesto é mostrar o critério —
reinícios maiores que zero, prontos menores que desejados, sem endereço, eventos
`Warning`. Todos são dados da API, então a ordem é auditável por quem discorda
dela.

**O terceiro caminho, que nenhuma das duas posturas cobria:** mostrar que o objeto
**não tem probe**. É fato da API, vem de graça no `spec` do Pod que a tela já
lista, e permite a quem lê descontar o `Ready` sozinho. Responde à pergunta que o
enunciado levanta — *quanto o dashboard pode afirmar sobre a saúde a partir do que
a API devolve* — sem a tela afirmar nada sobre saúde.

**Custo aceito:** duas colunas a mais em largura de terminal, que é recurso escasso.

## D8 · Só-ler, em três camadas — e a fronteira de contenção

**Escolhido:** um ponto único de acesso à API, um teste que falha diante de verbo
de escrita, e dois contextos RBAC.

**Descartado — confiar na revisão de código.** **Ganha** zero infraestrutura.
**Perde** a diferença entre promessa e garantia. O enunciado pede que a garantia
esteja *"visível no projeto, não só na intenção de quem escreveu"*.

**Descartado — um único contexto RBAC, sem `events`.** Era a ideia mais elegante da
conversa: um ServiceAccount sem permissão para `events` provaria o só-leitura **e**
seria o cenário de permissão parcial, dois requisitos com um tiro. **Ganha**
economia. **Perde** por um motivo simples que só apareceu ao escrever: os eventos
do namespace selecionado são requisito explícito da tela. Um contexto recomendado
que os nega entrega uma ferramenta que não faz o que foi pedida para fazer.

São dois, com papéis distintos:

| Contexto | Papel | Perfil |
|---|---|---|
| `platform-ro` | o jeito **documentado** de rodar | leitura no que a tela usa, `events` inclusive. Nunca `secrets`, nunca verbo de escrita, nunca `watch` |
| `platform-ro-sem-events` | só cenário de evidência | o mesmo, menos `events` |

**Descartado — só o teste automatizado, sem RBAC.** **Ganha** simplicidade de
ambiente. **Perde** a prova externa: um teste prova o que o código faz hoje; o RBAC
faz o cluster recusar o que o código venha a fazer amanhã.

**A fronteira de contenção — o segundo papel do ponto único.** Ele nasceu como o
lugar onde a garantia de só-leitura mora, e acumulou outro. Três riscos de
durabilidade se juntaram durante a verificação:

| Risco | O que pode mudar debaixo do projeto |
|---|---|
| `_preload_content` | API com sublinhado, convenção de privado |
| `urllib3.exceptions.MaxRetryError` | vem de **dependência transitiva**, que a D2 não escolheu |
| `Endpoints`, `core/v1 Event` | APIs cuja durabilidade foi pesada caso a caso, e pode virar |

Os três ficam confinados num módulo, e o resto do código conversa com o envelope da
D10. A mitigação que a D2 registra são duas linhas: **versão do cliente fixada**, e
**nenhum outro módulo importa `kubernetes` nem `urllib3`** — o mesmo teste que
falha diante de verbo de escrita falha diante desse import.

**Custo aceito:** dois contextos para criar e manter, e um README que manda
criá-los antes do primeiro uso.

## D9 · Ausente, nulo e vazio são a mesma coisa na fronteira

**Escolhido:** normalizar com `obj.get(campo) or []` no ponto de leitura. Nenhum
lugar do código testa presença de chave para decidir estado.

**Descartado — testar presença de chave.** **Ganha** expressividade aparente:
`"subsets" not in obj` lê como "não tem endereço". **Perde** por estar errado, e
isso está medido no mesmo Service:

```
Endpoints/nyx-api     : chave 'subsets'   AUSENTE
EndpointSlice do mesmo: chave 'endpoints' PRESENTE, valor null
```

Acerta num objeto e erra no outro.

**Descartado — deixar a biblioteca normalizar, com os modelos tipados.** **Ganha**
código mais curto. **Perde** a informação: os dois casos acima viram `None`. É a
mesma perda da D2, por outro caminho.

**Descartado — validar contra esquema e rejeitar o inesperado.** **Ganha** detecção
precoce de mudança de API. **Perde** o requisito central: uma tela que rejeita
objeto por forma inesperada é uma tela em branco com outro nome.

**A distinção que sobra, e que é a que importa.** Não é ausente contra zero —
`readyReplicas` ausente **significa** zero pronto. É **"o control plane afirmou
zero"** contra **"o control plane ainda não afirmou nada"**. Um Deployment criado
há três segundos também não tem `readyReplicas`, e pintá-lo de degradado é tão
falso quanto. Essa distinção se deriva de `observedGeneration`, das condições e da
idade do objeto — **nunca da forma do JSON**.

**Custo aceito:** `or []` é fácil de esquecer numa linha nova. O antídoto é teste, e
o motivo de acreditar que é preciso está registrado: **a armadilha foi cometida
dentro da própria verificação feita para demonstrá-la.** Ao conferir o campo
`series`, a verificação usou `i.get('series')`, viu `None` e reportou `series:
null` — o `.get()` colapsa ausente e nulo exatamente como o modelo tipado. Se ela
pega quem está olhando para ela de propósito, pega qualquer um.

## D10 · Envelope por tipo de recurso

**Escolhido:** cada tipo é lido de forma independente e devolve `ok`, `vazio`,
`negado` ou `indisponível`. A tela desenha os quatro.

**Descartado — `try/except` no ponto de uso.** **Ganha** menos estrutura para
escrever no começo. **Perde** por espalhar a degradação: cada painel trata a falha
do seu jeito, e o caso que ninguém lembrou vira tela em branco com traceback no
console — literalmente o que o enunciado recusa.

**Descartado — falhar a atualização inteira na primeira falha.** **Ganha**
simplicidade e consistência: ou a tela toda é do mesmo instante, ou não é nada.
**Perde** o requisito que o enunciado chama de mais interessante. Com o contexto
`platform-ro`, um 403 em `events` apagaria pods, controladores e services, que
estavam perfeitamente acessíveis.

**Herdado do Ticket 03, de propósito.** É o mesmo desenho do `nao_verificado`
daquele projeto: **registrar o "não sei" como dado, não como exceção.** Lá a coleta
gravava `null` no inventário e o avaliador traduzia em veredito; aqui a leitura
grava o envelope e a tela traduz em painel.

**Está medido, não suposto.** No mesmo cliente e na mesma sessão, com o contexto
`platform-ro-sem-events`: `events` devolveu 403 e `pods` devolveu três itens.

**Custo aceito:** cada painel da tela precisa saber desenhar quatro estados em vez
de um, inclusive os dois que quase nunca acontecem.

## D11 · Cluster de validação: os patológicos ficam

**Escolhido:** manter os três namespaces do Ticket 02 e acrescentar `nyx-dev`
(kube-news) e `orion-prod` (fake-shop).

**Descartado — limpar o cluster e subir só o que o Ticket 04 precisa.** **Ganha**
um ambiente limpo, sem herança, e menos coisa para explicar. **Perde** o dado de
teste mais caro que existe aqui: `CrashLoopBackOff` com `OOMKilled` real,
`ImagePullBackOff` em três réplicas, e um Service cujo seletor não casa. Fabricar
esses três de novo custa mais do que mantê-los, e o risco de mantê-los é zero,
porque os manifests estão versionados em `ticket-02-.../ambientes/` e voltam com um
`kubectl apply`.

**Descartado — validar só contra os três patológicos.** **Ganha** não precisar
subir workload nenhum. **Perde** o outro lado da comparação: sem workload saudável,
a spec especifica bem o anormal e mal o normal, e a ordenação da D7 não teria
contra o que se medir. O enunciado, aliás, exige os dois projetos.

**Custo aceito:** cinco namespaces de cliente no laboratório, imagens carregadas à
mão por `kind load` porque a regra 3.7 do padrão exige um registry que não existe,
e dois Secrets criados por linha de comando fora do Git.

**O que a amostra ficou tendo, e nenhuma alternativa daria:**

```
nyx-dev      deployment/nyx-api          1/1   saudavel, replica unica
nyx-prod     deployment/nyx-api          0/2   CrashLoopBackOff, OOMKilled
nyx-stg      deployment/nyx-api          2/2   pods ok, Service sem endereco
orion-prod   deployment/orion-web        2/2   saudavel, duas replicas + PDB
orion-stg    deployment/orion-web        0/3   ImagePullBackOff
nyx-dev      statefulset/nyx-postgres    1/1
orion-prod   statefulset/orion-postgres  1/1
```

O mesmo componente, `nyx-api`, existe em três ambientes e em três estados
distintos. Filtro por namespace e busca por nome passam a ter o que distinguir de
verdade, em vez de serem exercitados contra uma lista onde qualquer coisa serve.

---

## Achados sobre o enunciado e sobre o padrão

Coisas que a especificação encontrou e que não são decisão, mas ficariam perdidas
se não estivessem escritas.

**1. O enunciado nomeia cinco decisões, e a quinta é fácil de perder.** *"Quanto do
escopo entra na primeira fatia especificada e o que fica para depois"* vem no mesmo
parágrafo das outras quatro, sem destaque. Uma leitura apressada registra quatro.

**2. A armadilha do campo é enunciada com duas formas e tem três.** O texto fala de
ausente contra vazio. A API entrega ausente, nulo e vazio — e as três aparecem em
posições diferentes do mesmo projeto: `subsets` ausente, `endpoints` nulo,
`eventTime` nulo, `series` ausente.

**3. A premissa do enunciado sobre o fake-shop já estava vencida.** Ele diz que o
projeto *"não expõe endpoint de saúde"*, e usa isso para levantar a pergunta sobre
o quanto a tela pode afirmar. A leitura feita no Ticket 01 mostrou que ele tem
`/metrics`, servido pelo `prometheus_flask_exporter` — e os manifests gerados lá
têm as três probes. Quem exemplifica a pergunta hoje é o `orion-web` do
`orion-stg`, que não tem probe nenhuma.

**4. A lacuna 2 do padrão de manifests tem duas formas, e a segunda é pior.** O
padrão não trata de dependência que falha na inicialização. O kube-news morre por
`unhandled rejection` e o Kubernetes reinicia até o banco existir — ruidoso, mas
converge. O fake-shop não tem `set -e` no `entrypoint.sh`: o `flask db upgrade`
falha, o gunicorn sobe mesmo assim contra banco sem tabela, e o pod fica `Running`
com **zero reinícios e zero eventos**, sem nunca ficar pronto. Só a prontidão
denuncia, e só porque o alvo escolhido no Ticket 01 foi `/`, que toca o banco.

Esse caso é o argumento mais forte a favor da D7 que não veio da D7: é o pod em que
`phase` e `restartCount` não dizem nada, e um dashboard que mostrasse só esses dois
o pintaria de saudável.
