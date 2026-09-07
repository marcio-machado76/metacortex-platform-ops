"""Tarefa 2.12 — resumo por veredito e por severidade."""

from fixtures import baseline_padrao, inventario_com_desvios, inventario_conforme

from inventario_vm import avaliador


def test_soma_dos_tres_vereditos_e_igual_ao_numero_de_regras_do_baseline():
    baseline = baseline_padrao()
    resultado = avaliador.avaliar(inventario_conforme(), baseline)
    resumo = resultado["resumo"]
    total = resumo["conforme"] + resumo["desvio"] + resumo["nao_verificado"]
    assert total == len(resultado["conformidade"]) == 11


def test_inventario_totalmente_conforme_zera_desvios():
    baseline = baseline_padrao()
    resultado = avaliador.avaliar(inventario_conforme(), baseline)
    assert resultado["resumo"]["desvio"] == 0
    assert resultado["resumo"]["por_severidade"] == {"critico": 0, "alto": 0, "medio": 0}


def test_contagem_por_severidade_considera_apenas_os_desvios():
    baseline = baseline_padrao()
    resultado = avaliador.avaliar(inventario_com_desvios(), baseline)
    resumo = resultado["resumo"]

    # Soma ainda bate com o total de regras do baseline.
    assert resumo["conforme"] + resumo["desvio"] + resumo["nao_verificado"] == 11

    # A soma de por_severidade é igual à contagem de desvios (nunca conta
    # conforme ou nao_verificado).
    assert sum(resumo["por_severidade"].values()) == resumo["desvio"]

    # As severidades esperadas para os desvios plantados na fixture:
    # swap.habilitado (critico), portas_em_escuta.publicas_permitidas
    # (critico), servicos.ativos (alto), kernel.versao_minima (medio).
    assert resumo["por_severidade"]["critico"] >= 1
    assert resumo["por_severidade"]["alto"] >= 1
    assert resumo["por_severidade"]["medio"] >= 1
    assert resumo["nao_verificado"] >= 1  # ssh.login_de_root
