# Divergências da implementação — Grupos 1, 2 e 3

Registro produzido durante a implementação dos Grupos 1 (estrutura e
dependências), 2 (avaliador) e 3 (relatório) da mudança
`adicionar-inventario-de-vm`. Os Grupos 4, 5 e 6 (coletor, linha de comando e
validação) não foram implementados nesta sessão e não são cobertos aqui.

Nenhuma spec, nenhum documento em `docs/` e nenhum artefato de design foi
alterado para acomodar o código. Onde a especificação não respondia ou era
ambígua, a decisão foi tomada no código e documentada abaixo — não no
documento fonte.

## O que a spec não respondia

### 1. O campo que sustenta "leitura completa vs. parcial" de `chaves_ssh`

`docs/01-comportamento.md` descreve `chaves_ssh` na tabela "O inventário"
como "lista de `{identificacao, origem}`". No mesmo documento, a seção
"Escopo das chaves" exige que "arquivos existentes e ilegíveis são contados
e nomeados — é o que sustenta o veredito `nao_verificado`", e o Requirement
"Retrato do host" (spec de `coleta-de-inventario`) tem um cenário
("Escopo da leitura de chaves autorizadas") que exige que "o resultado
permite distinguir leitura completa de leitura parcial". Nenhum dos dois
textos nomeia o campo que carrega essa distinção — a tabela só descreve o
formato da lista de chaves *lidas*.

