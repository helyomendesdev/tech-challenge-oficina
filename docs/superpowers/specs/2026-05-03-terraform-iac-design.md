# Design: Infraestrutura como Código com Terraform (kind + Kubernetes)

**Data:** 2026-05-03
**Contexto:** Tech Challenge Fase 2 — FIAP SOAT 15ª turma  
**Responsável:** Luís Fernando Montes  
**Escopo:** IaC obrigatória do PDF (Terraform para cluster K8s + banco de dados)

---

## Problema

O PDF da Fase 2 exige scripts Terraform em `/infra` para provisionamento do cluster Kubernetes e banco de dados, com documentação dos recursos criados. O projeto já possui manifests YAML em `k8s/` e um cluster kind funcional, mas sem IaC — o provisionamento é manual (`kind create cluster` + `kubectl apply`).

---

## Solução

Criar a pasta `infra/` com Terraform que provisiona o cluster kind e aplica todos os recursos Kubernetes via provider `kubernetes`, tornando o ambiente completamente reproduzível com um único `terraform apply`.

---

## Estrutura de arquivos

```
infra/
├── main.tf           # Providers + kind_cluster
├── variables.tf      # Variáveis de entrada (cluster_name, secrets, etc.)
├── outputs.tf        # Outputs úteis (endpoint, kubeconfig_path)
├── k8s.tf            # Todos os recursos Kubernetes (namespace → HPA)
├── terraform.tfvars  # Valores padrão não-sensíveis (no .gitignore para tfvars com segredos)
└── README.md         # Documentação: recursos, pré-requisitos, como aplicar
```

---

## Providers

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    kind = {
      source  = "kreuzwerker/kind"
      version = "~> 0.7"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
  }
}

provider "kind" {}

provider "kubernetes" {
  host                   = kind_cluster.oficina.endpoint
  client_certificate     = kind_cluster.oficina.client_certificate
  client_key             = kind_cluster.oficina.client_key
  cluster_ca_certificate = kind_cluster.oficina.cluster_ca_certificate
}
```

O provider `kubernetes` usa as credenciais exportadas diretamente pelo `kind_cluster` — sem arquivo kubeconfig intermediário.

---

## Recursos criados (ordem de dependência)

```
kind_cluster.oficina
  └── kubernetes_namespace.oficina
        ├── kubernetes_secret.oficina
        ├── kubernetes_config_map.oficina
        ├── kubernetes_stateful_set.postgres
        ├── kubernetes_service.postgres
        ├── kubernetes_deployment.oficina_app
        ├── kubernetes_service.oficina_app
        └── kubernetes_horizontal_pod_autoscaler.oficina_app
```

| Recurso Terraform | Tipo K8s | Descrição |
|---|---|---|
| `kind_cluster.oficina` | — | Cluster kind local com 1 control-plane |
| `kubernetes_namespace.oficina` | Namespace | Namespace `oficina` |
| `kubernetes_secret.oficina` | Secret | `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` |
| `kubernetes_config_map.oficina` | ConfigMap | `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DB_HOST`, `DJANGO_LOG_FILE` |
| `kubernetes_stateful_set.postgres` | StatefulSet | PostgreSQL 15 com PVC de 1Gi |
| `kubernetes_service.postgres` | Service (ClusterIP) | Expõe porta 5432 internamente |
| `kubernetes_deployment.oficina_app` | Deployment | App Django/Gunicorn, 1 réplica inicial |
| `kubernetes_service.oficina_app` | Service (NodePort 30080) | Expõe a API externamente no host |
| `kubernetes_horizontal_pod_autoscaler.oficina_app` | HPA | CPU 70%, min 1 / max 5 réplicas |

Os recursos são a tradução direta dos YAMLs em `k8s/` para HCL. Nenhum comportamento novo é adicionado.

---

## Variáveis

| Variável | Tipo | Sensível | Padrão | Descrição |
|---|---|---|---|---|
| `cluster_name` | string | não | `"oficina"` | Nome do cluster kind |
| `namespace` | string | não | `"oficina"` | Namespace Kubernetes |
| `app_image` | string | não | `"oficina-app:latest"` | Imagem Docker da aplicação |
| `postgres_db` | string | não | `"oficina_db"` | Nome do banco |
| `postgres_user` | string | não | `"admin"` | Usuário do PostgreSQL |
| `postgres_password` | string | **sim** | — | Senha do PostgreSQL (obrigatório) |
| `django_secret_key` | string | **sim** | — | SECRET_KEY do Django (obrigatório) |
| `django_debug` | string | não | `"False"` | DEBUG mode |
| `django_allowed_hosts` | string | não | `"localhost,127.0.0.1"` | ALLOWED_HOSTS |

Variáveis sensíveis são passadas via `terraform.tfvars` local (`.gitignore`) ou `TF_VAR_*`.

---

## Outputs

| Output | Descrição |
|---|---|
| `cluster_name` | Nome do cluster kind criado |
| `cluster_endpoint` | Endpoint da API do cluster |
| `app_service_port` | NodePort da aplicação (30080) |

---

## Fluxo de uso

```bash
# Pré-requisitos: terraform >= 1.6, kind, docker

cd infra/

# 1. Inicializar providers
terraform init

# 2. Criar tfvars com segredos (não commitar)
cat > terraform.tfvars <<EOF
django_secret_key = "sua-secret-key-aqui"
postgres_password = "sua-senha-aqui"
EOF

# 3. Visualizar o plano
terraform plan

# 4. Aplicar (cria cluster + todos os recursos K8s)
terraform apply

# 5. Carregar a imagem Docker no cluster kind (necessário para imagePullPolicy: Never)
docker build -t oficina-app:latest ..
kind load docker-image oficina-app:latest --name oficina

# 6. Rodar as migrations
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate

# 7. Acessar a API
kubectl port-forward -n oficina svc/oficina-app 8000:30080

# 8. Destruir tudo
terraform destroy
```

---

## Documentação exigida pelo PDF (`infra/README.md`)

O `infra/README.md` deve conter:
- Descrição de cada recurso criado
- Pré-requisitos (versões de terraform, kind, docker)
- Passo a passo para aplicar
- Como passar variáveis sensíveis
- Como destruir o ambiente

O `README.md` raiz ganha uma seção **"Provisionamento com Terraform"** resumida com link para `infra/README.md`.

---

## O que não entra neste escopo

- Terraform remote state (S3/GCS) — desnecessário para ambiente acadêmico local
- Módulos Terraform reutilizáveis — estrutura flat em 4 arquivos é suficiente
- Terraform Cloud / workspaces
- Alteração nos YAMLs existentes em `k8s/` — continuam funcionando independentemente
- Integração do Terraform no CI/CD — pipeline existente usa kubectl direto

---

## Relação com os YAMLs existentes em `k8s/`

Os arquivos em `k8s/` continuam no repositório e funcionam de forma independente (para quem preferir `kubectl apply -f k8s/`). O Terraform em `infra/` é uma segunda forma de provisionar o mesmo ambiente — ambas coexistem.
