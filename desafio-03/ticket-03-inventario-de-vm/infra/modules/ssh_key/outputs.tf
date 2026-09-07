output "key_pair_name" {
  description = "Nome do key pair criado"
  value       = aws_key_pair.this.key_name
}

output "key_pair_fingerprint" {
  description = "Fingerprint da chave publica registrada"
  value       = aws_key_pair.this.fingerprint
}
