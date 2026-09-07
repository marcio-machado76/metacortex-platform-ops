"""Tarefa 2.10 — chaves_ssh.emitidas_por.

Três desfechos exigidos pela tarefa: chave estranha legível (desvio), todas
certas com arquivo ilegível (não verificado) e leitura completa e conforme
(conforme) — nessa ordem, exercitando a regra de desempate "prova positiva
vence incompletude".
"""

from inventario_vm import avaliador

EMISSOR = "metacortex-platform"


def test_chave_estranha_legivel_e_desvio():
    inventario = {
        "chaves_ssh": {
            "lidas": [
                {"identificacao": "platform@metacortex-platform", "origem": "/home/a/.ssh/authorized_keys"},
                {"identificacao": "alguem@laptop-pessoal", "origem": "/home/b/.ssh/authorized_keys"},
            ],
            "arquivos_ilegiveis": [],
        }
    }
    resultado = avaliador._regra_chaves_emitidas_por(inventario, EMISSOR)
    assert resultado["veredito"] == "desvio"
    identificacoes = [c["identificacao"] for c in resultado["encontrado"]]
    assert identificacoes == ["alguem@laptop-pessoal"]


def test_todas_certas_mas_arquivo_ilegivel_e_nao_verificado():
    inventario = {
        "chaves_ssh": {
            "lidas": [
                {"identificacao": "platform@metacortex-platform", "origem": "/home/a/.ssh/authorized_keys"},
            ],
            "arquivos_ilegiveis": ["/home/b/.ssh/authorized_keys"],
        }
    }
    resultado = avaliador._regra_chaves_emitidas_por(inventario, EMISSOR)
    assert resultado["veredito"] == "nao_verificado"
    assert "/home/b/.ssh/authorized_keys" in resultado["motivo"]


def test_prova_positiva_de_violacao_vence_incompletude():
    # Há uma chave estranha legível E um arquivo ilegível: o veredito
    # precisa ser desvio, não nao_verificado.
    inventario = {
        "chaves_ssh": {
            "lidas": [
                {"identificacao": "alguem@laptop-pessoal", "origem": "/home/b/.ssh/authorized_keys"},
            ],
            "arquivos_ilegiveis": ["/home/c/.ssh/authorized_keys"],
        }
    }
    resultado = avaliador._regra_chaves_emitidas_por(inventario, EMISSOR)
    assert resultado["veredito"] == "desvio"


def test_leitura_completa_e_conforme():
    inventario = {
        "chaves_ssh": {
            "lidas": [
                {"identificacao": "platform@metacortex-platform", "origem": "/home/a/.ssh/authorized_keys"},
            ],
            "arquivos_ilegiveis": [],
        }
    }
    resultado = avaliador._regra_chaves_emitidas_por(inventario, EMISSOR)
    assert resultado["veredito"] == "conforme"
