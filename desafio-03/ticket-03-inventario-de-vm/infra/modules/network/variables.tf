variable "name" {
  description = "Nome base aplicado aos recursos de rede"
  type        = string
  nullable    = false
}

variable "cidr_block" {
  description = "Bloco CIDR da VPC"
  type        = string
  nullable    = false
}

variable "public_subnets" {
  description = "Subnets publicas da VPC, no formato zona de disponibilidade => bloco CIDR"
  type        = map(string)
  nullable    = false
}

variable "ssh_ingress_cidr_block" {
  description = "Unico bloco CIDR autorizado a abrir SSH nas subnets"
  type        = string
  nullable    = false
}

variable "internet_egress_enabled" {
  description = "Libera na network ACL a saida HTTP, HTTPS, DNS e NTP e o retorno em portas efemeras. A network ACL e stateless: sem estas regras as VMs nao instalam pacote nem sincronizam relogio, e a rede fica restrita a SSH"
  type        = bool
  default     = true
  nullable    = false
}

variable "tags" {
  description = "Tags aplicadas aos recursos de rede"
  type        = map(string)
  default     = {}
  nullable    = false
}
