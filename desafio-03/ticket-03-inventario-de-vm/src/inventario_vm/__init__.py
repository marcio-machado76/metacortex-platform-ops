"""Ferramenta de inventário e drift de VM.

Pacote com quatro módulos, conforme `design.md` da mudança
`adicionar-inventario-de-vm`:

- `cli`: argumentos, orquestração, código de saída.
- `coletor`: único módulo que fala com a rede; devolve um inventário.
- `avaliador`: função pura ``(inventário, baseline) -> conformidade``.
- `relatorio`: serializa o mesmo dado em JSON e em Markdown.

Os quatro módulos estão implementados. A validação contra as duas VMs do
laboratório (Grupo 6 de `tasks.md`) não faz parte deste pacote: o
laboratório é efêmero e sobe/desce por `terraform apply`/`destroy` em
`infra/`.
"""

__version__ = "0.1.0"
