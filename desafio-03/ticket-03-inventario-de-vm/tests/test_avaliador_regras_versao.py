"""Tarefa 2.4 — so.distribuicao, so.versao_minima, kernel.versao_minima.

Comparação de versão testada com os formatos reais das duas VMs de
laboratório (`22.04` / `24.04` para o sistema operacional,
`6.8.0-31-generic` para o kernel) e com formatos anômalos.
"""

from fixtures import inventario_conforme

from inventario_vm import avaliador


def _inv(**overrides):
    inventario = inventario_conforme()
    inventario["so"].update(overrides.pop("so", {}))
    inventario["kernel"].update(overrides.pop("kernel", {}))
    return inventario


# --- so.distribuicao ---------------------------------------------------


def test_so_distribuicao_conforme_ignora_maiusculas():
    resultado = avaliador._regra_so_distribuicao(_inv(so={"distribuicao": "Ubuntu"}), "ubuntu")
    assert resultado["veredito"] == "conforme"


def test_so_distribuicao_desvio():
    resultado = avaliador._regra_so_distribuicao(_inv(so={"distribuicao": "debian"}), "ubuntu")
    assert resultado["veredito"] == "desvio"


def test_so_distribuicao_desconhecida_nao_verificado():
    resultado = avaliador._regra_so_distribuicao(_inv(so={"distribuicao": None}), "ubuntu")
    assert resultado["veredito"] == "nao_verificado"
    assert resultado["motivo"]


# --- so.versao_minima e kernel.versao_minima: formatos reais -----------


def test_so_versao_minima_formato_real_conforme_igual():
    resultado = avaliador._regra_so_versao_minima(_inv(so={"versao": "22.04"}), "22.04")
    assert resultado["veredito"] == "conforme"


def test_so_versao_minima_formato_real_conforme_maior():
    resultado = avaliador._regra_so_versao_minima(_inv(so={"versao": "24.04"}), "22.04")
    assert resultado["veredito"] == "conforme"


def test_so_versao_minima_formato_real_desvio():
    resultado = avaliador._regra_so_versao_minima(_inv(so={"versao": "20.04"}), "22.04")
    assert resultado["veredito"] == "desvio"


def test_kernel_versao_minima_formato_real_com_sufixo_de_distribuicao():
    resultado = avaliador._regra_kernel_versao_minima(
        _inv(kernel={"versao": "6.8.0-31-generic"}), "6.5"
    )
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"] == "6.8.0-31-generic"


def test_kernel_versao_minima_desvio_com_sufixo():
    resultado = avaliador._regra_kernel_versao_minima(
        _inv(kernel={"versao": "6.2.0-10-generic"}), "6.5"
    )
    assert resultado["veredito"] == "desvio"


# --- formatos anômalos ---------------------------------------------------


def test_versao_para_componentes_com_prefixo_nao_numerico_e_anomalo():
    assert avaliador._versao_para_componentes("v22.04") is None
    assert avaliador._versao_para_componentes("") is None
    assert avaliador._versao_para_componentes(None) is None


def test_kernel_versao_minima_formato_anomalo_nao_verificado():
    resultado = avaliador._regra_kernel_versao_minima(_inv(kernel={"versao": "desconhecida"}), "6.5")
    assert resultado["veredito"] == "nao_verificado"
    assert "formato de versão não reconhecido" in resultado["motivo"]


def test_so_versao_minima_dado_ausente_nao_verificado():
    resultado = avaliador._regra_so_versao_minima(_inv(so={"versao": None}), "22.04")
    assert resultado["veredito"] == "nao_verificado"


def test_versao_com_componentes_de_tamanhos_diferentes_compara_corretamente():
    # "6.5" (minima) precisa ser comparado corretamente com "6.5.0" (atual)
    resultado = avaliador._regra_kernel_versao_minima(_inv(kernel={"versao": "6.5.0"}), "6.5")
    assert resultado["veredito"] == "conforme"
