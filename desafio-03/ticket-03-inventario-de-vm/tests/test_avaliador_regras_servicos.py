"""Tarefas 2.5 e 2.6 — servicos.ativos e servicos.proibidos."""

from inventario_vm import avaliador


def _inventario(servicos):
    return {"servicos": servicos}


# --- Tarefa 2.5: servicos.ativos ----------------------------------------


def test_unidade_sem_sufixo_ativa_apenas_como_socket_sai_conforme():
    inventario = _inventario(
        [
            {"nome": "ssh.socket", "tipo": "socket", "estado": "active"},
            {"nome": "ssh.service", "tipo": "service", "estado": "inactive"},
        ]
    )
    resultado = avaliador._regra_servicos_ativos(inventario, ["ssh"])
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"]["ssh"] == {"ativo": True, "forma": "socket"}


def test_unidade_sem_sufixo_ativa_como_service_sai_conforme():
    inventario = _inventario([{"nome": "chrony.service", "tipo": "service", "estado": "active"}])
    resultado = avaliador._regra_servicos_ativos(inventario, ["chrony"])
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"]["chrony"]["forma"] == "service"


def test_servico_esperado_ausente_e_desvio_nao_nao_verificado():
    inventario = _inventario([])
    resultado = avaliador._regra_servicos_ativos(inventario, ["chrony"])
    assert resultado["veredito"] == "desvio"
    assert resultado["encontrado"]["chrony"] == {"ativo": False, "forma": None}


def test_gerenciador_de_servicos_indisponivel_e_nao_verificado():
    inventario = {"servicos": None}
    resultado = avaliador._regra_servicos_ativos(inventario, ["chrony"])
    assert resultado["veredito"] == "nao_verificado"
    assert resultado["motivo"]


# --- Tarefa 2.6: servicos.proibidos --------------------------------------


def test_unidade_proibida_nomeada_com_tipo_ativa_e_desvio():
    inventario = _inventario([{"nome": "telnet.socket", "tipo": "socket", "estado": "active"}])
    resultado = avaliador._regra_servicos_proibidos(inventario, ["telnet.socket", "rpcbind.socket"])
    assert resultado["veredito"] == "desvio"
    assert resultado["encontrado"] == ["telnet.socket"]


def test_unidade_proibida_nomeada_com_tipo_inativa_e_conforme():
    inventario = _inventario([{"nome": "telnet.socket", "tipo": "socket", "estado": "inactive"}])
    resultado = avaliador._regra_servicos_proibidos(inventario, ["telnet.socket"])
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"] == []


def test_proibidos_correspondencia_e_exata_nao_por_prefixo():
    # "telnet.service" ativo não deve casar com a proibição "telnet.socket".
    inventario = _inventario([{"nome": "telnet.service", "tipo": "service", "estado": "active"}])
    resultado = avaliador._regra_servicos_proibidos(inventario, ["telnet.socket"])
    assert resultado["veredito"] == "conforme"
