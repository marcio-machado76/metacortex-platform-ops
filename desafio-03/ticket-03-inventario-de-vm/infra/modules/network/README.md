# modules/network

VPC com subnets publicas, internet gateway, tabela de rotas e uma network ACL
compartilhada pelas subnets.

A network ACL e **stateless**, entao ela e o ponto sensivel deste modulo: o
conjunto permanente libera SSH na entrada e a resposta do SSH na saida, e nada
mais. As regras de HTTP, HTTPS, DNS e NTP existem so para permitir a preparacao
das VMs e sao removidas ao passar `internet_egress_enabled = false`.

## Entradas

| Nome | Tipo | Padrao | Descricao |
|---|---|---|---|
| `name` | `string` | — | nome base dos recursos |
| `cidr_block` | `string` | — | CIDR da VPC |
| `public_subnets` | `map(string)` | — | zona de disponibilidade => CIDR |
| `ssh_ingress_cidr_block` | `string` | — | unico CIDR autorizado a abrir SSH |
| `internet_egress_enabled` | `bool` | `true` | libera saida e retorno efemero na network ACL |
| `tags` | `map(string)` | `{}` | tags dos recursos |

## Saidas

| Nome | Descricao |
|---|---|
| `vpc_id` | ID da VPC |
| `public_subnet_ids` | IDs das subnets, indexados pela zona |
| `public_network_acl_id` | ID da network ACL |

## Exemplo

```hcl
module "network" {
  source = "../../modules/network"

  name                   = "metacortex-lab"
  cidr_block             = "10.42.0.0/16"
  public_subnets         = { "us-east-1a" = "10.42.1.0/24", "us-east-1b" = "10.42.2.0/24" }
  ssh_ingress_cidr_block = "200.158.165.27/32"
}
```
