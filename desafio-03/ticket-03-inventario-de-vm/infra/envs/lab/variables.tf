variable "ssh_ingress_cidr_block" {
  description = "Bloco CIDR do operador, unico autorizado a abrir SSH nas VMs do laboratorio"
  type        = string
  default     = "200.158.165.27/32"
  nullable    = false

  validation {
    condition     = can(cidrhost(var.ssh_ingress_cidr_block, 0))
    error_message = "Informe um bloco CIDR valido, por exemplo 200.158.165.27/32."
  }
}

variable "internet_egress_enabled" {
  description = "Mantem liberada a saida para internet no security group e na network ACL. Necessaria para a preparacao das VMs; passe false depois dela para deixar a rede restrita a SSH"
  type        = bool
  default     = true
  nullable    = false
}
