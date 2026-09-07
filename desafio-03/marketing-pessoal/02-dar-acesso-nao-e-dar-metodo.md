# Dei ao agente acesso somente-leitura a todos os clusters. Ele continuou sem saber por onde começar.

*Sobre a diferença entre alcance e critério — e sobre a skill que eu descobri que faltava só depois de escrevê-la à mão quatro vezes.*

---

Existe uma corrida acontecendo agora para dar ferramenta a agente. Servidor MCP
para o cluster, para o banco, para o repositório, para o rastreador de incidentes.
A promessa implícita é que o agente fica competente quando ganha alcance.

Passei um projeto inteiro testando isso, e a evidência mais clara veio de um lugar
que eu não esperava: **as ferramentas estiveram carregadas o tempo todo, em modo
somente-leitura, e nenhuma foi usada.**

Não por defeito. Porque o trabalho daquele momento exigia comparar chaves de topo
de um objeto JSON — distinguir campo ausente de campo nulo, contar quantos eventos
tinham determinado atributo. Para isso o instrumento certo era o shell, que devolve
a resposta crua. A ferramenta que devolve saída já organizada teria apagado
exatamente a distinção que eu estava perseguindo.

O alcance estava lá. O que decidia era o critério.

## O plantonista novo com kubectl na mão

O caso que originou o projeto: dezenas de clusters, alerta que acusa o sintoma, e
a triagem variando por pessoa. Um começa pelos eventos, outro pelos logs, quem
entrou mês passado começa por onde der.

Dar acesso ao cluster não resolve nada disso — é a mesma situação do plantonista
novo que recebeu credencial e não recebeu procedimento. Ele consegue rodar
qualquer comando. Não sabe qual rodar primeiro.

O que faltava era responder quatro perguntas que nenhuma ferramenta responde:

- por onde começar, a partir do sintoma que a pessoa declarou
- em que ordem descer as camadas
- quando cruzar duas fontes em vez de aprofundar numa só
- **quando parar**

A última é a que mais se ignora. Identificada a causa, o trabalho da triagem
acabou — e é exatamente aí que a mão escorrega para "já que estou aqui, conserto".

## O caso que provou o ponto

Três incidentes com o mesmo texto de abertura: *"o cliente diz que está fora do
ar"*. As causas estavam em três camadas diferentes.

Dois deles um agente com acesso resolve sem método: a resposta está no primeiro
lugar onde qualquer um olharia.

O terceiro, não. Os pods estavam rodando e prontos. O objeto de controle mostrava
todas as réplicas disponíveis. Não havia um único evento de alerta. Os logs
estavam limpos. **Nenhuma fonte isolada acusava nada** — e mesmo assim ninguém
conseguia acessar a aplicação.

A causa era um caractere de diferença entre o seletor do serviço e o rótulo dos
pods. Só aparece cruzando dois objetos que, sozinhos, estão ambos corretos.

Esse é o formato do problema que separa ferramenta de método. Não existe comando
que revele; existe uma pergunta que alguém precisa ter aprendido a fazer — *"e se
as camadas de baixo estiverem todas limpas?"*. Ferramenta nenhuma faz essa
pergunta por você.

## Método também é o que a ferramenta se recusa a poder fazer

Quando empacotei o método, tomei uma decisão que pareceu excesso de zelo e não era.

A ferramenta de acesso ao cluster tem um modo chamado "não-destrutivo". Nome
tranquilizador. Fui ler o que ele faz: remove apagar, remover instalação, limpar
recursos — e **mantém disponíveis aplicar, criar e escalar**.

O limite que eu precisava era outro: *lê, nunca escreve, nem quando o agente tem
permissão para isso*. Então o servidor passou a rodar em somente-leitura de
verdade, que é um modo diferente e mais estrito.

A diferença não é de configuração, é de natureza. **Uma instrução pode ser
contornada por um pedido bem formulado; uma ferramenta ausente, não.** Escrever na
skill "não corrija o cluster" é promessa. Tirar do agente a capacidade de corrigir
é garantia.

Isso se repetiu em três formas ao longo do projeto: o servidor sem ferramentas de
escrita, o usuário de coleta sem privilégio administrativo, e um perfil de
permissão que nega todo verbo de escrita — e que, por não conceder o modo de
observação contínua, faz o próprio cluster recusar a alternativa que eu havia
descartado no papel.

Método bom não é o que está escrito. É o que sobrou possível depois de escrito.

## A skill que faltava nunca foi de domínio

Aqui está a parte que eu não esperava, e que só apareceu porque eu contei.

O projeto pedia que eu registrasse o que precisei reexplicar ao agente
repetidamente, mesmo tendo as skills instaladas. Fui olhar. Eram cinco regras,
escritas à mão, palavra por palavra, em **todos** os prompts de implementação:

1. Nada é afirmado sem ser rodado
2. Caixa marcada significa verificado, não escrito
3. Trabalhe em contexto frio, só a partir dos artefatos
4. Não conserte o documento em silêncio — reporte
5. Não invente requisito que a especificação não tem

Nenhuma delas está em skill alguma. E o motivo é que eu tinha empacotado as coisas
erradas — ou melhor, tinha empacotado as certas e não percebido que faltava outra
categoria.

As skills que eu entreguei cobrem **método de domínio**: como se confere um
manifesto, como se tria um incidente. O que eu tive que repetir quatro vezes foi
**método de trabalho**: como se produz qualquer coisa com um agente sem que o
resultado apodreça.

Descobri isso por ter repetido quatro vezes. Não existe outra forma honesta de
descobrir: enquanto você repete duas, três, parece só contexto do pedido. Na
quarta, o padrão fica visível.

E a quarta regra pagou por si na mesma semana. Foi ela que fez uma validação
independente **reprovar um critério de aceite meu** em vez de contorná-lo em
silêncio — o critério estava errado, e eu só soube porque quem validou tinha
instrução explícita de reportar em vez de consertar.

## O que eu levo disso

**Ferramenta resolve alcance. Não resolve critério.** As duas coisas são compradas
separadamente, e só uma delas tem preço de assinatura.

**O que a ferramenta não pode fazer é parte do método.** Restrição estrutural vale
mais que instrução bem escrita, porque instrução depende de quem lê estar disposto
a obedecer.

**Conhecimento tácito só aparece quando alguém conta as repetições.** Se você
nunca registrou o que reexplica em toda conversa, você tem um método não
empacotado e não sabe.

**A skill mais valiosa talvez não seja sobre o seu domínio.** Eu fui empacotar
Kubernetes e descobri que o que mais faltava era como não se enganar trabalhando
com agente. Essa não estava no escopo, e é a que eu escreveria primeiro se
começasse de novo.

---

*Tudo que este texto afirma é verificável: o registro de comportamento das skills,
com as cinco regras e a contagem das repetições, está em
[`ticket-04-dashboard-do-cluster/docs/04-log-de-skills.md`](../ticket-04-dashboard-do-cluster/docs/04-log-de-skills.md);
a diferença entre os dois modos do servidor, medida e documentada, em
[`ticket-02-triagem-no-cluster/mcp/`](../ticket-02-triagem-no-cluster/mcp/);
e a triagem dos três incidentes, com a causa de cada um, em
[`ticket-02-triagem-no-cluster/execucoes/`](../ticket-02-triagem-no-cluster/execucoes/).*
