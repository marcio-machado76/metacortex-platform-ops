resource "aws_security_group" "this" {
  name        = var.name
  description = var.description
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.this.id
  description       = "SSH somente a partir do IP do operador"
  cidr_ipv4         = var.ssh_ingress_cidr_block
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22

  tags = merge(var.tags, { Name = "${var.name}-ssh" })
}

# O security group e stateful: a resposta do SSH nao precisa de regra.
# Esta saida existe para a preparacao das VMs e pode ser removida depois.
resource "aws_vpc_security_group_egress_rule" "all" {
  count = var.internet_egress_enabled ? 1 : 0

  security_group_id = aws_security_group.this.id
  description       = "Saida irrestrita para instalacao de pacotes"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"

  tags = merge(var.tags, { Name = "${var.name}-egress" })
}
