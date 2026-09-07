"""Transporte SSH simulado para os testes do coletor (Grupo 4).

`coletor.py` é, por desenho, o único módulo do pacote que fala com a rede
(`design.md`). Sem VM de laboratório disponível nesta sessão (destruída
para não gerar custo), a maior parte do Grupo 4 é verificável trocando
`paramiko.SSHClient` por um objeto que se comporta como ele — mesma
interface (`connect`, `exec_command`, `close`, `load_system_host_keys`,
`load_host_keys`, `set_missing_host_key_policy`, `get_host_keys`) — mas
nunca abre um socket. Isso mantém `coletor.coletar()` e o analisador de
blocos exercitados de ponta a ponta em teste automatizado, sem rede e sem
espera, exatamente como o `design.md` pede para o avaliador (seção "Isolar
tudo que depende de rede num único ponto").

Não substitui a validação real contra as duas VMs do laboratório (Grupo 6):
onde a tarefa de `tasks.md` pede explicitamente "contra uma VM" ou "contra
as duas VMs", ela continua desmarcada em `tasks.md` — ver
`docs/03-divergencias-da-implementacao.md`, seção "Grupos 4 e 5".
"""

from __future__ import annotations

from typing import List, Optional


class CanalFalso:
    """GESTOR de saída — imita o objeto de arquivo devolvido por
    `paramiko.SSHClient.exec_command` para stdout/stderr."""

    def __init__(self, texto: str = "") -> None:
        self._dados = texto.encode("utf-8")

    def read(self) -> bytes:
        dados, self._dados = self._dados, b""
        return dados


class _HostKeysFalso:
    """Sempre reporta o host como desconhecido — suficiente para os testes,
    que controlam `identidade_verificada` fixando o retorno aqui."""

    def lookup(self, *_args):
        return None


class ClienteSSHFalso:
    """Substitui `paramiko.SSHClient` nos testes do coletor.

    `excecao_ao_conectar`, se dada, é levantada dentro de `connect()` —
    para simular as falhas de transporte que o coletor precisa traduzir
    (Tarefa 4.2). `saida_stdout` é o texto (formato do script composto)
    devolvido por `exec_command`. `comandos_executados` registra cada
    comando que o coletor mandou executar, para os testes verificarem que
    nenhum comando é enviado antes de uma conexão bem-sucedida (Tarefa 4.1)
    e que nenhum comando enviado escreve no host (Tarefa 4.11).
    """

    def __init__(
        self,
        saida_stdout: str = "",
        excecao_ao_conectar: Optional[BaseException] = None,
    ) -> None:
        self.saida_stdout = saida_stdout
        self.excecao_ao_conectar = excecao_ao_conectar
        self.comandos_executados: List[str] = []
        self.fechado = False
        self.politica_definida = None

    # --- interface usada por coletor._preparar_cliente ---------------
    def load_system_host_keys(self) -> None:
        pass

    def load_host_keys(self, caminho: str) -> None:
        pass

    def set_missing_host_key_policy(self, politica) -> None:
        self.politica_definida = politica

    def get_host_keys(self) -> _HostKeysFalso:
        return _HostKeysFalso()

    # --- interface usada por coletor._conectar / _executar_script_composto
    def connect(self, **_kwargs) -> None:
        if self.excecao_ao_conectar is not None:
            raise self.excecao_ao_conectar

    def exec_command(self, comando: str, timeout=None):
        self.comandos_executados.append(comando)
        return None, CanalFalso(self.saida_stdout), CanalFalso("")

    def close(self) -> None:
        self.fechado = True
