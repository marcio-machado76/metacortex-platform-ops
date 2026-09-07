"""Inventários e baselines escritos à mão para os testes do avaliador e do
relatório.

Nenhum destes dados vem de host algum — são fixtures estáticas, exatamente
o que `design.md` pede: "a suíte de testes exercita as regras de
conformidade sobre inventários gravados em arquivo, sem host, sem rede e
sem espera".
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

CAMINHO_BASELINE_REAL = Path(__file__).resolve().parents[1] / "baseline.yaml"


def inventario_conforme() -> dict:
    """Inventário que atende a todas as onze regras de `baseline.yaml`.

    `ssh.service` inativo e `ssh.socket` ativo, de propósito: exercita a
    decisão D9 (unidade ativa por socket satisfaz a exigência) mesmo no
    caminho "tudo conforme".
    """
    return {
        "host": {
            "endereco": "10.0.1.10",
            "hostname": "vm-conforme",
            "coletado_em": "2026-01-01T00:00:00Z",
        },
        "so": {"distribuicao": "Ubuntu", "versao": "22.04"},
        "kernel": {"versao": "6.8.0-31-generic"},
        "servicos": [
            {"nome": "ssh.socket", "tipo": "socket", "estado": "active"},
            {"nome": "ssh.service", "tipo": "service", "estado": "inactive"},
            {"nome": "containerd.service", "tipo": "service", "estado": "active"},
            {"nome": "node_exporter.service", "tipo": "service", "estado": "active"},
            {"nome": "chrony.service", "tipo": "service", "estado": "active"},
            {"nome": "telnet.socket", "tipo": "socket", "estado": "inactive"},
            {"nome": "rpcbind.socket", "tipo": "socket", "estado": "inactive"},
        ],
        "swap": {"habilitado": False, "tamanho": None},
        "portas_em_escuta": [
            {"porta": 22, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "sshd"},
            {"porta": 9100, "protocolo": "tcp", "bind": "10.0.1.10", "processo": "node_exporter"},
            {"porta": 8125, "protocolo": "udp", "bind": "127.0.0.1", "processo": "statsd"},
        ],
        "chaves_ssh": {
            "lidas": [
                {
                    "identificacao": "platform@metacortex-platform",
                    "origem": "/home/ubuntu/.ssh/authorized_keys",
                },
            ],
            "arquivos_ilegiveis": [],
        },
        "ssh": {"login_de_root": False},
        "ntp": {"sincronizado": True, "mecanismo": "chrony"},
    }


def inventario_com_desvios() -> dict:
    """Inventário com desvios cobrindo as três severidades e uma regra não
    verificável, para exercitar resumo, ordenação por severidade e o
    relatório.

    - crítico: `swap.habilitado` (swap ligado) e a porta 9100 exposta
      publicamente (duas regras críticas, `publicas_permitidas` e
      `somente_rede_interna`, acusam a mesma porta).
    - alto: `chrony` (via `.service`/`.socket`) ausente de `servicos.ativos`.
    - médio: kernel abaixo da versão mínima.
    - não verificado: `ssh.login_de_root` (sem privilégio).
    """
    inventario = inventario_conforme()
    inventario["host"] = {
        "endereco": "10.0.1.20",
        "hostname": "vm-com-desvio",
        "coletado_em": "2026-01-01T00:05:00Z",
    }
    inventario["kernel"] = {"versao": "6.2.0-10-generic"}
    inventario["swap"] = {"habilitado": True, "tamanho": "2G"}
    inventario["servicos"] = [
        s for s in inventario["servicos"] if not s["nome"].startswith("chrony")
    ]
    inventario["portas_em_escuta"] = [
        {"porta": 22, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "sshd"},
        {"porta": 9100, "protocolo": "tcp", "bind": "0.0.0.0", "processo": "node_exporter"},
    ]
    inventario["ssh"] = {"login_de_root": None}
    return inventario


def baseline_padrao() -> dict:
    """Carrega o `baseline.yaml` real do repositório (versão 1, 11 regras)."""
    import yaml

    with open(CAMINHO_BASELINE_REAL, "r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def baseline_versao_futura() -> dict:
    baseline = deepcopy(baseline_padrao())
    baseline["versao"] = 99
    return baseline
