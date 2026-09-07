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
