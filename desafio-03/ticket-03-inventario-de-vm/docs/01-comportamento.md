# Comportamento — ferramenta de inventário e drift de VM

Especificação de comportamento. Descreve **o que** a ferramenta faz, não como.
As decisões de implementação estão em `02-decisoes-tecnicas.md`.

## Escopo

**Dentro:** uma VM Linux por execução, alcançada por SSH com usuário e chave
privada informados; levantamento do inventário; avaliação contra um
`baseline.yaml`; saída em JSON e em Markdown; código de saída para pipeline.

**Fora:** varredura de frota em paralelo; qualquer escrita no host; instalação de
agente; correção de desvio; persistência ou histórico (quem guarda é o Roster,
que ainda não existe).

## Interface

```
inventario-vm --host <endereço> --usuario <nome> --chave <caminho>
              [--baseline <caminho>] [--formato json|markdown|ambos]
              [--saida <diretório>] [--porta <n>] [--timeout <segundos>]
              [--aceitar-host-desconhecido]
```

| Argumento | Obrigatório | Default | Observação |
|---|---|---|---|
| `--host` | sim | — | endereço usado na conexão; reaparece no inventário |
| `--usuario` | sim | — | usuário comum, sem privilégio esperado |
| `--chave` | sim | — | caminho da chave privada. **É credencial** — ver Invariantes |
| `--baseline` | não | `./baseline.yaml` | arquivo versionado pelo time |
| `--formato` | não | `ambos` | |
| `--saida` | não | stdout | quando informado, grava `inventario.json` e `inventario.md` |
| `--porta` | não | `22` | |
| `--timeout` | não | `15` | segundos para conexão e para a coleta |
| `--aceitar-host-desconhecido` | não | desligado | aceita host fora do `known_hosts`. A saída registra que a identidade não foi verificada — ver decisão D3 |

## O inventário

Uma coleta produz o retrato abaixo. **Campo que não pôde ser coletado vem `null`**
— nunca vem ausente, nunca vem com valor inventado. O inventário registra o "não
sei" como dado; quem o traduz em veredito é a avaliação.

| Grupo | Campos | Quando é `null` |
|---|---|---|
| `host` | `endereco`, `hostname`, `coletado_em` (ISO 8601, UTC, sufixo `Z`) | nunca — se não houver conexão, não há saída |
| `so` | `distribuicao`, `versao` | arquivo de identificação da distribuição ilegível |
| `kernel` | `versao` | — |
| `servicos` | lista de `{nome, tipo, estado}`, com `nome` sendo a unidade completa, `tipo` ∈ `service`\|`socket`\|`timer` e `estado` no vocabulário do gerenciador, em que **só `active` conta como ativo** | gerenciador de serviços indisponível → lista `null` |
| `swap` | `habilitado`, `tamanho` | — |
| `portas_em_escuta` | lista de `{porta, protocolo, bind, processo}` | `processo` vem `null` para socket de outro usuário (exige privilégio); a lista em si não |
| `chaves_ssh` | `lidas`, lista de `{identificacao, origem}`; e `arquivos_ilegiveis`, lista de caminhos | ver "Escopo das chaves" |
| `ssh` | `login_de_root` | quase sempre: a configuração **efetiva** exige privilégio |
| `ntp` | `sincronizado`, `mecanismo` | nenhum mecanismo de tempo reconhecido |

Dois campos são acréscimos ao exemplo do enunciado, ambos aditivos e necessários
para o veredito ser defensável: `protocolo` na porta, porque `9100/tcp` e
`9100/udp` são coisas diferentes, e `origem` na chave, porque sem saber de qual
arquivo ela veio não dá para declarar o escopo da leitura.

### Escopo das chaves

A regra `chaves_ssh.emitidas_por` é propriedade **do host**, não de um usuário.
A coleta lê todo `authorized_keys` que conseguir, a partir dos diretórios pessoais
declarados no arquivo de contas do sistema, e registra em `origem` de onde cada
chave veio. Arquivos existentes e ilegíveis entram em `chaves_ssh.arquivos_ilegiveis`
pelo caminho completo — contados **e nomeados**, que é o que sustenta o veredito
`nao_verificado`.

### Classificação de endereço de escuta

O baseline não define o que é porta pública. Esta especificação define:

