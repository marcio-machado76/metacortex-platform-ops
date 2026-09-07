"""Tarefa 1.3: a suíte precisa rodar com sucesso antes de existir qualquer
tarefa de avaliador ou de relatório, para que elas tenham onde entrar.

Este teste apenas confirma que o pacote é importável a partir de `src/` via
`pythonpath` configurado em `pytest.ini`. Nenhuma rede, nenhum host.
"""

import inventario_vm


def test_pacote_e_importavel():
    assert inventario_vm.__version__