**Decisão:** o grupo `chaves_ssh` do inventário tem dois campos:
`chaves_ssh.lidas` (a lista de `{identificacao, origem}` como descrito na
tabela) e `chaves_ssh.arquivos_ilegiveis` (lista de caminhos de arquivos que
existem mas não puderam ser lidos). O avaliador usa o segundo campo para
decidir entre `desvio` e `nao_verificado` na regra `chaves_ssh.emitidas_por`
(Requirement "Prova positiva de violação prevalece sobre leitura
incompleta"). Está documentado no docstring de `src/inventario_vm/avaliador.py`.

Isso também significa uma decisão implícita para o Grupo 4 (coletor, fora do
escopo desta sessão): quem implementar a coleta real precisa preencher
`arquivos_ilegiveis` com os caminhos, não apenas com uma contagem — a
especificação usa a palavra "nomeados" ("contados e nomeados"), que a
escolha acima respeita.

### 2. Se `severidade` e `motivo` aparecem como `null` ou ficam ausentes na entrada de conformidade quando não se aplicam

O requisito de "campo desconhecido sai como `null`, nunca ausente" está
escrito em `docs/01-comportamento.md` e na spec de `relatorio-e-saida`
apenas para campos do *inventário*. Para a entrada de conformidade, o texto
diz apenas "quatro informações... mais `severidade` quando o veredito é
`desvio`, e `motivo` quando é `nao_verificado`" — o que é compatível tanto
com "chave ausente quando não se aplica" quanto com "chave presente e
`null`".

**Decisão:** por consistência com a convenção "nunca ausente, nunca
inventado" aplicada ao resto do sistema, e porque um consumidor de máquina
(o Roster) se beneficia de um formato de chaves estável entre entradas, as
duas chaves estão sempre presentes em toda entrada de conformidade, com
valor `null` quando não se aplicam. Testado em
`tests/test_avaliador_estrutura.py`.

### 3. Onde fica `host` no JSON final: dentro de `inventario` ou como irmão dele

A tabela "O inventário" em `docs/01-comportamento.md` lista `host`
(`endereco`, `hostname`, `coletado_em`) como o primeiro grupo de campos do
inventário. Mas a seção "Saídas" do mesmo documento, e o Requirement "Saída
em JSON para consumo automático", descrevem o JSON como "um objeto com
`host`, `inventario`, `conformidade` e `resumo`" — quatro membros distintos
no mesmo nível. Os dois textos não se conciliam sozinhos.

**Decisão:** o inventário Python interno mantém `host` como um dos seus
grupos (igual à tabela). `relatorio.montar_relatorio` extrai
`inventario["host"]` para a chave raiz `host` do relatório, e a chave
`inventario` do relatório contém os demais grupos, sem repetir `host` lá
dentro — evita duplicar o dado e ainda assim satisfaz "objeto com host,
inventario, conformidade e resumo" ao pé da letra. Documentado no docstring
de `src/inventario_vm/relatorio.py` e coberto em `tests/test_relatorio.py`.

### 4. Formato de `estado` nos objetos de `servicos`

Nem `docs/01-comportamento.md` nem as specs definem o vocabulário do campo
`estado` de uma unidade (`{nome, tipo, estado}`). Como o Grupo 4 (coletor)
não foi implementado nesta sessão, o avaliador precisava assumir um
vocabulário para poder comparar "está ativo".

**Decisão:** usei o termo literal que `systemctl is-active` devolve —
`"active"` — como único valor que conta como "ativo" nas regras
`servicos.ativos` e `servicos.proibidos`. Qualquer outro valor (`"inactive"`,
`"failed"`, etc.) conta como não ativo. Quem implementar o Grupo 4 precisa
preencher `estado` com esse vocabulário para o avaliador funcionar como
testado.

### 5. Classificação de um IP público específico (não coringa) vinculado explicitamente

A tabela "Classificação de endereço de escuta" cobre três casos: coringa
(`0.0.0.0`/`::`), faixa privada/link-local, e loopback. Ela não diz o que
fazer com um endereço IP público específico vinculado explicitamente (por
exemplo, o IP elástico da própria VM, sem ser coringa) — um caso plausível
na prática, mesmo que não apareça nas duas VMs de laboratório.

**Decisão:** esse caso também classifica como "pública" (é o que sobra
depois de descartar loopback, coringa e privado/link-local). É a leitura
mais conservadora e a mais consistente com a definição operacional da
tabela ("o que não é privado nem loopback é exposição"). Documentado no
docstring de `classificar_endereco_de_escuta`.

## O que entendi diferente (ambiguidade resolvida por leitura)

### 6. Armadilha real encontrada na implementação: `0.0.0.0` e `::` são "privados" para o módulo `ipaddress` do Python

Isto não é uma ambiguidade da especificação — é um comportamento do módulo
`ipaddress` da biblioteca padrão que quase produziu uma implementação
incorreta. `ipaddress.ip_address("0.0.0.0").is_private` é `True` (a faixa
`0.0.0.0/8` é reservada) e o mesmo vale para `::`. A primeira versão de
`classificar_endereco_de_escuta` checava `is_private` antes de checar o
caso coringa, e classificava `0.0.0.0`/`::` como "rede interna" —
exatamente o oposto do que a tabela pede ("pública"). Os testes de
`tests/test_avaliador_regras_portas.py` pegaram isso imediatamente (3 testes
falhando). Corrigido checando `is_unspecified` antes de `is_private`. Fica
registrado porque é o tipo de bug que reaparece se alguém reescrever essa
função sem os testes.

### 7. "Comparação numérica por componentes" de `so.versao_minima` interpretada com o mesmo algoritmo de "componentes numéricos iniciais" de `kernel.versao_minima`

A tabela das onze regras descreve `kernel.versao_minima` explicitamente como
"componentes numéricos iniciais... `6.8.0-31-generic` vira `6.8.0`", mas
descreve `so.versao_minima` de forma mais seca: "comparação numérica por
componentes; versão do host ≥ mínima", sem a ressalva de "iniciais". A
Tarefa 2.4 do `tasks.md`, porém, agrupa as duas regras num único item e pede
para "verificar a comparação de versão com os formatos reais das duas VMs e
com formatos anômalos" para ambas — sugerindo que se espera o mesmo
tratamento de robustez para as duas.

**Leitura adotada:** usei a mesma função de extração de componentes
numéricos iniciais para as duas regras. Não há indício de que a versão do
SO precise de um algoritmo mais estrito, e usar dois algoritmos diferentes
para duas regras estruturalmente idênticas pareceu mais arriscado do que
unificá-las.

### 8. Empate entre "esperado" da entrada de conformidade e o valor bruto do baseline

Não há texto que diga explicitamente que `esperado` na entrada de
conformidade é sempre o valor bruto lido do baseline (sem transformação).
Assumi que sim, em todas as onze regras — nenhuma rotina de avaliação
reformata o valor esperado antes de colocá-lo na entrada. Isso é visível e
testável (ex.: `test_kernel_versao_minima_formato_real_com_sufixo_de_distribuicao`
verifica que `esperado` sai como a string `"6.5"` do baseline, sem
conversão).

## Erros ou contradições encontrados

Nenhum novo além dos quatro já registrados por vocês mesmos em
`docs/02-decisoes-tecnicas.md`, seção "Achados sobre o baseline e o
enunciado" (o exemplo de saída que não fecha, "porta pública" indefinida no
enunciado original, `servicos.ativos` que deveria nomear a unidade completa,
e `chaves_ssh.emitidas_por` conferindo etiqueta e não procedência). Esses já
estavam documentados antes desta sessão e não exigiram nenhuma decisão nova
da minha parte — os Grupos 2 e 3 já foram desenhados levando-os em conta.

Não encontrei contradição entre `proposal.md`, as três specs, `design.md` e
os dois documentos de `docs/` que afetasse os Grupos 1, 2 ou 3. As
contradições/lacunas que encontrei estão listadas acima, nas seções
anteriores, junto com a decisão tomada.

## Testes

A suíte usa `pytest` (a mesma ferramenta já usada no restante do repositório
— `ticket-01`). Localização: `tests/`, configurada via `pytest.ini`
(`pythonpath = src`). 59 testes, todos sem rede, sobre inventários e
baselines escritos à mão em `tests/fixtures.py` (o baseline real usado nos
testes é o `baseline.yaml` do repositório, carregado do disco, sem qualquer
acesso de rede).