| `bind` | Classe |
|---|---|
| `0.0.0.0`, `::` | **pública** |
| faixa privada (RFC 1918) ou link-local | **rede interna** |
| `127.0.0.1`, `::1` | **loopback** |
| qualquer outro endereço roteável | **pública** |

Loopback **entra no inventário e não gera desvio**. Ele não é exposição, e criar
violação onde o baseline é silencioso seria a ferramenta legislando. Mas omiti-lo
faria o inventário mentir por omissão — e a porta em loopback de hoje é a porta
exposta de amanhã, que é exatamente o que o Roster deveria notar.

## A avaliação

Uma entrada por regra do baseline, com quatro informações: `regra`, `esperado`,
`encontrado`, `veredito` — mais `severidade` quando o veredito é `desvio`, e
`motivo` quando é `nao_verificado`.

### Os três vereditos

| Veredito | Significado |
|---|---|
| `conforme` | o host atende a regra |
| `desvio` | o host não atende, e há prova disso. Carrega a `severidade` que o baseline atribui |
| `nao_verificado` | não foi possível afirmar. Carrega `motivo` |

`nao_verificado` tem três causas, todas com motivo próprio: **falta de
privilégio**, **recurso inexistente no host** (o comando não existe) e **saída em
formato não reconhecido**.

**A distinção que mais erra:** serviço ausente é **desvio**, não
`nao_verificado`. `chrony` não instalado viola `servicos.ativos`; o gerenciador de
serviços não existir é que seria não verificável.

**Regra de desempate — prova positiva vence incompletude.** Quando parte da
evidência é ilegível mas o que foi lido já demonstra violação, o veredito é
`desvio`. `nao_verificado` só quando a incompletude é o que impede a conclusão.

### As onze regras

| Regra | Severidade | Como é avaliada |
|---|---|---|
| `so.distribuicao` | alto | comparação literal, sem diferenciar maiúsculas |
| `so.versao_minima` | alto | comparação numérica por componentes; versão do host ≥ mínima |
| `kernel.versao_minima` | médio | componentes numéricos iniciais da versão em execução ≥ mínima. `6.8.0-31-generic` vira `6.8.0` |
| `servicos.ativos` | alto | cada nome esperado está ativo. Nome **sem sufixo** casa com `.service` **ou** `.socket`; o inventário registra qual. Faltando algum → desvio, listando os ausentes |
| `servicos.proibidos` | alto | nenhuma unidade proibida ativa. Nome **com sufixo** casa exatamente |
| `swap.habilitado` | crítico | igualdade com o esperado; quando habilitado, `encontrado` traz o tamanho |
| `portas_em_escuta.publicas_permitidas` | crítico | toda porta classificada como **pública** está na lista. Qualquer outra → desvio |
| `portas_em_escuta.somente_rede_interna` | crítico | nenhuma porta da lista aparece como **pública**. Não estar escutando satisfaz por vacuidade — a ausência já é acusada por `servicos.ativos`, e contá-la duas vezes infla o resumo |
| `chaves_ssh.emitidas_por` | crítico | toda chave legível tem o emissor no seu identificador. Chave estranha legível → desvio. Todas certas com algum arquivo ilegível → `nao_verificado` |
| `ssh.login_de_root` | alto | configuração **efetiva** do daemon, não o arquivo. Sem privilégio → `nao_verificado` |
| `ntp.sincronizado` | médio | igualdade com o esperado; `mecanismo` é informativo e não entra no veredito |

**Regra presente no baseline e desconhecida pela ferramenta** → `nao_verificado`,
com motivo dizendo que a versão da ferramenta não a implementa. Ignorar em
silêncio faria o resumo dizer "conforme" sobre o que ninguém checou. Quando a
`versao` do baseline for maior que a conhecida, a ferramenta avisa — e prossegue.

### O resumo

Contagem por veredito, e `por_severidade` contando **apenas os desvios**. As três
contagens somadas são iguais ao número de regras do baseline.

## Saídas

**JSON**, porque o Roster vai consumir automaticamente: um objeto com `host`,
`inventario`, `conformidade` e `resumo`, seguindo o exemplo do enunciado.

O grupo `host` é coletado como parte do inventário, mas aparece **na raiz** do
relatório, ao lado de `inventario` — e não repetido dentro dele. A tabela acima
descreve o que a coleta produz; esta seção descreve como isso é apresentado.

