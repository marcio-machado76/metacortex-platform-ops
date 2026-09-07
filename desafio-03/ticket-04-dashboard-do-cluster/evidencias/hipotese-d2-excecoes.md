# A hipótese que a D2 dependia, medida

Saída crua em `hipotese-d2-excecoes.stdout.txt`, código de saída em
`.rc.txt`. Reproduz com:

```bash
cd desafio-03/ticket-04-dashboard-do-cluster
kubectl apply -f rbac/platform-ro.yaml -f rbac/platform-ro-sem-events.yaml
./.venv/bin/python verificacoes/verificar-hipotese-d2.py
```

O cenário 6 precisa de um certificado de cliente vencido, assinado pela CA do
cluster. Ele **não é versionado** — a chave da CA não sai do laboratório. O
cabeçalho de `verificacoes/verificar-hipotese-d2.py` traz os comandos que o
geram, e sem as variáveis de ambiente o cenário é pulado com aviso na saída, em
vez de fingir que passou.

Ambiente: cliente `kubernetes` 36.0.3, Python 3.10.12, contra o
`kind-metacortex-lab` (servidor v1.31.0).

## O que estava em aberto

O `00-brainstorm.md` fechou a D2 — cliente oficial com `_preload_content=False` —
sobre uma hipótese que não tinha sido medida: que a exceção continua carregando
`.status` quando o conteúdo não é pré-processado. Se falhasse, a decisão caía
inteira e a escolha voltaria para `kubectl` como subprocesso.

## Resultado

| Cenário | Esperado | Medido | Veredito |
|---|---|---|---|
| 403 — `platform-ro-sem-events` lendo `events` | `ApiException.status == 403` | `ForbiddenException`, `.status = 403` | confirma |
| Mesmo cliente lendo `pods` | sucesso | 3 itens, resposta crua | confirma |
| 401 — token inválido | `.status == 401`, distinto do 403 | `UnauthorizedException`, `.status = 401` | confirma |
| Conexão recusada | tipo diferente, não `ApiException` | `urllib3.exceptions.MaxRetryError` | confirma |
| Forma do JSON, cru contra tipado | cru preserva, tipado colapsa | ver abaixo | confirma |
| Certificado de cliente vencido | quebra no handshake TLS, mesmo balde da conexão recusada | `UnauthorizedException`, `.status = 401` | **refuta** |

**A D2 fica de pé.** E a D10 sai provada junto: no mesmo cliente e na mesma
sessão, `events` devolveu 403 e `pods` devolveu três itens. A degradação parcial
não é hipótese de desenho, é comportamento observado.

## O cenário 5, que é o coração da decisão

```
Endpoints/nyx-api  cru    : chaves de topo = ['metadata']
                            'subsets' presente? False
EndpointSlice      cru    : 'endpoints' presente? True | valor = None

Endpoints/nyx-api  tipado : .subsets   = None
EndpointSlice      tipado : .endpoints = None
```

No JSON cru, "a chave não veio" e "a chave veio nula" continuam sendo dois fatos
distintos. No modelo tipado viram o mesmo `None`. É exatamente a perda que a D2
existe para evitar.

## Três coisas que a medição acrescentou

**1. Um argumento meu era largo demais, e a medição o estreita.** Durante o
brainstorm eu disse que `_preload_content=False` era a única forma de atender aos
dois requisitos difíceis ao mesmo tempo. Não é: o modelo tipado levanta a **mesma
exceção, com o mesmo `.status`** (linhas `[1a]` e `[1b]` da saída, idênticas). O
tratamento de erro sai de graça nos dois modos. **`_preload_content=False` compra
uma coisa, não duas** — a forma do JSON. A tabela da decisão já dizia isso
corretamente; a frase da conversa, não. A escolha não muda; a justificativa fica
mais honesta.

**2. O cliente levanta subclasses tipadas.** Não é `ApiException` genérica: é
`ForbiddenException` no 403 e `UnauthorizedException` no 401. O envelope da D10
pode ramificar por **tipo de exceção**, que é mais legível do que comparar
`.status` com número mágico.

**3. A falha de conexão não vem do cliente oficial.** `MaxRetryError` é do
`urllib3`, dependência transitiva. O ponto único de acesso à API precisa capturar
**três famílias**, e uma delas não pertence à biblioteca que a D2 escolheu — o que
é justamente o tipo de detalhe que só aparece rodando, e que teria virado um
`except` faltando na validação.

## O erro cometido dentro da própria verificação

Vale registrar porque é do assunto do ticket, não um deslize lateral.

Ao conferir se o campo `series` dos eventos vinha preenchido, a verificação usou
`i.get('series')`, viu `None` e concluiu `series: null`. **O `.get()` colapsa
ausente e nulo no mesmo `None` — exatamente a perda que o modelo tipado provoca, e
que é o motivo da D2.** O teste correto é `'series' in i`, e ele mostra que a
chave está **ausente** nos três eventos do `nyx-prod`, com `deprecatedCount`
preenchido e `reportingController: kubelet` nos três.

A conclusão sobre a D6 não muda — o campo continua vazio onde o dado existe. O que
muda é a lição: **a armadilha do ticket foi cometida dentro da verificação feita
para demonstrá-la.** Se ela pega quem está olhando para ela de propósito, um
`or []` distraído no código de renderização é questão de tempo. Isso reforça a
D9 e vira material para o `02-decisoes-tecnicas.md`.

Nota sobre reprodutibilidade: os valores de `deprecatedCount` crescem enquanto o
`nyx-api` reinicia (foram lidos em 105/2429/2420 e depois em 105/2476/2467). A
alegação reproduzível não são os números, é a forma: **zero eventos com `series`,
todos com `deprecatedCount` maior que um, todos do kubelet.**

## O cenário 6, que refutou a própria expectativa

A expectativa registrada era que certificado de cliente vencido não produzisse
401: quebraria no handshake TLS, antes de existir resposta HTTP, chegando como
`MaxRetryError` embrulhando um `SSLError` — o mesmo tipo da conexão recusada. Se
fosse assim, distinguir "credencial expirada" de "cluster que não responde"
dependeria de ler a mensagem interna da exceção.

Certificado assinado pela CA do cluster, válido por um dia de 2020:

```
validade: notBefore=Jan  1 00:00:00 2020 GMT  notAfter=Jan  2 00:00:00 2020 GMT

tipo da excecao : kubernetes.client.exceptions.UnauthorizedException
.status         : 401
mesmo TIPO do cenario 4 (conexao recusada)?  False
```

O handshake completa. O apiserver **pede** o certificado de cliente em vez de
exigi-lo — é o que permite token e certificado no mesmo endpoint — então a
verificação falha na camada de autenticação e o pedido chega como anônimo.
Anônimo é 401.

Os três ambientes hostis do enunciado se separam por tipo de exceção, sem ler
mensagem nenhuma:

| Ambiente hostil | Como chega |
|---|---|
| Permissão negada num tipo | `ForbiddenException`, `.status = 403` |
| Credencial expirada ou inválida | `UnauthorizedException`, `.status = 401` |
| Cluster que não responde | `urllib3.exceptions.MaxRetryError` |

Duas ressalvas: **401 não separa "expirada" de "inválida"** — mesmo status, mesmo
corpo —, então a tela não deve afirmar *expirada*, porque não é isso que ela sabe.
E a conclusão vale para este apiserver: um proxy exigindo mTLS quebraria no
transporte, como a expectativa original previa. O tratamento da família de erro do
transporte continua necessário; o que mudou é que ela não é o caminho normal da
credencial vencida.
