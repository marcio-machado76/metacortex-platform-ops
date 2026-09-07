variable "name" {
  description = "Nome do security group"
  type        = string
  nullable    = false
}

variable "description" {
  description = "Descricao do security group"
  type        = string
  nullable    = false
}

variable "vpc_id" {
  description = "ID da VPC onde o security group e criado"
  type        = string
  nullable    = false
}

variable "ssh_ingress_cidr_block" {
  description = "Unico bloco CIDR autorizado a abrir SSH"
  type        = string
  nullable    = false
}

variable "internet_egress_enabled" {
  description = "Cria a regra de saida irrestrita. Necessaria para instalar pacote nas VMs; sem ela o security group nao permite nenhuma conexao iniciada pela instancia"
  type        = bool
  default     = true
  nullable    = false
}

variable "tags" {
  description = "Tags aplicadas ao security group"
  type        = map(string)
  default     = {}
  nullable    = false
}
