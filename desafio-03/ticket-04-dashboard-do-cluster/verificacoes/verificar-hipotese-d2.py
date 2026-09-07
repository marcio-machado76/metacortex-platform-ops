"""Verifica a hipotese de que a D2 depende, antes de a spec fechar.

A D2 escolhe o cliente oficial com _preload_content=False porque essa seria a
unica combinacao que entrega, ao mesmo tempo, JSON com a forma original da API
e erro estruturado o bastante para distinguir 401, 403 e falha de conexao.

Isso era hipotese. Este script mede.

Cenarios, e o que cada um prova:

  1. 403  — token do platform-ro-sem-events lendo events
            -> ApiException com .status == 403
  2. 403 + sucesso no mesmo cliente  — o mesmo token lendo pods
            -> prova a D10: um tipo negado, os outros seguem
  3. 401  — token invalido
            -> ApiException com .status == 401, distinto do 403
  4. conexao recusada — endereco morto
            -> excecao de tipo diferente, nao ApiException
  5. forma do JSON — o mesmo objeto cru e tipado
            -> prova a outra metade da D2
  6. certificado de cliente vencido
            -> a segunda forma de "credencial expirada". O kubeconfig do kind
               autentica por certificado, e certificado vencido nao produz 401:
               quebra no handshake TLS, antes de existir resposta HTTP. Este
               cenario mede se ele cai no mesmo balde do cenario 4 — e, se
               cair, o que sobra para distinguir um do outro.

Uso:
    .venv/bin/python verificacoes/verificar-hipotese-d2.py

O cenario 6 precisa de um certificado de cliente vencido, assinado pela CA do
cluster. Ele nao e versionado — a chave da CA nao sai do laboratorio. Gere fora
do repositorio e aponte por variavel de ambiente:

    docker cp metacortex-lab-control-plane:/etc/kubernetes/pki/ca.crt .
    docker cp metacortex-lab-control-plane:/etc/kubernetes/pki/ca.key .
    openssl genrsa -out cliente-vencido.key 2048
    openssl req -new -key cliente-vencido.key -out cliente-vencido.csr \
        -subj "/CN=platform-ro/O=metacortex"
    openssl ca -batch -config ca.cnf -keyfile ca.key -cert ca.crt \
        -in cliente-vencido.csr -out cliente-vencido.crt \
        -startdate 200101000000Z -enddate 200102000000Z -notext

    export CERT_VENCIDO_CRT=.../cliente-vencido.crt
    export CERT_VENCIDO_KEY=.../cliente-vencido.key

Sem as variaveis o cenario 6 e pulado, e o script diz isso na saida em vez de
fingir que passou.
"""

import json
import os
import subprocess
import sys

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

NS_COM_FALHA = "nyx-prod"
NS_SEM_ENDPOINT = "nyx-stg"


def linha(titulo):
    print()
    print("=" * 72)
    print(titulo)
    print("=" * 72)


def descreve_excecao(e):
    """Tudo que o codigo de degradacao graciosa teria disponivel."""
    tipo = f"{type(e).__module__}.{type(e).__name__}"
    print(f"  tipo da excecao : {tipo}")
    print(f"  e ApiException? : {isinstance(e, ApiException)}")
    status = getattr(e, "status", "<ATRIBUTO AUSENTE>")
    print(f"  .status         : {status!r}")
    print(f"  .reason         : {getattr(e, 'reason', '<ATRIBUTO AUSENTE>')!r}")
    corpo = getattr(e, "body", None)
    if corpo:
        texto = corpo.decode() if isinstance(corpo, bytes) else str(corpo)
        print(f"  .body (200)     : {texto[:200]}")
    else:
        print(f"  .body           : {corpo!r}")
    print(f"  str(e) (200)    : {str(e)[:200]}")


