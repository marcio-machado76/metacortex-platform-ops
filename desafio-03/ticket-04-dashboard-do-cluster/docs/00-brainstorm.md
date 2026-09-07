# Brainstorm — o que foi maturado antes de existir documento

Registro do que a conversa de amadurecimento produziu, antes de qualquer
especificação e muito antes de qualquer código. As decisões do
`02-decisoes-tecnicas.md` só fazem sentido com as perguntas e as medições que as
originaram, e estão aqui.

Toda medição citada traz o comando que a reproduz. Foram feitas contra o cluster
`kind-metacortex-lab`, servidor `v1.31.0`, com os três chamados do Ticket 02 no
ar.

## O problema, em uma frase

Uma aplicação de terminal que roda na estação de quem opera, lê o contexto
corrente do kubeconfig e mostra numa tela o retrato de um namespace — os seis a
dez `kubectl` que abrem todo chamado — sem nunca escrever no cluster e sem mentir
quando a API não responde, a credencial expira ou falta permissão para um tipo de
recurso.

## O que o enunciado já fecha, e o que ele deixa aberto

**Fechado:** o conteúdo mínimo da tela (namespaces; pods com estado, reinícios e
motivo em falha; deployments prontos sobre desejados; services com ou sem
endpoint; eventos recentes do namespace selecionado), filtro por namespace e busca
por nome, o contexto corrente e só ele, os três ambientes hostis, e o invariante
de só leitura com garantia visível no projeto.

**Aberto, e nomeado como decisão a registrar.** São **cinco**, não quatro — a da
primeira fatia é fácil de perder porque vem no mesmo parágrafo das outras:

1. Linguagem e stack, sabendo que quem mantém é time de infraestrutura
2. Como falar com a API: cliente oficial, `kubectl` como subprocesso, ou HTTP direto
3. Como atualizar a tela, e o custo de cada opção em **carga sobre o apiserver,
   complexidade e atraso** — três eixos que não apontam para o mesmo lado
4. Quanto do escopo entra na primeira fatia e o que fica para depois
5. `Endpoints` ou `EndpointSlice`, "com consequência de durabilidade"

**Aberto e não nomeado** — o que a conversa encontrou:

1. **A forma da tela não está no enunciado.** Ele diz "aplicação que roda na
   máquina de quem opera", nunca web nem terminal. É o garfo que determina o resto,
   e estava escondido dentro da decisão 1.
2. **A armadilha do campo tem três formas, não duas.** O enunciado planta
   ausente-vs-vazio. A realidade entrega ausente, nulo e vazio.
3. **Os eventos têm o mesmo garfo do `Endpoints`, e ele responde ao contrário.**
4. **O motivo da falha não está onde se olha primeiro.** `state` diz o quê;
   `lastState` diz o porquê.
5. **Metade do workload de validação não é Deployment.** O postgres do fake-shop
   é StatefulSet.
6. **O cenário da credencial expirada não sai de graça no kind.** Cluster morto é
   trivial e permissão parcial se monta com RBAC; certificado vencido precisa ser
   fabricado.

## A medição que decidiu duas coisas de uma vez

O mesmo Service sem endereço, nos dois objetos que descrevem endereço:

```bash
kubectl get endpoints nyx-api -n nyx-stg -o json
kubectl get --raw "/apis/discovery.k8s.io/v1/namespaces/nyx-stg/endpointslices"
```

| Objeto | Como expressa "sem endereço" |
|---|---|
| `Endpoints/nyx-api` | chave `subsets` **ausente** — o JSON traz só `apiVersion`, `kind` e `metadata` |
| `EndpointSlice` do mesmo Service | chave `endpoints` **presente, com valor `null`** |

E o Deployment do Chamado 2, no mesmo cluster:

```bash
kubectl get deploy orion-web -n orion-stg -o json   # status: sem readyReplicas
```

Daí sai a regra que atravessa o projeto inteiro: **nunca testar presença de chave
para decidir estado.** `"subsets" not in obj` acerta no `Endpoints` e erra no
`EndpointSlice`; `obj.get("endpoints") or []` acerta nos dois.