Resultado nesta sessão: `59 passed` (`python3 -m pytest -q`).

---

# Grupos 4 e 5

Registro produzido durante a implementação dos Grupos 4 (coletor) e 5
(linha de comando) da mudança `adicionar-inventario-de-vm`, na sessão
seguinte à que produziu o texto acima. O laboratório AWS (`infra/`) estava
destruído antes desta sessão começar — nenhuma das duas VMs existia para
verificação. O Grupo 6 (validação contra elas) não foi tocado, como
instruído, e continua inteiramente desmarcado em `tasks.md`.

Mesma regra da sessão anterior: nenhuma spec, nenhum documento em `docs/` e
nenhum artefato de design foi alterado para acomodar o código. Decisões e
achados ficam registrados aqui.

## Como a ausência de VM foi tratada

`coletor.py` é, por desenho (`design.md`), o único módulo que abre socket.
Isso tornou possível testar tudo que não depende do *conteúdo real* de um
host específico através de um transporte SSH simulado
(`tests/fakes_transporte.py`): um objeto com a mesma interface de
`paramiko.SSHClient` (`connect`, `exec_command`, `close`,
`set_missing_host_key_policy`, `get_host_keys`, ...), que nunca abre socket
e devolve texto gravado à mão no formato exato que o script composto
produz. Com ele, ficou possível exercitar de ponta a ponta:
`coletor.coletar()` completo, a tradução de exceções de transporte, a
política de identidade de host, o analisador de blocos e todas as funções
de extração de campo — sem host, sem rede, sem espera, e determinístico.

**O que isso não substitui:** a suíte prova que o código faz o que o texto
das mensagens/estruturas diz que faz, dado um texto de entrada. Ela não
prova que os comandos do script composto (`systemctl list-units`, `ss -H
-tulnp`, `sshd -T`, etc.) realmente produzem esse texto nas duas VMs reais
do laboratório — isso só a Tarefa 4.3 (explicitamente "contra uma VM"), a
Tarefa 4.5 (explicitamente "contra as duas VMs") e o Grupo 6 inteiro podem
provar. Essas tarefas continuam **desmarcadas** em `tasks.md`:

- **4.3** — escrever o script composto e verificar, contra uma VM, que
  todos os blocos aparecem na saída.
- **4.5** — coleta de identificação/SO/kernel verificada contra as duas VMs.
- **6.1 a 6.8** — todo o Grupo 6, que depende do laboratório subir.

Como validação adicional (não substitui as tarefas acima, mas reduz risco):
rodei o script composto de verdade, via `sh -c`, contra esta própria
máquina de desenvolvimento (Ubuntu com `systemd`, não uma VM do laboratório)
e passei a saída pelo analisador. Isso pegou um bug real antes dos testes
automatizados existirem — ver achado 6 abaixo — mas **não é** a verificação
que a Tarefa 4.3/4.5 pedem, porque não é uma VM do parque nem tem o
`baseline.yaml` como alvo (a máquina não está preparada para o baseline).

## O que a spec não respondia

### 1. Onde registrar que a identidade do host não foi verificada

O Requirement "Conexão autenticada com identidade do host verificada",
cenário "Host desconhecido com autorização explícita", exige que "o
resultado registra que a identidade do host não foi verificada". Nenhum
documento (`docs/01-comportamento.md`, as três specs, `design.md`) diz
*onde* — o formato do inventário fixado no Grupo 2
(`avaliador.py`, grupo `host`: `endereco`, `hostname`, `coletado_em`) não
tem campo para isso, e nenhuma regra do baseline depende dele.

**Decisão:** acrescentei `host.identidade_verificada` (booleano) ao
inventário — `True` no caminho normal, `False` apenas quando
`--aceitar-host-desconhecido` foi usado **e** o host realmente não constava
no `known_hosts`. É um campo aditivo: nenhuma regra do avaliador o lê, os
testes do Grupo 2 continuam passando sem tocar nele, e ele não aparece na
tabela "O inventário" de `docs/01-comportamento.md` porque essa tabela é
anterior a esta decisão. Documentado no docstring de
`coletor.montar_inventario_de_blocos`.

### 2. A que código de saída mapeia "host desconhecido recusado"

A tabela de códigos de saída em `docs/01-comportamento.md` lista quatro
situações (`conforme`, `desvio`, `host inalcançável`, `erro interno`) e
associa "host inalcançável" a "endereço errado, chave recusada, SSH fora do
ar, timeout" — a recusa por identidade de host desconhecida não está nessa
lista nem em nenhuma outra.