def token_da_sa(nome):
    return subprocess.run(
        ["kubectl", "create", "token", nome, "-n", "kube-system", "--duration=10m"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def config_com_certificado(base, crt, key):
    cfg = client.Configuration()
    cfg.host = base.host
    cfg.ssl_ca_cert = base.ssl_ca_cert
    cfg.verify_ssl = base.verify_ssl
    cfg.cert_file = crt
    cfg.key_file = key
    return cfg


def config_com_token(base, token, host=None):
    cfg = client.Configuration()
    cfg.host = host or base.host
    cfg.ssl_ca_cert = None if host else base.ssl_ca_cert
    cfg.verify_ssl = False if host else base.verify_ssl
    cfg.api_key = {"authorization": f"Bearer {token}"}
    # Sem isto o apiserver autenticaria pelo certificado de admin do kubeconfig
    # e o token nem seria olhado — o cenario mediria a coisa errada.
    cfg.cert_file = None
    cfg.key_file = None
    return cfg


def chamada(rotulo, fn, **kwargs):
    print(f"\n{rotulo}")
    try:
        r = fn(**kwargs)
        if hasattr(r, "data"):
            n = len(json.loads(r.data)["items"])
            print(f"  SUCESSO — resposta crua, {n} itens")
        else:
            print(f"  SUCESSO — modelo tipado, {len(r.items)} itens")
        return None
    except Exception as e:  # noqa: BLE001 — medir e o objetivo
        descreve_excecao(e)
        return e


def main():
    print(f"cliente kubernetes : {client.__dict__.get('__version__', 'ver pip')}")
    import kubernetes
    print(f"kubernetes.__version__ : {kubernetes.__version__}")
    print(f"python             : {sys.version.split()[0]}")

    config.load_kube_config()
    base = client.Configuration.get_default_copy()
    print(f"servidor           : {base.host}")

    # ---------------------------------------------------------------- 1 e 2
    linha("CENARIO 1 e 2 — 403 num tipo, sucesso nos outros (platform-ro-sem-events)")
    cfg = config_com_token(base, token_da_sa("platform-ro-sem-events"))
    with client.ApiClient(cfg) as api:
        v1 = client.CoreV1Api(api)
        e_cru = chamada(
            "[1a] list_namespaced_event  _preload_content=False (o que a D2 propoe)",
            v1.list_namespaced_event, namespace=NS_COM_FALHA, _preload_content=False)
        e_tipado = chamada(
            "[1b] list_namespaced_event  modelo tipado (para comparar)",
            v1.list_namespaced_event, namespace=NS_COM_FALHA)
        chamada(
            "[2 ] list_namespaced_pod    _preload_content=False (outro tipo, mesmo cliente)",
            v1.list_namespaced_pod, namespace=NS_COM_FALHA, _preload_content=False)

    print("\n  --> .status preservado com _preload_content=False? ",
          getattr(e_cru, "status", None) == 403)
    print("  --> mesmo .status no cru e no tipado?               ",
          getattr(e_cru, "status", None) == getattr(e_tipado, "status", None))

    # -------------------------------------------------------------------- 3
    linha("CENARIO 3 — 401, credencial invalida")
    cfg = config_com_token(base, "token-invalido-de-proposito")
    with client.ApiClient(cfg) as api:
        e401 = chamada(
            "[3 ] list_namespaced_pod    _preload_content=False",
            client.CoreV1Api(api).list_namespaced_pod,
            namespace=NS_COM_FALHA, _preload_content=False)

    print("\n  --> 401 distinto de 403? ",
          getattr(e401, "status", None) == 401
          and getattr(e401, "status", None) != getattr(e_cru, "status", None))

    # -------------------------------------------------------------------- 4
    linha("CENARIO 4 — conexao recusada, endereco morto")
    cfg = config_com_token(base, "irrelevante", host="https://127.0.0.1:1")
    cfg.retries = 0
    with client.ApiClient(cfg) as api:
        erede = chamada(
            "[4 ] list_namespaced_pod    _preload_content=False",
            client.CoreV1Api(api).list_namespaced_pod,
            namespace=NS_COM_FALHA, _preload_content=False)

    print("\n  --> tipo distinto de ApiException? ", not isinstance(erede, ApiException))

    # -------------------------------------------------------------------- 5
    linha("CENARIO 5 — a forma do JSON: cru contra tipado (D9)")
    with client.ApiClient() as api:
        v1 = client.CoreV1Api(api)
        d = client.DiscoveryV1Api(api)

        cru = json.loads(v1.list_namespaced_endpoints(
            NS_SEM_ENDPOINT, _preload_content=False).data)
        ep = [i for i in cru["items"] if i["metadata"]["name"] == "nyx-api"][0]
        print(f"\n  Endpoints/nyx-api  cru    : chaves de topo = {sorted(ep)}")
        print(f"                             'subsets' presente? {'subsets' in ep}")

        cru_es = json.loads(d.list_namespaced_endpoint_slice(
            NS_SEM_ENDPOINT, _preload_content=False).data)
        sl = [i for i in cru_es["items"]
              if i["metadata"]["labels"]["kubernetes.io/service-name"] == "nyx-api"][0]
        print(f"  EndpointSlice      cru    : 'endpoints' presente? {'endpoints' in sl}"
              f" | valor = {sl.get('endpoints')!r}")

        tip = [i for i in v1.list_namespaced_endpoints(NS_SEM_ENDPOINT).items
               if i.metadata.name == "nyx-api"][0]
        tip_es = [i for i in d.list_namespaced_endpoint_slice(NS_SEM_ENDPOINT).items
                  if i.metadata.labels["kubernetes.io/service-name"] == "nyx-api"][0]
        print(f"\n  Endpoints/nyx-api  tipado : .subsets   = {tip.subsets!r}")
        print(f"  EndpointSlice      tipado : .endpoints = {tip_es.endpoints!r}")
        print("\n  --> no cru, a diferenca entre ausente e nulo sobrevive.")
        print("  --> no tipado, as duas viram None e a diferenca some.")

    # -------------------------------------------------------------------- 6
    linha("CENARIO 6 — certificado de cliente vencido (a outra forma de credencial expirada)")
    crt, key = os.environ.get("CERT_VENCIDO_CRT"), os.environ.get("CERT_VENCIDO_KEY")
    if not (crt and key):
        print("\n  PULADO — CERT_VENCIDO_CRT e CERT_VENCIDO_KEY nao definidos.")
        print("  Ver o cabecalho deste arquivo para gerar o certificado.")
        return

    print(f"\n  certificado: {crt}")
    print("  validade  : " + subprocess.run(
        ["openssl", "x509", "-in", crt, "-noout", "-dates"],
        capture_output=True, text=True).stdout.replace("\n", " ").strip())

    cfg = config_com_certificado(base, crt, key)
    cfg.retries = 0
    with client.ApiClient(cfg) as api:
        ecert = chamada(
            "[6 ] list_namespaced_pod    _preload_content=False",
            client.CoreV1Api(api).list_namespaced_pod,
            namespace=NS_COM_FALHA, _preload_content=False)

    print()
    print("  --> mesmo TIPO do cenario 4 (conexao recusada)? ",
          type(ecert) is type(erede))
    print("  --> tem .status para distinguir?                ",
          hasattr(ecert, "status") and getattr(ecert, "status", None) is not None)
    print("  --> a distincao teria de sair da mensagem interna, nao do tipo.")


if __name__ == "__main__":
    main()
