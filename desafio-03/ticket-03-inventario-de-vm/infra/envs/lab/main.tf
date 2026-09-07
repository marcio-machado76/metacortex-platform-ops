module "network" {
  source = "../../modules/network"

  name                    = "${local.name_prefix}-lab"
  cidr_block              = local.vpc_cidr
  public_subnets          = local.public_subnets
  ssh_ingress_cidr_block  = var.ssh_ingress_cidr_block
  internet_egress_enabled = var.internet_egress_enabled
}

module "security_group" {
  source = "../../modules/security_group"

  name                    = "${local.name_prefix}-lab-vm"
  description             = "Acesso as VMs do laboratorio de inventario"
  vpc_id                  = module.network.vpc_id
  ssh_ingress_cidr_block  = var.ssh_ingress_cidr_block
  internet_egress_enabled = var.internet_egress_enabled
}

module "ssh_key" {
  source = "../../modules/ssh_key"

  key_name   = "${local.name_prefix}-platform"
  public_key = local.chave_platform
}

# VM dentro do baseline: Ubuntu 24.04 entrega kernel 6.8, acima do minimo 6.5.
module "vm_conforme" {
  source = "../../modules/vm"

  name                   = "${local.name_prefix}-vm-conforme"
  ami_name_pattern       = "ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"
  subnet_id              = module.network.public_subnet_ids["us-east-1a"]
  vpc_security_group_ids = [module.security_group.security_group_id]
  key_name               = module.ssh_key.key_pair_name
  user_data              = local.user_data_conforme
}

# VM fora do baseline: Ubuntu 22.04 entrega kernel 5.15, abaixo do minimo 6.5,
# e o user_data adiciona um desvio de cada severidade.
module "vm_desvio" {
  source = "../../modules/vm"

  name                   = "${local.name_prefix}-vm-desvio"
  ami_name_pattern       = "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
  subnet_id              = module.network.public_subnet_ids["us-east-1b"]
  vpc_security_group_ids = [module.security_group.security_group_id]
  key_name               = module.ssh_key.key_pair_name
  user_data              = local.user_data_desvio
}