Isso também mata uma leitura fácil e errada da armadilha. "Tratar ausência como
zero faz a tela mentir" não é bem o caso: `readyReplicas` ausente **significa**
zero pronto. A mentira está noutro lugar — um Deployment criado há três segundos
também não tem `readyReplicas`, e pintá-lo de "0/3 degradado" é falso do mesmo
jeito. **A distinção que importa não é ausente-vs-zero, é "o control plane afirmou
zero" contra "o control plane ainda não afirmou nada"** — e essa se deriva de
`observedGeneration`, das condições e da idade do objeto, nunca da forma do JSON.

## A gêmea dos eventos, que responde ao contrário

O `EndpointSlice` é o substituto moderno e é melhor. Por simetria, esperava-se que
`events.k8s.io/v1` fosse o mesmo caso. Não é.

```bash
kubectl get --raw "/apis/events.k8s.io/v1/namespaces/nyx-prod/events"
```

| `core/v1` | `events.k8s.io/v1` |
|---|---|
| `message` | `note` |
| `involvedObject` | `regarding` |
| `count` | **`deprecatedCount`** |
| `firstTimestamp` / `lastTimestamp` | **`deprecatedFirstTimestamp`** / **`deprecatedLastTimestamp`** |
| `source` | **`deprecatedSource`** |

A API nova marca como *deprecated* exatamente os quatro campos que uma triagem
usa — a contagem de repetição e a janela em que o evento aconteceu. O substituto
declarado desses campos é `series`, e a medição fecha o argumento:

```
total de eventos no nyx-prod: 3
com series preenchido:        0   (a chave está ausente nos três)
com deprecatedCount > 1:      3   (105, 2429 e 2420)
reportingController:          kubelet nos três
```

**O kubelet ainda escreve pelo caminho da `core/v1`.** Então os eventos que mais
importam numa triagem — os de `BackOff`, os do kubelet — são precisamente os que
chegam sem `series`, com a repetição registrada só no campo `deprecated*`. Ler
pela API nova hoje significa ler o campo desencorajado ou perder a contagem.

Repare que a chave `series` está **ausente**, não vazia nem nula: é a mesma
ausência do `subsets`, numa terceira posição do projeto. A regra da seção anterior
vale aqui sem mudança.

O par vira o argumento da decisão, não uma inconsistência: **"prefira a API mais
nova" não é princípio, é heurística que se verifica caso a caso.** No mesmo ticket
ela acerta uma vez e erra a outra.

## O princípio herdado do Ticket 03

O requisito mais difícil do enunciado — permissão negada para **um** tipo de
recurso enquanto os outros funcionam — é o mesmo problema que o Ticket 03 já
resolveu com `nao_verificado`: **registrar o "não sei" como dado, não como
exceção.**

Cada tipo de recurso volta num envelope com quatro estados possíveis — `ok`,
`vazio`, `negado`, `indisponível` — e a tela desenha os quatro. Com isso a
degradação graciosa deixa de ser `try/except` espalhado e vira consequência da
estrutura: um 403 em `events` preenche o envelope de eventos e não toca nos
outros.

E é esse requisito que decide como falar com a API. Cada opção resolve dois dos
três problemas; só uma resolve os três:

| Opção | JSON com a forma original | Erro estruturado (403 ≠ 401 ≠ rede) | kubeconfig/auth resolvido |
|---|---|---|---|
| `kubectl` como subprocesso | sim | **não** — classificar erro vira regex em texto de stderr | sim |
| HTTP direto | sim | sim | **não** — reimplementar contexto, certificado, CA e *exec plugins* |
| Cliente oficial, modelos tipados | **não** — ausente e `null` viram o mesmo `None` | sim | sim |
| Cliente oficial, `_preload_content=False` | sim | sim | sim |

## Relatar sem opinar, e o terceiro caminho

O enunciado levanta uma pergunta e não responde: *quanto o dashboard pode afirmar
sobre a saúde de um objeto a partir do que a API devolve*. O cluster responde por
ele:

