# Workloads do parque — origem e versao lida

Os tres projetos hospedados pela Metacortex nao versionam manifests de
Kubernetes. Porta, endpoint de probe, dependencia de banco e credencial saem de
dentro do projeto — por isso a skill do Ticket 01, no modo de escrita, **le o
codigo**, e a conferencia do manifesto barrado tambem depende de abrir o
kube-news.

Os repositorios sao clonados em `workloads/`, na raiz deste repositorio, e ficam
**fora do versionamento** (`.gitignore`): sao codigo de terceiros, nao artefato
da entrega. O que fica registrado aqui e o commit exato que foi lido, para que
qualquer conclusao da skill seja reproduzivel.

| Projeto | Cliente | Repositorio | Commit lido | Data do commit |
|---|---|---|---|---|
| kube-news | nyx | https://github.com/KubeDev/kube-news | `aab93563069d184c66dd1f0359bd131ffbe34433` | 2025-04-19 |
| fake-shop | orion | https://github.com/KubeDev/fake-shop | `a3fa74fcadea2f163dd785313b119d4c8e03ecea` | 2026-07-19 |
| encontros-tech | helio | https://github.com/KubeDev/encontros-tech | `0f5bbad86f7e576cd9d64189c581ecee20f547df` | 2026-05-31 |

Clonados em 2026-09-06 com `git clone --depth 1` do branch padrao.

## Como refazer o clone

```bash
mkdir -p workloads && cd workloads
for r in kube-news fake-shop encontros-tech; do
  git clone --depth 1 https://github.com/KubeDev/$r.git
done
```

## Para que serve cada um

- **kube-news** — alvo do modo de conferencia. O Deployment barrado nao declara
  probes, e decidir para onde elas deveriam apontar exige ver os endpoints que a
  aplicacao expoe.
- **fake-shop** — alvo do modo de escrita. E o caso que mais cobra decisao:
  migracao de banco no start e nenhum endpoint de saude exposto, o que deixa as
  regras de probe do padrao sem resposta obvia.
- **encontros-tech** — alvo do modo de escrita da skill, rodado por um agente em
  sessao limpa. Escolhido de proposito por ser o projeto que nem eu nem a skill
  tinham aberto: testa se o metodo generaliza, em vez de reproduzir o que ja
  estava documentado.

## Achado sobre o encontros-tech, com consequencia para o Ticket 04

O repositorio tem **dois commits**, e o `0f5bbad` registrado acima — o commit
lido — chama-se **"Removendo Docker"**:

```
0f5bbad Removendo Docker
 docker-compose.yml | 36 -----
 src/.dockerignore  | 68 -----
 src/Dockerfile     |  7 -----
```

O projeto **nao tem Dockerfile hoje e nao tem imagem publicada**. Duas
consequencias:

1. No manifesto gerado, o `image:` e um placeholder declarado como tal. Nenhuma
   regra do padrao alcanca isso — e um bloqueio anterior ao manifesto.
2. **O Ticket 04 usa kube-news e fake-shop**, que tem imagem publica. Subir o
   encontros-tech exigiria reconstruir o build, o que esta fora do escopo daquele
   ticket.

O Dockerfile recuperado do historico (`git show 0f5bbad^:src/Dockerfile`) e o que
respondeu porta e concorrencia para o manifesto:

```dockerfile
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

Quatro workers por replica, e nenhum `USER` na imagem — ela roda como root, o que
torna `runAsUser: 10001` um risco declarado e nao um fato verificado.
