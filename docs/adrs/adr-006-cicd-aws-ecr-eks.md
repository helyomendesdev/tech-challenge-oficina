# ADR-006: CI/CD AWS — ECR + EKS com OIDC

## Status

Aceito (Fase 3)

## Contexto

O pipeline CD anterior usava Kind local para deploy. Na Fase 3, a aplicação roda em EKS na AWS com banco RDS gerenciado e ECR para imagens. O ambiente é AWS Academy (sessão temporária), então IDs e recursos podem mudar entre sessões.

## Decisão

**Pipeline:**
- `ci.yml` roda em PRs e pushes (build + test + docker build, sem push)
- `cd.yml` dispara só em `main`: docker build → push ECR → deploy EKS

**Autenticação:** OIDC (role IAM) via `aws-actions/configure-aws-credentials@v4`.
Sem segredos estáticos no GitHub. Se AWS Academy bloquear IAM, fallback para
Access Keys (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` como secrets).

**Imagens:** tag = `git sha` (imutável, rastreável). ECR repository: `oficina-api`.

**Deploy:** `kubectl set image` + `rollout status`. Migration via Job antes do deploy.

## Consequências

- Sem cache de imagem (diferente do Kind): `imagePullPolicy: Always` no deployment.
- OIDC provider precisa existir na AWS (Sophia/Hélio criam).
- Secrets necessários no GitHub: `AWS_ROLE_ARN`, `AWS_REGION`, `EKS_CLUSTER_NAME`, `ECR_REPOSITORY`, `AWS_ACCOUNT_ID`.
- Reprovável: destruir ECR + cluster e recriar do zero para testar resiliência.

## Referências

- [aws-actions/configure-aws-credentials](https://github.com/aws-actions/configure-aws-credentials)
- [aws-actions/amazon-ecr-login](https://github.com/aws-actions/amazon-ecr-login)
- Conversation grupo WhatsApp 30/08/2026
