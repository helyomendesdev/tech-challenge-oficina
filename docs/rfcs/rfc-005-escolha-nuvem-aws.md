# RFC-005 — Escolha da Nuvem: AWS

| Informação | Valor |
|---|---|
| **RFC** | 005 |
| **Título** | Escolha da Nuvem para a Fase 3 |
| **Status** | Aprovado |
| **Autores** | Hélio Mendes (RM374170) |
| **Data** | 2026-09-08 |
| **Versão** | 1.0 |

---

## 1. Objetivo

Formalizar a escolha da nuvem para a Fase 3 do Tech Challenge, justificando a decisão com base nos requisitos do projeto, custos e disponibilidade de serviços.

## 2. Motivação

A Fase 3 exige:
- API Gateway para controle e roteamento
- Function Serverless para autenticação
- Banco de Dados Gerenciado (PostgreSQL)
- Cluster Kubernetes com escalabilidade
- Terraform para provisionamento

A AWS Academy oferece créditos gratuitos para estudantes, permitindo o uso real dos serviços sem custo financeiro durante o desenvolvimento.

## 3. Serviços AWS Escolhidos

| Requisito | Serviço AWS | Justificativa |
|---|---|---|
| API Gateway | API Gateway REST | Regional, suporte a VPC Link, integração com Lambda |
| Function Serverless | Lambda Python 3.11 | Execução sob demanda, escalabilidade automática |
| Banco Gerenciado | RDS PostgreSQL | Multi-AZ, backup automático, Performance Insights |
| Kubernetes | EKS | Gerenciado, integração com ALB, HPA |
| IaC | Terraform + AWS Provider | Declarativo, versionado, multi-cloud |
| Segurança | Secrets Manager | Rotação automática, criptografia KMS |
| Monitoramento | CloudWatch + New Relic | Logs, métricas, alertas, APM |
| Container Registry | ECR | Integração nativa com ECR, scan de vulnerabilidades |

## 4. Arquitetura de Rede

```
VPC: 10.0.0.0/16
├── Subnets Públicas (10.0.1.0/24, 10.0.2.0/24)
│   ├── Internet Gateway
│   └── NAT Gateway
└── Subnets Privadas (10.0.10.0/24, 10.0.11.0/24)
    ├── EKS Node Group
    ├── Lambda (oficina-auth-cpf)
    └── RDS PostgreSQL
```

## 5. Justificativa

### 5.1 Por que AWS?

1. **AWS Academy**: créditos gratuitos para estudantes, sem custo durante o desenvolvimento
2. **Integração nativa**: todos os serviços se integram sem necessidade de adapters
3. **Documentação**: extensa e atualizada, com exemplos práticos
4. **Mercado**: líder de mercado, skills transferíveis para o mercado de trabalho

### 5.2 Por que não Azure/GCP?

- Azure: sem programa educacional equivalente na FIAP
- GCP: menor participação de mercado, menos vagas em empresas brasileiras

## 6. Custos Estimados (fora AWS Academy)

| Serviço | Custo Mensal (estimativa) |
|---|---|
| EKS Cluster | ~$0.10/hora ($73/mês) |
| RDS db.t3.micro | ~$15/mês |
| Lambda | ~$0 (1M requests gratuitas) |
| API Gateway | ~$3.50/mês |
| NAT Gateway | ~$32/mês |
| **Total** | **~$123/mês** |

> Com AWS Academy, o custo é $0 durante o período de lab.

## 7. Impacto

| Área | Mudança |
|---|---|
| Repo `k8s` | Terraform para EKS, VPC, ALB, Node Group |
| Repo `database` | Terraform para RDS PostgreSQL |
| Repo `auth` | Terraform para Lambda, API Gateway, VPC Link |
| Repo principal | ConfigMap com endpoint RDS, ECR image |

## 8. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| Azure | Sem programa educacional na FIAP |
| GCP | Menor mercado no Brasil |
| On-premise | Sem escalabilidade, sem serverless |

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-09-08 | Hélio Mendes | Versão inicial, formalizando a escolha da nuvem |
