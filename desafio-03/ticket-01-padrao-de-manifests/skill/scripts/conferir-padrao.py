#!/usr/bin/env python3
"""Confere manifestos contra o Padrao de Manifests da Metacortex (rev. 2026-07-29).

Escopo deliberado: aqui estao apenas as regras cuja resposta esta INTEIRA no YAML
e que sao convencao da Metacortex — nenhuma ferramenta de mercado as conhece.

Fica de fora de proposito:
  2.1, 3.1, 3.2, 3.6   `trivy config` ja cobre. Medido, nao suposto: 17 dos 18
                       achados do manifesto barrado caem nessas regras.
                       Reimplementar criaria duas fontes de verdade.
  2.6                  depende de quanto a aplicacao demora para drenar.
  o alvo das probes    depende de quais rotas o projeto expoe (2.2 parcial).
  o "1,5x a 2x" da 2.1 depende do consumo observado em regime.
  julgar a 3.3         a heuristica aponta onde olhar; decidir e leitura.

Excecoes: a secao Excecoes do padrao exige, para desvio de regra obrigatoria,
aprovacao escrita e prazo de validade. Um objeto que declare
`metacortex.io/excecao-regra` com o numero da regra, mais `excecao-motivo`,
`excecao-aprovada-por` e `excecao-valida-ate`, tem o achado daquela regra
rebaixado a EXCECAO em vez de ERRO.

Uso:
    python3 conferir-padrao.py <arquivo-ou-diretorio> [...]

Saida:
    ERRO     regra obrigatoria ou proibida — reprova, codigo de saida 1
    AVISO    regra recomendada — nao reprova, exige justificativa no PR
    EXCECAO  desvio declarado no objeto, com aprovacao e prazo
"""
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    print("ERRO: este script precisa de PyYAML (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAMESPACE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*-(dev|stg|prod)$")
CREDENCIAL_EM_URL = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
NOME_SENSIVEL = re.compile(
    r"(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY|PRIVATE_?KEY|CREDENTIAL|_PWD|^PWD)", re.I)

ROTULOS = ("app.kubernetes.io/name", "app.kubernetes.io/instance",
           "app.kubernetes.io/part-of", "app.kubernetes.io/managed-by")
REGISTRY = "registry.metacortex.io"
NOMES_GENERICOS = {"app", "main", "container", "server", "service"}
COM_POD = {"Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"}

achados = []   # (nivel, onde, regra, mensagem)


def registra(nivel, onde, regra, msg):
    achados.append((nivel, onde, regra, msg))


def excecao_declarada(obj, regra):
    """Devolve o motivo se o objeto declara excecao completa para esta regra."""
    ann = (obj.get("metadata") or {}).get("annotations") or {}
    declaradas = str(ann.get("metacortex.io/excecao-regra", "")).split(",")
    if regra not in [d.strip() for d in declaradas]:
        return None
    faltando = [c for c in ("excecao-motivo", "excecao-aprovada-por", "excecao-valida-ate")
                if not ann.get(f"metacortex.io/{c}")]
    if faltando:
        return f"INCOMPLETA (falta {', '.join(faltando)})"
    return f"{ann['metacortex.io/excecao-motivo']} · aprovada por " \
           f"{ann['metacortex.io/excecao-aprovada-por']} · vale ate " \
           f"{ann['metacortex.io/excecao-valida-ate']}"


def cobra(obj, onde, regra, msg, nivel="ERRO"):
    """Registra o achado, rebaixando para EXCECAO se houver uma declarada."""
    just = excecao_declarada(obj, regra)
    if just is None:
        registra(nivel, onde, regra, msg)
    elif just.startswith("INCOMPLETA"):
        registra("ERRO", onde, regra, f"{msg} — excecao declarada mas {just}")
    else:
        registra("EXCECAO", onde, regra, f"{msg} — {just}")


def ambiente(ns):
    return ns.rsplit("-", 1)[-1] if ns and "-" in ns else None


def pod_template(obj):
    if obj.get("kind") == "CronJob":
        return (((obj.get("spec") or {}).get("jobTemplate") or {})
                .get("spec") or {}).get("template") or {}
    return (obj.get("spec") or {}).get("template") or {}


def containers(pod_spec):
    return (pod_spec.get("containers") or []) + (pod_spec.get("initContainers") or [])


# ---------------------------------------------------------------- por objeto

