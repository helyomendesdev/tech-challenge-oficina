# Integração entre Repositórios — Fase 3

## Visão inicial

```text
Cliente
  |
  v
API Gateway
  |-- autenticação por CPF --> Function Serverless --> banco gerenciado
  |
  `-- JWT válido --> aplicação Django no Kubernetes --> banco gerenciado
                                      |
                                      `--> logs, métricas e alertas
```

A posição definitiva do API Gateway e seus módulos Terraform depende de decisão conjunta com Sophia.

## Contratos que precisam ser definidos

### Autenticação

Entrada mínima:

```json
{
  "cpf": "00000000000"
}
```

Saída esperada em caso de sucesso:

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Decisao aprovada na aplicacao principal: `Cliente.ativo` indica se o cliente pode usar os fluxos integrados da Fase 3, nasce como `true` para preservar a base existente e nao altera endpoints publicos de OS.

Tokens de cliente aceitos pela aplicação usam `RS256`, `iss=oficina-auth`,
`aud=oficina-api`, `principal_type=cliente`, `token_type=access` e
`sub=cliente:<id>`. A aplicação valida a assinatura com
`AUTH_JWT_PUBLIC_KEY_B64`, que deve conter a chave pública PEM do emissor
codificada em Base64. Chaves reais não devem ser versionadas.

As demais decisões de autorização serão registradas com Lucas em RFC/ADR.

### Infraestrutura

Os módulos Terraform devem expor somente outputs necessários, por exemplo:

- Endpoint do banco.
- Identificador do cluster.
- Endpoint do API Gateway.
- Identificador da Function.
- URLs dos ambientes.

Segredos não devem ser publicados como outputs abertos nem copiados entre repositórios.

## Ambientes

| Branch | Ambiente | Regra |
|---|---|---|
| `develop` | Homologação | Deploy automático após CI e merge por PR |
| `main` | Produção | Deploy automático após CI e merge por PR aprovado |

## Ordem provisória de implantação

1. Infraestrutura do banco gerenciado.
2. Infraestrutura Kubernetes e rede.
3. Function Serverless de autenticação.
4. Aplicação principal.
5. API Gateway e rotas integradas, conforme decisão de infraestrutura.
6. Dashboards, monitores e alertas.

A ordem será revisada após a escolha da nuvem e a definição das dependências Terraform.

## Observabilidade transversal

Todos os componentes devem fornecer:

- Logs estruturados em JSON.
- **`X-Correlation-Id`** enviado pelo cliente e **encaminhado sem modificação pelo API
  Gateway**; a Function e a aplicação validam o valor, geram um UUIDv4 quando ele falta ou
  é inválido, e o devolvem no header da resposta — é dele que o cliente tira o valor a
  reusar na chamada seguinte. É o que liga o fluxo de autenticação ao de aplicação — os dois
  saem do Gateway de forma independente, e o `traceparent` sozinho não os cruza (ver
  `observabilidade/README.md` §3).
- `traceparent` / `tracestate` (W3C) para o trace técnico **dentro** de cada fluxo.
- Métricas de erro, latência e disponibilidade.
- Healthchecks quando aplicável.
- Alertas de falha no processamento de ordens de serviço.

A implementação e a ferramenta serão definidas com Luís.

---

## Decisões do grupo — 2026-09-02

### Teste ponta a ponta realizado

O Luís validou a integração ALB → NodePort → pods → RDS com deploy no EKS.
`/health/live/` e `/health/ready/` responderam 200, `/api/schema/` devolveu OpenAPI.
HPA escalou de 2 → 4 → 6 pods em 36s sob carga e voltou sozinho pra 2.

### Correções no Terraform (Sophia)

1. Security group do ALB sem regra nenhuma, nem ingress nem egress. Declarar sem bloco de egress remove o allow-all padrão, então o ALB não conseguia falar com os nodes.
2. Regra da porta 30080 estava no `oficina-eks-sg` (control plane). Node de managed node group sem launch template usa o cluster SG do EKS. A regra existia, no SG errado.
3. Target group ficava unhealthy com `Target.Timeout` mesmo sem aplicação rodando.

### Correções nos manifests (Sophia)

- Adicionado `imagePullSecrets` em deployment e migration-job (não existia em nenhum).
- `timeoutSeconds: 5` nas probes — default de 1s estourava sob carga.
- Output `eks_cluster_security_group_id` adicionado para o RDS autorizar na 5432.

### Repositório de documentação (Sophia)

Sophia criou 11 ADRs em `tech-challenge-oficina-k8s` (branch `docs/documentacao-infraestrutura`):
- ADR-001 ao ADR-011 (EKS, VPC, ECR, ALB/NodePort, escalabilidade, disponibilidade, config/secrets, migrations, IaC, security groups, NAT).
- `architecture.md` com diagramas da arquitetura.
- Abertos PRs para main, aguardando merge.

### Repositório de autenticação (Lucas)

- PR #5 (Draft) com 30 arquivos: Clean Architecture, CPF validation, JWT RS256, Lambda handler, OpenAPI, testes.
- Ainda em desenvolvimento, sem review formal.

### Repositório principal (Lucas)

- PR #24 mergeado: campo `Cliente.ativo` + migration.
- PR #25 mergeado: autenticação JWT de cliente (`atendimento/authentication.py`).

### Pendências

- Credenciais AWS atualizadas necessárias para deploy no EKS e push no ECR (sessão expirada).
