# Divergências da implementação

O que apareceu quando os artefatos foram entregues a quem não participou de
escrevê-los. Cada onda de implementação roda em **contexto frio**: o agente lê os
documentos e mais nada, e o que ele precisa decidir sozinho é o buraco da
especificação aparecendo.

Registrado por onda, na ordem em que aconteceu.

---

# Grupos 1, 2 e 3 — estrutura, fixtures e fronteira de leitura

Implementado em contexto frio, a partir de `01-comportamento.md`,
`02-decisoes-tecnicas.md` e dos artefatos do OpenSpec.

## O que a spec não respondia

### 1. Onde vive o encerramento com código 2

A tarefa 3.7 pede o código de saída 2 para "sem kubeconfig legível", e está no
grupo da fronteira de leitura. Mas encerrar processo parece papel do ponto de
entrada, que é o grupo 9.

**Resolvido em `cliente.py`**, levantando `SystemExit(2)` com mensagem em stderr e
sem rastreamento de pilha. Quando o grupo 9 for feito, o ponto de entrada deve
**deixar a exceção propagar**, não reimplementar a lógica.

**Isto é um defeito de ordenação das tarefas, não do desenho.** A tarefa foi posta
no grupo errado; o comportamento está certo onde ficou.

### 2. O texto do motivo no envelope

Nenhum artefato define a string que a fronteira põe no campo `motivo`. O
`01-comportamento.md` traz os textos ("sem permissão para ler eventos") como
responsabilidade **da tela**, não da fronteira.

**Resolvido** com motivo curto e voltado a máquina na fronteira, deixando a frase
final para a camada de tela. A única restrição que a spec de fato impõe — não
afirmar que a credencial está expirada — está coberta e testada.

### 3. `ApiException` que não é 401 nem 403

O `design.md` mapeia três exceções. Um 5xx do apiserver não é nenhuma das três, e
nenhuma tarefa o cobre.

**Resolvido** capturando também o caso genérico e devolvendo `indisponível` com o
status HTTP no motivo, em vez de deixar a exceção escapar. A justificativa vem de
dois invariantes que já estavam escritos: *nenhuma falha esvazia a tela* e *nenhum
rastreamento chega ao terminal*.

**Aceito, e com dívida registrada:** o comportamento existe mas não tem teste
dedicado. Foi acrescentada a tarefa 8.5 para cobri-lo.

### 4. Granularidade das fixtures

As tarefas do grupo 2 falam em "capturar o pod X", no singular. A fronteira,
porém, devolve sempre um envelope por **tipo e namespace**, nunca um objeto
isolado.

**Resolvido** capturando o `LIST` inteiro do tipo no namespace. É a granularidade
que o código realmente recebe; fixture de objeto único testaria uma forma que
nunca chega.

## O que a implementação descobriu e a spec não sabia

### 5. `kubectl -o json` não devolve o que a fronteira recebe

A tarefa 2.7 manda registrar o comando que reproduz cada captura, e o caminho
óbvio seria `kubectl get -o json`. Ele **omite `managedFields`**; a leitura crua
que o projeto usa, não.

```
kubectl get pods -n nyx-prod -o json          | grep -c managedFields  -> 0
kubectl get --raw "/api/v1/namespaces/nyx-prod/pods" | grep -c managedFields  -> 1
```

**Resolvido** capturando pelo próprio cliente, do jeito que a fronteira lê, e
registrando `kubectl get --raw` como o equivalente reproduzível. Fixture capturada
por `kubectl -o json` seria uma forma que o código nunca vê — exatamente o defeito
que a decisão D-B do `design.md` existe para evitar, aparecendo por um caminho que
a decisão não previu.

### 6. A regra de fronteira precisa dizer "em `src/`"

Encontrado na conferência, não pelo agente. A D8 e a spec dizem que **nenhum outro
módulo** importa `kubernetes` ou `urllib3`. Mas o teste da fronteira precisa
importar os tipos de exceção para simular o transporte — e importa.

Como está escrita, a regra reprovaria o próprio teste que a verifica. **A intenção
sempre foi sobre código de produção.** A tarefa 8.2 foi ajustada para dizer
`src/`, antes que a onda que a implementa tropece nisso.

## Erros e contradições nos artefatos

### 7. "Seis tipos" contra "sete tipos"

O `proposal.md` dizia *"Seis tipos de recurso lidos por `LIST`"*. A spec e as
tarefas dizem sete: seis no namespace mais os namespaces, que também passam por
`LIST` e também precisam de envelope.

**Corrigido no `proposal.md`**, com nota dizendo o que estava errado. O erro era do
documento: a contagem esqueceu que a lista de namespaces não é privilegiada — ela
tem os mesmos quatro estados de envelope que os outros tipos, inclusive `negado`,
que é o caso de quem não pode listar namespaces.

## O que rodou

Conferido de forma independente, não aceito do relatório:

```
22 passed in 0.25s
importa kubernetes ou urllib3: src/painel_cluster/cliente.py (e o teste da fronteira)
verbos de escrita em src/: nenhum
caixas marcadas: 17 de 62  (grupos 1, 2 e 3 completos)
```

As quatro armadilhas do ticket sobreviveram intactas à captura:

