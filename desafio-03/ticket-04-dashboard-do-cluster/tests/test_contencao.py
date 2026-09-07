"""Testes da garantia de só-leitura e da fronteira de contenção — grupo 8.

Duas das três verificações do grupo vivem aqui, cada uma correspondendo a
uma tarefa de `tasks.md`:

  - 8.1 nenhum verbo de escrita de API aparece em `src/`;
  - 8.2 nenhum módulo de `src/`, fora de `cliente.py`, importa `kubernetes`
    nem `urllib3`.

As outras duas tarefas do grupo vivem noutro lugar por serem sobre o
comportamento de `cliente.py`, não sobre a forma do código-fonte:

  - 8.3 (a distinção ausente/nulo sobrevive só no modo cru) e 8.5 (5xx vira
    `indisponivel` com o status no motivo) estão em `test_cliente.py`, ao
    lado dos outros testes da mesma fronteira;
  - 8.4 (a suíte inteira roda sem tocar rede) não é um teste novo — é a
    verificação de que rodar `pytest --disable-socket` sobre a suíte
    inteira continua passando, registrada em
    `docs/03-divergencias-da-implementacao.md` e no relatório desta onda.

Os dois testes abaixo são **estáticos**: leem o texto-fonte de `src/` e não
executam nada — rodar de verdade um verbo de escrita ou um import indevido
seria o próprio defeito que este arquivo existe para impedir. São testes de
regex sobre texto, não de AST, de propósito: mais simples de auditar a olho,
e a regra que protegem ("nenhuma destas substrings aparece como código") é
ela mesma uma regra textual.

**Estes dois testes foram vistos falhando**, de propósito, antes de este
commit fechar — não é alegação, é verificação. Ver o relatório desta onda
(`docs/03-divergencias-da-implementacao.md`) para o comando exato usado e a
saída obtida ao introduzir cada violação e desfazê-la.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "painel_cluster"
MODULOS_SRC = sorted(p for p in SRC.glob("*.py") if p.name != "__pycache__")

# --------------------------------------------------------------------- 8.1
# Nenhum verbo de escrita de API em src/.
#
# O cliente oficial `kubernetes` gera um método por verbo x tipo, sempre no
# formato `<verbo>_<resto>(...)`, chamado como atributo de um objeto (nunca
# solto): `create_namespaced_pod(...)`, `patch_namespaced_deployment(...)`,
# `delete_collection_namespaced_pod(...)`, `replace_namespaced_service(...)`.
# O padrão exige o "_" logo depois do verbo — sem isso, `str.replace(...)`
# (usado por `dataclasses.replace(...)` em modelo.py e tela.py) daria falso
# positivo, e o teste perderia a confiança de quem o lê.
VERBO_DE_ESCRITA = re.compile(r"\.(create|delete|patch|replace)_\w*\(")


def test_nenhum_verbo_de_escrita_em_src():
    ofensores = {}
    for modulo in MODULOS_SRC:
        achados = VERBO_DE_ESCRITA.findall(modulo.read_text())
        if achados:
            ofensores[modulo.name] = achados
    assert not ofensores, (
        f"verbo de escrita encontrado em src/painel_cluster/: {ofensores}. "
        "Nenhuma operação de escrita é permitida em nenhum caminho de "
        "código (docs/01-comportamento.md, Invariante 1)."
    )


# --------------------------------------------------------------------- 8.2
# Nenhum módulo de src/, fora de cliente.py, importa kubernetes ou urllib3.
#
# Ancorado no início da linha (col 0, e a única indentação aceita é
# whitespace) para não disparar em texto de docstring que apenas *cite* a
# string "import kubernetes" para documentar a própria regra — como o
# docstring de tela.py faz.
IMPORT_PROIBIDO = re.compile(r"^[ \t]*(?:import|from)[ \t]+(kubernetes|urllib3)\b", re.MULTILINE)


def test_nenhum_modulo_fora_de_cliente_importa_kubernetes_ou_urllib3():
    ofensores = {}
    for modulo in MODULOS_SRC:
        if modulo.name == "cliente.py":
            continue
        achados = IMPORT_PROIBIDO.findall(modulo.read_text())
        if achados:
            ofensores[modulo.name] = achados
    assert not ofensores, (
        f"import de kubernetes/urllib3 fora de cliente.py: {ofensores}. "
        "cliente.py é o único módulo do pacote autorizado a importar o "
        "cliente e o transporte (D8/D-E; docs/02-decisoes-tecnicas.md)."
    )


def test_cliente_py_e_o_unico_modulo_que_de_fato_importa_kubernetes_e_urllib3():
    """Contraprova do teste acima: se `cliente.py` parasse de importar os
    dois, o teste de contenção passaria por motivo errado — nenhum módulo
    importaria nada, não porque a fronteira está intacta, mas porque ela
    desapareceu. Este teste garante que a fronteira continua existindo."""
    texto = (SRC / "cliente.py").read_text()
    achados = set(IMPORT_PROIBIDO.findall(texto))
    assert achados == {"kubernetes", "urllib3"}, (
        "cliente.py deveria importar tanto kubernetes quanto urllib3 — "
        f"encontrado: {achados}"
    )
