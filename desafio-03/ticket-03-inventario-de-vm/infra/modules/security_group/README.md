# modules/security_group

Security group que autoriza SSH a partir de um unico bloco CIDR e, opcionalmente,
saida irrestrita para preparar as instancias.

Ao contrario da network ACL, o security group e **stateful**: a resposta de uma
conexao autorizada volta sem regra de saida correspondente.

## Entradas

| Nome | Tipo | Padrao | Descricao |
|---|---|---|---|
| `name` | `string` | — | nome do security group |
| `description` | `string` | — | descricao do security group |
| `vpc_id` | `string` | — | VPC onde ele e criado |
| `ssh_ingress_cidr_block` | `string` | — | unico CIDR autorizado a abrir SSH |
| `internet_egress_enabled` | `bool` | `true` | cria a regra de saida irrestrita |
| `tags` | `map(string)` | `{}` | tags do recurso |

## Saidas

| Nome | Descricao |
|---|---|
| `security_group_id` | ID do security group |

## Exemplo

```hcl
module "security_group" {
  source = "../../modules/security_group"

  name                   = "metacortex-lab-vm"
  description            = "Acesso as VMs do parque"
  vpc_id                 = module.network.vpc_id
  ssh_ingress_cidr_block = "200.158.165.27/32"
}
```
