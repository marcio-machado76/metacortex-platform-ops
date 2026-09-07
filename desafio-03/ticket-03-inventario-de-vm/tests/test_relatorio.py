"""Tarefas 3.1, 3.2 e 3.3 — relatório em JSON e em Markdown."""

import json

from fixtures import baseline_padrao, inventario_com_desvios, inventario_conforme

from inventario_vm import avaliador, relatorio


# --- Tarefa 3.1: JSON ------------------------------------------------------


def test_estrutura_json_corresponde_ao_contrato():
    baseline = baseline_padrao()
    inventario = inventario_conforme()
    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    rel = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    bruto = relatorio.gerar_json(rel)
    objeto = json.loads(bruto)

    assert set(objeto.keys()) == {"host", "inventario", "conformidade", "resumo"}
    assert objeto["host"]["endereco"] == inventario["host"]["endereco"]
    assert "host" not in objeto["inventario"]
    assert len(objeto["conformidade"]) == 11
    assert objeto["resumo"]["conforme"] + objeto["resumo"]["desvio"] + objeto["resumo"]["nao_verificado"] == 11


def test_json_campo_desconhecido_sai_como_nulo():
    baseline = baseline_padrao()
    inventario = inventario_com_desvios()  # tem ssh.login_de_root desconhecido
    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    rel = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    objeto = json.loads(relatorio.gerar_json(rel))

    assert objeto["inventario"]["ssh"]["login_de_root"] is None
    entrada_nv = next(e for e in objeto["conformidade"] if e["regra"] == "ssh.login_de_root")
    assert entrada_nv["veredito"] == "nao_verificado"
    assert entrada_nv["encontrado"] is None
    assert entrada_nv["severidade"] is None
    assert entrada_nv["motivo"] is not None


# --- Tarefa 3.2: Markdown ---------------------------------------------------


def test_markdown_desvios_ordenados_por_severidade():
    baseline = baseline_padrao()
    inventario = inventario_com_desvios()
    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    rel = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    texto = relatorio.gerar_markdown(rel, baseline)

    assert "## Desvios" in texto
    secao = texto.split("## Desvios", 1)[1].split("## ", 1)[0]
    ordem_encontrada = [
        linha.split("|")[1].strip()
        for linha in secao.splitlines()
        if linha.startswith("|") and "Severidade" not in linha and "---" not in linha
    ]
    rotulos_em_ordem = ["crítico", "alto", "médio"]
    indices = [rotulos_em_ordem.index(rotulo) for rotulo in ordem_encontrada if rotulo in rotulos_em_ordem]
    assert indices == sorted(indices)


def test_markdown_secao_sem_conteudo_nao_e_apresentada():
    baseline = baseline_padrao()
    inventario = inventario_conforme()  # sem desvios, sem nao_verificado
    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    rel = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    texto = relatorio.gerar_markdown(rel, baseline)

    assert "## Desvios" not in texto
    assert "## Não verificado" not in texto
    assert "## Conforme" in texto


# --- Tarefa 3.3: as duas saídas descrevem o mesmo dado ----------------------


def test_json_e_markdown_descrevem_o_mesmo_dado():
    baseline = baseline_padrao()
    inventario = inventario_com_desvios()
    resultado_avaliacao = avaliador.avaliar(inventario, baseline)
    rel = relatorio.montar_relatorio(inventario, resultado_avaliacao)

    objeto_json = json.loads(relatorio.gerar_json(rel))
    texto_md = relatorio.gerar_markdown(rel, baseline)

    resumo = objeto_json["resumo"]

    def _contar_linhas_de_tabela(secao_titulo: str) -> int:
        if secao_titulo not in texto_md:
            return 0
        secao = texto_md.split(secao_titulo, 1)[1].split("## ", 1)[0]
        return sum(
            1
            for linha in secao.splitlines()
            if linha.startswith("|") and "---" not in linha and "Severidade" not in linha and "Regra |" not in linha
        )

    def _contar_itens_de_lista(secao_titulo: str) -> int:
        if secao_titulo not in texto_md:
            return 0
        secao = texto_md.split(secao_titulo, 1)[1].split("## ", 1)[0]
        return sum(1 for linha in secao.splitlines() if linha.startswith("- "))

    assert _contar_linhas_de_tabela("## Desvios") == resumo["desvio"]
    assert _contar_linhas_de_tabela("## Não verificado") == resumo["nao_verificado"]
    assert _contar_itens_de_lista("## Conforme") == resumo["conforme"]
