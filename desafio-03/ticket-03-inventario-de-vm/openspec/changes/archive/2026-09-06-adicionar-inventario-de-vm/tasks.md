## 1. Estrutura e dependências

- [x] 1.1 Criar o pacote em `src/` com os quatro módulos (`cli`, `coletor`, `avaliador`, `relatorio`) e verificar que `python -m` no ponto de entrada responde com a ajuda
- [x] 1.2 Fixar Paramiko e o analisador de YAML em `requirements.txt` e verificar que a instalação num ambiente virtual limpo conclui sem erro
- [x] 1.3 Criar a suíte de testes e verificar que ela roda vazia com sucesso, para que as tarefas seguintes tenham onde entrar

## 2. Avaliador — a parte que não depende de rede

Construído antes do coletor de propósito: ele é função pura, e tê-lo pronto
primeiro permite testar as onze regras sobre inventários escritos à mão, antes de
existir qualquer conexão.

- [x] 2.1 Definir a estrutura do inventário e a da entrada de conformidade, e verificar que ambas serializam para JSON com campo desconhecido saindo como nulo
- [x] 2.2 Implementar a leitura do baseline, incluindo o aviso quando a versão do arquivo for posterior à conhecida, e verificar com um baseline de versão futura
- [x] 2.3 Implementar o registro de regras indexado pelo caminho do baseline e verificar que caminho sem função registrada produz `nao_verificado` com motivo
- [x] 2.4 Implementar `so.distribuicao`, `so.versao_minima` e `kernel.versao_minima`, e verificar a comparação de versão com os formatos reais das duas VMs e com formatos anômalos
- [x] 2.5 Implementar `servicos.ativos` com a correspondência de unidade sem sufixo casando serviço ou socket, e verificar que unidade ativa apenas como socket sai conforme com a forma registrada
- [x] 2.6 Implementar `servicos.proibidos` com correspondência exata de unidade nomeada com tipo, e verificar que unidade proibida ativa sai como desvio
- [x] 2.7 Implementar `swap.habilitado` e verificar que o desvio traz o tamanho no campo encontrado
- [x] 2.8 Implementar a classificação de endereço de escuta em pública, interna e loopback, e verificar as quatro situações previstas na spec, inclusive porta restrita que não está em escuta
- [x] 2.9 Implementar `portas_em_escuta.publicas_permitidas` e `portas_em_escuta.somente_rede_interna` e verificar cada uma contra inventário com porta exposta indevidamente
- [x] 2.10 Implementar `chaves_ssh.emitidas_por` com a regra de prova positiva vencendo incompletude, e verificar os três desfechos: chave estranha legível, todas certas com arquivo ilegível, e leitura completa e conforme
- [x] 2.11 Implementar `ssh.login_de_root` e `ntp.sincronizado`, e verificar que dado desconhecido produz `nao_verificado` com motivo em vez de conforme
- [x] 2.12 Implementar o resumo e verificar que a soma dos três vereditos é igual ao número de regras do baseline e que a contagem por severidade considera apenas desvios
- [x] 2.13 Verificar que avaliar o mesmo inventário repetidamente produz resultado idêntico, sem qualquer acesso a rede

## 3. Relatório

- [x] 3.1 Implementar a saída em JSON e verificar que a estrutura corresponde ao contrato, com campo desconhecido saindo como nulo
- [x] 3.2 Implementar a saída em Markdown com desvios ordenados por severidade e verificar que seção sem conteúdo não é apresentada
- [x] 3.3 Verificar que as duas saídas descrevem o mesmo dado, comparando as contagens de cada seção com o resumo

## 4. Coletor — o único módulo com rede