def checa_metadata(onde, obj):
    md = obj.get("metadata") or {}
    nome = md.get("name")
    kind = obj.get("kind")

    if nome and not KEBAB.match(str(nome)):
        cobra(obj, onde, "1.1", f"nome '{nome}' fora do kebab-case")

    ns = md.get("namespace") or (nome if kind == "Namespace" else None)
    if ns and not NAMESPACE.match(str(ns)):
        cobra(obj, onde, "1.2",
              f"namespace '{ns}' fora do formato <cliente>-<ambiente> (dev|stg|prod)")

    faltando = [r for r in ROTULOS if r not in (md.get("labels") or {})]
    if faltando:
        cobra(obj, onde, "1.3", f"faltam rotulos obrigatorios: {', '.join(faltando)}")

    if not (md.get("annotations") or {}).get("metacortex.io/owner"):
        cobra(obj, onde, "1.5", "sem anotacao metacortex.io/owner", nivel="AVISO")


def checa_workload(onde, obj):
    kind, spec = obj.get("kind"), obj.get("spec") or {}
    ns = (obj.get("metadata") or {}).get("namespace")
    amb = ambiente(ns)
    tpl = pod_template(obj)
    tpl_labels = (tpl.get("metadata") or {}).get("labels") or {}
    pod_spec = tpl.get("spec") or {}

    faltando = [r for r in ROTULOS if r not in tpl_labels]
    if faltando:
        cobra(obj, onde, "1.3",
              f"template do pod sem os rotulos: {', '.join(faltando)}")

    seletor = (spec.get("selector") or {}).get("matchLabels") or {}
    divergentes = {k: v for k, v in seletor.items() if tpl_labels.get(k) != v}
    if divergentes:
        cobra(obj, onde, "1.4",
              f"matchLabels nao casa com os rotulos do template: {divergentes}")

    if amb == "prod" and kind in ("Deployment", "StatefulSet"):
        if (spec.get("replicas") or 1) < 2:
            cobra(obj, onde, "2.3",
                  f"replicas={spec.get('replicas', 1)} em producao; o minimo e 2")
        if kind == "Deployment":
            est = spec.get("strategy") or {}
            ru = est.get("rollingUpdate") or {}
            if est.get("type") != "RollingUpdate" or ru.get("maxUnavailable") not in (0, "0"):
                cobra(obj, onde, "2.4",
                      "producao exige RollingUpdate com maxUnavailable: 0")

    if pod_spec.get("automountServiceAccountToken") is not False:
        cobra(obj, onde, "3.4",
              "automountServiceAccountToken nao esta false no pod")

    sa = pod_spec.get("serviceAccountName")
    if not sa or sa == "default":
        cobra(obj, onde, "3.5",
              "usa a ServiceAccount default do namespace", nivel="AVISO")

    for c in containers(pod_spec):
        checa_container(f"{onde} · container '{c.get('name')}'", obj, c)


def checa_container(onde, obj, c):
    nome = c.get("name") or ""
    if nome.lower() in NOMES_GENERICOS:
        cobra(obj, onde, "1.6",
              f"nome de container generico '{nome}'; use o nome do componente",
              nivel="AVISO")

    img = c.get("image") or ""
    if img and not img.startswith(REGISTRY + "/"):
        cobra(obj, onde, "3.7", f"imagem fora do registry do parque: {img}")

    e_init = c in ((pod_template(obj).get("spec") or {}).get("initContainers") or [])
    if not e_init:
        ready, live = c.get("readinessProbe"), c.get("livenessProbe")
        if not ready or not live:
            faltam = [n for n, p in (("readinessProbe", ready), ("livenessProbe", live)) if not p]
            cobra(obj, onde, "2.2", f"faltam probes: {', '.join(faltam)}")
        elif ready == live:
            cobra(obj, onde, "2.2",
                  "readiness e liveness apontam para o mesmo alvo; banco lento vira reinicio")

    for env in c.get("env") or []:
        valor = env.get("value")
        if valor is None:
            continue
        if CREDENCIAL_EM_URL.search(str(valor)):
            cobra(obj, onde, "3.3",
                  f"credencial embutida em URL na variavel {env.get('name')}")
        elif NOME_SENSIVEL.search(str(env.get("name") or "")):
            cobra(obj, onde, "3.3",
                  f"variavel {env.get('name')} com valor literal; use secretKeyRef")


