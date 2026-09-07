# Alcance ao cluster — mcp-server-kubernetes

O `.mcp.json` deste diretorio e a copia canonica; a raiz do repositorio tem um
symlink para ele, que e onde o agente le a configuracao. Uma fonte so, e o
arquivo fica dentro da pasta do ticket a que ele pertence.

```json
{
  "mcpServers": {
    "kubernetes": {
      "command": "npx",
      "args": ["-y", "mcp-server-kubernetes"],
      "env": { "ALLOW_ONLY_READONLY_TOOLS": "true" }
    }
  }
}
```

## Decisao: somente-leitura, e nao apenas nao-destrutivo

O enunciado descreve o servidor "em modo nao-destrutivo". O servidor tem os dois
modos, e eles nao sao equivalentes:

| Variavel | O que remove | O que continua disponivel |
|---|---|---|
| `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS` | `kubectl_delete`, `cleanup`, `cleanup_pods`, `node_management`, `uninstall_helm_chart`, `kubectl_generic` | `kubectl_apply`, `kubectl_create`, `kubectl_scale`, `kubectl_patch`, `helm install/upgrade` |
| `ALLOW_ONLY_READONLY_TOOLS` | toda ferramenta capaz de alterar o estado do cluster | somente consulta: `kubectl_get`, `kubectl_describe`, `kubectl_logs`, eventos |

O invariante do ticket e mais forte que a palavra usada para descreve-lo:
"triagem le, nunca escreve; nenhuma correcao e aplicada no cluster por
iniciativa propria, **nem quando o agente tem permissao para isso**". O modo
nao-destrutivo deixa `kubectl_apply` e `kubectl_scale` na mesa — ou seja,
deixa exatamente a permissao que o invariante manda nao exercer.

Por isso a garantia tecnica fica em `ALLOW_ONLY_READONLY_TOOLS=true`. O texto da
skill reforca o limite, mas quem o impede e o servidor: uma instrucao pode ser
contornada por um pedido bem formulado, uma ferramenta ausente nao.

Fonte: `README.md` e `ADVANCED_README.md` de https://github.com/flux159/mcp-server-kubernetes,
consultados em 2026-09-06.

## Verificacao

A evidencia de que o modo esta valendo nao e a configuracao, e a recusa: com o
servidor no ar, pedir uma escrita ao agente e capturar a resposta. Isso entra em
`../execucoes/` junto com a triagem dos tres chamados.
