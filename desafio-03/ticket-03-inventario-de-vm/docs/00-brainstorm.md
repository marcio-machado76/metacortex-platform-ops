# Brainstorm — o que foi maturado antes de existir documento

Registro do que a conversa de amadurecimento produziu, antes de qualquer
especificação e muito antes de qualquer código. Está aqui porque as decisões
seguintes só fazem sentido com as perguntas que as originaram.

## O problema, em uma frase

Substituir a página do Roster mantida à mão por uma ferramenta que roda na
estação de quem opera, entra por SSH numa VM do parque, levanta o retrato real
daquele host e o compara com o `baseline.yaml` versionado — apontando cada
desvio, sua gravidade, e o que não pôde ser verificado.

## O que o enunciado já fecha, e o que ele deixa aberto

**Fechado:** o que precisa voltar (inventário campo a campo, uma entrada de
conformidade por regra, resumo), os dois formatos de saída, o código de saída
utilizável em pipeline, os dois invariantes e os cinco critérios de aceite.

**Aberto, e nomeado como decisão a registrar:** como a ferramenta conversa com o
host remoto, o que acontece quando um dado não pode ser coletado, e em que
linguagem ela é escrita.

**Aberto e não nomeado** — o que a conversa encontrou:

1. **O exemplo de saída não fecha.** O resumo mostra `conforme: 4, desvio: 4,
   nao_verificado: 1` = 9, e o baseline tem 11 regras. É ilustração, não contrato.
2. **"Porta pública" não está definida.** O baseline fala em
   `publicas_permitidas` e `somente_rede_interna` sem dizer o que é cada uma.
   Sem regra fixa, a mesma VM dá veredito diferente por implementador.
3. **`nao_verificado` tem três causas** e o enunciado nomeia uma. Falta de
   privilégio, comando inexistente e saída em formato inesperado. Com uma
   armadilha: **serviço ausente é desvio, não `nao_verificado`**.
4. **O baseline mistura unidade nomeada e unidade completa.** `servicos.ativos`
   traz `ssh` e `chrony`; `proibidos` traz `telnet.socket` e `rpcbind.socket`.
5. **`chaves_ssh.emitidas_por` confere etiqueta, não procedência.** Comentário de
   chave é campo livre.

## A virada que mudou o desenho

A primeira intuição era um coletor dirigido pelo baseline — ele lê as regras e
busca só o que precisa. Foi descartada.

| Opção | Ganho | Custo |
|---|---|---|
| Coletor dirigido pelo baseline | menos comandos no host | inventário incompleto e acoplado à v1; conformidade só testável com host real |
| **Coletor completo + avaliador puro** | inventário serve ao Roster independente do baseline; avaliador testável sem SSH | coleta alguns campos que a v1 não usa |

O segundo destrava o requisito mais difícil de provar — *"duas execuções seguidas
devolvem o mesmo veredito"*. Com o avaliador sendo função pura de
`(inventário, baseline)`, a idempotência do julgamento se prova em CI, sem host;
sobra só a idempotência da coleta para provar contra a VM.

O próprio enunciado aponta nessa direção: o exemplo traz
`"ssh": {"login_de_root": null}` **dentro do inventário**. A coleta registra o
"não sei" como dado; quem traduz `null` em `nao_verificado` é o avaliador.

## O princípio que resolveu dois casos de borda

Dois pontos pareciam independentes e caíram na mesma regra: **não inventar desvio
que a realidade não sustenta.**

- **Loopback.** O baseline é silencioso sobre `127.0.0.1`. Criar violação onde a
  política não pede seria a ferramenta legislando. Reporta no inventário, não
  gera desvio.
- **Serviço ativado por socket.** No Ubuntu 24.04 o `ssh.socket` fica ativo e o
  `ssh.service` inativo. A coleta **chega no host por SSH** — uma ferramenta que
  entra por ssh e reporta "ssh ausente" está errada por construção.

Nos dois casos a transparência é o que segura a interpretação: o inventário
registra exatamente o que foi visto, e a entrada de conformidade diz por que
chegou àquele veredito. Quem ler discorda se quiser.

## O que ficou explicitamente para depois

- **Política de host key do Paramiko** — decisão de segurança que precisa de
  posição escrita, não de escolha silenciosa no código. Resolvida em
  `02-decisoes-tecnicas.md`.
- **Como o Roster consome o JSON** — o Roster não existe; a v1 entrega o formato.
- **Varredura de frota em paralelo** — fora do escopo declarado.
