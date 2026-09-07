# modules/vm

Uma instancia EC2 em subnet publica, com a AMI resolvida por padrao de nome.

O modulo cria **uma** instancia. Multiplicidade e responsabilidade de quem chama:
o ambiente `envs/lab` chama este modulo duas vezes, com AMIs e `user_data`
diferentes, para produzir um host dentro do baseline e um host fora dele.

A instancia sobe com IMDSv2 obrigatorio e volume raiz criptografado.

## Entradas

| Nome | Tipo | Padrao | Descricao |
|---|---|---|---|
| `name` | `string` | — | nome da instancia |
| `ami_name_pattern` | `string` | — | padrao de nome da AMI |
| `ami_owner` | `string` | `099720109477` | conta dona da AMI (Canonical) |
| `instance_type` | `string` | `t3.micro` | tipo da instancia |
| `subnet_id` | `string` | — | subnet de destino |
| `vpc_security_group_ids` | `list(string)` | — | security groups da instancia |
| `key_name` | `string` | — | key pair do usuario padrao da imagem |
| `user_data` | `string` | `null` | script de inicializacao |
| `root_volume_size` | `number` | `8` | tamanho do volume raiz em GiB |
| `tags` | `map(string)` | `{}` | tags do recurso |

## Saidas

| Nome | Descricao |
|---|---|
| `instance_id` | ID da instancia |
| `instance_public_ip` | IP publico, usado na conexao SSH |
| `instance_private_ip` | IP privado |
| `ami_id` | AMI resolvida |

## Exemplo

```hcl
module "vm_conforme" {
  source = "../../modules/vm"

  name                   = "metacortex-vm-conforme"
  ami_name_pattern       = "ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"
  subnet_id              = module.network.public_subnet_ids["us-east-1a"]
  vpc_security_group_ids = [module.security_group.security_group_id]
  key_name               = module.ssh_key.key_pair_name
}
```
