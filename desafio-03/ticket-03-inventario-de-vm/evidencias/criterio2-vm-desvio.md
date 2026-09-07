# Inventário e conformidade — ip-10-42-2-140

- Endereço: 44.211.244.86
- Coletado em: 2026-09-07T02:30:26Z
- Baseline: versão 1

## Desvios

| Severidade | Regra | Esperado | Encontrado |
|---|---|---|---|
| crítico | swap.habilitado | não | {"habilitado": true, "tamanho": "4G"} |
| crítico | portas_em_escuta.publicas_permitidas | [22] | [{"porta": 111, "protocolo": "tcp", "bind": "0.0.0.0", "processo": null}, {"porta": 111, "protocolo": "tcp", "bind": "::", "processo": null}, {"porta": 111, "protocolo": "udp", "bind": "0.0.0.0", "processo": null}, {"porta": 111, "protocolo": "udp", "bind": "::", "processo": null}, {"porta": 9100, "protocolo": "tcp", "bind": "0.0.0.0", "processo": null}] |
| crítico | portas_em_escuta.somente_rede_interna | [9100] | [{"porta": 9100, "protocolo": "tcp", "bind": "0.0.0.0", "processo": null}] |
| crítico | chaves_ssh.emitidas_por | metacortex-platform | [{"identificacao": "dozer@laptop-pessoal", "origem": "/home/roster/.ssh/authorized_keys"}] |
| alto | servicos.ativos | ["ssh", "containerd", "node_exporter", "chrony"] | {"ssh": {"ativo": true, "forma": "service"}, "containerd": {"ativo": false, "forma": null}, "node_exporter": {"ativo": true, "forma": "service"}, "chrony": {"ativo": false, "forma": null}} |
| alto | servicos.proibidos | ["telnet.socket", "rpcbind.socket"] | ["rpcbind.socket"] |
| médio | ntp.sincronizado | sim | {"sincronizado": false, "mecanismo": null} |

## Não verificado

| Regra | Motivo |
|---|---|
| ssh.login_de_root | leitura da configuração efetiva de login de root exige privilégio que o usuário da coleta não tem |

## Conforme

- so.distribuicao
- so.versao_minima
- kernel.versao_minima
