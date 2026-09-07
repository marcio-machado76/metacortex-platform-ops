# Decisões técnicas

O enunciado nomeia três decisões que a ferramenta não carrega sozinha — como ela
conversa com o host remoto, o que acontece quando um dado não pode ser coletado, e
em que linguagem ela é escrita. Elas estão aqui, com o que foi descartado. As
outras seis apareceram durante o amadurecimento e valem pelo mesmo motivo: quem
pegar este código daqui a um ano vai perguntar por quê, e o commit não responde.

---

## D1 · Linguagem: Python

**Escolhido:** Python 3, sem framework.

**Descartado — Go.** Entrega binário único, sem runtime na estação de quem opera, e
é a escolha natural para ferramenta distribuída para uma frota. Perde por dois
motivos: seria a segunda linguagem do repositório (que já tem Python no conferidor
do Ticket 01 e Terraform na infraestrutura), e o argumento de distribuição vale
menos aqui do que parece — **a ferramenta roda na estação de quem opera, não no
host auditado**. Não há frota de instalação.

**Descartado — shell.** É a linguagem nativa do problema e a que o time de
infraestrutura mais domina. Perde porque a entrega exige JSON estruturado com
`null` significativo, comparação de versão e teste automatizado do avaliador —
três coisas em que shell é hostil.

**Custo aceito:** a estação precisa de Python e de duas bibliotecas. Mitigado por
`requirements.txt` fixado e por um único ponto de entrada.

## D2 · Transporte: Paramiko

**Escolhido:** Paramiko, uma conexão por execução.

**Descartado — `subprocess` chamando o `ssh` do sistema.** Herdaria
`~/.ssh/config`, `known_hosts`, agente e `ProxyJump` — vantagem real para quem
opera atrás de bastion. Perde por dois motivos:

1. **A interface é credencial explícita.** O enunciado define a entrada como
   endereço, usuário e chave privada. Uma ferramenta que herda configuração
   ambiente responde uma pergunta diferente: passa a depender de como a estação
   está configurada, o que colide com a exigência de que duas execuções devolvam
   o mesmo retrato.
2. **`ssh -i /caminho/chave` fica visível no `ps`** para qualquer outro usuário da
   estação. O caminho não é a chave, mas é um vazamento gratuito num projeto cujo
   segundo invariante é sobre justamente isso.

E há um ganho direto: o critério de aceite pede que host inalcançável falhe *"com
mensagem que diz o que houve, sem stack trace cru"*. Paramiko distingue
`AuthenticationException` (chave recusada) de `NoValidConnectionsError` (endereço
errado ou SSH fora do ar) de `socket.timeout` por tipo — muito mais confiável do
que interpretar o texto de erro do `ssh`, que muda entre versões.

## D3 · Política de chave de host: estrita por padrão, frouxa por opção declarada

Esta ficou em aberto no brainstorm por ser decisão de segurança.

**Escolhido:** carregar o `known_hosts` do usuário e **recusar host desconhecido**.
Para o primeiro contato existe `--aceitar-host-desconhecido`, que precisa ser
passado conscientemente e que faz a ferramenta **registrar na saída** que a
identidade do host não foi verificada.

**Descartado — `AutoAddPolicy` como padrão.** É o que quase toda ferramenta
parecida faz, e é tentador porque uma frota provisiona VMs o tempo todo e o
`known_hosts` nunca está populado. Perde porque um intermediário no caminho
alimentaria a ferramenta com um inventário falso — e uma ferramenta de auditoria
que aceita qualquer host audita a resposta de qualquer um. O modo inseguro
continua disponível; ele só deixa de ser silencioso.

**Descartado — recusar sempre, sem escape.** Tornaria o primeiro contato
impossível e empurraria o time para um `ssh` manual antes de cada coleta, o que na
prática vira `AutoAdd` feito à mão e sem registro.

## D4 · Arquitetura: coleta e julgamento separados

**Escolhido:** o coletor produz o inventário completo; o avaliador é função pura
`(inventário, baseline) → conformidade`.

**Descartado — coletor dirigido pelo baseline**, buscando só o que as regras
pedem. Menos comandos no host, mas produz inventário incompleto e acoplado à v1 do
baseline — e o inventário é a entrega que o Roster vai consumir, independente da
política vigente.

**O ganho decisivo é de verificabilidade.** O requisito mais difícil de provar é
*"duas execuções seguidas devolvem o mesmo veredito"*. Com o avaliador puro, a
idempotência do julgamento se demonstra em teste automatizado, sobre inventários
gravados, sem host nenhum. Sobra apenas a idempotência da coleta para provar
contra a VM real.

O enunciado aponta nessa direção: o exemplo traz `"ssh": {"login_de_root": null}`
**dentro do inventário**. A coleta registra o "não sei"; o avaliador o traduz.

## D5 · Uma conexão, um script composto

**Escolhido:** abrir uma conexão e executar um único script que emite blocos
delimitados por marcador, um por grupo de dados.

**Descartado — uma conexão por comando.** Mais simples de escrever e depurar, ao
custo de nove handshakes.

**Descartado — uma conexão, um comando por vez.** Elimina os handshakes, mas
mantém o problema real.