```
deploy/orion-web  (orion-stg)  'readyReplicas' presente? False
sts/nyx-postgres  (nyx-dev)    'conditions'    presente? False
Endpoints/nyx-api (nyx-stg)    'subsets'       presente? False
slice   /nyx-api  (nyx-stg)    'endpoints'     presente? True | valor: None
pod/nyx-api       (nyx-prod)   state: CrashLoopBackOff | lastState: OOMKilled
```

A suíte foi rodada também com o socket bloqueado, e passou igual — a ausência de
rede é prova, não suposição.

---

# Grupos 4, 5 e 6 — a camada de interpretação

Segunda onda em contexto frio. O agente leu os documentos, o código da fronteira e
as oito fixtures, e escreveu `modelo.py` inteiro.

## O erro do documento que esta onda expôs

### 8. "Geração observada, condições e idade" — três sinais, dois inúteis

O `01-comportamento.md` e a D9 diziam que "o control plane ainda não falou" se
deriva de `observedGeneration`, das condições e da idade do objeto. **Dois desses
três não servem**, e só se descobre tentando implementar:

- **condições não existem em StatefulSet** — é o achado que a própria D4 já tinha
  registrado, e que eu não propaguei para a D9;
- **nenhum documento fixou limiar de idade**, então usá-la obrigaria quem
  implementa a inventar um número que a spec não dá.

Sobrou o par `status.observedGeneration` contra `metadata.generation`, que está
presente nos dois controladores e é o que o `kubectl rollout status` usa para
responder à mesma pergunta.

**Corrigido nos dois documentos**, com nota do que estava errado. O defeito era
sobre-especificação: nomear três sinais deu aparência de rigor e teria levado quem
implementasse a inventar o limiar que faltava.

## O que a spec não respondia

### 9. Precedência entre `Terminating` e motivo de espera

A spec testa os dois sinais isoladamente e não diz o que acontece quando coexistem.
**Resolvido:** a marca de remoção vence sempre. Um pod que está saindo é informação
mais urgente do que o motivo pelo qual ele estava esperando. Testado.

### 10. Vários containers em espera, com motivos diferentes

A spec generaliza a partir de um exemplo com um container.
**Resolvido:** o primeiro da lista vence, por falta de critério de desempate. E,
mais importante, **qualquer motivo de espera substitui a fase, não só
`CrashLoopBackOff`** — a regra escrita descreve onde o motivo vive, não um valor
específico.

### 11. Ordem entre objetos anormais

O requisito diz "anormais primeiro, os demais em ordem alfabética" e não diz como
ordenar os anormais entre si.
**Resolvido** com `(menor peso satisfeito, nome)`, reaproveitando o peso que já é
exibido na linha. Nenhum escore novo foi inventado — o que teria contrariado a D7.

### 12. Evento sem nenhum dos dois instantes

Não coberto. **Resolvido** excluindo da janela: não há como afirmar "recente" sobre
um instante que não existe.

### 13. `containerStatuses` ausente

Não coberto. **Resolvido** recuando para `spec.containers` para obter o total, em
vez de produzir `0/0`.

### 14. O instante corrente é parâmetro, não relógio

Decisão de desenho, não de ambiguidade, mas afeta assinatura pública: as funções de
janela de evento recebem o instante corrente em vez de consultarem o relógio. Sem
isso a interpretação deixaria de ser pura e os testes dependeriam da hora em que
rodassem — as fixtures foram capturadas num instante fixo do passado.

## Onde a implementação ficou melhor que a spec

### 15. A condição some pela forma do dado, não por um `if` no tipo

A tarefa 5.4 e a D4 sugeriam tratar StatefulSet como "o tipo que não tem condição",
o que em código vira `if tipo == "StatefulSet"`.

O agente recusou e extraiu a condição genericamente de `status.conditions`
normalizado. Como o StatefulSet não tem a chave, ela normaliza para lista vazia e a
busca não encontra nada — `condicao_available` sai `None` **pela forma dos dados**,
sem nenhum desvio dependente do Kind.

É mais fiel à regra "não testa presença de chave" do que a alternativa que a spec
sugeria. Conferido: não há desvio por Kind no módulo.

### 16. Uma observação sobre a tarefa 5.7

A tarefa cita a fixture que tem `Endpoints` **e** `EndpointSlice`, mas o código de
produção só lê a segunda — a D5 descartou a primeira. A redação poderia sugerir que
o código deveria ler as duas.

O agente escreveu dois testes em vez de um: o do caminho real de produção, e outro
provando que a normalização trataria a forma do `Endpoints` de modo idêntico se um
dia fosse lida. A ambiguidade da tarefa virou teste, em vez de virar código a mais.

## O que rodou

Conferido de forma independente:

```
66 passed in 0.29s
66 passed com --disable-socket
importa kubernetes ou urllib3 em src/: só cliente.py
desvio dependente do Kind em modelo.py: nenhum
caixas marcadas: 36 de 62  (grupos 1 a 6 completos)
```

As armadilhas, pelo código de produção e não pelos testes dele:

```
deploy/orion-web (0/3, sem readyReplicas)
  -> prontos=0, desejados=3, criterio campo='status.readyReplicas'
sts/nyx-postgres (sem conditions)
  -> condicao_available=None, criterios=()   e NAO marcado como anormal
pod/nyx-api (CrashLoop + OOMKilled)
  -> estado='CrashLoopBackOff', motivo=(atual='CrashLoopBackOff', causa='OOMKilled')
```

Cada critério carrega o campo que o originou — que era a exigência da D7 para a
ordenação ser auditável.
