# Meu critério de aceite estava errado. Só descobri porque quem validou não fui eu.

*Sobre o que muda quando existe documento antes do primeiro prompt — e sobre a única forma de saber se ele presta.*

---

Escrevi uma especificação de comportamento antes de escrever código. Ela dizia,
entre outras coisas, que um determinado ambiente de teste deveria aparecer sem
nenhuma marca de anormalidade.

Quando a validação rodou, falhou. A tela mostrava um alerta ali.

A reação instintiva é consertar o código. A segunda reação, mais perigosa, é
consertar o critério — e é a que eu tomei. Só que "corrigi o critério em vez do
código" é uma frase que deveria levantar suspeita imediata em quem lê. É
indistinguível de mover a trave depois de ver onde a bola caiu.

O que desfaz a suspeita não é explicação. É a ordem dos commits:

```
56008ac   o FATO       (o ambiente já registrava o alerta, na evidência)
3a5b830   o CRITÉRIO   que afirmava "nenhum objeto anormal"
c600442   a CORREÇÃO
```

O fato estava versionado **um commit antes** do critério que o contradizia. O
critério nasceu errado — a tela estava certa desde sempre. Isso não é argumento
meu; é linha do tempo, e ela existe porque cada etapa virou commit no momento em
que aconteceu.

Se eu tivesse feito tudo num commit só no fim, essa defesa não existiria.

## Documento antes do código não é sobre disciplina

É sobre poder ser contestado.

A tese comum sobre especificação antes de código fala em clareza, alinhamento,
menos retrabalho. Tudo verdade e tudo difícil de verificar. O ganho concreto que
eu vi foi outro: **um documento escrito antes pode estar errado de um jeito
verificável.** Um entendimento que só existe na sua cabeça, não.

Quando a spec é código já escrito, "o sistema faz isso" e "o sistema deveria fazer
isso" são a mesma frase. Não há como o código contradizer a intenção, porque ele
*é* a intenção. Separar os dois cria a possibilidade de um discordar do outro — e
essa discordância é informação.

## A única forma de saber se a spec presta

Escrever a especificação e implementar você mesmo prova pouco. Você carrega
contexto que não está escrito: sabe o que quis dizer, preenche as lacunas sem
notar que são lacunas, e no fim tem um sistema que funciona e um documento que
ninguém mais consegue usar.

O que eu fiz foi entregar os artefatos a **quem não participou da especificação**,
com instrução explícita de não consertar nada em silêncio: encontrando erro,
ambiguidade ou contradição, anotar e reportar.

Isso transforma a implementação em teste da spec. E o teste reprovou em quatro
pontos.

Dois eram inofensivos. Dois eram **contratos entre partes do sistema** — um campo
cujo nome eu nunca defini e um vocabulário que eu nunca fixei. Sem eles resolvidos,
o módulo que coleta preencheria um formato, o módulo que julga leria outro, e a
suíte de testes passaria enquanto a execução real quebraria. É o tipo de defeito
que não aparece em teste unitário, porque cada lado está internamente correto.

Eu não teria encontrado sozinho. Não porque sou desatento — porque eu sabia o que
tinha querido dizer.

## Quando o documento erra, corrija o documento

Achar o erro é metade. A outra metade é o que você faz com ele.

A saída fácil é reescrever a especificação como se ela sempre tivesse estado
certa. O resultado parece melhor e é pior: some a informação mais útil que aquele
projeto produziu, que é *onde o entendimento falhou*.

Cada correção ficou registrada como correção, com o que estava errado e por quê.
Num dos projetos isso virou uma seção de quatro linhas explicando que dois dos
erros eram contratos entre módulos e que, sem eles, a suíte passaria e a execução
real falharia. Quem pegar aquele código daqui a um ano lê isso e entende por que
o campo tem o nome que tem.

Houve um caso em que o caminho foi o inverso, e a distinção importa. Uma ferramenta
que eu havia declarado como somente-leitura foi flagrada **mudando o estado do host
que ela auditava** — uma consulta de horário ativava um serviço por efeito
colateral, e duas execuções seguidas passavam a divergir.

Havia uma saída elegante: afrouxar o critério de repetibilidade para valer só
sobre os vereditos, já que nenhum veredito mudava de fato. Teria passado, e teria
sido defensável no papel.

Era defeito de implementação, e implementação se conserta. Afrouxar a
especificação para acomodar o que o código faz é como se chama, com outro nome, o
hábito que ter spec deveria eliminar.

**A regra que ficou:** documento errado se corrige no documento; código errado se
corrige no código. Confundir os dois desfaz o motivo de existirem separados.

## O que eu levo disso

**Documento antes do código compra falseabilidade, não clareza.** Clareza é
subjetiva; contradição entre documento e execução é objetiva.

**Quem escreve a spec não deveria ser quem testa se ela presta.** Não por
desconfiança — por contexto não escrito, que é invisível para quem o tem.

**Preserve a correção, não só o resultado corrigido.** "Estava errado assim, e o
motivo era este" vale mais que a versão limpa, porque é a única parte que ensina
alguma coisa.

**Commit no momento em que a coisa acontece.** Não por higiene de histórico: no
dia em que alguém desconfiar de você, a ordem dos commits vai ser a única prova
que não depende da sua palavra.

---

*Tudo que este texto afirma é verificável: a ordem dos commits que sustenta a
correção do critério está no histórico da branch do
[`ticket-04-dashboard-do-cluster/`](../ticket-04-dashboard-do-cluster/); os quatro
pontos em que a especificação não sobreviveu ao contato com o código estão em
[`ticket-03-inventario-de-vm/docs/01-comportamento.md`](../ticket-03-inventario-de-vm/docs/01-comportamento.md),
na seção final; e o que quem implementou entendeu diferente do que eu escrevi, em
[`docs/03-divergencias-da-implementacao.md`](../ticket-03-inventario-de-vm/docs/03-divergencias-da-implementacao.md).*