- [x] 4.1 Implementar a conexão com verificação de identidade do host e a opção explícita de aceitar host desconhecido, e verificar que sem a opção o host desconhecido é recusado antes de qualquer comando
- [x] 4.2 Traduzir as falhas do transporte em falha de alcance com mensagem legível, e verificar que endereço sem serviço, credencial recusada e tempo esgotado produzem mensagens distintas sem rastro de pilha
- [x] 4.3 Escrever o script composto com blocos delimitados por marcador e verificar, contra uma VM, que todos os blocos previstos aparecem na saída
- [x] 4.4 Implementar o analisador dos blocos e verificar que bloco ausente, vazio e em formato não reconhecido levam o campo a nulo com motivos distintos
- [x] 4.5 Implementar a coleta de identificação, sistema operacional e kernel, e verificar contra as duas VMs
- [x] 4.6 Implementar a coleta de unidades preservando nome completo e tipo, e verificar que socket e serviço são distinguíveis na saída
- [x] 4.7 Implementar a coleta de swap, de portas com protocolo, vínculo e processo, e verificar que porta em loopback aparece no inventário
- [x] 4.8 Implementar a leitura das chaves autorizadas a partir das contas do sistema, registrando o arquivo de origem, e verificar que arquivo ilegível é contado e nomeado
- [x] 4.9 Implementar a leitura da configuração efetiva de login de root e da sincronização de tempo, e verificar que sem privilégio o primeiro sai nulo
- [x] 4.10 Aplicar ordenação estável a todas as listas e verificar que duas coletas seguidas contra o mesmo host diferem apenas no instante da coleta
- [x] 4.11 Verificar, por inspeção do código e por execução, que nenhum comando enviado ao host escreve, instala, remove ou reinicia qualquer coisa

Tarefas 4.3 e 4.5 foram verificadas nesta sessão contra o laboratório real
— ver `docs/03-divergencias-da-implementacao.md`, seção "Grupo 6 —
validação", para as evidências. As demais deste grupo foram implementadas e
verificadas contra um transporte SSH simulado (`tests/fakes_transporte.py`)
— ver a mesma seção "Grupos 4 e 5" para o que essa verificação cobre.

## 5. Linha de comando

- [x] 5.1 Implementar os argumentos conforme a interface especificada e verificar que a ajuda apresenta todos com os seus valores padrão
- [x] 5.2 Implementar os quatro códigos de saída e verificar cada um deles isoladamente
- [x] 5.3 Sobrescrever o código de saída padrão do analisador de argumentos e verificar que argumento inválido termina em erro interno, e não em host inalcançável
- [x] 5.4 Verificar que regra não verificada não altera o código de saída, com um host conforme que tenha ao menos uma regra não verificável

## 6. Validação contra os critérios de aceite

Executada contra as duas VMs do laboratório, que sobem para esta etapa e são
destruídas em seguida.

- [x] 6.1 Subir o laboratório com `terraform apply` e verificar que as duas VMs respondem por SSH com o usuário de coleta
- [x] 6.2 Critério 1 — coletar a VM preparada dentro do baseline e verificar que não há desvio e que o código de saída é o de conforme
- [x] 6.3 Critério 2 — coletar a VM com desvios e verificar que cada um aparece com a severidade que o baseline atribui, cobrindo as três severidades
- [x] 6.4 Critério 3 — verificar que a configuração efetiva de login de root aparece como não verificada, com motivo, e distinta de conforme
- [x] 6.5 Critério 4 — apontar a ferramenta para um endereço sem serviço e para um host que recusa a credencial, e verificar mensagem legível, ausência de rastro de pilha e o código de host inalcançável
- [x] 6.6 Critério 5 — executar duas coletas seguidas contra o mesmo host e verificar, por comparação dos dois JSON, que a única diferença é o instante da coleta
- [x] 6.7 Critério 6 — procurar o conteúdo da chave privada nas duas saídas, no registro de execução e nas mensagens de erro, e verificar que não aparece em nenhum
- [x] 6.8 Gravar as saídas das execuções acima em `evidencias/` e destruir o laboratório com `terraform destroy`

A tarefa 6.1 verificou apenas o acesso — o laboratório já estava no ar no
início da sessão de validação, que não foi a que rodou `terraform apply`.

A tarefa 6.8 tem duas metades e elas foram feitas em momentos diferentes: a
gravação das evidências saiu da sessão de validação (a lista de arquivos está
em `docs/03-divergencias-da-implementacao.md`, seção "Grupo 6 — validação"),
e as evidências afetadas pela correção da ordem dos blocos foram regravadas
depois dela. O `terraform destroy` foi executado por quem detém a credencial
AWS, encerrando o laboratório.

Registro de por que a caixa ficou desmarcada por um tempo: a sessão de
validação não tinha credencial AWS e se recusou a marcar tarefa cuja
verificação ela não pôde realizar. Caixa marcada significa verificado.
