## 1. Estrutura e dependências

- [x] 1.1 Criar `src/painel_cluster/` com os módulos vazios `cliente.py`, `modelo.py`, `tela.py` e `cli.py`, e verificar que `python -c "import painel_cluster"` funciona a partir de `src/`
- [x] 1.2 Escrever `requirements.txt` com `kubernetes` e `textual` em versão fixada, e verificar que `pip install -r requirements.txt` numa venv limpa instala sem conflito
- [x] 1.3 Escrever `pytest.ini` marcando `tests/` e verificar que `pytest --collect-only` roda sem erro de coleta

## 2. Fixtures capturadas do cluster real

- [x] 2.1 Capturar o JSON cru do pod `nyx-api` do `nyx-prod` e verificar que a fixture contém `state.waiting.reason` igual a `CrashLoopBackOff` e `lastState.terminated.reason` igual a `OOMKilled`
- [x] 2.2 Capturar o Deployment `orion-web` do `orion-stg` e verificar que a chave `readyReplicas` **não** existe no status da fixture
- [x] 2.3 Capturar o StatefulSet `nyx-postgres` do `nyx-dev` e verificar que a chave `conditions` **não** existe no status da fixture
- [x] 2.4 Capturar o `Endpoints` e a `EndpointSlice` do Service `nyx-api` do `nyx-stg` e verificar que na primeira a chave `subsets` está ausente e na segunda `endpoints` está presente com valor nulo
- [x] 2.5 Capturar eventos do `nyx-prod` pela API `core/v1` e verificar que a fixture tem `count` e `lastTimestamp` preenchidos
- [x] 2.6 Capturar o Deployment `nyx-api` do `nyx-dev` e o `orion-web` do `orion-prod` como amostras saudáveis de uma e de duas réplicas, e verificar que as duas têm `readyReplicas` presente
- [x] 2.7 Registrar em `tests/fixtures/README.md` o comando que reproduz cada captura, e verificar que rodar os comandos contra o cluster produz JSON com a mesma forma

## 3. Fronteira de leitura

- [x] 3.1 Implementar em `cliente.py` a resolução do contexto corrente e a exposição de nome de contexto e endereço do servidor, e verificar com teste que o contexto lido é o corrente do kubeconfig de teste
- [x] 3.2 Implementar o tipo de envelope com os quatro estados e o motivo associado, e verificar com teste que os quatro são distinguíveis entre si
- [x] 3.3 Implementar a leitura dos sete tipos por `LIST`, devolvendo JSON cru dentro do envelope, e verificar com teste de transporte simulado que nenhuma interpretação acontece nesta camada
- [x] 3.4 Implementar o mapeamento de falha de autorização para envelope `negado` restrito ao tipo, e verificar com teste que os demais envelopes seguem `ok`
- [x] 3.5 Implementar o mapeamento de falha de autenticação para `indisponível` por credencial em todos os tipos, e verificar com teste que a mensagem não afirma que a credencial está expirada
- [x] 3.6 Implementar o mapeamento de falha de transporte para `indisponível` por cluster, e verificar com teste que a exceção da dependência transitiva é capturada aqui e não escapa
- [x] 3.7 Implementar o encerramento com código 2 quando não houver kubeconfig legível ou contexto corrente, e verificar com teste que nenhum rastreamento de pilha é impresso

## 4. Interpretação — pods

- [x] 4.1 Implementar o estado exibido de pod a partir de fase, marca de remoção e estado dos containers, e verificar com a fixture 2.1 que o resultado é `CrashLoopBackOff` e não `Running`
- [x] 4.2 Implementar a detecção de pod em remoção pela marca de remoção, e verificar com teste que fase `Running` mais marca presente produz `Terminating`
- [x] 4.3 Implementar a contagem de containers prontos sobre o total, e verificar com teste que pod sem container pronto produz `0/1` e não erro
- [x] 4.4 Implementar a exibição das duas metades do motivo de falha, e verificar com a fixture 2.1 que os dois motivos aparecem e que o do encerramento anterior é apresentado como causa
- [x] 4.5 Implementar a leitura de presença de sonda de prontidão por container, e verificar com teste que pod com dois containers e uma sonda produz `1/2`

## 5. Interpretação — controladores e Services

- [x] 5.1 Implementar a normalização de campo ausente, nulo e coleção vazia num único ponto, e verificar com teste que nenhuma chamada dessa camada testa presença de chave
- [x] 5.2 Implementar prontos sobre desejados para Deployment, e verificar com a fixture 2.2 que o resultado é `0/3` mesmo sem a chave `readyReplicas`
- [x] 5.3 Implementar prontos sobre desejados para StatefulSet pelo mesmo caminho, e verificar com a fixture 2.3 que o resultado é `1/1`
- [x] 5.4 Implementar a condição de controlador só onde a API a fornece, e verificar com a fixture 2.3 que o StatefulSet não produz coluna de condição e não é marcado como anormal
- [x] 5.5 Implementar a distinção entre zero afirmado e nada afirmado usando geração observada, condições e idade, e verificar com teste que controlador recém-criado não é classificado como degradado
- [x] 5.6 Implementar a agregação de fatias de endereço por Service, e verificar com teste que várias fatias do mesmo Service produzem uma só linha
- [x] 5.7 Implementar os três estados de endereço de Service, e verificar com a fixture 2.4 que as duas formas de ausência produzem o mesmo `sem endereço`
- [x] 5.8 Implementar a marcação de Service sem endereço como anormal, e verificar com teste que ela ocorre mesmo com todos os pods do namespace prontos

## 6. Interpretação — eventos e ordenação

