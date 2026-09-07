# Matriz de roteamento — duas skills disputando o mesmo território

As duas moram em Kubernetes, YAML e coisa que quebra, e o agente escolhe qual
carregar lendo um trecho de texto só. Isto mede o que acontece de verdade.

## Método

Cada frase rodou numa **sessão limpa** — `claude -p`, a partir da raiz do
repositório, com as duas skills instaladas em `.claude/skills/` e nenhum contexto
desta conversa. Saída bruta de cada uma em `saidas-brutas/`.

```bash
claude -p "<frase>" --output-format stream-json --verbose --max-turns 1
```

O `--max-turns` corta a sessão logo após a decisão, o que mantém a medição barata
(~3s e ~US$ 0,07 por frase) — e foi também a fonte do único erro de método aqui.

## O instrumento estava errado antes das skills

Na primeira passada, três frases não dispararam skill nenhuma e gastaram o único
turno com um `Bash`. A leitura fácil seria "a skill não disparou". A leitura certa
exigia desconfiar da régua: **o turno foi gasto procurando de que manifesto a
pessoa estava falando**, porque a frase não diz.

Re-rodando as duas relevantes com `--max-turns 3`:

| Frase | 1 turno | 3 turnos |
|---|---|---|
| "esse manifesto está no padrão da casa?" | nenhuma skill | `find` → `find` → **padrao-de-manifests** |
| "esse manifesto não sobe no cluster" | nenhuma skill | `find` → `git status` → **padrao-de-manifests** |

Não era falha de roteamento; era a régua curta demais. Fica registrado porque é o
tipo de erro que produz "correção" de skill que conserta o que não estava quebrado.

## O resultado

| # | Frase | Disparou | Veredito |
|---|---|---|---|
| 1 | "o pod do nyx-prod não sobe" | `triagem-de-cluster` | ✅ |
| 2 | "por que esse deployment está 0/3" | `triagem-de-cluster` | ✅ |
| 3 | "o service do nyx-stg não tem endpoint" | `triagem-de-cluster` | ✅ |
| 4 | "revisa esse deployment antes de eu subir" | `padrao-de-manifests` | ✅ |
| 5 | "esse manifesto está no padrão da casa?" | `padrao-de-manifests` | ✅ (com orientação antes) |
| 6 | "cria um Deployment novo do zero pra mim" | `padrao-de-manifests` | ✅ |
| 7 | "esse manifesto não sobe no cluster" | `padrao-de-manifests` | ⚠️ ambígua |
| 8 | "o Service do nyx não está entregando tráfego" | `triagem-de-cluster` | ⚠️ ambígua |
| 9 | "o que é um DaemonSet?" | **nenhuma**, respondeu direto | ✅ |
| 10 | "provisiona uma VM nova no Construct pro cliente orion" | **nenhuma** | ✅ |

**Oito de dez limpas, zero disparo errado, duas ambíguas resolvidas de forma
defensável.**

A frase 9 merece nota porque o acerto é não disparar. `"o que é um DaemonSet?"`
está no território das duas skills e é conhecimento geral — carregar skill ali
seria custo puro. As descrições delimitam **quando** usar, e isso segurou.

A 10 é fora de escopo: o Construct não tem skill, e nenhuma das duas se ofereceu.

## As duas ambíguas, e por que não viram correção

O enunciado avisa que nem todo disparo errado vira correção — às vezes o pedido é
que estava mal formulado. É o caso das duas.

**7 · "esse manifesto não sobe no cluster"** — pode ser YAML que o apiserver
rejeita (padrão) ou pod que não agenda depois de aplicado (triagem). O fato que
decide é **se o objeto já existe no cluster**, e a frase não diz.

**8 · "o Service do nyx não está entregando tráfego"** — é o Chamado 3, e a triagem
acertou. Mas o defeito nasceu no manifesto: seletor que não casa é a regra 1.4. Com
o Service já no ar, triagem é a resposta certa; com o YAML na mão antes de subir,
seria a outra.

**As duas descrições já carregam o critério que desempata** — as duas dizem que a
fronteira é o objeto já estar rodando. O que falta não está na skill, está na
frase. Mexer na descrição para forçar uma delas a vencer pioraria o outro lado da
ambiguidade.

## O que mudou por causa desta matriz

**Uma mudança, nas duas skills.** O teste mostrou que o agente resolve a
ambiguidade sozinho e em silêncio — e que ele resolve *plausivelmente*, não
*corretamente*, porque o dado que decide não está no pedido. Cada skill ganhou uma
linha dizendo o que fazer quando não dá para saber: perguntar se o objeto já está
no cluster custa uma frase, e adivinhar custa uma triagem inteira na camada errada.

**Nenhuma mudança de descrição.** Não houve disparo errado para corrigir. Ajustar
descrição sem falha que a justifique é o começo do inchaço que faz skill parar de
ser usada.

## O custo do roteamento

Cerca de US$ 0,07 e três segundos por decisão, incluindo as frases em que a
resposta certa foi não carregar skill nenhuma. É o preço de a escolha ser feita
por leitura de descrição, e não por palavra-chave.
