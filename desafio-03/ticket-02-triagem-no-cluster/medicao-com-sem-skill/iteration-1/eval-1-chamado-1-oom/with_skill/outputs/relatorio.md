## Chamado: nyx-prod/nyx-api — "a API de produção fica caindo sozinha"

**Causa:** o container `api` do Deployment `nyx-api` é morto pelo cgroup por
estourar memória (`lastState.terminated.reason: OOMKilled`, `exitCode: 137`) porque
o limite declarado — `resources.limits.memory: 24Mi` — é baixo demais para o
processo da aplicação sustentar, gerando reinício em loop nos dois pods.

**Evidência:**
```
$ kubectl get all -n nyx-prod
pod/nyx-api-79c5f4d8d7-2w5kd        0/1   CrashLoopBackOff   9 (93s ago)    23m
pod/nyx-api-79c5f4d8d7-hkw2t        0/1   CrashLoopBackOff   9 (100s ago)   23m
deployment.apps/nyx-api             0/2   2            0           23m

# pod nyx-api-79c5f4d8d7-2w5kd — containerStatuses[0]
"lastState": {
  "terminated": {
    "exitCode": 137,
    "reason": "OOMKilled",
    "startedAt": "2026-09-06T19:28:35Z",
    "finishedAt": "2026-09-06T19:28:37Z"
  }
}
# pod nyx-api-79c5f4d8d7-hkw2t — mesmo padrão, exitCode 137 / OOMKilled

# deployment nyx-api — spec.template.spec.containers[0].resources
{
  "limits":   {"cpu": "200m", "memory": "24Mi"},
  "requests": {"cpu": "50m",  "memory": "16Mi"}
}
```

**Como cheguei:**
1. `kubectl get all -n nyx-prod` — Deployment `nyx-api` em 0/2 disponíveis, dois
   pods em `CrashLoopBackOff` com `restartCount` já em 9. Isso descarta "rollout
   travado": o objeto criou os pods, eles rodaram e morreram.
2. Bifurcação da skill: `restartCount > 0` em ambos → causa está dentro do
   container, não antes dele. Fui direto para `lastState.terminated` em vez de
   `state.waiting` (que só mostra `CrashLoopBackOff`, o efeito, não a causa).
3. `lastState.terminated` dos dois pods: `reason: OOMKilled`, `exitCode: 137` —
   assinatura de catálogo A (container que reinicia por estouro de memória).
4. Cruzei com o `resources.limits.memory` do Deployment: `24Mi`, abaixo de
   qualquer runtime de aplicação web comum — fecha o diagnóstico sem precisar de
   log.
5. `kubectl logs --previous` na instância morta: retorno vazio, como esperado —
   processo morto pelo cgroup não escreve log; não é uma pista perdida.
6. `kubectl get events -n nyx-prod`: confirma o ciclo (`BackOff` recorrente),
   sem revelar motivo — usado só para confirmar repetição, não como fonte de
   causa.
7. Verificação em paralelo da dependência: `nyx-postgres` (1/1, `Running`,
   `restartCount: 0`, `ready: true`) — descarta hipótese de banco indisponível.

**O que está saudável ao lado:**
- `nyx-postgres` (Deployment e pod): 1/1 disponível, pronto, zero reinícios — não
  é o banco.
- Agendamento dos pods: ambos com `nodeName` atribuído e `Scheduled` bem-sucedido
  — não é problema de scheduling/nó.
- Pull de imagem: eventos mostram `Pulled`/`Started`/`Created` normais para
  `fabricioveronez/kube-news:v1` — não é `ErrImagePull` nem imagem inexistente.
- `Service`/`Endpoints` não foram a causa investigada aqui: o sintoma já fecha em
  camada de container (restartCount > 0), então a camada de metadado/rede não
  precisou ser cruzada.

**Correção sugerida (não aplicada):**
Elevar `resources.limits.memory` (e `requests.memory` proporcionalmente) do
container `api` no Deployment `nyx-api` em `nyx-prod` para um valor compatível com
o consumo real do processo — medir o RSS do processo fora do limite atual antes de
fixar o novo valor, em vez de arbitrar outro número às cegas. Vale checar se o
mesmo teto de `24Mi` foi aplicado a outros Deployments do namespace/parque por um
corte de custo genérico, já que o padrão bate com um caso já catalogado
(`references/assinaturas.md`, assinatura A) de mesmo namespace e mesmo limite.