- [x] 6.1 Implementar a leitura de eventos recentes com janela de uma hora sobre o instante da última ocorrência, e verificar com a fixture 2.5 que evento fora da janela não aparece
- [x] 6.2 Implementar a ordenação de eventos do mais recente para o mais antigo, e verificar com teste que a ordem de entrada não influencia a de saída
- [x] 6.3 Implementar o recuo para o campo alternativo de instante quando o principal vier ausente ou nulo, e verificar com teste que os dois casos produzem o mesmo resultado
- [x] 6.4 Implementar os cinco critérios de anormalidade, cada um apontando o campo lido que o originou, e verificar com teste que nenhum critério é derivado de outro critério
- [x] 6.5 Implementar a ordenação por anormalidade com alfabética para os demais, e verificar com as fixtures 2.2 e 2.6 que o degradado vem antes do saudável
- [x] 6.6 Verificar com teste que todo objeto ordenado como anormal carrega ao menos um critério exibível

## 7. Tela

- [ ] 7.1 Montar a estrutura da tela com os painéis de namespaces, pods, controladores, Services e eventos, e verificar por captura de texto que os cinco aparecem
- [ ] 7.2 Implementar a exibição permanente de contexto e endereço do servidor, e verificar por captura que eles continuam visíveis nos estados de falha
- [ ] 7.3 Implementar a seleção de namespace e o escopo dos demais painéis, e verificar que trocar de namespace troca o conteúdo dos quatro painéis
- [ ] 7.4 Implementar a busca por trecho de nome e a limpeza da busca, e verificar que buscar `postgres` no `nyx-prod` deixa só os objetos correspondentes
- [ ] 7.5 Implementar o desenho dos quatro estados de envelope, e verificar por captura que `vazio`, `negado` e `indisponível` são visualmente distintos entre si
- [ ] 7.6 Implementar a atualização em intervalo fixo com ritmo próprio para a lista de namespaces, e verificar que os dois intervalos são independentes
- [ ] 7.7 Implementar a atualização sob comando e a exibição da idade do dado, e verificar que o comando zera a idade exibida
- [ ] 7.8 Implementar a coluna de critério de anormalidade, e verificar por captura que o motivo aparece na linha do objeto

## 8. Garantia de só-leitura e contenção

- [ ] 8.1 Escrever o teste que falha se qualquer verbo de escrita aparecer no código, e verificar que ele falha quando um verbo de escrita é introduzido de propósito
- [ ] 8.2 Escrever o teste que falha se qualquer módulo **de `src/`** fora da fronteira importar o cliente ou o transporte, e verificar que ele falha quando o import é introduzido de propósito. O teste da própria fronteira precisa importar os tipos de exceção para simular o transporte, e está fora da regra
- [ ] 8.3 Escrever o teste que falha se a leitura deixar de preservar a distinção entre chave ausente e valor nulo, e verificar que ele falha com o modo de leitura alternativo
- [ ] 8.5 Escrever o teste que cobre falha de apiserver que não é 401 nem 403 (por exemplo 5xx), e verificar que ela vira envelope `indisponível` com o status no motivo, em vez de escapar
- [ ] 8.4 Verificar que a suíte inteira roda sem tocar a rede, com o transporte simulado, e registrar a contagem de testes

## 9. Empacotamento

- [ ] 9.1 Escrever `pyproject.toml` expondo o comando `painel-cluster`, e verificar que `painel-cluster --help` funciona após instalação editável
- [ ] 9.2 Implementar o código de saída 1 para erro de uso, e verificar que argumento inválido produz 1 e mensagem, sem rastreamento de pilha
- [ ] 9.3 Escrever o `README.md` do ticket com a instalação, os dois contextos RBAC e qual deles é o recomendado, e verificar que seguir o README numa máquina limpa produz painel funcionando

## 10. Validação contra o cluster real

- [ ] 10.1 Rodar contra `nyx-dev` e verificar o critério de aceite 1: Deployment `1/1`, StatefulSet `1/1`, dois Services com endereço, nenhum objeto anormal
- [ ] 10.2 Rodar contra `nyx-prod`, `orion-stg` e `nyx-stg` e verificar o critério de aceite 2: `0/2` com os dois motivos, `0/3` sem `readyReplicas`, e Service sem endereço
- [ ] 10.3 Comparar `nyx-dev` e `orion-prod` e verificar o critério de aceite 3: réplica única e duas réplicas no mesmo formato de coluna
- [ ] 10.4 Verificar o critério de aceite 4: o StatefulSet aparece sem coluna de condição e sem marca de anormalidade
- [ ] 10.5 Verificar o critério de aceite 5: `orion-web` do `orion-stg` sem sonda de prontidão e `nyx-api` do `nyx-dev` com sonda
- [ ] 10.6 Rodar sob o contexto `platform-ro-sem-events` e verificar o critério de aceite 6: painel de eventos negado, os demais preenchidos
- [ ] 10.7 Rodar com o certificado de cliente vencido e verificar o critério de aceite 7: estado de credencial recusada, contexto e servidor visíveis, sem rastreamento de pilha
- [ ] 10.8 Rodar contra endereço morto e verificar o critério de aceite 8: estado de indisponível, endereço tentado visível, código de saída 0 ao encerrar
- [ ] 10.9 Verificar o critério de aceite 9: busca por nome dentro do namespace selecionado
- [ ] 10.10 Rodar a sessão inteira sob `platform-ro` e verificar o critério de aceite 10: nenhuma negativa de RBAC no registro de auditoria
- [ ] 10.11 Gravar a saída crua de cada verificação acima em `evidencias/`, com o comando que a reproduz ao lado
