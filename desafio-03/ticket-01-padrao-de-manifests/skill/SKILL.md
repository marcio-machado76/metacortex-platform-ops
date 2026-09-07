---
name: padrao-de-manifests
description: >-
  Escreve e confere manifestos de Kubernetes contra o Padrão de Manifests da
  Metacortex — as 19 regras de identidade, resiliência e segurança que a revisão
  de Segurança & Compliance aplica antes de qualquer coisa subir para um cluster
  do parque. Use nos dois momentos: quando for **escrever** manifesto novo para um
  projeto (Deployment, Service, ConfigMap, StatefulSet, Job, PDB) e quando for
  **conferir** manifesto que já existe, antes de subir ou numa revisão de PR.
  Dispare mesmo quando o pedido não citar o padrão — "revisa esse deployment antes
  de eu subir", "esse YAML está certo?", "cria um Deployment novo pro cliente X",
  "por que o Seraph barrou isso?" — porque o padrão é o critério da casa e não uma
  opção. NÃO use para diagnosticar objeto que já está rodando e apresentando
  problema no cluster: pod reiniciando, deployment em 0/N, Service sem endpoint em
  execução — isso é triagem, é outra skill, e o critério é o objeto já estar no ar.
---

# Padrão de Manifests da Metacortex

O padrão existe, está escrito, e é justamente esse o problema: uma página de wiki é
boa para guardar decisão e péssima para conferir regra a regra no meio de uma
tarefa. Esta skill é aquela página transformada em procedimento.

Fonte: revisão de **2026-07-29**. São 19 regras acionáveis. O vocabulário do
Bloco 4 não entra aqui — ele é onboarding, não regra, e não aprova nem reprova
manifesto nenhum.

## A divisão do trabalho

Nem toda regra se confere do mesmo jeito, e isso foi **medido**, não suposto:
`trivy config` no manifesto barrado do nyx produz 18 achados que colapsam em
quatro regras. As outras quinze ele não menciona.

| Quem responde | Regras | Por quê |
|---|---|---|
| **`trivy config`** | 2.1, 3.1, 3.2, 3.6 | já vem no catálogo; reimplementar cria duas fontes de verdade |
| **`scripts/conferir-padrao.py`** | 1.1–1.6, 2.2–2.5, 3.3, 3.4, 3.5, 3.7 | convenção da Metacortex; nenhuma ferramenta de mercado conhece |
| **Você, lendo o projeto** | o alvo das probes, o que a app escreve em disco, se ela fala com o apiserver, o nome do componente, o porte dos recursos | a resposta não está no YAML |

Duas coisas que essa tabela esconde e que decidem o resultado:

- **A 3.7 não vai para o Trivy** apesar de ele tocá-la. O check KSV-0125 marca
  `registry.metacortex.io` como registry não confiável — ou seja, avalia a regra ao
  contrário e acusa quem acertou.
- **A 3.3 é a mais grave e a mais invisível.** Senha em `env.value` passa limpa
  pelo `trivy config` **e** pelo `trivy fs --scanners secret`. Enquanto isso, o
  KSV-01010 acusa `DB_PORT: "5432"` como conteúdo sensível. A heurística da
  ferramenta erra nos dois sentidos; por isso a regra fica no script, que procura
  credencial em URL e nome de variável sensível — e por isso ele aponta onde olhar
  em vez de decidir.

## Modo conferência

O uso frequente. No parque se mexe em manifesto pronto o tempo todo.

**Quando o pedido não disser se o objeto já está no cluster, pergunte.** Frases como
*"esse manifesto não sobe no cluster"* ou *"o Service não está entregando tráfego"*
cabem aqui e cabem em triagem, e o que desempata é um fato que o pedido não traz: se
o objeto já existe e está com problema, é triagem; se ainda vai subir ou está sendo
rejeitado, é conformidade. Dá para escolher de forma plausível sem perguntar —
plausível não é correto, e uma frase de pergunta é mais barata que conferir o
manifesto errado.

**1. Rode as duas ferramentas.** Elas não se substituem:

```bash
python3 scripts/conferir-padrao.py <caminho>
trivy config <caminho>
```

O script sai com código 1 se houver ERRO. Um ERRO é regra obrigatória ou proibida —
barra sem discussão. Um AVISO é regra recomendada — não barra, mas a exceção
precisa estar escrita no PR.

**2. Confira o que nenhuma das duas sabe.** Aqui você abre o projeto que o
manifesto empacota. Sem isso a conferência fica pela metade, e é essa metade que
mais barra revisão. O detalhamento está em
`references/regras-que-exigem-o-projeto.md` — leia antes de opinar sobre probes,
`readOnlyRootFilesystem`, `automountServiceAccountToken` ou valores de recurso.

O caso que ilustra: um Deployment sem probes é ERRO do script. Mas dizer **para
onde as probes deveriam apontar** exige saber quais rotas a aplicação expõe e
quais delas tocam o banco. Não se sabe olhando o YAML.

