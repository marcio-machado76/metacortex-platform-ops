# Quanto o Trivy já pega — medido, não suposto

Antes de escrever qualquer linha de script, a pergunta do ticket: o ferramental
determinístico que já existe na máquina do time cobre quanto do padrão?

Rodado em 2026-09-06, `trivy 0.74.0`, sobre o manifesto barrado do nyx
(`insumos/manifesto-barrado-nyx.yaml`). Saída bruta em
`trivy-manifesto-barrado.txt` e `.json`.

```
Tests: 117 (SUCCESSES: 99, FAILURES: 18)
Failures: 18 (LOW: 10, MEDIUM: 5, HIGH: 3, CRITICAL: 0)
```

18 achados parece bastante — até mapeá-los de volta para o padrão.

## Os 18 achados, agrupados pela regra que eles cobrem

| Regra do padrão | Peso | Checks do Trivy | Achados |
|---|---|---|---|
| **2.1** requests e limits | obrigatório | KSV-0011, KSV-0015, KSV-0016, KSV-0018 | 4 |
| **3.1** tag `:latest` | proibido | KSV-0013 | 1 |
| **3.2** securityContext | obrigatório | KSV-0001, KSV-0003, KSV-0004, KSV-0012, KSV-0014, KSV-0020, KSV-0021, KSV-0030, KSV-0104, KSV-0106, KSV-0118 ×2 | 12 |
| **3.7** registry interno | obrigatório | KSV-0125 | 1 — **invertido, ver abaixo** |

Três regras cobertas de fato. Uma quarta, a **3.6** (`hostNetwork`, `hostPID`,
`privileged`), está no catálogo do Trivy e não gerou achado aqui apenas porque o
manifesto barrado não a viola — ela também é dele.

**Quatro das 19.** As outras quinze o Trivy não menciona uma única vez.

## O KSV-0125 anda para o lado errado

O manifesto barrado usa `registry.metacortex.io/nyx/api:latest`, que **cumpre** a
regra 3.7. O Trivy marca assim mesmo:

```
KSV-0125 (MEDIUM): Restrict container images to trusted registries
```

O catálogo dele tem lista própria de registries confiáveis e o domínio do parque
não está nela. Ou seja: obedecer à regra 3.7 gera achado na ferramenta que a mesma
Segurança & Compliance opera. O custo não é o achado — é o hábito de ignorar
MEDIUM que ele ensina.

Consequência para a skill: a 3.7 **não** pode ser delegada ao Trivy. Quem sabe
qual é o registry da casa é a skill.

## O que passa batido, e que não é periferia

As quinze regras que o Trivy não menciona incluem três violações reais **presentes
neste manifesto**:

| Regra | Peso | O desvio no manifesto barrado | O Trivy diz |
|---|---|---|---|
| **1.1** kebab-case | obrigatório | `metadata.name: NyxAPI` | nada |
| **1.4** seletor casa com o pod | obrigatório | Service seleciona `app: nyx-api`, pod tem `app: nyxapi` | nada — zero ocorrências de "selector" na saída |
| **3.3** segredo em texto puro | **proibido** | `DATABASE_URL` com `s3nh4-do-banco` embutida | nada |

A 3.3 merece um teste próprio, porque a hipótese natural é que o scanner dedicado
a segredos a pegue. Não pega:

```
$ trivy fs --scanners secret insumos/manifesto-barrado-nyx.yaml
┌────────┬──────┬─────────┐
│ Target │ Type │ Secrets │
├────────┼──────┼─────────┤
│   -    │  -   │    -    │
└────────┴──────┴─────────┘
```

Uma senha em URL de conexão dentro de `env.value` sai limpa das duas varreduras.
É a regra classificada como **proibida** — a categoria que o padrão define como
"existe um caso registrado de estrago" — e nenhuma ferramenta de mercado a vê.

## Onde o Trivy é mais exigente que o padrão

Dois achados cobram algo que a regra 3.2 não lista: `KSV-0030` e `KSV-0104` pedem
`seccompProfile: RuntimeDefault`. O padrão enumera cinco campos de
`securityContext` e esse não está entre eles.

Não é conflito, é lacuna do padrão: sem `seccompProfile`, o pod é recusado na
admissão em namespace com Pod Security `restricted`. Seguir a 3.2 ao pé da letra
produz manifesto que o cluster não aceita.

## O que esta medição decide

1. **Não reimplementar 2.1, 3.1, 3.2 e 3.6.** Já vêm prontas. Duplicar detecção
   cria duas fontes de verdade que divergem no dia em que uma mudar.
2. **A skill responde pelo que é da Metacortex, não do Kubernetes.** Nomenclatura,
   formato de namespace, rótulos da casa, registry do parque, cruzamento de
   seletor: nenhuma ferramenta de mercado tem como conhecer.
3. **A 3.7 fica com a skill**, apesar de o Trivy tocar nela — porque ele a avalia
   ao contrário.
4. **A 3.3 é prioridade**, não detalhe: é a regra mais grave do padrão e a mais
   completamente invisível ao ferramental existente.