**Markdown**, porque o plantão vai ler no terminal às três da manhã: cabeçalho com
host, endereço, instante e versão do baseline; tabela de **Desvios** ordenada por
severidade (crítico, alto, médio); tabela de **Não verificado** com regra e
motivo; e lista de **Conforme**. Seção sem conteúdo não aparece.

## Códigos de saída

| Código | Situação |
|---|---|
| `0` | coleta concluída, nenhum desvio |
| `1` | coleta concluída, ao menos um desvio |
| `2` | host inalcançável — endereço errado, chave recusada, SSH fora do ar, timeout |
| `3` | erro interno, incluindo baseline ausente ou inválido e argumento inválido |

`nao_verificado` **não** reprova. Reprovar por ele tornaria a ferramenta inútil
com usuário comum, que é o caso normal — mas ele sempre aparece no resumo e nas
duas saídas.

A severidade **não** entra no código de saída: ela pertence ao baseline, que é
versionado e vai mudar, e codificá-la acoplaria o contrato da CLI à taxonomia dele.
Quem quiser barrar só em crítico lê `resumo.por_severidade` do JSON.

## Invariantes

**1 · A ferramenta só lê.** Nada é instalado, escrito, corrigido ou reiniciado do
outro lado da conexão. Duas execuções seguidas contra o mesmo host inalterado
devolvem o mesmo veredito para cada regra, mudando apenas `coletado_em`.

Isso impõe determinismo: toda lista sai em ordem estável, e nenhum campo volátil
entra no inventário — sem tempo de atividade, sem carga, sem identificador de
processo. Por isso a porta guarda o **nome** do processo, e não o PID.

**2 · A chave privada é credencial.** Não aparece na saída, no log nem em mensagem
de erro. Nenhum campo do inventário a contém, e nenhum caminho de erro imprime o
conteúdo do arquivo.

## Critérios de aceite

| # | Critério | Como se verifica |
|---|---|---|
| 1 | Host conforme sai sem desvio | VM preparada dentro do baseline; `resumo.desvio == 0`, saída `0` |
| 2 | Host com desvios traz cada um classificado pela severidade do baseline | VM com um desvio por severidade; cada entrada com a severidade correta, saída `1` |
| 3 | Regra não verificável aparece como tal, distinta de conforme | usuário sem privilégio; `ssh.login_de_root` como `nao_verificado` com motivo |
| 4 | Host inalcançável falha dizendo o que houve, sem stack trace e sem ser confundido com conforme | endereço sem listener, chave recusada; mensagem em uma linha, saída `2` |
| 5 | Execução repetida devolve o mesmo retrato | duas execuções seguidas; diferença entre os JSON restrita a `coletado_em` |
| 6 | A chave não vaza | as duas saídas, o log e a mensagem de erro não contêm o conteúdo da chave |


---

## Correções feitas durante a implementação

Esta seção existe porque a especificação errou, e apagar o erro apagaria a
informação mais útil que ele produziu.

Os grupos 1 a 3 foram implementados por um agente que não participou da
especificação, a partir apenas destes documentos. Quatro pontos não se
sustentaram no contato com o código, e todos foram corrigidos **aqui**, no
documento — não contornados no código:

| # | O que estava errado | Correção |
|---|---|---|
| 1 | A seção "Escopo das chaves" exigia que arquivos ilegíveis fossem "contados e nomeados", e a tabela do inventário não nomeava o campo que carrega isso | `chaves_ssh` passa a ter `lidas` e `arquivos_ilegiveis` |
| 2 | A tabela listava `host` como grupo do inventário; a seção "Saídas" o descrevia como irmão de `inventario` no JSON. Os dois textos não se conciliavam | fixado que `host` é coletado no inventário e apresentado na raiz do relatório, sem duplicação |
| 3 | O vocabulário do campo `estado` de uma unidade não estava definido em lugar nenhum | fixado que só `active` conta como ativo |
| 4 | A classificação de endereço cobria coringa, faixa privada e loopback, e era silenciosa sobre endereço roteável específico | acrescentada a linha que faltava |

As duas primeiras eram **contratos entre a coleta e o resto**: sem elas fixadas,
o coletor preencheria campos que o avaliador não lê, e a suíte passaria enquanto
a execução real falharia.

O registro do lado de quem implementou está em
`03-divergencias-da-implementacao.md`, preservado como foi escrito.
