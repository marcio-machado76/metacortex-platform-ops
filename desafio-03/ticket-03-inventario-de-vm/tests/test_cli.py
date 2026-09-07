"""Tarefas 5.1 a 5.4: linha de comando.

Nenhum destes testes fala com rede: `coletor.coletar` é substituído por uma
função de teste (monkeypatch de `cli.coletor.coletar`) que devolve um
inventário fixo ou levanta `FalhaDeAlcance` — o mesmo espírito do
transporte simulado usado nos testes do coletor, só que aqui a substituição
acontece uma camada acima, porque o que a CLI orquestra é a chamada a
`coletor.coletar`, não o transporte em si.
"""

from __future__ import annotations

import json

import pytest

from inventario_vm import avaliador, cli, coletor
from tests.fixtures import (
    CAMINHO_BASELINE_REAL,
    inventario_com_desvios,
    inventario_conforme,
)


# ---------------------------------------------------------------------------
# Tarefa 5.1 — argumentos e ajuda
# ---------------------------------------------------------------------------


def test_ajuda_apresenta_todos_os_argumentos_com_valores_padrao(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0

    saida = capsys.readouterr().out
    for argumento in (
        "--host",
        "--usuario",
        "--chave",
        "--baseline",
        "--formato",
        "--saida",
        "--porta",
        "--timeout",
        "--aceitar-host-desconhecido",
    ):
        assert argumento in saida

    assert "./baseline.yaml" in saida
    assert "ambos" in saida
    assert "22" in saida
    assert "15" in saida


def test_argumentos_obrigatorios_ausentes_terminam_em_erro(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == cli.CODIGO_ERRO_INTERNO


# ---------------------------------------------------------------------------
# Tarefa 5.2 — os quatro códigos de saída, isoladamente
# ---------------------------------------------------------------------------


def _argumentos_minimos(tmp_path, extras=None):
    argumentos = [
        "--host",
        "10.0.1.10",
        "--usuario",
        "roster",
        "--chave",
        "/tmp/chave-fake",
        "--baseline",
        str(CAMINHO_BASELINE_REAL),
        "--saida",
        str(tmp_path),
    ]
    return argumentos + (extras or [])


def test_codigo_conforme_quando_nenhum_desvio(monkeypatch, tmp_path):
    monkeypatch.setattr(coletor, "coletar", lambda **_kwargs: inventario_conforme())
    codigo = cli.main(_argumentos_minimos(tmp_path))
    assert codigo == cli.CODIGO_CONFORME == 0


def test_codigo_desvio_quando_ha_ao_menos_um_desvio(monkeypatch, tmp_path):
    monkeypatch.setattr(coletor, "coletar", lambda **_kwargs: inventario_com_desvios())
    codigo = cli.main(_argumentos_minimos(tmp_path))
    assert codigo == cli.CODIGO_DESVIO == 1


def test_codigo_host_inalcancavel(monkeypatch, tmp_path, capsys):
    def _levanta(**_kwargs):
        raise coletor.FalhaDeAlcance("host inalcançável: simulação de teste")

    monkeypatch.setattr(coletor, "coletar", _levanta)
    codigo = cli.main(_argumentos_minimos(tmp_path))
    assert codigo == cli.CODIGO_HOST_INALCANCAVEL == 2
    erro = capsys.readouterr().err
    assert "host inalcançável: simulação de teste" in erro
    assert "Traceback" not in erro


def test_codigo_erro_interno_baseline_ausente(tmp_path):
    argumentos = _argumentos_minimos(tmp_path)
    indice_baseline = argumentos.index("--baseline") + 1
    argumentos[indice_baseline] = str(tmp_path / "nao-existe.yaml")
    codigo = cli.main(argumentos)
    assert codigo == cli.CODIGO_ERRO_INTERNO == 3


# ---------------------------------------------------------------------------
# Tarefa 5.3 — argumento inválido termina em erro interno, não em host inalcançável
# ---------------------------------------------------------------------------


def test_argumento_invalido_termina_em_erro_interno_e_nao_em_host_inalcancavel(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "--host",
                "10.0.1.10",
                "--usuario",
                "roster",
                "--chave",
                "/tmp/chave-fake",
                "--formato",
                "formato-que-nao-existe",
            ]
        )
    assert excinfo.value.code == cli.CODIGO_ERRO_INTERNO
    assert excinfo.value.code != cli.CODIGO_HOST_INALCANCAVEL


def test_porta_nao_numerica_termina_em_erro_interno():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "--host",
                "10.0.1.10",
                "--usuario",
                "roster",
                "--chave",
                "/tmp/chave-fake",
                "--porta",
                "nao-e-um-numero",
            ]
        )
    assert excinfo.value.code == cli.CODIGO_ERRO_INTERNO


# ---------------------------------------------------------------------------
# Tarefa 5.4 — regra não verificada não altera o código de saída
# ---------------------------------------------------------------------------


def test_regra_nao_verificada_nao_altera_codigo_de_saida_em_host_conforme(monkeypatch, tmp_path):
    inventario = inventario_conforme()
    assert inventario["ssh"]["login_de_root"] is False
    inventario["ssh"]["login_de_root"] = None  # simula ausência de privilégio

    monkeypatch.setattr(coletor, "coletar", lambda **_kwargs: inventario)
    codigo = cli.main(_argumentos_minimos(tmp_path))

    assert codigo == cli.CODIGO_CONFORME == 0

    conteudo = json.loads((tmp_path / "inventario.json").read_text(encoding="utf-8"))
    entrada_login_root = next(
        e for e in conteudo["conformidade"] if e["regra"] == "ssh.login_de_root"
    )
    assert entrada_login_root["veredito"] == avaliador.VEREDITO_NAO_VERIFICADO
    assert conteudo["resumo"]["nao_verificado"] >= 1


# ---------------------------------------------------------------------------
# Saída em arquivo e em stdout
# ---------------------------------------------------------------------------


def test_saida_em_diretorio_grava_json_e_markdown(monkeypatch, tmp_path):
    monkeypatch.setattr(coletor, "coletar", lambda **_kwargs: inventario_conforme())
    cli.main(_argumentos_minimos(tmp_path))
    assert (tmp_path / "inventario.json").exists()
    assert (tmp_path / "inventario.md").exists()


def test_saida_padrao_vai_para_stdout(monkeypatch, capsys):
    monkeypatch.setattr(coletor, "coletar", lambda **_kwargs: inventario_conforme())
    codigo = cli.main(
        [
            "--host",
            "10.0.1.10",
            "--usuario",
            "roster",
            "--chave",
            "/tmp/chave-fake",
            "--baseline",
            str(CAMINHO_BASELINE_REAL),
        ]
    )
    assert codigo == 0
    saida = capsys.readouterr().out
    assert '"host"' in saida
    assert "# Inventário e conformidade" in saida
