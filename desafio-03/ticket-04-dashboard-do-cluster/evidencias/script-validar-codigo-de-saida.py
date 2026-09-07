"""Roda o binario REAL `painel-cluster` (o `pyproject.toml` instalado na
venv do ticket) dentro de um pseudo-terminal, envia 'q' depois de alguns
segundos, e reporta o codigo de saida do processo -- para provar o
Requirement "Codigos de saida" / criterio de aceite 8 ("nao sai com codigo
diferente de zero") e, de quebra, o criterio 7, contra a execucao real do
comando instalado (nao o harness de teste do Textual).

So leitura: nao aplica, nao altera nada no cluster nem no kubeconfig alem
do que ja foi preparado por fora (contexto corrente do kubeconfig apontado
por --kubeconfig).

Uso:
    python3 validar-codigo-de-saida.py <caminho-do-binario painel-cluster> \
        <KUBECONFIG> <segundos-de-espera-antes-do-q>
"""
import os
import pty
import subprocess
import sys
import time


def rodar(binario: str, kubeconfig: str, espera: float) -> tuple[int, bytes]:
    master, slave = pty.openpty()
    env = dict(os.environ)
    env["KUBECONFIG"] = kubeconfig
    env["TERM"] = "xterm-256color"
    env["COLUMNS"] = "200"
    env["LINES"] = "50"
    proc = subprocess.Popen(
        [binario],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env=env,
        preexec_fn=os.setsid,
        close_fds=True,
    )
    os.close(slave)

    saida = b""
    inicio = time.time()
    q_enviado = False
    while True:
        if proc.poll() is not None:
            break
        if time.time() - inicio > espera and not q_enviado:
            try:
                os.write(master, b"q")
            except OSError:
                pass
            q_enviado = True
        try:
            import select

            r, _, _ = select.select([master], [], [], 0.2)
            if r:
                chunk = os.read(master, 65536)
                if not chunk:
                    break
                saida += chunk
        except OSError:
            break
        if time.time() - inicio > espera + 15:
            # não saiu sozinho depois do 'q' — força o encerramento e reporta
            proc.terminate()
            break

    try:
        rc = proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = proc.wait()
    try:
        os.close(master)
    except OSError:
        pass
    return rc, saida


def main():
    binario, kubeconfig, espera = sys.argv[1], sys.argv[2], float(sys.argv[3])
    rc, saida = rodar(binario, kubeconfig, espera)
    print(f"codigo de saida: {rc}")
    print(f"bytes capturados (raw, com sequencias ANSI): {len(saida)}")
    print("--- ultimos 4000 bytes da saida crua ---")
    sys.stdout.buffer.write(saida[-4000:])
    print()
    print(f"contem 'Traceback'? {'Traceback' in saida.decode(errors='replace')}")


if __name__ == "__main__":
    main()
