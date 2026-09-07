## Why

O inventário do parque é uma página mantida à mão desde a época em que havia trinta
hosts. Ela nasceu correta e envelheceu: host que mudou de papel, agente instalado
numa madrugada de incidente e nunca registrado, chave SSH que entrou para
desbloquear alguém e ficou. Quando Segurança & Compliance pergunta quantas VMs
estão fora do padrão, a resposta honesta é "não sei" — e a mesma resposta serve
quando a pergunta é quanto o parque custa a mais por estar assim.

Não existe agente instalado nas VMs e ninguém vai instalar um só para isso. O que
existe em toda VM é acesso por chave, e é com ele que a substituição do Roster
manual precisa trabalhar.

## What Changes

- Nova ferramenta de linha de comando que roda na estação de quem opera, recebe
  endereço, usuário e chave privada, entra por SSH numa VM do parque e devolve o
  retrato real daquele host.
- O retrato é comparado com o `baseline.yaml` versionado pelo time, produzindo uma
  entrada de conformidade por regra com veredito e severidade.
- O veredito tem **três** valores, não dois: `conforme`, `desvio` e
  `nao_verificado`. O terceiro existe porque a coleta entra com usuário comum e
  parte do baseline só se lê com privilégio — reportar isso como conforme seria
  mentira, e abortar a execução seria inútil.
- Duas saídas do mesmo dado: JSON, para o Roster consumir quando existir, e
  Markdown, para o plantão ler no terminal.
- Código de saída utilizável em pipeline, distinguindo host conforme, host com
  desvio, host inalcançável e erro interno.
- A ferramenta **só lê**. Nada é instalado, escrito ou corrigido do outro lado da
  conexão, e duas execuções seguidas devolvem o mesmo veredito para cada regra.
- A chave privada é tratada como credencial: não aparece na saída, no log nem em
  mensagem de erro.

Não há mudança que quebre nada: o Roster manual continua existindo enquanto esta
ferramenta não for adotada.

## Capabilities

### New Capabilities

- `coleta-de-inventario`: conexão SSH somente-leitura com um host e produção do
  retrato do sistema — identificação, sistema operacional, kernel, unidades ativas
  distinguindo serviço de socket, swap, portas em escuta com endereço de vínculo e
  processo dono, chaves SSH autorizadas, configuração efetiva de login de root e
  sincronização de tempo. Inclui a semântica de dado não coletável e as garantias
  de determinismo e de sigilo da credencial.
- `avaliacao-de-conformidade`: comparação entre um inventário e um baseline,
  produzindo uma entrada por regra com os três vereditos possíveis, a severidade
  declarada pelo baseline e o motivo quando não foi possível verificar. É função
  pura do par (inventário, baseline), sem acesso a rede.
- `relatorio-e-saida`: apresentação do mesmo dado em JSON e em Markdown, o resumo
  por veredito e por severidade, e os códigos de saída que o pipeline consome.

### Modified Capabilities

Nenhuma. É a primeira capacidade especificada neste projeto.

## Impact

- **Novo código:** pacote Python com três módulos correspondentes às três
  capacidades, mais um ponto de entrada de linha de comando.
- **Novas dependências:** Paramiko, para o transporte SSH, e um analisador de YAML
  para ler o baseline. Fixadas em `requirements.txt`.
- **Ambiente de quem opera:** exige Python 3 e as duas bibliotecas. A ferramenta
  não é instalada nos hosts auditados.
- **Hosts auditados:** nenhum impacto. Nenhuma escrita, nenhum pacote, nenhum
  agente. O único efeito é uma sessão SSH de leitura.
- **Infraestrutura de validação:** duas VMs EC2 já descritas em `infra/`, uma
  preparada dentro do baseline e outra com um desvio de cada severidade. Elas
  sobem para a validação e são destruídas em seguida.
- **Documentos que sustentam esta mudança:** `docs/01-comportamento.md` fixa o
  contrato observável e os critérios de aceite; `docs/02-decisoes-tecnicas.md`
  registra as dez decisões com as alternativas descartadas.
