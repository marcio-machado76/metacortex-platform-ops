# modules/ssh_key

Registra na AWS um key pair a partir de uma chave publica ja existente.

O modulo recebe apenas a **chave publica**. A chave privada permanece na estacao
de quem opera e nunca entra no state nem em output — o Ticket 03 trata a chave
privada como credencial, e state do Terraform e um lugar onde credencial nao
deve aparecer.

## Entradas

| Nome | Tipo | Padrao | Descricao |
|---|---|---|---|
| `key_name` | `string` | — | nome do key pair na AWS |
| `public_key` | `string` | — | chave publica em formato OpenSSH |
| `tags` | `map(string)` | `{}` | tags do recurso |

## Saidas

| Nome | Descricao |
|---|---|
| `key_pair_name` | nome do key pair criado |
| `key_pair_fingerprint` | fingerprint da chave publica |

## Exemplo

```hcl
module "ssh_key" {
  source = "../../modules/ssh_key"

  key_name   = "metacortex-platform"
  public_key = file("../../.secrets/metacortex-platform.pub")
}
```
