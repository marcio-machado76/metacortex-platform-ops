# Medi minha automação. Ela não melhorou o resultado.

*Sobre por que mantive assim mesmo — e por que a parte difícil de automatizar é decidir o que fica de fora.*

---

Empacotei o método de triagem de incidentes do time numa skill. Depois fiz o que
quase ninguém faz: medi se ela adiantava alguma coisa.

Três chamados reais, num cluster de laboratório. Cada um rodado duas vezes em
sessão limpa — uma com a skill carregada, outra sem nada. Mesmo prompt, mesmo
cluster, mesmo modelo. O resultado:

|  | com skill | sem skill |
|---|---:|---:|
| Asserções atendidas | 18/18 | 17/18 |
| **Causa correta** | **3/3** | **3/3** |
| Tokens (média) | 51.010 | 43.947 |
| Tempo (média) | 80,4 s | 79,0 s |

**As duas acertaram os três diagnósticos.** Um modelo capaz, com acesso ao
cluster e um sintoma bem formulado, resolve estouro de memória, tag inexistente
no registry e seletor que não casa sem método escrito nenhum. A skill custou 16%
mais tokens para chegar exatamente onde o modelo já chegava sozinho.

Se você automatiza coisas e nunca mediu, essa tabela é o resultado que você
provavelmente vai encontrar. Vale saber antes.

## Por que mantive

Porque "chegou à mesma causa" não é a mesma coisa que "fez o mesmo trabalho".

A diferença apareceu nas bordas, e as bordas são o que custa caro no plantão:

**Disciplina de escopo.** Num dos chamados, a rodada sem skill terminou
recomendando mudança no pipeline de CI. É um bom conselho — e não é triagem. Em
outro, foi olhar um namespace diferente, de *outro* chamado, e de lá inferiu qual
seria "a convenção correta da casa" a partir de uma amostra de um. As duas coisas
são o tipo de deriva que transforma dez minutos em quarenta.

**Ruído nomeado como ruído.** Num dos casos havia um pod com um reinício isolado,
sem relação com o problema. A rodada com skill encontrou, classificou como ruído
e seguiu. A sem skill não mencionou. As duas acertaram — mas só uma deixou
registrado que aquilo foi visto e descartado, que é o que impede a próxima pessoa
de perseguir o mesmo fantasma.

**Menos texto, e menos invenção.** Os relatórios com skill saíram 34% mais
curtos. E o mais longo dos sem skill gastou 124 linhas para, no meio delas,
afirmar que a aplicação era escrita numa linguagem que não era a dela. Detalhe
inventado que não mudou o diagnóstico e que, num relatório de plantão, vira
folclore.

O pedido que originou a skill nunca foi "descubram mais rápido". Foi **"parem de
variar por pessoa"**. Para esse pedido, 16% de token é barato.

## A parte que ninguém publica

Publicar resultado negativo parece autossabotagem. É o contrário: é a única forma
de o resultado positivo significar alguma coisa.

Se eu tivesse escrito "empacotei o método do time numa skill e ficou ótimo", você
não teria como saber se eu medi ou se eu gostei. A tabela lá em cima é o que
separa as duas leituras. E ela também me impede de vender a skill como coisa que
ela não é — na próxima vez que alguém no time perguntar "isso acelera a triagem?",
a resposta honesta é não, e eu tenho o número.

O que a medição também disse, e que eu não sabia antes: os três chamados eram
**bem-postos**. Sintoma com namespace, defeito único, cluster no estado do
incidente. Triagem real raramente chega assim. Onde eu esperaria ver ganho de
diagnóstico — e o que aqueles três casos não testam — é sintoma mal formulado,
dois defeitos simultâneos, e plantonista novo. Que é, aliás, o caso que motivou a
skill existir.

## A decisão mais difícil não foi o que incluir

Foi o que recusar.

O padrão de manifests que eu tinha que empacotar numa outra skill tem quatro
blocos. O último, um terço da página inteira, é vocabulário: o que é um Pod, o que
é um ReplicaSet, a diferença entre `port` e `targetPort`. Bem escrito, útil para
quem está chegando.

Deixei inteiro de fora.

Não porque seja ruim — porque nenhum daqueles verbetes aprova ou reprova
manifesto nenhum. Empacotar aquilo custaria contexto em toda invocação para
ensinar Kubernetes a um agente que já sabe Kubernetes. É o caso clássico do
artefato que incha até parar de ser usado.

E o próprio documento entregava o argumento, na primeira linha da seção: *"Quem
já opera os clusters pode pular direto para os blocos anteriores."* O padrão
sabia que aquilo não era regra. Bastava ler.

A skill de triagem também recusou algo, e esse foi mais contraintuitivo: ela **não
tem script**. Um script que consultasse o cluster precisaria de credencial própria
e rodaria fora do servidor que garante o modo somente-leitura. A garantia
deixaria de ser estrutural e viraria promessa de quem escreveu o script. Então a
skill empacota método, e método não precisa de credencial.

## Medir antes de escrever, não depois

Tem uma terceira recusa, e ela veio de uma medição feita **antes** de existir
código.

O padrão tem 19 regras. A ferramenta de varredura que o time já usava cobria
quantas? Ninguém sabia — todo mundo tinha uma opinião. Rodei: 18 achados, que ao
serem mapeados de volta colapsam em **quatro** das 19.

Isso definiu o escopo do que eu ia escrever. As quatro que a ferramenta já cobre
não foram reimplementadas, porque duas fontes de verdade sobre a mesma regra
divergem no dia em que uma delas muda — e aí ninguém sabe qual está certa.

O caminho inverso é o comum: escrever primeiro, descobrir a sobreposição depois,
e ficar com um script que reimplementa metade do que já vinha pronto e continua
devendo o que só você sabe.

## O que eu levo disso

**Cobertura não é a métrica.** A métrica é se a coisa continua sendo usada daqui a
seis meses — e o que mata artefato interno não é faltar conteúdo, é sobrar.

**Medir a sobreposição vem antes de escrever.** Vinte minutos rodando a ferramenta
que já existe decidem o escopo melhor do que qualquer reunião sobre ele.

**O que você recusa precisa estar escrito, com o motivo.** Senão a próxima pessoa
acrescenta de volta, achando que foi esquecimento. "Não incluí o bloco de
vocabulário porque nenhum verbete aprova ou reprova manifesto" é uma frase que
sobrevive à minha saída do time.

**Resultado negativo publicado vale mais que resultado positivo afirmado.** Se
você automatizou algo e nunca mediu, você não sabe se automatizou ou se decorou.

---

*Tudo que este texto afirma é verificável: a tabela que o abre está em
[`ticket-02-triagem-no-cluster/medicao-com-sem-skill/`](../ticket-02-triagem-no-cluster/medicao-com-sem-skill/),
com as saídas cruas das seis execuções; a medição da varredura está em
[`ticket-01-padrao-de-manifests/baseline-trivy/`](../ticket-01-padrao-de-manifests/baseline-trivy/);
e a recusa do bloco de vocabulário, com o motivo, em
[`curadoria-das-regras.md`](../ticket-01-padrao-de-manifests/curadoria-das-regras.md).*