**Decisão:** tratei a recusa por identidade (Requirement "Host desconhecido
sem autorização explícita") como mais uma causa de `FalhaDeAlcance`, que a
CLI mapeia para o código `2` (host inalcançável) — é a leitura mais
próxima: a coleta não aconteceu, e não é nem `desvio`/`conforme` (que
exigem coleta concluída) nem `erro interno` (que a spec reserva para
baseline e argumento inválidos). Não encontrei texto que confirme ou
contradiga essa escolha.

### 3. O protocolo de marcadores do script composto e o problema do "vazio ambíguo"

`design.md` descreve o script composto em termos gerais ("cada bloco abre
com um marcador... bloco cujo comando falhou sai vazio, não ausente") mas
não fixa o protocolo exato. Ao implementar, apareceu um problema que o
texto não antecipa: para alguns campos, saída vazia com sucesso é um dado
válido, não uma falha — `swapon --show` vazio significa legitimamente "sem
swap habilitado" (`swap.habilitado: false`), e é indistinguível de "o
comando `swapon` não existe no host" (recurso ausente) se só o texto for
observado.

**Decisão:** cada bloco do script termina com um segundo marcador de
status carregando o código de saída do comando (`echo "@@STATUS:$?@@"`).
`analisar_blocos` usa esse código para diferenciar "rodou e não achou nada"
(código `0`, texto vazio) de "não existe" (código diferente de zero). Isso
não está pedido em lugar nenhum, mas é necessário para o contrato de
`swap.habilitado` (nunca `None` sem motivo real) se sustentar. Idem para
`servicos` e `portas_em_escuta`, onde lista vazia por sucesso é "nenhuma
unidade/porta encontrada" (um dado real, que o avaliador trata como desvio
quando o baseline exige algo) e não deve ser confundida com o gerenciador
estar indisponível.

O protocolo interno do bloco `CHAVES` (linhas `LIDO:<caminho>`,
`ILEGIVEL:<caminho>`, `@@FIM-ARQUIVO@@`) também é integralmente uma
invenção desta implementação — a spec não desce a esse nível de detalhe, e
não havia como haver, já que é puramente uma decisão de como transportar
uma lista de tamanho variável de arquivos dentro de um único bloco de
texto.

## Erros ou contradições encontrados

### 4. `portas_em_escuta` e `chaves_ssh` não têm como expressar "não verificado"

O Grupo 2 fixou (na sessão anterior, achado 1 do documento acima) que
`chaves_ssh.lidas`/`arquivos_ilegiveis` e, no docstring de `avaliador.py`,
`portas_em_escuta` "nunca são `None`" — ao contrário de `servicos`, que tem
`None` como sentinela explícita para "gerenciador indisponível". Isso é
coerente para os casos normais (nenhuma chave lida, nenhuma porta em
escuta), mas deixa sem representação exatamente o terceiro motivo de
`nao_verificado` que a spec prevê para todo o resto: "recurso inexistente
no host" (`ss` ou os utilitários usados para ler `/etc/passwd`/`authorized_keys`
não existirem).