def checa_configmap(onde, obj):
    for k, v in (obj.get("data") or {}).items():
        if CREDENCIAL_EM_URL.search(str(v)):
            cobra(obj, onde, "3.3", f"credencial embutida em URL na chave {k}")
        elif NOME_SENSIVEL.search(str(k)):
            cobra(obj, onde, "3.3", f"chave {k} parece sensivel para um ConfigMap")


# ------------------------------------------------------------- cruzamentos

def checa_cruzamentos(objs):
    """1.4 no ponto em que ela e silenciosa: o Service.

    O apiserver ja rejeita matchLabels divergente do template. Quem sobe sem
    reclamar e o Service, que e criado normalmente e nasce sem endpoint.
    """
    pods = []
    for onde, o in objs:
        if o.get("kind") in COM_POD:
            tpl = pod_template(o)
            labels = (tpl.get("metadata") or {}).get("labels") or {}
            if labels:
                pods.append(((o.get("metadata") or {}).get("namespace"), labels, onde))

    prod_com_replicas, pdbs = [], []
    for onde, o in objs:
        md = o.get("metadata") or {}
        if o.get("kind") == "Service":
            sel = (o.get("spec") or {}).get("selector") or {}
            if not sel:
                continue
            ns = md.get("namespace")
            casa = [p for pns, plabels, _ in pods
                    if pns == ns and all(plabels.get(k) == v for k, v in sel.items())
                    for p in [1]]
            if not casa:
                cobra(o, onde, "1.4",
                      f"seletor {sel} nao casa com nenhum pod de '{ns}' neste conjunto; "
                      "o Service sobe sem reclamar e nasce sem endpoint")
        if o.get("kind") in ("Deployment", "StatefulSet") \
                and ambiente(md.get("namespace")) == "prod" \
                and ((o.get("spec") or {}).get("replicas") or 1) > 1:
            prod_com_replicas.append((onde, o, md.get("name"), md.get("namespace")))
        if o.get("kind") == "PodDisruptionBudget":
            pdbs.append((md.get("namespace"),
                         ((o.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}))

    for onde, o, nome, ns in prod_com_replicas:
        tpl_labels = (pod_template(o).get("metadata") or {}).get("labels") or {}
        coberto = any(pns == ns and sel and all(tpl_labels.get(k) == v for k, v in sel.items())
                      for pns, sel in pdbs)
        if not coberto:
            cobra(o, onde, "2.5",
                  f"workload de producao com mais de uma replica e sem PDB", nivel="AVISO")


# ------------------------------------------------------------------- carga

def carrega(caminhos):
    objs = []
    for c in caminhos:
        p = pathlib.Path(c)
        arquivos = sorted(list(p.rglob("*.yaml")) + list(p.rglob("*.yml"))) if p.is_dir() else [p]
        for a in arquivos:
            try:
                docs = list(yaml.safe_load_all(a.read_text(encoding="utf-8")))
            except yaml.YAMLError as e:
                registra("ERRO", str(a), "-", f"YAML invalido: {e}")
                continue
            for i, d in enumerate(docs):
                if isinstance(d, dict) and d.get("kind"):
                    nome = (d.get("metadata") or {}).get("name", f"doc{i}")
                    objs.append((f"{a.name}:{d['kind']}/{nome}", d))
    return objs


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    objs = carrega(argv[1:])
    if not objs:
        print("Nenhum manifesto encontrado.", file=sys.stderr)
        return 2

    for onde, o in objs:
        checa_metadata(onde, o)
        if o.get("kind") in COM_POD or o.get("kind") == "CronJob":
            checa_workload(onde, o)
        if o.get("kind") == "ConfigMap":
            checa_configmap(onde, o)
    checa_cruzamentos(objs)

    ordem = {"ERRO": 0, "AVISO": 1, "EXCECAO": 2}
    for nivel, onde, regra, msg in sorted(achados, key=lambda a: (ordem[a[0]], a[1])):
        print(f"{nivel:<7} [{regra}] {onde}\n        {msg}")

    erros = sum(1 for a in achados if a[0] == "ERRO")
    avisos = sum(1 for a in achados if a[0] == "AVISO")
    excs = sum(1 for a in achados if a[0] == "EXCECAO")
    print(f"\n{len(objs)} objetos · {erros} erro(s) · {avisos} aviso(s) · {excs} excecao(oes)")
    print("Regras 2.1, 3.1, 3.2 e 3.6 nao sao conferidas aqui: rode `trivy config`.")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
