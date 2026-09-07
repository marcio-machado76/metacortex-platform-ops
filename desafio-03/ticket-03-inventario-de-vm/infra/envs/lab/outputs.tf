output "vpc_id" {
  description = "ID da VPC do laboratorio"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "IDs das subnets publicas, indexados pela zona de disponibilidade"
  value       = module.network.public_subnet_ids
}

output "security_group_id" {
  description = "ID do security group das VMs"
  value       = module.security_group.security_group_id
}

output "vm_conforme_public_ip" {
  description = "IP publico da VM preparada dentro do baseline"
  value       = module.vm_conforme.instance_public_ip
}

output "vm_desvio_public_ip" {
  description = "IP publico da VM preparada fora do baseline"
  value       = module.vm_desvio.instance_public_ip
}

output "vm_private_ips" {
  description = "IPs privados das VMs, usados na regra de porta interna do baseline"
  value = {
    conforme = module.vm_conforme.instance_private_ip
    desvio   = module.vm_desvio.instance_private_ip
  }
}

output "ssh_commands" {
  description = "Comandos de conexao com o usuario de coleta, que nao tem sudo"
  value = {
    conforme = "ssh -i ../../.secrets/metacortex-platform roster@${module.vm_conforme.instance_public_ip}"
    desvio   = "ssh -i ../../.secrets/metacortex-platform roster@${module.vm_desvio.instance_public_ip}"
  }
}