**Não corrigi isso** — mudar o contrato do inventário fixado pela sessão
anterior está fora do escopo desta sessão, e o Grupo 2 já está coberto por
59 testes que assumem esse contrato. O coletor, ao encontrar essas duas
categorias de bloco malsucedidas, devolve lista vazia (mesmo valor que "o
host não tem nada disso"), o que é uma escolha conservadora mas
silenciosamente errada nesse caso específico — a ferramenta relataria
"nenhuma porta em escuta" (conforme por vacuidade) num host onde `ss`
simplesmente não existe. Documentado no docstring do módulo `coletor.py` e
aqui, para quem decidir se vale a pena revisar o contrato do inventário
numa próxima fatia.

### 5. `sshd` aceita mais valores que `yes`/`no` para `PermitRootLogin`, e o baseline modela a regra como booleana

Nem a spec nem o baseline preveem `without-password`, `prohibit-password`
ou `forced-commands-only` — os outros valores reais que `sshd -T` pode
reportar para `permitrootlogin`, e que são inclusive o padrão de fábrica do
Ubuntu (`prohibit-password`, citado em
`infra/envs/lab/user_data/desvio.sh.tftpl`).

**Decisão:** só `no` conta como "login de root desabilitado" (`False`);
qualquer um dos outros valores reconhecidos conta como `True`, porque login
de root continua possível de alguma forma. Documentado no docstring de
`coletor._extrair_login_de_root`. Não pôde ser exercitada contra as VMs
reais (onde o usuário sem sudo nunca chega a ler o valor de qualquer forma —
ver achado do próprio `infra/README.md`: as duas VMs do laboratório saem
com `ssh.login_de_root` sempre `nao_verificado`), então esta decisão é
verificada só pelos testes sintéticos de `tests/test_coletor_extracao.py`.

### 6. Achado real durante o smoke test local (não é dos critérios de aceite): identificador de zona em endereço de loopback

Ao rodar o script composto de verdade nesta máquina de desenvolvimento (via
`sh -c`, não uma VM do laboratório — ver seção acima), `ss` reportou o
stub resolver do `systemd-resolved` como `127.0.0.53%lo:53`. O sufixo
`%lo` é um identificador de zona de interface, não parte do endereço IP, e
`ipaddress.ip_address` (usado por `avaliador.classificar_endereco_de_escuta`)
levanta `ValueError` ao recebê-lo. Corrigido em
`coletor._separar_endereco_porta`, removendo qualquer sufixo `%...` do
endereço antes de colocá-lo no inventário. Coberto por
`tests/test_coletor_extracao.py::test_endereco_com_identificador_de_zona_e_normalizado`.
Não é um achado sobre a spec ou o baseline — é um comportamento real do
`ss` que a spec não tinha como prever, e que só apareceu por ter havido
*alguma* execução real do script, mesmo fora do laboratório.

### 7. `requirements.txt` fixa Paramiko 3.5.1; o ambiente de desenvolvimento tem 2.9.3 instalado via pacote do sistema

`python3 -c "import paramiko; print(paramiko.__version__)"` reporta `2.9.3`
(`/usr/lib/python3/dist-packages/paramiko`), não `3.5.1`. Não instalei a
versão fixada num ambiente virtual isolado nesta sessão — os testes do
Grupo 4 (incluindo os que usam `paramiko.RejectPolicy`,
`paramiko.AutoAddPolicy`, `paramiko.AuthenticationException`,
`paramiko.ssh_exception.NoValidConnectionsError`) rodaram contra a 2.9.3.
As classes e a política padrão usadas por este módulo são estáveis entre
essas duas versões (conferido por inspeção do código-fonte instalado), mas
o comportamento exato do `SSHClient` real (não o transporte simulado) só
foi exercitado na versão do sistema, não na versão fixada em
`requirements.txt`. Achado, não corrigido — corrigir exigiria criar o
ambiente virtual limpo que a Tarefa 1.2 já verificou noutra sessão.

## O que entendi diferente (ambiguidade resolvida por leitura)

### 8. Timeout durante a leitura da saída do script é tratado como falha de alcance, não como coleta parcial

`docs/01-comportamento.md` diz que `--timeout` é "segundos para conexão e
para a coleta", sem dizer o que fazer se o tempo se esgotar no meio da
leitura do script composto (depois da conexão ter sido bem-sucedida).
Poderia, em tese, devolver um inventário parcial com os blocos que deram
tempo de chegar marcados como `null` pelo motivo "ausente". Decidi não
fazer isso: `_executar_script_composto` traduz um timeout de leitura em
`FalhaDeAlcance` (código de saída `2`), porque um inventário parcial
arriscaria ser lido como "dado completo com pouca coisa a reportar" —
justamente o tipo de mentira por omissão que a spec pede para evitar. Não
testável sem VM real ou sem simular uma trava de leitura mais elaborada no
transporte falso; não incluí esse teste nesta sessão por não haver um
requisito explícito que o peça.

## Testes

Localização: `tests/`. Adicionados nesta sessão:

- `tests/fakes_transporte.py` — o transporte SSH simulado (não é arquivo de
  teste; não começa com `test_`, não é coletado pelo `pytest`).
- `tests/test_coletor_conexao.py` — Tarefas 4.1 e 4.2.
- `tests/test_coletor_blocos.py` — Tarefa 4.4.
- `tests/test_coletor_extracao.py` — Tarefas 4.6 a 4.9.
- `tests/test_coletor_determinismo_e_somente_leitura.py` — Tarefas 4.10 e
  4.11.
- `tests/test_cli.py` — Tarefas 5.1 a 5.4.

45 testes novos, nenhum com rede real. Resultado desta sessão:
`104 passed` (`python3 -m pytest -q`, 59 da sessão anterior + 45 novos).

---

# Grupo 6 — validação

Registro produzido na sessão que executou a Tarefa 4.3, a Tarefa 4.5 e o
Grupo 6 inteiro (validação contra hosts reais) da mudança
`adicionar-inventario-de-vm`. O laboratório já estava no ar no início desta
sessão (duas EC2 Ubuntu, `3.92.162.67` "conforme" e `44.211.244.86`
"desvio"), com o usuário `roster` sem sudo, como descrito em
`infra/README.md`. Esta sessão não rodou `terraform apply` nem
`terraform destroy` — o segundo fica para quem tem a credencial AWS, por
instrução explícita.

Ambiente usado: `.venv/bin/inventario-vm` (pacote instalado com
`paramiko==3.5.1` e `PyYAML==6.0.2`, as versões fixadas em
`requirements.txt`/`pyproject.toml` — resolve o achado 7 da seção anterior,
que rodou os testes do Grupo 4 contra o Paramiko 2.9.3 do sistema). A suíte
completa (`104 passed`) foi conferida antes e depois desta sessão, sem
alteração de código.

Nenhuma spec, nenhum documento em `docs/` e nenhum artefato de design foi
alterado para acomodar um resultado de execução. Onde a execução real
revelou algo que a spec ou os documentos técnicos não previam, a decisão ou
o achado ficam registrados aqui.

## Tarefas 4.3 e 4.5 — verificação contra VM real

Rodei o script composto de `coletor.montar_script_composto()` de verdade
via `ssh ... 'sh -s' < script.sh` contra as duas VMs (não apenas contra esta
máquina de desenvolvimento, como na sessão anterior). Contra a VM conforme
e contra a VM de desvio, os nove marcadores de abertura (`@@INV:...@@`)
apareceram na saída, cada um seguido do seu marcador de status —
confirma a Tarefa 4.3 ("contra uma VM") e, por ter sido repetido nas duas,
cobre também a exigência mais forte.

A extração de identificação/SO/kernel (Tarefa 4.5) foi conferida nas duas
VMs: a VM conforme devolveu `so.distribuicao = ubuntu`, `so.versao = 24.04`
e `kernel.versao = 7.0.0-1012-aws`; a VM de desvio devolveu os mesmos
campos preenchidos e reconhecidos pelo analisador. Nas duas, o bloco
`LOGIN_ROOT` terminou com `@@STATUS:1@@` (não zero) — `sshd -T` falhou por
falta de privilégio, e `_extrair_login_de_root` devolveu `None` como
esperado, dado a nota do achado 5 da seção anterior.

**Achado sobre a AMI atual:** o kernel das duas VMs é `7.0.0-1012-aws`, não
`6.8` como `infra/README.md` registra ("A AMI se moveu..."). A AMI moveu de
novo entre a redação daquele parágrafo e esta sessão. Não afeta nenhum
critério — `7.0.0` ainda passa no mínimo `6.5` — mas quem for atualizar
`infra/README.md` deveria também atualizar esse número.

## Critério 1 — host conforme sem desvio

`inventario-vm --host 3.92.162.67 ...` devolveu `resumo.desvio == 0` e
código de saída `0`. `resumo.nao_verificado == 1` (a regra
`ssh.login_de_root`, coberta pelo critério 3). Evidências:
`evidencias/criterio1-vm-conforme.json`, `.md`, `.rc.txt`, `.stderr.txt`
(vazio).

## Critério 2 — host com desvios, três severidades

`inventario-vm --host 44.211.244.86 ...` devolveu código de saída `1` e
`resumo = {"conforme": 3, "desvio": 7, "nao_verificado": 1,
"por_severidade": {"critico": 4, "alto": 2, "medio": 1}}` — as três
severidades do baseline aparecem. Evidências:
`evidencias/criterio2-vm-desvio.json`, `.md`, `.rc.txt`.

**Achado — sétimo desvio não descrito em `infra/README.md`:** o README lista
seis desvios plantados (um por regra, ver a tabela "Estado das VMs"), mas a
execução real produziu sete entradas de `desvio`, cobrindo apenas cinco
regras diferentes mais uma consequência não antecipada: com `rpcbind.socket`
ativo (o desvio de `servicos.proibidos`), o `ss` real mostra a porta `111`
em escuta em `0.0.0.0`/`::` (TCP e UDP) — e isso também viola
`portas_em_escuta.publicas_permitidas`, que só permite `[22]`. Não é um
bug: é uma consequência real e correta do desvio plantado se propagando
para outra regra, que nem o baseline nem o README prevêem explicitamente
como "dois desvios do mesmo plantio". Registrado aqui porque quem olhar
só para o README esperaria seis entradas de desvio, não sete, e poderia
achar que a ferramenta contou uma a mais por engano.

## Critério 3 — regra não verificável distinta de conforme

Nas duas VMs, `ssh.login_de_root` aparece na seção "Não verificado" do
Markdown com o motivo "leitura da configuração efetiva de login de root
exige privilégio que o usuário da coleta não tem", e não na lista de
"Conforme". Mesma evidência do critério 1 (`criterio1-vm-conforme.md`) e do
critério 2 (`criterio2-vm-desvio.md`).

## Critério 4 — host inalcançável

Duas causas verificadas separadamente:

- **Endereço sem serviço:** `--host 127.0.0.1 --porta 65000` (porta local
  sem nada escutando, para não depender de uma rota de rede externa
  instável) devolveu código `2` e a mensagem em uma linha "127.0.0.1:65000
  não respondeu: nenhum serviço SSH alcançável", sem rastro de pilha.
  Evidência: `evidencias/criterio4-endereco-sem-servico.*`.
- **Credencial recusada:** `--host 3.92.162.67` com a chave
  `metacortex-chave-nao-emitida` (autorizada apenas na VM de desvio, não na
  conforme) devolveu código `2` e a mensagem "autenticação falhou para
  roster@3.92.162.67:22: a chave informada foi recusada pelo host", também
  sem rastro de pilha. Evidência:
  `evidencias/criterio4-credencial-recusada.*`.

As duas mensagens são distintas entre si e de qualquer mensagem de
`desvio`/`conforme`, como a Tarefa 4.2 já garantia por teste sintético —
aqui confirmado contra falha real de rede/autenticação.

## Critério 5 — repetibilidade

**Achado real, não previsto por nenhum documento:** a primeira tentativa de
comparar duas coletas seguidas (~3 segundos de intervalo) contra a VM
conforme não bateu — além de `coletado_em`, a segunda coleta trouxe uma
unidade a mais na lista de `servicos`:
`{"nome": "systemd-timedated.service", "tipo": "service", "estado":
"active"}`, ausente na primeira.

Investiguei a causa por inspeção do host (`systemctl show
systemd-timedated.service -p ActiveState -p StopWhenUnneeded`, fora da
ferramenta, só para diagnóstico): `systemd-timedated` é um serviço
ativado sob demanda por D-Bus. O próprio bloco `NTP` do script composto
(`timedatectl show -p NTPSynchronized --value`) o ativa como efeito
colateral da leitura. Ele fica `active` por um período curto de ociosidade
depois de qualquer chamada e some sozinho. Como o bloco `NTP` é o último do
script, a primeira coleta o ativa **depois** de já ter capturado o bloco
`SERVICOS` (que vem antes) — mas se a segunda coleta começa antes desse
serviço voltar a ficar ocioso, o bloco `SERVICOS` da segunda coleta o
encontra `active`. Confirmado experimentalmente: com ~90 segundos de
intervalo entre as duas coletas, a diferença fica restrita a
`coletado_em` (`evidencias/criterio5-execucao-1.json`,
`criterio5-execucao-2.json`, `criterio5-diff.txt`,
`criterio5-comparacao.txt`, esta última com a comparação programática que
neutraliza `coletado_em` e confere igualdade estrutural do resto).

**Isto não foi tratado como defeito de implementação e não foi corrigido no
código.** Motivos:

1. O coletor relata fielmente o que `systemctl` informa no momento em que
   roda — não há erro de extração ou de parsing.
2. O invariante "nenhum campo volátil entra no inventário" (D10,
   `docs/02-decisoes-tecnicas.md`) foi escrito pensando em campos dentro de
   uma entrada (tempo de atividade, PID) — não na possibilidade de a
   própria leitura de um grupo (`ntp`) alterar, por efeito colateral do
   sistema operacional, a associação de outro grupo (`servicos`) numa
   coleta futura. Nenhum documento antecipa isso.
3. Qualquer correção de código (excluir `systemd-timedated.service` da
   lista, trocar a forma de ler `NTPSynchronized`, ou reordenar blocos)
   seria uma decisão de produto sobre o que conta como "estado do host que
   importa" — não uma correção de bug, e está fora do escopo desta sessão
   de validação decidir isso sozinha.

**O que isto significa na prática:** o critério de aceite 5, como
formulado ("duas execuções seguidas"), pode falhar de forma
intermitente e reproduzível se as duas coletas ficarem muito próximas no
tempo (segundos) — não por falha do host, e não por bug de determinismo do
código (a ordenação das listas continua estável; o *conteúdo* da lista é
que muda porque o próprio ato de auditar perturbou o host por um instante).
Isto é uma lacuna real da especificação (D10 cobre ordenação e campos
voláteis dentro de uma entrada, não efeitos colaterais observáveis de
D-Bus entre coletas), reportada aqui sem alteração da spec ou do design,
como pedido.

## Critério 6 — a chave não vaza

Busquei o conteúdo das duas chaves privadas de laboratório (uma linha do
miolo base64 de cada, mais os cabeçalhos `BEGIN OPENSSH PRIVATE KEY` /
`BEGIN RSA PRIVATE KEY` / `PRIVATE KEY`) em todo o diretório `evidencias/`
— saídas JSON e Markdown das duas VMs, as duas execuções do critério 5, as
mensagens de erro do critério 4 e a saída de argumento inválido. Nenhuma
ocorrência (`grep` retornou código `1` — sem casamento — em todas as
buscas). Evidência do comando e do resultado:
`evidencias/criterio1-vm-conforme.stderr.txt` (vazio),
`evidencias/criterio4-*.stderr.txt`, e a saída do próprio `grep` reproduzida
no transcript desta sessão (não gravada em arquivo separado porque o
próprio código de saída do `grep` já é a evidência: sem correspondência).

## Argumento inválido (evidência adicional, fora dos seis critérios)

`inventario-vm --formato xml ...` devolveu código `3` (erro interno) e a
mensagem padrão do `argparse` em `stderr`, nunca o código `2` (host
inalcançável) — confirma a Tarefa 5.3 e a decisão D7 contra falha real de
digitação. Evidência: `evidencias/argumento-invalido.*`.

## Evidências gravadas (Tarefa 6.8, parte de gravação)

Todos os arquivos abaixo estão em `evidencias/`, com saída crua (não
parafraseada):

- `criterio1-vm-conforme.{json,md,rc.txt,stderr.txt}`
- `criterio2-vm-desvio.{json,md,rc.txt,stderr.txt}`
- `criterio4-endereco-sem-servico.{stdout.txt,stderr.txt,rc.txt}`
- `criterio4-credencial-recusada.{stdout.txt,stderr.txt,rc.txt}`
- `criterio5-execucao-1.json`, `criterio5-execucao-2.json`,
  `criterio5-execucao-1.rc.txt`, `criterio5-execucao-2.rc.txt`,
  `criterio5-diff.txt` (diff bruto), `criterio5-comparacao.txt`
  (comparação programática com `coletado_em` neutralizado)
- `argumento-invalido.{stdout.txt,stderr.txt,rc.txt}`

**A destruição do laboratório (`terraform destroy`) não foi executada nesta
sessão** — por instrução explícita, fica para quem tem a credencial AWS.
As duas VMs (`3.92.162.67` e `44.211.244.86`) continuavam no ar ao final
desta sessão.

## Resumo do que a execução real revelou

1. Tarefas 4.3 e 4.5 se confirmam contra as duas VMs reais, sem surpresa
   além da AMI ter mudado de kernel de novo (achado cosmético sobre
   `infra/README.md`, não sobre o código).
2. Os seis critérios de aceite passam. O critério 5 exigiu entender e
   documentar uma causa raiz não trivial (achado sobre
   `systemd-timedated.service`) para produzir uma comparação limpa — a
   diferença entre execuções muito próximas no tempo é real, reproduzível,
   e não é um bug do coletor nem uma falha do host: é um efeito colateral
   do próprio ato de auditar via `timedatectl`, fora do que qualquer
   documento desta mudança previu.
3. O laboratório de desvio produz um desvio a mais do que o README
   documenta (sétimo, em `portas_em_escuta.publicas_permitidas`, por conta
   do `rpcbind.socket` exposto), consequência correta de um desvio
   plantado se propagando para outra regra — vale nota para quem mantiver
   `infra/README.md`.
4. Nenhuma spec, design ou documento de `docs/` precisou de correção: os
   três achados acima são registros de comportamento do ambiente real, não
   contradições no texto especificado.

---

# Correção pós-validação — a coleta mudava o que ela observava

A sessão de validação registrou, sem corrigir, que duas coletas muito próximas no
tempo divergiam. A causa foi confirmada de forma independente depois:

```
antes de qualquer coleta : systemd-timedated.service  inactive
imediatamente após uma coleta: systemd-timedated.service  active
```

O bloco `NTP` do script usa `timedatectl`, que conversa com o `systemd-timedated`
por D-Bus — e o systemd ativa esse serviço **sob demanda**. Ou seja: uma ferramenta
declarada somente-leitura provocava mudança de estado no host auditado.

O efeito prático quebrava o critério de aceite 5. Com o bloco `SERVICOS` sendo
amostrado **antes** do bloco `NTP`, a primeira execução via a unidade inativa e a
segunda a via ativa — duas coletas seguidas divergiam sem que o host tivesse
mudado por conta própria.

**Correção aplicada:** o bloco `NTP` passou a ser emitido **antes** do bloco
`SERVICOS`. Acionando o D-Bus primeiro, toda execução amostra o mesmo estado, e a
repetibilidade passa a valer inclusive para coletas coladas.

Verificado com duas execuções separadas por dois segundos:

```
.host.coletado_em: '2026-09-07T02:30:01Z' -> '2026-09-07T02:30:03Z'
total de diferenças: 1
```

**Alternativas descartadas:**

- **Abandonar o `timedatectl`** e ler a sincronização de outra fonte. Elimina o
  efeito colateral, mas as fontes alternativas são específicas de cada mecanismo
  de tempo — transformaria uma regra verificável em `nao_verificado` na maioria
  dos hosts, que é pior do que o problema.
- **Filtrar da lista de serviços as unidades que a própria coleta ativou.** Frágil
  e desonesto: o inventário deixaria de ser retrato fiel para esconder um efeito
  que a ferramenta causou.
- **Afrouxar o critério 5 para valer só sobre vereditos.** Nenhum veredito mudava
  de fato — `systemd-timedated` não aparece em nenhuma regra do baseline. Mas
  afrouxar a especificação para acomodar um defeito é o caminho contrário ao deste
  projeto: era defeito de implementação, e implementação se conserta.

**O que fica registrado como limite conhecido:** observar não é gratuito. O
inventário passa a listar `systemd-timedated` como ativo em todo host onde a
coleta rodou, mesmo que ele estivesse inativo antes. É determinístico e está
documentado, mas é uma pegada que a ferramenta deixa — e o único jeito de não
deixá-la seria abrir mão de ler a sincronização de tempo.
