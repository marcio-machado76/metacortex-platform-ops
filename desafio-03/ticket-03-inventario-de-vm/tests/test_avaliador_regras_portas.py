"""Tarefas 2.8 e 2.9 — classificação de endereço de escuta e regras de porta."""

from inventario_vm import avaliador


# --- Tarefa 2.8: classificação --------------------------------------------


def test_classificar_coringa_ipv4_e_ipv6_como_publica():
    assert avaliador.classificar_endereco_de_escuta("0.0.0.0") == "publica"
    assert avaliador.classificar_endereco_de_escuta("::") == "publica"


def test_classificar_faixa_privada_e_link_local_como_rede_interna():
    assert avaliador.classificar_endereco_de_escuta("10.0.1.10") == "rede_interna"
    assert avaliador.classificar_endereco_de_escuta("192.168.1.5") == "rede_interna"
    assert avaliador.classificar_endereco_de_escuta("172.16.0.4") == "rede_interna"
    assert avaliador.classificar_endereco_de_escuta("169.254.1.1") == "rede_interna"


def test_classificar_loopback_ipv4_e_ipv6():
    assert avaliador.classificar_endereco_de_escuta("127.0.0.1") == "loopback"
    assert avaliador.classificar_endereco_de_escuta("::1") == "loopback"


def test_porta_restrita_a_rede_interna_que_nao_esta_em_escuta_e_conforme():
    # Nenhuma entrada com a porta 9100 no inventário: vacuidade satisfaz.
    inventario = {"portas_em_escuta": []}
    resultado = avaliador._regra_portas_somente_rede_interna(inventario, [9100])
    assert resultado["veredito"] == "conforme"
    assert resultado["encontrado"] == []


# --- Tarefa 2.9: publicas_permitidas e somente_rede_interna ---------------


def test_publicas_permitidas_porta_exposta_indevidamente_e_desvio():
    inventario = {
        "portas_em_escuta": [
            {"porta": 22, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "sshd"},
            {"porta": 8080, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "app"},
        ]
    }
    resultado = avaliador._regra_portas_publicas_permitidas(inventario, [22])
    assert resultado["veredito"] == "desvio"
    assert [p["porta"] for p in resultado["encontrado"]] == [8080]


def test_publicas_permitidas_conforme_quando_todas_estao_na_lista():
    inventario = {
        "portas_em_escuta": [{"porta": 22, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "sshd"}]
    }
    resultado = avaliador._regra_portas_publicas_permitidas(inventario, [22])
    assert resultado["veredito"] == "conforme"


def test_somente_rede_interna_porta_exposta_publicamente_e_desvio():
    inventario = {
        "portas_em_escuta": [
            {"porta": 9100, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "node_exporter"}
        ]
    }
    resultado = avaliador._regra_portas_somente_rede_interna(inventario, [9100])
    assert resultado["veredito"] == "desvio"
    assert resultado["encontrado"][0]["porta"] == 9100


def test_somente_rede_interna_conforme_quando_restrita_a_rede_interna():
    inventario = {
        "portas_em_escuta": [
            {"porta": 9100, "protocolo": "tcp", "bind": "10.0.1.10", "processo": "node_exporter"}
        ]
    }
    resultado = avaliador._regra_portas_somente_rede_interna(inventario, [9100])
    assert resultado["veredito"] == "conforme"


def test_porta_em_loopback_nunca_produz_desvio_em_nenhuma_das_duas_regras():
    inventario = {
        "portas_em_escuta": [
            {"porta": 9100, "protocolo": "tcp", "bind": "127.0.0.1", "processo": "node_exporter"}
        ]
    }
    publicas = avaliador._regra_portas_publicas_permitidas(inventario, [22])
    internas = avaliador._regra_portas_somente_rede_interna(inventario, [9100])
    assert publicas["veredito"] == "conforme"
    assert internas["veredito"] == "conforme"
