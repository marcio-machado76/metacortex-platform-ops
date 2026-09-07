variable "key_name" {
  description = "Nome do key pair na AWS"
  type        = string
  nullable    = false
}

variable "public_key" {
  description = "Conteudo da chave publica em formato OpenSSH. A chave privada correspondente nunca transita pelo Terraform"
  type        = string
  nullable    = false
}

variable "tags" {
  description = "Tags aplicadas ao key pair"
  type        = map(string)
  default     = {}
  nullable    = false
}
