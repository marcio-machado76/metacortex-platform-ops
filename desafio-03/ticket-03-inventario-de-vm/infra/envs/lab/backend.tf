# State remoto por ambiente. O bloqueio usa o lockfile nativo do S3,
# sem tabela DynamoDB.
terraform {
  backend "s3" {
    bucket       = "metacortex-terraform-state"
    key          = "metacortex/ticket-03/lab.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
