output "vpc_id" {
  description = "ID da VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "IDs das subnets publicas, indexados pela zona de disponibilidade"
  value       = { for zona, subnet in aws_subnet.public : zona => subnet.id }
}

output "public_network_acl_id" {
  description = "ID da network ACL associada as subnets publicas"
  value       = aws_network_acl.public.id
}
