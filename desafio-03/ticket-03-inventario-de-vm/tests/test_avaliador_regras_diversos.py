"""Tarefa 2.11 — ssh.login_de_root e ntp.sincronizado.

Dado desconhecido produz `nao_verificado` com motivo, nunca `conforme`.
"""

from inventario_vm import avaliador


def test_login_de_root_conforme():
    resultado = avaliador._regra_ssh_login_de_root({"ssh": {"login_de_root": False}}, False)
    assert resultado["veredito"] == "conforme"


def test_login_de_root_desvio():
    resultado = avaliador._regra_ssh_login_de_root({"ssh": {"login_de_root": True}}, False)
    assert resultado["veredito"] == "desvio"


def test_login_de_root_desconhecido_e_nao_verificado_com_motivo_nunca_conforme():
    resultado = avaliador._regra_ssh_login_de_root({"ssh": {"login_de_root": None}}, False)
    assert resultado["veredito"] == "nao_verificado"
    assert resultado["veredito"] != "conforme"
    assert resultado["motivo"]


def test_ntp_sincronizado_conforme():
    resultado = avaliador._regra_ntp_sincronizado({"ntp": {"sincronizado": True, "mecanismo": "chrony"}}, True)
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"]["mecanismo"] == "chrony"


def test_ntp_dessincronizado_e_desvio():
    resultado = avaliador._regra_ntp_sincronizado({"ntp": {"sincronizado": False, "mecanismo": None}}, True)
    assert resultado["veredito"] == "desvio"


def test_ntp_desconhecido_e_nao_verificado_com_motivo_nunca_conforme():
    resultado = avaliador._regra_ntp_sincronizado({"ntp": {"sincronizado": None, "mecanismo": None}}, True)
    assert resultado["veredito"] == "nao_verificado"
    assert resultado["veredito"] != "conforme"
    assert resultado["motivo"]
