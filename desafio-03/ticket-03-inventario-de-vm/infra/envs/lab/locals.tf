locals {
  region      = "us-east-1"
  name_prefix = "metacortex"
  vpc_cidr    = "10.42.0.0/16"

  public_subnets = {
    "us-east-1a" = "10.42.1.0/24"
    "us-east-1b" = "10.42.2.0/24"
  }

  tags = {
    Projeto   = "metacortex-platform-ops"
    Ticket    = "03-inventario-de-vm"
    Ambiente  = "lab"
    Terraform = "true"
  }

  # Somente a chave publica entra no user_data. A privada fica em .secrets,
  # fora do versionamento, e nunca transita pelo state.
  chave_platform    = trimspace(file("${path.root}/../../.secrets/metacortex-platform.pub"))
  chave_nao_emitida = trimspace(file("${path.root}/../../.secrets/metacortex-chave-nao-emitida.pub"))

  user_data_conforme = templatefile("${path.root}/user_data/conforme.sh.tftpl", {
    chave_platform = local.chave_platform
  })

  user_data_desvio = templatefile("${path.root}/user_data/desvio.sh.tftpl", {
    chave_platform    = local.chave_platform
    chave_nao_emitida = local.chave_nao_emitida
  })
}
