"""Ponto de entrada `painel-cluster` (grupo 9 do `tasks.md`).

Este módulo interpreta os argumentos de linha de comando, resolve a sessão
contra o contexto corrente do kubeconfig e sobe a tela. Não reimplementa
nada que já exista em `cliente.py` — em particular, o encerramento com
código 2 quando não há kubeconfig legível ou contexto corrente nasce dentro
de `cliente.resolver_contexto()`/`cliente.conectar()` (`SystemExit(2)`, sem
rastreamento de pilha) e este módulo **deixa a exceção propagar**, em vez de
testar de novo a mesma condição.

`docs/03-divergencias-da-implementacao.md`, item 1, registra por que o
código 2 mora em `cliente.py` e não aqui: a tarefa 3.7 (grupo 3, já
implementado) colocou o `SystemExit(2)` na fronteira de leitura porque é lá
que se sabe se o kubeconfig é legível; a única responsabilidade que sobra
para este ponto de entrada é não reimplementar essa lógica.
"""

from __future__ import annotations

import argparse
import sys

from . import cliente
from .tela import PainelClusterApp

__all__ = ["main", "cli"]


class _ArgumentParser(argparse.ArgumentParser):
    """`argparse` sai com código 2 em erro de uso, por padrão — e 2 já tem
    dono neste projeto: "não há kubeconfig legível, ou o contexto corrente
    não existe" (Requirement "Códigos de saída"). Erro de uso é código 1, e
    esta subclasse é o único ponto onde essa troca acontece, sem reimplementar
    o parsing do argparse."""

    def error(self, message: str) -> None:  # type: ignore[override]
        print(f"painel-cluster: {message}", file=sys.stderr)
        raise SystemExit(1)


def _criar_parser() -> _ArgumentParser:
    parser = _ArgumentParser(
        prog="painel-cluster",
        description=(
            "Retrato de um namespace do cluster corrente do kubeconfig — "
            "pods, controladores, services e eventos recentes, numa tela "
            "de terminal que não substitui o kubectl."
        ),
    )
    parser.add_argument(
        "--kubeconfig",
        metavar="CAMINHO",
        default=None,
        help=(
            "caminho do kubeconfig a usar (padrão: a resolução normal do "
            "cliente kubernetes — variável KUBECONFIG, ou ~/.kube/config). "
            "Em qualquer caso, é sempre o contexto CORRENTE daquele arquivo "
            "que a tela lê; não há seletor de contexto nem de cluster "
            "(Requirement \"Contexto corrente e somente ele\")."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Interpreta os argumentos, conecta e sobe a tela. Devolve o código de
    saída — 0 em saída normal pelo `q` (Requirement "Códigos de saída"). Erro
    de uso e ausência de kubeconfig/contexto encerram por `SystemExit` antes
    de devolver nada (código 1 e 2, respectivamente); esta função não os
    intercepta."""
    parser = _criar_parser()
    args = parser.parse_args(argv)

    sessao = cliente.conectar(args.kubeconfig)
    app = PainelClusterApp(sessao=sessao)
    app.run()
    return 0


def cli() -> None:
    """O que `pyproject.toml` registra como o comando `painel-cluster`."""
    raise SystemExit(main())


if __name__ == "__main__":
    cli()