```bash
kubectl get pod -n orion-stg -l app=orion-web -o json   # container web: NENHUMA PROBE
kubectl get pod -n nyx-prod  -l app=nyx-api   -o json   # container api: só readinessProbe
```

Sem probe nenhuma, o `Ready` do `orion-web` significa apenas "o processo subiu".
Uma coluna "saudável" mentiria com autoridade — e mentir com autoridade é pior do
que não dizer nada.

A conversa separou duas coisas que pareciam uma só. **Ordenar não é opinar sobre
saúde, é opinar sobre onde olhar primeiro** — e isso a ferramenta pode fazer,
desde que o critério apareça na tela: reinícios maiores que zero, prontos menores
que desejados, sem endereço, eventos de tipo `Warning`. Todos são dados da API,
então a ordem é auditável por quem discorda dela.

E existe um terceiro caminho que nenhuma das duas posturas cobria: **mostrar que o
objeto não tem probe.** É fato da API, não juízo, e vem de graça no `spec` do Pod
que a tela já lista. Permite a quem lê descontar o `Ready` sozinho — responde à
pergunta do enunciado sem a tela afirmar nada sobre saúde.

Da mesma família, o motivo da falha:

```
nyx-prod/nyx-api  state    : waiting.reason  = CrashLoopBackOff
                  lastState: terminated.reason = OOMKilled, exitCode 137
                  restartCount: 105
```

Um dashboard que só lê `state` mostra "CrashLoopBackOff" e 105 reinícios, que é a
informação inútil: quem tria já sabe que está reiniciando — quer o `OOMKilled`.

## A garantia de só-ler precisa de dois contextos, não de um

A garantia tem três camadas que se somam: um ponto único de acesso à API (nenhum
outro módulo importa o cliente), um teste que falha se aparecer verbo de escrita,
e execução real sob RBAC restrito.

A terceira começou como uma ideia de matar dois requisitos com um tiro — um
ServiceAccount sem permissão para `events` provaria o só-leitura e seria o cenário
de permissão parcial. **A ideia estava errada por um motivo simples:** os eventos
são requisito explícito da tela. Um contexto recomendado que nega `events` entrega
uma ferramenta que não faz o que foi pedida para fazer.

São dois contextos, com papéis distintos:

| Contexto | Papel | Perfil |
|---|---|---|
| `platform-ro` | o jeito **documentado** de rodar | leitura em tudo que a tela usa, inclusive `events`. Nunca `secrets` |
| `platform-ro-sem-events` | só cenário de evidência | o mesmo, menos `events` |

O primeiro é a garantia, o segundo é a demonstração. E negar `secrets` no perfil
recomendado é de graça: a tela nunca lê secret, então a restrição não custa nada e
faz parte de "a garantia visível no projeto".

E há um efeito que só apareceu ao escrever o perfil: **o `platform-ro` não concede
`watch`.** Com isso a D3 deixa de ser afirmação num documento e vira coisa que o
cluster recusaria. Se alguém trocar o intervalo fixo por watch sem reabrir a
decisão, não é o código que reclama — é o apiserver. A decisão de desenho passa a
ter quem a defenda depois que a conversa que a produziu for esquecida.

```bash
kubectl auth can-i watch pods --as=system:serviceaccount:kube-system:platform-ro -n nyx-prod
# no
```

A diferença entre "contexto de evidência" e "contexto recomendado" é o que muda o
peso da garantia. Se o RBAC restrito for só o cenário de teste, o só-leitura
continua sendo promessa do código. Sendo o jeito documentado de rodar — README
manda criar o contexto, e o de admin é acidente —, quem aplica a garantia passa a
ser o cluster.

## As decisões

A justificativa estendida de cada uma, com pelo menos duas alternativas
descartadas e o que se ganha e se perde em cada caminho, é o
`02-decisoes-tecnicas.md`. Aqui fica o resultado e a alternativa que mais custou a
descartar.

