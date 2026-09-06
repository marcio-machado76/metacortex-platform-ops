variable "name" {
  description = "Nome da instancia"
  type        = string
  nullable    = false
}

variable "ami_name_pattern" {
  description = "Padrao de nome usado para resolver a AMI mais recente, por exemplo ubuntu/images/hvm-ssd*/ubuntu-noble-24.04-amd64-server-*"
  type        = string
  nullable    = false
}

variable "ami_owner" {
  description = "Conta proprietaria da AMI. 099720109477 e a Canonical"
  type        = string
  default     = "099720109477"
  nullable    = false
}

variable "instance_type" {
  description = "Tipo da instancia EC2"
  type        = string
  default     = "t3.micro"
  nullable    = false
}

variable "subnet_id" {
  description = "ID da subnet onde a instancia e criada"
  type        = string
  nullable    = false
}

variable "vpc_security_group_ids" {
  description = "IDs dos security groups associados a instancia"
  type        = list(string)
  nullable    = false
}

variable "key_name" {
  description = "Nome do key pair usado para o acesso administrativo do usuario padrao da imagem"
  type        = string
  nullable    = false
}

variable "user_data" {
  description = "Script de inicializacao da instancia"
  type        = string
  default     = null
}

variable "root_volume_size" {
  description = "Tamanho em GiB do volume raiz"
  type        = number
  default     = 8
  nullable    = false
}

variable "tags" {
  description = "Tags aplicadas a instancia"
  type        = map(string)
  default     = {}
  nullable    = false
}
