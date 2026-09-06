output "instance_id" {
  description = "ID da instancia EC2"
  value       = aws_instance.this.id
}

output "instance_public_ip" {
  description = "Endereco IP publico usado na conexao SSH"
  value       = aws_instance.this.public_ip
}

output "instance_private_ip" {
  description = "Endereco IP privado da instancia"
  value       = aws_instance.this.private_ip
}

output "ami_id" {
  description = "ID da AMI resolvida para a instancia"
  value       = data.aws_ami.this.id
}