| # | Decisão | Escolha | Principal alternativa descartada, e por quê |
|---|---|---|---|
| D1 | Linguagem e stack | Python + Textual (TUI) | **Web local (FastAPI)**: sobe servidor HTTP na estação com a credencial de produção atrás, para uma ferramenta que só lê. E snapshot de TUI é texto — versiona e diffa em PR; PNG ninguém revisa |
| D2 | Acesso à API | cliente oficial `kubernetes`, `_preload_content=False`, versão fixada | **`kubectl` como subprocesso**: morre no requisito mais difícil — distinguir 403 em um tipo de "cluster não responde" viraria regex em mensagem de erro |
| D3 | Atualização da tela | intervalo fixo escopado ao namespace + refresh manual; watch fora da v1 | **Watch**: ganha no eixo de carga, perde no de manutenção. Resync, `410 Gone` e bookmarks é o código que um time de infra herda e não mexe |
| D4 | Primeira fatia | o mínimo do enunciado + StatefulSet | **Só Deployment**: o enunciado diz "no mínimo", o que autoriza o acréscimo; sem ele metade do workload de validação aparece como pod sem controlador. DaemonSet fica fora |
| D5 | Endereços | `EndpointSlice`, agregado por `kubernetes.io/service-name` | **`Endpoints`**: além da aposentadoria, embaralha "sem endereço" e "endereço não pronto", que no cluster são dois chamados diferentes |
| D6 | Eventos | `core/v1` | **`events.k8s.io/v1`**: marca como `deprecated*` os campos que a triagem usa, e o kubelet ainda escreve pela `core/v1` — medido |
| D7 | Relatar ou opinar | relata o vocabulário da API; ordena por anormalidade com o motivo visível; mostra ausência de probe | **Coluna de severidade derivada**: afirmaria saúde que a API não dá — o `orion-web` sem probe prova que `Ready` não sustenta a afirmação |
| D8 | Garantia de só-ler | ponto único de acesso + teste contra verbo de escrita + dois contextos RBAC | **Um contexto só, sem `events`**: negaria um requisito explícito da tela. O ponto único acumula um segundo papel — ver "A fronteira de contenção" |
| D9 | Ausente, nulo e vazio | normaliza com `or []` na fronteira; nunca testa presença de chave | **Testar presença de chave**: medido errando entre `Endpoints` e `EndpointSlice`, e de novo em `series` |
| D10 | Falha por tipo de recurso | envelope `ok · vazio · negado · indisponível` | **`try/except` no ponto de uso**: espalha a degradação e deixa a tela em branco quando alguém esquece um caso |
| D11 | Cluster de validação | mantém os três namespaces do Ticket 02; fake-shop em `orion-prod`, kube-news em `nyx-dev` | **Limpar o cluster**: jogaria fora os três estados patológicos, que são o dado de teste mais caro que existe aqui |

## O que ficou explicitamente para depois

- **Hipótese ainda não medida:** que `_preload_content=False` continua levantando
  `ApiException` com `.status` preenchido num 403. **A D2 inteira depende disso.**
  Se falhar, a escolha vira `kubectl` como subprocesso e a classificação de erro
  precisa de outro desenho. É a primeira coisa a rodar antes de a spec fechar.
  **Medida e confirmada logo depois deste documento — ver a última seção.**
- **Como fabricar a credencial expirada.** Cluster inalcançável e permissão parcial
  saem do ambiente; certificado vencido ou token inválido precisa ser construído de
  propósito. Fica registrado como decisão de evidência para não virar o cenário que
  ninguém testa — e é justamente ele que prova a distinção que a D2 comprou:
  401 ≠ 403 ≠ conexão recusada.
  **Fabricado e medido depois deste documento — ver a última seção. O resultado
  contraria o que se esperava dele.**
- **"Eventos recentes" não está definido** — janela de tempo, ordenação (a API não
  devolve ordenado) e o TTL de eventos deste apiserver, que precisa ser medido e
  não assumido.
- **O intervalo concreto de atualização**, em segundos. Detalhe de execução.
- **Ausência de probe num pod com mais de um container** — como agrega na linha do
  pod. O `Ready` do pod é o E lógico dos containers; a ausência de probe não é.
- **Layout da tela** — visão única com painéis ou navegação entre telas. Não muda
  direção; entra no documento de comportamento.
