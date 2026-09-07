# infra — laboratorio do Ticket 03

Duas EC2 Ubuntu na `us-east-1`, uma dentro e outra fora do `baseline.yaml`, para
servir de alvo real da ferramenta de inventario e drift.

Estrutura conforme o padrao da casa: um diretorio por ambiente em `envs/`,
capacidades em `modules/`, todos escritos neste repositorio.

```
infra/
├── envs/lab/          # ambiente aplicado (provider, backend, chamadas de modulo)
├── modules/network/           # VPC, subnets, IGW, rotas e network ACL
├── modules/security_group/    # SSH restrito ao IP do operador
├── modules/ssh_key/           # key pair a partir da chave publica
├── modules/vm/                # uma instancia EC2
└── .secrets/          # chaves SSH, fora do versionamento
```

## O que sobe

| Recurso | Valor |
|---|---|
| VPC | `10.42.0.0/16`, nome `metacortex-lab` |
| Subnets publicas | `10.42.1.0/24` em `us-east-1a`, `10.42.2.0/24` em `us-east-1b` |
| Security group | entrada TCP 22 somente de `ssh_ingress_cidr_block` |
| Network ACL | entrada TCP 22 do mesmo CIDR, saida das respostas, e nada mais quando `internet_egress_enabled = false` |
| `metacortex-vm-conforme` | Ubuntu 24.04 em `us-east-1a` |
| `metacortex-vm-desvio` | Ubuntu 22.04 em `us-east-1b` |

Nenhuma das duas abre a porta 9100 para fora: a diferenca entre elas esta no
endereco em que o `node_exporter` escuta dentro do host, que e o que a regra
`portas_em_escuta.somente_rede_interna` do baseline avalia.

## Network ACL e a saida para internet

A network ACL e stateless, entao ela nao "sabe" que um pacote e resposta de uma
conexao que a propria VM iniciou. Uma ACL estritamente so-SSH impede `apt`,
download e sincronizacao de relogio — e sem isso a VM conforme nao tem como
ficar conforme.

O ajuste fica em `internet_egress_enabled`:

- `true` (padrao) — sobem as regras de saida 80, 443, DNS e NTP e o retorno em
  portas efemeras. Use no apply inicial, que e quando o `user_data` roda.
- `false` — restam apenas SSH na entrada e a resposta do SSH na saida. Aplique
  depois que as duas VMs estiverem preparadas.

O mesmo interruptor governa a regra de saida do security group.

## Estado das VMs

`metacortex-vm-conforme` sai do `user_data` sem nenhum desvio: `containerd`,
`chrony` e `node_exporter` ativos, `node_exporter` ligado ao IP privado, swap
desligado e `PermitRootLogin no`.

`metacortex-vm-desvio` sai com um desvio de cada severidade:

| Regra | Severidade | Desvio plantado |
|---|---|---|
| `swap.habilitado` | critico | swapfile de 4G ativo |
| `chaves_ssh.emitidas_por` | critico | segunda chave com comentario `dozer@laptop-pessoal` |
| `portas_em_escuta.somente_rede_interna` | critico | `node_exporter` em `0.0.0.0:9100` |
| `servicos.ativos` | alto | `containerd` nao instalado e `chrony` desligado |
| `servicos.proibidos` | alto | `rpcbind.socket` ativo |
| `ntp.sincronizado` | medio | sincronizacao de tempo desligada |

> **A AMI se moveu, e a descricao envelheceu junto.** A versao anterior deste
> laboratorio contava com o Ubuntu 22.04 entregando kernel 5.15 (desvio medio) e
> sem `chrony` instalado (desvio alto). A AMI atual da AWS entrega kernel 6.8, que
> passa no minimo de 6.5, e ja traz `chrony` ativo — os dois desvios sumiram sem
> que nada no codigo mudasse. Descoberto ao conferir o laboratorio antes da
> validacao, e corrigido desligando a sincronizacao de tempo, que e o unico desvio
> medio que resta sob nosso controle.

Nos dois hosts a coleta entra com o usuario `roster`, **sem sudo**. E isso que
produz o veredito `nao_verificado` em `ssh.login_de_root`, que exige ler a
configuracao efetiva do sshd com privilegio.

## Chaves

Ja geradas em `.secrets/`, fora do versionamento:

| Arquivo | Comentario | Uso |
|---|---|---|
| `metacortex-platform` | `platform@metacortex-platform` | chave da plataforma, autorizada nas duas VMs |
| `metacortex-chave-nao-emitida` | `dozer@laptop-pessoal` | chave nao emitida pela plataforma, so na VM de desvio |

O comentario da chave e o que a regra `chaves_ssh.emitidas_por` do baseline le.
Somente a chave publica entra no Terraform; a privada nunca toca o state.

## Como aplicar

O state fica no bucket `metacortex-terraform-state`, chave
`metacortex/ticket-03/lab.tfstate`, com bloqueio pelo lockfile nativo do S3.
Se o versionamento do bucket ainda nao estiver ligado:

```bash
aws s3api put-bucket-versioning --bucket metacortex-terraform-state \
  --versioning-configuration Status=Enabled
```

A partir de `envs/lab`:

```bash
aws sso login

terraform init
terraform plan
terraform apply
```

As duas variaveis do ambiente podem vir de `terraform.tfvars` (copie de
`terraform.tfvars.example`, o arquivo real esta no .gitignore) ou do ambiente:

```bash
export TF_VAR_ssh_ingress_cidr_block="200.158.165.27/32"
export TF_VAR_internet_egress_enabled=true
```

O `user_data` leva de dois a tres minutos apos o `apply` retornar. O arquivo
`/var/lib/metacortex-preparado` marca o fim da preparacao em cada host.

Depois que as duas VMs estiverem prontas, para deixar a rede restrita a SSH:

```bash
terraform apply -var="internet_egress_enabled=false"
```

Ao terminar as evidencias:

```bash
terraform destroy
```

## O laboratorio e efemero por decisao

As duas VMs existem para produzir a evidencia de execucao do Ticket 03 e nada
mais. Fora dessa janela elas ficam destruidas: EC2 ligada sem uso e custo sem
contrapartida, e todo o estado delas esta descrito aqui.

Sobe com `terraform apply`, desce com `terraform destroy`, e o `user_data`
devolve os dois hosts no mesmo estado — a VM conforme com `containerd`, `chrony`
e `node_exporter` no IP privado, e a VM de desvio com um desvio de cada
severidade.

O que sobrevive ao `destroy` e nao precisa ser refeito: as chaves em `.secrets/`,
que sao locais e nao gerenciadas pelo Terraform (o `aws_key_pair` volta da mesma
chave publica, com o mesmo comentario `platform@metacortex-platform` que a regra
`chaves_ssh.emitidas_por` do baseline le), o bucket de state, e o codigo.

O que muda ao recriar: os IPs publicos, que sao parametro da ferramenta e nao
constante. E se o seu IP publico tiver mudado, `ssh_ingress_cidr_block` precisa
acompanhar, senao o SSH nao entra.


## Validacao

`terraform fmt -recursive`, `terraform init -backend=false` e `terraform validate`
rodaram sem erro no ambiente e em cada um dos quatro modulos. O
`.terraform.lock.hcl` foi gerado para `linux_amd64` e `darwin_arm64` e esta
versionado.