**3. Relate por regra, com o número.** Quem lê a conferência vai discutir com o
padrão aberto ao lado; achado sem número de regra vira opinião.

## Modo escrita

**Comece pelo projeto, não pelo YAML.** Esta é a inversão que a skill impõe: quem
começa escrevendo o Deployment acaba inventando porta, endpoint e nome de variável,
e descobre o erro em execução.

Antes da primeira linha de manifesto, extraia do repositório:

| O que | Onde costuma estar |
|---|---|
| porta em que o processo escuta | entrypoint, Dockerfile, `app.listen`/`--bind` |
| rotas expostas, e quais tocam o banco | as declarações de rota no código |
| nomes exatos das variáveis de ambiente | onde a aplicação lê a configuração |
| o que a aplicação escreve em disco | diretórios de métrica, cache, temporário de worker |
| se ela fala com o apiserver | as dependências declaradas |
| o que roda antes do processo principal | migração, seed, compilação de asset |

Só então escreva. `references/regras-que-exigem-o-projeto.md` diz como cada um
desses achados vira campo no manifesto.

**Ordem dos arquivos.** Numere na ordem de aplicação — namespace, contas,
configuração, workloads, exposição — para que um `kubectl apply -f <dir>/` funcione
sem ajuda.

**Não escreva o objeto Secret.** O manifesto do workload aponta para o Secret por
`secretKeyRef`; quem o cria é o cofre da plataforma, fora do Git. Versionar um
Secret, mesmo com valor de placeholder, cria o arquivo que alguém preenche com a
credencial real no dia em que tiver pressa — e a regra 3.3 existe justamente para
que esse arquivo não exista. Documente no README quais Secrets precisam existir
antes do deploy, com suas chaves, em vez de deixar um esqueleto pronto para ser
preenchido.

**Ao terminar, rode o modo conferência sobre o que você escreveu.** Manifesto novo
não é exceção: é o primeiro cliente do conferidor.

## Exceções

O padrão define três pesos, e eles não são intercambiáveis: **obrigatório** barra
sem discussão, **recomendado** aceita exceção justificada no PR, **proibido** não
tem exceção para workload de cliente.

Desvio de regra obrigatória exige aprovação escrita e prazo de validade. O script
reconhece isso quando está declarado **no próprio objeto**:

```yaml
annotations:
  metacortex.io/excecao-regra: "2.3"
  metacortex.io/excecao-motivo: "banco de escrita unica; replica adicional divergiria"
  metacortex.io/excecao-aprovada-por: seguranca-e-compliance
  metacortex.io/excecao-valida-ate: "2027-03-31"
```

O achado é rebaixado a EXCECAO em vez de ERRO. Faltando qualquer um dos três
campos de justificativa, continua ERRO — exceção pela metade não é exceção.

Anote no objeto, não no PR: PR ninguém acha seis meses depois.

## Onde o padrão está incompleto

Três lacunas conhecidas. Ao esbarrar numa delas, resolva e **registre** — não
finja que o documento respondeu:

1. **`seccompProfile` falta na regra 3.2.** Seguir os cinco campos listados produz
   pod que o Pod Security `restricted` recusa na admissão, e que nasce com dois
   achados no Trivy. Inclua `seccompProfile: {type: RuntimeDefault}` no nível de
   pod.
2. **Nada trata de dependência que falha na inicialização.** Aplicação que resolve
   o banco na subida e sai quando não encontra exibe CrashLoop que não é defeito de
   manifesto. Probe não resolve — o processo morre antes de qualquer probe.
3. **Nenhum vocabulário para carga com estado.** A 1.3 nem lista StatefulSet, e a
   2.3 exige duas réplicas sem qualificar o tipo de carga — o que não faz sentido
   para banco de escrita única. Use o mecanismo de exceção.

## O que esta skill não faz

- **Não confere o Bloco 4.** São oito verbetes de vocabulário, zero regra.
- **Não reimplementa o Trivy.** Se ele já cobre, a skill manda rodá-lo.
- **Não acrescenta regra que o padrão não tem.** NetworkPolicy, Ingress, HPA e RBAC
  detalhado ficam de fora: inventar regra transforma o padrão em opinião de quem
  escreveu a skill.
- **Não decide o que é segredo.** A heurística da 3.3 aponta; o julgamento é seu.
- **Não diagnostica objeto rodando.** Manifesto que já subiu e está com problema é
  triagem, não conformidade.

## Permissões que a skill pede

Leitura dos manifestos e do repositório do projeto, e execução de dois comandos
locais: `python3 scripts/conferir-padrao.py` (que só lê arquivos e não faz rede) e
`trivy config`. **Nenhum acesso a cluster** — conformidade se confere no YAML e no
código, antes de subir. O script depende de PyYAML.