- **Nome do comando empacotado.** O Ticket 03 entregou `inventario-vm`.

Adiados por estarem fora do escopo declarado: watch, multicluster, logs,
`describe`, visualização de YAML, nós e métricas.

## O que aconteceu com as duas skills durante o brainstorm

Entradas para o registro que o Ticket 04 pede como entregável. O log consolidado é
outro documento; estas são as que aconteceram antes de existir código.

- **`triagem-de-cluster` não disparou, e é o comportamento certo.** O assunto do
  dashboard *é* pod reiniciando, deployment em 0/N e Service sem endpoint — as
  frases-gatilho dela. Mas o critério da skill é o objeto já estar rodando e
  apresentando problema, e aqui os mesmos objetos foram lidos como **dado de
  projeto**, não como chamado. O falso-positivo foi previsto como hipótese no
  começo da conversa e não se confirmou.
- **`padrao-de-manifests` não disparou, e também é o comportamento certo.** Os
  manifests do `orion-prod` foram lidos, e as regras 1.2 e 3.7 entraram na
  conversa. O gatilho dela é escrever manifesto novo ou conferir manifesto
  existente; **ler manifesto para decidir arquitetura de outra coisa não é nem um
  nem outro.**
- **A entrada anterior ao ticket continua valendo:** o servidor MCP estava
  explicitamente desabilitado em `settings.local.json`, e o sintoma era "nenhum
  servidor configurado" — que parece ausência de configuração e não recusa de
  autorização. Ferramenta ausente por um motivo que não aparece onde a falha se
  manifesta.

## Depois do brainstorm — a hipótese da D2, medida

Esta seção foi acrescentada depois de o documento ser commitado. O que está
acima não foi reescrito: o ponto em aberto continua registrado como estava, e a
resolução vem aqui, porque a ordem em que se soube das coisas é parte da
evidência.

A hipótese se confirmou nos três cenários, e a D10 saiu provada de brinde — no
mesmo cliente e na mesma sessão, `events` devolveu 403 e `pods` devolveu três
itens.

| Cenário | Medido |
|---|---|
| 403, `platform-ro-sem-events` lendo `events` | `ForbiddenException`, `.status = 403` |
| 401, token inválido | `UnauthorizedException`, `.status = 401` |
| Conexão recusada | `urllib3.exceptions.MaxRetryError`, sem `.status` |

Evidência crua em `evidencias/hipotese-d2-excecoes.stdout.txt`, leitura em
`evidencias/hipotese-d2-excecoes.md`, script em
`verificacoes/verificar-hipotese-d2.py`, perfis RBAC em `rbac/`.

**Uma frase da conversa era larga demais e a medição a estreita.** Foi dito que
`_preload_content=False` seria a única forma de atender aos dois requisitos
difíceis ao mesmo tempo. Não é: o modelo tipado levanta a mesma exceção com o
mesmo `.status`. O tratamento de erro sai de graça nos dois modos, e o modo cru
compra **uma** coisa — a forma do JSON. A tabela da D2 já dizia isso
corretamente; a frase, não. A escolha não muda, a justificativa fica mais
estreita e mais honesta.

Duas consequências de desenho que só apareceram rodando:

- O cliente levanta **subclasses tipadas** (`ForbiddenException`,
  `UnauthorizedException`), então o envelope da D10 ramifica por tipo de exceção
  em vez de comparar `.status` com número mágico.
- A falha de conexão vem do `urllib3`, **dependência transitiva**. O ponto único
  de acesso captura três famílias de exceção, e uma delas não pertence à
  biblioteca que a D2 escolheu.

E uma entrada para o log que é do assunto do ticket: ao conferir o campo `series`
dos eventos, a verificação usou `i.get('series')`, viu `None` e reportou
`series: null`. **O `.get()` colapsa ausente e nulo no mesmo `None` — a mesma
perda que o modelo tipado provoca, que é o motivo da D2.** O teste certo é
`'series' in i`, e ele mostra a chave **ausente** nos três eventos. A conclusão da
D6 não muda; a lição é que a armadilha do ticket foi cometida dentro da
verificação feita para demonstrá-la. Se ela pega quem está olhando para ela de
propósito, um `or []` distraído no código de renderização é questão de tempo.

