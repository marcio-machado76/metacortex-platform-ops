"""Linha de comando da ferramenta de inventário e drift de VM (Grupo 5 de
`tasks.md`).

Orquestra os três outros módulos — `coletor`, `avaliador`, `relatorio` — e
traduz o resultado em um dos quatro códigos de saída descritos em
`docs/01-comportamento.md`, seção "Códigos de saída", e no Requirement
"Código de saída utilizável em pipeline" de `specs/relatorio-e-saida/spec.md`.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import List, Optional, Sequence

import yaml

from . import avaliador, coletor, relatorio

# Códigos de saída (docs/01-comportamento.md, "Códigos de saída"; decisão D7
# em docs/02-decisoes-tecnicas.md).
CODIGO_CONFORME = 0
CODIGO_DESVIO = 1
CODIGO_HOST_INALCANCAVEL = 2
CODIGO_ERRO_INTERNO = 3

_FORMATOS_VALIDOS = ("json", "markdown", "ambos")


class _AnalisadorComCodigoDeErroPersonalizado(argparse.ArgumentParser):
    """Sobrescreve o código de saída padrão do `argparse` diante de erro de
    argumento (Tarefa 5.3).

    Por padrão, `argparse.ArgumentParser.error()` termina o processo com
    código `2` — que nesta ferramenta é "host inalcançável" (decisão D7,
    "armadilha concreta"). Um erro de digitação no comando apareceria no
    painel como host fora do ar. Aqui o erro de argumento sempre termina em
    `3` (erro interno), distinto de `2`.
    """

    def error(self, message: str) -> None:  # pragma: no cover - repassa ao SystemExit
        self.print_usage(sys.stderr)
        self.exit(CODIGO_ERRO_INTERNO, f"{self.prog}: erro: {message}\n")


def construir_analisador() -> argparse.ArgumentParser:
    """Monta o analisador de argumentos com a interface completa descrita em
    `docs/01-comportamento.md`, seção "Interface" (Tarefa 5.1).
    """
    analisador = _AnalisadorComCodigoDeErroPersonalizado(
        prog="inventario-vm",
        description=(
            "Coleta o inventário de uma VM por SSH e avalia a conformidade "
            "contra um baseline versionado."
        ),
    )
    analisador.add_argument(
        "--host", required=True, help="endereço usado na conexão; reaparece no inventário"
    )
    analisador.add_argument(
        "--usuario", required=True, help="usuário comum, sem privilégio esperado"
    )
    analisador.add_argument(
        "--chave",
        required=True,
        help="caminho da chave privada. É credencial: nunca aparece na saída, no log ou em mensagem de erro",
    )
    analisador.add_argument(
        "--baseline",
        default="./baseline.yaml",
        help="arquivo de baseline versionado pelo time (padrão: %(default)s)",
    )
    analisador.add_argument(
        "--formato",
        choices=_FORMATOS_VALIDOS,
        default="ambos",
        help="formato da saída (padrão: %(default)s)",
    )
    analisador.add_argument(
        "--saida",
        default=None,
        help=(
            "diretório onde gravar inventario.json e/ou inventario.md; "
            "quando omitido, a saída vai para stdout (padrão: stdout)"
        ),
    )
    analisador.add_argument(
        "--porta", type=int, default=22, help="porta SSH do host (padrão: %(default)s)"
    )
    analisador.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="segundos para conexão e para a coleta (padrão: %(default)s)",
    )
    analisador.add_argument(
        "--aceitar-host-desconhecido",
        action="store_true",
        default=False,
        help=(
            "aceita host fora do known_hosts; a saída registra que a "
            "identidade não foi verificada (padrão: desligado)"
        ),
    )
    return analisador


def _carregar_baseline_ou_none(caminho: str) -> Optional[dict]:
    """Carrega o baseline, emitindo em stderr qualquer aviso de versão
    futura (Requirement "Regra desconhecida não é silenciada"). Devolve
    `None` quando o arquivo está ausente ou é inválido — o chamador decide
    o código de saída (`erro interno`).
    """
    try:
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            baseline = avaliador.carregar_baseline(caminho)
        for aviso in avisos:
            print(f"aviso: {aviso.message}", file=sys.stderr)
    except (OSError, yaml.YAMLError) as exc:
        print(f"erro: não foi possível carregar o baseline '{caminho}': {exc}", file=sys.stderr)
        return None
    if not isinstance(baseline, dict):
        print(f"erro: baseline '{caminho}' inválido: conteúdo não é um mapeamento", file=sys.stderr)
        return None
    return baseline


def _emitir_saida(relatorio_final: dict, baseline: dict, formato: str, saida: Optional[str]) -> None:
    saidas: List[tuple] = []
    if formato in ("json", "ambos"):
        saidas.append(("json", relatorio.gerar_json(relatorio_final)))
    if formato in ("markdown", "ambos"):
        saidas.append(("markdown", relatorio.gerar_markdown(relatorio_final, baseline)))

    if saida:
        diretorio = Path(saida)
        diretorio.mkdir(parents=True, exist_ok=True)
        for nome_formato, conteudo in saidas:
            extensao = "json" if nome_formato == "json" else "md"
            (diretorio / f"inventario.{extensao}").write_text(conteudo, encoding="utf-8")
    else:
        for _, conteudo in saidas:
            print(conteudo)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Ponto de entrada da CLI. Nunca deixa uma exceção de transporte ou de
    autenticação chegar ao usuário como rastro de pilha — ver Requirement
    "Falha de alcance é reportada de forma legível".
    """
    analisador = construir_analisador()
    args = analisador.parse_args(argv)

    baseline = _carregar_baseline_ou_none(args.baseline)
    if baseline is None:
        return CODIGO_ERRO_INTERNO

    try:
        inventario = coletor.coletar(
            host=args.host,
            usuario=args.usuario,
            chave=args.chave,
            porta=args.porta,
            timeout=args.timeout,
            aceitar_host_desconhecido=args.aceitar_host_desconhecido,
        )
    except coletor.FalhaDeAlcance as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return CODIGO_HOST_INALCANCAVEL

    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    relatorio_final = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    try:
        _emitir_saida(relatorio_final, baseline, args.formato, args.saida)
    except OSError as exc:
        print(f"erro: não foi possível gravar a saída em '{args.saida}': {exc}", file=sys.stderr)
        return CODIGO_ERRO_INTERNO

    # nao_verificado nunca altera o código de saída (Requirement "Código de
    # saída utilizável em pipeline").
    if resultado_avaliacao["resumo"][avaliador.VEREDITO_DESVIO] > 0:
        return CODIGO_DESVIO
    return CODIGO_CONFORME


if __name__ == "__main__":
    raise SystemExit(main())
