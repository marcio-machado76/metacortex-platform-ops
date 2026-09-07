# Onde passa a linha: Trivy, script, instrução, e o que não entra

O padrão tem **19 regras acionáveis** nos Blocos 1 a 3, e 8 verbetes de vocabulário
no Bloco 4. Esta é a classificação regra a regra, e ela vem depois da medição em
`baseline-trivy/cobertura-medida.md` — não antes.

São quatro destinos, e o terceiro é o que esta skill inventa em relação a um
conferidor de CI:

| Destino | Critério |
|---|---|
| **Trivy** | já vem pronto no catálogo; reimplementar cria duas fontes de verdade |
| **Script** | a resposta está inteira no YAML, e é convenção da Metacortex que ferramenta de mercado não conhece |
| **Instrução** | a resposta exige **ler o projeto que está sendo empacotado** |
| **Fora** | não aprova nem reprova manifesto nenhum |

## A tabela

| Regra | Peso | Trivy | Script | Instrução |
|---|---|:-:|:-:|:-:|
| 1.1 kebab-case | obrigatório | | ● | |
| 1.2 namespace `<cliente>-<ambiente>` | obrigatório | | ● | |
| 1.3 os quatro rótulos | obrigatório | | ● | |
| 1.4 seletor casa com o pod | obrigatório | | ● | |
| 1.5 anotação de dono | recomendado | | ○ | |
| 1.6 nome do container = componente | recomendado | | ○ | ● |
| 2.1 requests e limits | obrigatório | ● | | ● |
| 2.2 as duas probes | obrigatório | | ● | ● |
| 2.3 replicas ≥ 2 em prod | obrigatório | | ● | |
| 2.4 estratégia de rollout | obrigatório em prod | | ● | |
| 2.5 PDB em prod | recomendado | | ○ | |
| 2.6 grace period | recomendado | | | ● |
| 3.1 tag `:latest` | proibido | ● | | |
| 3.2 securityContext | obrigatório | ● | | ● |
| 3.3 segredo em texto puro | **proibido** | | ◐ | ● |
| 3.4 token desmontado | obrigatório | | ● | ● |
| 3.5 ServiceAccount dedicada | recomendado | | ○ | |
| 3.6 hostNetwork / hostPID / privileged | proibido | ● | | |
| 3.7 registry interno | obrigatório | | ● | |

● responde · ○ avisa, não reprova · ◐ levanta suspeita, não decide

## O que ficou com o Trivy — e o que ele não termina

**2.1, 3.1, 3.2 e 3.6.** Medido: 17 dos 18 achados do manifesto barrado caem
nessas regras. Nenhuma delas foi reimplementada.

Mas em duas ele resolve só metade, e a outra metade não é detalhe:

- **2.1** — ele confere que `requests` e `limits` existem. A regra da casa é que o
  limite de memória fique **entre 1,5x e 2x o consumo em regime**, e consumo não
  está no YAML.
- **3.2** — ele confere que os campos estão lá. `readOnlyRootFilesystem: true`
  exige saber **o que a aplicação escreve em disco** para montar `emptyDir` no
  caminho certo. No fake-shop são dois caminhos, e nenhum aparece no manifesto de
  origem.

**A 3.7 não foi delegada**, apesar de o Trivy tocá-la: o KSV-0125 marca
`registry.metacortex.io` como registry não confiável, ou seja, avalia a regra ao
contrário. Quem sabe qual é o registry da casa é a skill.

## O que ficou com o script

Onze regras respondidas e quatro avisadas. O critério é o mesmo em todas: a
resposta está inteiramente no YAML e a convenção é da Metacortex.

A **1.4** merece nota, porque o padrão descreve o sintoma no lugar errado. O
apiserver já rejeita `matchLabels` divergente do template — esse desvio não chega
a existir. Quem sobe calado é o **Service**, criado sem reclamação e nascendo sem
endpoint. O script cruza o seletor de cada Service com os rótulos dos pods do mesmo
conjunto de manifests, que é a metade que acrescenta alguma coisa.

A **3.3** entra como `◐`: o script procura URL com credencial embutida e nome de
variável que pareça sensível, em `env.value` e em ConfigMap. Ele aponta onde olhar;
decidir se aquilo é segredo é leitura. É a regra mais grave do padrão e a única
completamente invisível às duas varreduras do Trivy — inclusive a de segredos.

## Onde a linha se moveu: cinco regras que deixaram de ser "revisão humana"

Este é o ponto do ticket. Um conferidor de CI só enxerga o YAML, então tudo que
depende do projeto vira "conferir no PR". Uma skill roda dentro de um agente que
**tem o repositório do projeto à mão** — e cinco regras mudam de categoria:

| Regra | O que a revisão humana respondia | O que a instrução manda o agente fazer |
|---|---|---|
| **2.2** | "as probes apontam para endpoints reais?" | listar as rotas do projeto e escolher: liveness num endpoint que não toque o banco, readiness num que responda pela dependência |
| **3.2** | "o filesystem pode ser read-only?" | procurar o que a aplicação escreve — diretório de métrica, temporário de worker — e montar `emptyDir` ali |
| **3.4** | "esta aplicação fala com o apiserver?" | procurar cliente de Kubernetes nas dependências; não achando, `automountServiceAccountToken: false` |
| **1.6** | "qual é o nome do componente?" | derivar do projeto, não do genérico `app` |
| **2.1** | "o limite bate com o consumo?" | ler o runtime e o porte da aplicação e propor um ponto de partida, declarando que é estimativa |

Nenhuma delas vira script — a resposta continua fora do YAML. Mas elas deixam de
depender de alguém lembrar de olhar.

**A 2.6 é a que não se move.** Quanto uma aplicação demora para drenar e se ela
trata SIGTERM não se lê com confiança no código; depende de carga real. Fica como
instrução fraca: o agente aponta que o valor foi deixado no padrão de 30s e que
isso é decisão de quem conhece a operação.

## O que não entra

**O Bloco 4 inteiro.** Oito verbetes — Pod, ReplicaSet, Deployment, Service,
`port` × `targetPort`, Endpoints, ConfigMap e Secret, probes. Ele mesmo declara o
seu público logo na abertura: *"Esta seção existe para quem está chegando na
plataforma... Quem já opera os clusters pode pular direto para os blocos
anteriores."*

Nenhum verbete aprova ou reprova manifesto. É um terço da página e zero regra.
Empacotar isso numa skill custa contexto em toda invocação para ensinar Kubernetes
a um agente que já sabe Kubernetes — é o caso clássico de artefato que incha até
parar de ser usado.

Um trecho do Bloco 4 sobrevive, mas migrado de lugar: a observação da 4.6 de que
*"o campo dos endereços não vem vazio... ele simplesmente não aparece"* é armadilha
de leitura de API, não vocabulário. Ela já está na skill de triagem do Ticket 02,
em `references/leitura-da-api.md`, que é onde ela é usada.

**Também não entra:** NetworkPolicy, Ingress, HPA e RBAC detalhado. O padrão não
fala de nenhum deles, e acrescentar regra que o documento não tem transformaria a
skill em opinião de quem a escreveu.

## Onde o padrão está incompleto

Duas lacunas apareceram ao aplicar o padrão ao fake-shop. Elas não mudam a
classificação, mas a skill precisa saber que o documento não responde:

1. **`seccompProfile` falta na 3.2.** O Trivy cobra por dois checks (KSV-0030,
   KSV-0104), e sem ele o pod é recusado na admissão em namespace com Pod Security
   `restricted`. Seguir a regra ao pé da letra produz manifesto que o cluster não
   aceita.
2. **Nada trata de migração de banco na inicialização.** O fake-shop roda
   `flask db upgrade` no start, e a regra 2.3 manda duas réplicas em prod: duas
   migrações partem juntas. O padrão não tem vocabulário para isso.


---

# O que o agente entendeu diferente do que eu escrevi

Rodar a skill em sessão limpa, num projeto que ela não conhecia, expôs uma lacuna
que a leitura do próprio texto não expõe.

**O agente versionou um objeto `Secret`.** Ao escrever os manifests do
`encontros-tech`, ele criou `03-secret-web-db.yaml` com
`DATABASE_URL: postgresql://CHANGEME:CHANGEME@...`, acompanhado de um comentário
extenso avisando que o valor é placeholder e que a credencial real deve entrar por
cofre, nunca por commit.

Não é vazamento e não contraria a letra da regra 3.3 — nenhum valor sensível foi
escrito. Mas contraria a prática: nos manifests do fake-shop, escritos à mão antes
da skill existir, nenhum Secret foi versionado; o workload aponta para `orion-db` e
o README diz quem o cria. A entrega anterior fez o mesmo.

**A culpa é da skill, não do agente.** O `SKILL.md` dizia "sempre por referência a
um Secret" e nunca dizia "e o objeto Secret não entra no repositório". Diante de
uma instrução que pede referência a um objeto que não existe, criar o objeto é a
leitura razoável.

O que mudou por causa disso: o modo de escrita ganhou uma linha explícita, com o
motivo — Secret versionado com placeholder é o arquivo que alguém preenche com a
credencial real no dia em que tiver pressa.

**O manifesto gerado ficou como saiu.** Ele é a evidência da execução, e corrigi-lo
apagaria justamente o achado. O que a entrega mostra é a sequência: a skill foi
executada, a saída divergiu da prática, a lacuna estava no texto da skill, e o
texto foi corrigido — nessa ordem, e visível no histórico.
