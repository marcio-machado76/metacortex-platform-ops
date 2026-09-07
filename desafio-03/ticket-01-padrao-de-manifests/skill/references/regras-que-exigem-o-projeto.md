# As regras que só se resolvem lendo o projeto

Sete regras do padrão têm a resposta **fora do YAML**. Nenhuma delas vira script:
o dado que decide está no repositório da aplicação. Este arquivo diz o que
procurar e como o achado vira campo no manifesto.

Leia antes de escrever manifesto novo, e antes de opinar numa conferência sobre
probes, filesystem somente-leitura, token de ServiceAccount ou valores de recurso.

## Índice

- 2.2 · Para onde as probes apontam
- 3.2 · O que a aplicação escreve em disco
- 3.4 · Se ela fala com o apiserver
- 1.6 · Qual é o nome do componente
- 2.1 · Quanto de recurso reservar
- 2.6 · Quanto tempo ela precisa para drenar
- 3.3 · Se aquele valor é mesmo segredo

---

## 2.2 · Para onde as probes apontam

O script confere que as duas existem e que não são idênticas. **Escolher o alvo é
leitura de projeto.**

Procure as rotas declaradas e classifique cada candidata por **o que ela toca**:

| Pergunta | Alvo certo |
|---|---|
| `livenessProbe` — "ainda estou vivo?" | rota que responde sem tocar dependência externa |
| `readinessProbe` — "posso receber tráfego?" | rota que exercita a dependência sem a qual a aplicação não serve |

A regra descreve o erro a evitar: apontar as duas para o mesmo endpoint que checa
banco derruba a aplicação inteira quando o banco fica lento — a liveness falha, o
container reinicia, e reinício não conserta banco.

**Quando não existe endpoint de saúde.** É comum, e não autoriza pular a regra.
Procure nesta ordem:

1. **Um endpoint de métrica.** Frequente em aplicação instrumentada, servido pelo
   próprio processo e normalmente sem tocar banco — bom alvo de liveness.
2. **Uma rota trivial da aplicação.** Se ela renderiza consultando o banco, serve
   de readiness, não de liveness.
3. **Uma checagem por `exec`.** Para bancos, o utilitário de prontidão da própria
   imagem costuma ser a resposta.

Registre a escolha e o custo. Readiness que executa consulta a cada checagem pesa;
a mitigação é `periodSeconds`, não trocar o alvo por um que não detecta nada.

**Se algo roda antes do processo principal** — migração, seed, compilação — use
`startupProbe` com janela folgada. Sem ela, a liveness mata o container no meio da
inicialização e o pod nunca sobe.

## 3.2 · O que a aplicação escreve em disco

`readOnlyRootFilesystem: true` é obrigatório, e ele quebra toda aplicação que
escreve fora de um volume. Descobrir **onde** ela escreve é leitura de projeto, e
o manifesto de origem nunca conta.

Procure por:

- **diretório de métrica** exigido por biblioteca de instrumentação em modo
  multiprocesso — costuma vir de variável de ambiente;
- **temporário do servidor de aplicação** — muitos escrevem em `/tmp` por padrão;
- **cache, sessão, upload, log em arquivo**;
- **socket unix**, comum em banco de dados.

Cada caminho vira um `emptyDir` montado ali. Montagens aninhadas funcionam: um
volume em `/tmp` e outro em `/tmp/metrics` garantem que o segundo exista, o que
importa quando a biblioteca não cria o diretório sozinha.

**O campo `securityContext` se divide em dois níveis, e o padrão não diz isso.**
Copiar o bloco da regra inteiro para o nível de pod produz manifesto que o
apiserver rejeita, porque três dos campos só existem em container:

| Nível de pod | Nível de container |
|---|---|
| `runAsNonRoot`, `runAsUser`, `runAsGroup`, `fsGroup`, `seccompProfile` | `allowPrivilegeEscalation`, `readOnlyRootFilesystem`, `capabilities.drop` |

E o `runAsUser: 10001` do exemplo é ilustração, não piso. Imagem de terceiro
frequentemente exige outro UID — o dono dos arquivos dentro dela. O que a regra
exige de fato é `runAsNonRoot: true`.

## 3.4 · Se ela fala com o apiserver

A regra é condicional: `automountServiceAccountToken: false` "quando não fala com
a API". Verifique, não suponha — procure cliente de Kubernetes nas dependências
declaradas do projeto.

Não achando, declare `false` em dois lugares: na ServiceAccount e no pod. O do pod
é o que vale; o da ServiceAccount protege quem esquecer no pod.

Achando, o token fica montado **e** a 3.5 passa a exigir RBAC mínimo — não a
ServiceAccount `default`, e não permissão ampla.

## 1.6 · Qual é o nome do componente

O script avisa sobre nomes genéricos (`app`, `main`, `container`). Qual é o nome
certo vem do projeto: `api`, `worker`, `scheduler`, `web`. Quem lê log às três da
manhã não deveria precisar abrir o manifesto para descobrir o que está lendo.

## 2.1 · Quanto de recurso reservar

O script não confere valor nenhum — o Trivy confere só a presença. A regra da casa
é limite de memória entre **1,5x e 2x o consumo em regime**, e consumo em regime
não está no repositório.

O que o projeto dá é o **porte**: qual runtime, quantos processos por réplica,
quais bibliotecas pesadas. Isso produz um ponto de partida, não um valor.

**Declare que é estimativa.** Este costuma ser o único número do manifesto que
precisa ser corrigido depois de observar o workload rodando, e tratá-lo como
decisão fechada é exatamente como se produz reinício por falta de memória.

## 2.6 · Quanto tempo ela precisa para drenar

A única regra que não se resolve lendo código. Quanto uma aplicação demora para
drenar e se ela trata SIGTERM depende de carga real.

Mantenha o padrão de 30s, **diga que foi mantido por falta de dado**, e aponte
quem decide. Onde o desligamento limpo notoriamente não cabe em 30s — banco, worker
de mensagem longa — eleve e diga por quê.

## 3.3 · Se aquele valor é mesmo segredo

A heurística do script procura credencial embutida em URL e nome de variável que
pareça sensível. Ela aponta o lugar; **decidir é leitura**.

Nos dois sentidos: ela pode apontar um valor inofensivo, e pode deixar passar um
segredo com nome inocente. Ferramenta de mercado erra igual — o scanner de
segredos do Trivy não vê senha em URL de conexão dentro de `env.value`, e o check
de ConfigMap acusa um número de porta.

Na dúvida, a pergunta é: **se isto vazar no Git, alguém precisa rotacionar
alguma coisa?** Se sim, é segredo, e entra por `secretKeyRef`.

E lembre do que a própria regra encerra dizendo: Secret do Kubernetes é base64,
não criptografia. Cumprir a 3.3 resolve o vazamento por repositório, e só ele.
