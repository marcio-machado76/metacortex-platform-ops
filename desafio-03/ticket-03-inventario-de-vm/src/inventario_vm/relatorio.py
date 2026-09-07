"""Relatório — serializa o mesmo dado em JSON e em Markdown.

Não conhece SSH e não importa Paramiko. Consome o inventário e o resultado
de `avaliador.avaliar` e produz as duas saídas descritas em
`docs/01-comportamento.md`, seção "Saídas", e em
`specs/relatorio-e-saida/spec.md`.

## Sobre o campo "host" no contrato JSON (decisão desta implementação)

`docs/01-comportamento.md` descreve a saída em JSON como "um objeto com
`host`, `inventario`, `conformidade` e `resumo`" — quatro membros distintos.
Mas a tabela "O inventário", no mesmo documento, lista `host` como o
primeiro grupo de campos *do próprio inventário* (`endereco`, `hostname`,
`coletado_em`). Os dois textos não se conciliam sozinhos: se `host` já mora
dentro de `inventario`, chamá-lo de novo de membro irmão no nível raiz seria
duplicar o dado ou description confusa.

Esta implementação resolve a ambiguidade assim: o inventário Python (ver
`avaliador.py`) mantém `host` como um dos seus grupos, exatamente como a
tabela descreve. `montar_relatorio`, ao montar o objeto final que vai para o
JSON e para o Markdown, **extrai** `inventario["host"]` para o nível raiz
como `relatorio["host"]` e mantém `relatorio["inventario"]` com os
**demais** grupos (sem repetir `host` lá dentro). Isso satisfaz a frase "um
objeto com host, inventario, conformidade e resumo" ao pé da letra, sem
duplicar o dado. Ver `docs/03-divergencias-da-implementacao.md`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

SEVERIDADES_EM_ORDEM = ("critico", "alto", "medio")

_ROTULO_SEVERIDADE = {
    "critico": "crítico",
    "alto": "alto",
    "medio": "médio",
}


# ---------------------------------------------------------------------------
# Montagem do relatório (compartilhada pelas duas saídas)
# ---------------------------------------------------------------------------


def montar_relatorio(inventario: dict, resultado_avaliacao: dict) -> dict:
    """Monta o objeto de relatório a partir do inventário e da avaliação.

    `resultado_avaliacao` é o que `avaliador.avaliar` devolve:
    ``{"conformidade": [...], "resumo": {...}}``.
    """
    inventario_sem_host = {chave: valor for chave, valor in inventario.items() if chave != "host"}
    return {
        "host": inventario.get("host"),
        "inventario": inventario_sem_host,
        "conformidade": resultado_avaliacao["conformidade"],
        "resumo": resultado_avaliacao["resumo"],
    }


# ---------------------------------------------------------------------------
# JSON (Tarefa 3.1)
# ---------------------------------------------------------------------------


def gerar_json(relatorio: dict) -> str:
    """Serializa o relatório em JSON.

    Campo desconhecido (valor `None` em Python) sai como `null` — é o
    comportamento nativo de `json.dumps`, sem tratamento especial.
    """
    return json.dumps(relatorio, indent=2, ensure_ascii=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Markdown (Tarefa 3.2)
# ---------------------------------------------------------------------------


def _agrupar_por_veredito(conformidade: List[dict]) -> Dict[str, List[dict]]:
    grupos: Dict[str, List[dict]] = {"desvio": [], "nao_verificado": [], "conforme": []}
    for entrada in conformidade:
        grupos[entrada["veredito"]].append(entrada)
    return grupos


def _formatar_valor(valor: Any) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def gerar_markdown(relatorio: dict, baseline: dict) -> str:
    """Gera a saída em Markdown a partir do mesmo relatório usado no JSON.

    Ordem das seções: cabeçalho, Desvios (por severidade: crítico, alto,
    médio), Não verificado, Conforme. Seção sem conteúdo não é apresentada
    — ver Requirement "Saída em Markdown para leitura humana".
    """
    host = relatorio.get("host") or {}
    linhas: List[str] = []

    titulo = host.get("hostname") or host.get("endereco") or "host"
    linhas.append(f"# Inventário e conformidade — {titulo}")
    linhas.append("")
    linhas.append(f"- Endereço: {_formatar_valor(host.get('endereco'))}")
    linhas.append(f"- Coletado em: {_formatar_valor(host.get('coletado_em'))}")
    linhas.append(f"- Baseline: versão {_formatar_valor(baseline.get('versao'))}")

    grupos = _agrupar_por_veredito(relatorio.get("conformidade", []))

    desvios = sorted(
        grupos["desvio"],
        key=lambda entrada: SEVERIDADES_EM_ORDEM.index(entrada["severidade"])
        if entrada.get("severidade") in SEVERIDADES_EM_ORDEM
        else len(SEVERIDADES_EM_ORDEM),
    )
    if desvios:
        linhas.append("")
        linhas.append("## Desvios")
        linhas.append("")
        linhas.append("| Severidade | Regra | Esperado | Encontrado |")
        linhas.append("|---|---|---|---|")
        for entrada in desvios:
            rotulo = _ROTULO_SEVERIDADE.get(entrada.get("severidade"), entrada.get("severidade"))
            linhas.append(
                f"| {rotulo} | {entrada['regra']} | {_formatar_valor(entrada['esperado'])} "
                f"| {_formatar_valor(entrada['encontrado'])} |"
            )

    nao_verificados = grupos["nao_verificado"]
    if nao_verificados:
        linhas.append("")
        linhas.append("## Não verificado")
        linhas.append("")
        linhas.append("| Regra | Motivo |")
        linhas.append("|---|---|")
        for entrada in nao_verificados:
            linhas.append(f"| {entrada['regra']} | {_formatar_valor(entrada['motivo'])} |")

    conformes = grupos["conforme"]
    if conformes:
        linhas.append("")
        linhas.append("## Conforme")
        linhas.append("")
        for entrada in conformes:
            linhas.append(f"- {entrada['regra']}")

    linhas.append("")
    return "\n".join(linhas)