## A fronteira de contenção

Três riscos de durabilidade se acumularam durante a verificação, e o mitigante é o
mesmo para os três:

| Risco | O que pode mudar debaixo do projeto |
|---|---|
| `_preload_content` | é API com sublinhado — convenção de privado. Nada garante que sobreviva a uma versão maior do cliente |
| `urllib3.exceptions.MaxRetryError` | vem de uma **dependência transitiva**, que a D2 não escolheu e não controla |
| `Endpoints` | já está em trilha de aposentadoria, e o `EndpointSlice` que o substitui tem forma diferente |

O ponto único de acesso à API da D8 nasceu como o lugar onde a garantia de
só-leitura mora. Ele acumula um segundo papel, e vale dizer isto explicitamente
porque muda o que se cobra dele numa revisão: **é a fronteira de contenção de tudo
que pode mudar debaixo do projeto.** Os três riscos acima ficam confinados a um
módulo, e o resto do código conversa com o envelope da D10, não com o cliente.

A mitigação que a D2 registra, em duas linhas:

- **versão do cliente fixada** em `requirements.txt`, como o Ticket 03 fez com o
  Paramiko;
- **nenhum outro módulo importa `kubernetes` nem `urllib3`** — o mesmo teste que
  falha diante de verbo de escrita falha diante desse import.

O teste da D8 passa a provar duas coisas com o mesmo mecanismo: que ninguém
escreve no cluster, e que ninguém fura a fronteira.

## O cenário 6 — a suposição sobre a credencial expirada estava errada

O 401 do cenário 3 usa token inválido. Mas o kubeconfig do `kind` autentica por
**certificado de cliente**, e a expectativa registrada era esta: certificado
vencido não produziria 401, quebraria no handshake TLS antes de existir resposta
HTTP, caindo no mesmo balde da conexão recusada. Se fosse assim, distinguir
"credencial expirada" de "cluster que não responde" — que o enunciado exige —
teria de sair da mensagem interna da exceção, não do tipo. Seria decisão de
desenho, não detalhe.

Foi fabricado um certificado de cliente assinado pela CA do cluster, com validade
em 2020:

```
validade: notBefore=Jan  1 00:00:00 2020 GMT  notAfter=Jan  2 00:00:00 2020 GMT
```

**A medição contraria a expectativa:**

```
tipo da excecao : kubernetes.client.exceptions.UnauthorizedException
.status         : 401
mesmo TIPO do cenario 4 (conexao recusada)?  False
```

O handshake TLS **completa**. O apiserver pede o certificado de cliente em vez de
exigi-lo — é o que permite que token e certificado convivam no mesmo endpoint — e
então a verificação falha na camada de autenticação, não na de transporte. O
pedido chega como anônimo, e anônimo é 401.

Consequência para o desenho, e é boa: **os três ambientes hostis do enunciado se
separam por tipo de exceção, sem ler mensagem nenhuma.**

| Ambiente hostil | Como chega |
|---|---|
| Permissão negada num tipo | `ForbiddenException`, `.status = 403` |
| Credencial expirada ou inválida | `UnauthorizedException`, `.status = 401` |
| Cluster que não responde | `urllib3.exceptions.MaxRetryError` |

Duas ressalvas que ficam registradas para não virarem surpresa:

- **401 não separa "expirada" de "inválida".** As duas formas produzem o mesmo
  status e o mesmo corpo. Para a tela isso não é problema — as duas dizem "sua
  credencial não serve" e pedem a mesma ação — mas a tela não deve afirmar
  *expirada*, porque não é isso que ela sabe.
- **A conclusão vale para este apiserver.** Um proxy à frente do cluster exigindo
  mTLS quebraria no transporte, como a expectativa original previa. O ponto único
  de acesso continua tendo que tratar a família de erro do transporte; o que muda é
  que ela não é o caminho normal da credencial vencida.