**O problema real não é desempenho, é o instante.** O inventário declara
`coletado_em` como um momento. Nove idas e voltas transformam esse momento numa
janela de vários segundos em que o host pode mudar debaixo da leitura — um serviço
sobe entre a coleta de serviços e a de portas, e o retrato fica internamente
inconsistente. Um script composto aproxima o retrato de um instante real.

**Custo aceito:** parsing mais trabalhoso e falha parcial que precisa de
disciplina. Mitigado pelos marcadores: bloco ausente ou vazio vira `null` no
campo correspondente, e o avaliador cuida do resto.

## D6 · Quando um dado não pode ser coletado

**Escolhido:** o campo vem `null` no inventário, e o avaliador o traduz em
`nao_verificado` com motivo. Nunca valor inventado, nunca campo ausente, nunca
abortar a execução.

O enunciado é explícito sobre por que não abortar: *"reportar isso como conforme
seria mentira, e abortar a execução inteira por causa disso seria inútil"*.

**Três causas, cada uma com motivo próprio:** falta de privilégio, recurso
inexistente no host, saída em formato não reconhecido. O campo `motivo` é texto
para leitura humana, mas os três casos são distinguíveis nele.

**A armadilha que essa decisão precisa evitar:** serviço ausente é **desvio**, não
`nao_verificado`. `chrony` não instalado viola `servicos.ativos` — o gerenciador de
serviços não existir é que seria não verificável. Confundir os dois transforma
desvio real em "não consegui ver", que é exatamente o tipo de silêncio que o Roster
manual já produzia.

**Regra de desempate:** prova positiva de violação vence incompletude.

## D7 · Códigos de saída sem severidade

**Escolhido:** `0` conforme · `1` desvio · `2` inalcançável · `3` erro interno.

**Descartado — codificar severidade no código de saída** (por exemplo, `1` médio,
`2` alto, `3` crítico). Atende ao pipeline que quer barrar só em crítico, mas
acopla o contrato da CLI à taxonomia do `baseline.yaml`, que é versionado e vai
mudar: uma severidade nova na v2 quebraria pipeline alheio. Quem precisa desse
corte lê `resumo.por_severidade` do JSON, que é uma linha de `jq`.

**Descartado — `nao_verificado` reprovando.** Tornaria a ferramenta inútil no caso
normal, que é coleta com usuário comum.

**Armadilha concreta desta escolha em Python:** o `argparse` termina com **2** por
conta própria diante de argumento inválido — e `2` é "host inalcançável" nesta
tabela. Um erro de digitação apareceria no painel como host fora do ar. O
comportamento padrão precisa ser sobrescrito para `3`, deliberadamente.

## D8 · Classificação de endereço de escuta

**Escolhido:** `0.0.0.0`/`::` é pública; faixa privada é rede interna;
`127.0.0.1`/`::1` é loopback, que entra no inventário e não gera desvio.

**Descartado — omitir loopback do inventário.** Simplificaria, e faria o inventário
mentir por omissão. A porta em loopback de hoje é a porta exposta de amanhã, e
notar essa mudança é justamente o que se espera do Roster.

**Descartado — tratar loopback como desvio.** Seria a ferramenta legislando onde o
baseline é silencioso.

**Caso de borda aceito conscientemente:** `9100` escutando apenas em `127.0.0.1`
sai **conforme**, porque a regra restringe exposição e loopback não é exposição —
mesmo que na prática o Prometheus não consiga coletar. Conforme e quebrado ao
mesmo tempo. Inventar veredito que o baseline não pede seria pior.

## D9 · Unidade ativa por socket conta como ativa

**Escolhido:** nome sem sufixo no baseline casa com `.service` **ou** `.socket`
ativo; o inventário registra qual dos dois foi encontrado.

**Descartado — casar apenas com `.service`.** É a leitura literal, e reprovaria o
SSH em Ubuntu 24.04, onde `ssh.socket` fica ativo e `ssh.service` inativo.

O argumento decisivo é embaraçoso de tão direto: **a coleta chega no host por
SSH**. Uma ferramenta que entra por ssh e reporta "ssh ausente" está errada por
construção.

Vale como achado sobre o baseline: ele **deveria nomear a unidade completa** em
`servicos.ativos`, como já faz em `proibidos`.

## D10 · Determinismo explícito

**Escolhido:** toda lista sai ordenada por chave estável; nenhum campo volátil
entra no inventário.

Sem isso o critério de aceite 5 não passa: `ss` e `systemctl` não garantem ordem
entre execuções, e uma lista reordenada faria dois retratos idênticos parecerem
diferentes. Pelo mesmo motivo ficam de fora tempo de atividade, carga e
identificador de processo — a porta guarda o **nome** do processo, e não o PID,
que muda a cada reinício sem que nada tenha mudado.

---

## Achados sobre o baseline e o enunciado

Não são decisões, são coisas que a especificação encontrou e que valem correção
do lado do time:

1. **O exemplo de saída não fecha:** `4 + 4 + 1 = 9` para 11 regras.
2. **"Porta pública" não está definida** em lugar nenhum — cada implementador
   chegaria a um veredito diferente para a mesma VM.
3. **`servicos.ativos` deveria nomear a unidade completa**, como `proibidos` já faz.
4. **`chaves_ssh.emitidas_por` confere etiqueta, não procedência.** Comentário de
   chave é campo livre: qualquer um escreve `platform@metacortex-platform` numa
   chave própria. A ferramenta implementa o que está escrito; o documento registra
   que isso não é controle de segurança.
