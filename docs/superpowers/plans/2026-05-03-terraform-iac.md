# Terraform IaC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **DO NOT commit** — the user commits manually.

**Goal:** Criar a pasta `infra/` com Terraform que provisiona um cluster kind local e aplica todos os recursos Kubernetes da aplicação, tornando o ambiente completamente reproduzível com `terraform apply`.

**Architecture:** Provider `kreuzwerker/kind` cria o cluster kind; provider `hashicorp/kubernetes` aplica os recursos K8s usando as credenciais exportadas diretamente pelo cluster. Os recursos HCL são a tradução direta dos YAMLs existentes em `k8s/` — nenhum comportamento novo é adicionado.

**Tech Stack:** Terraform >= 1.6, provider `kreuzwerker/kind ~> 0.7`, provider `hashicorp/kubernetes ~> 2.35`, kind, Docker

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `infra/main.tf` | Criar | Providers + `kind_cluster` |
| `infra/variables.tf` | Criar | Todas as variáveis de entrada |
| `infra/outputs.tf` | Criar | Outputs do cluster e da aplicação |
| `infra/k8s.tf` | Criar | Todos os 8 recursos Kubernetes |
| `infra/terraform.tfvars` | Criar | Valores padrão não-sensíveis |
| `infra/README.md` | Criar | Documentação obrigatória pelo PDF |
| `.gitignore` | Modificar | Ignorar `*.secret.tfvars` e `.terraform/` |
| `README.md` | Modificar | Adicionar seção "Provisionamento com Terraform" |

---

## Task 1: Providers, cluster kind e variáveis

**Files:**
- Create: `infra/main.tf`
- Create: `infra/variables.tf`
- Create: `infra/outputs.tf`

- [ ] **Step 1: Criar a pasta `infra/`**

```bash
mkdir infra
```

- [ ] **Step 2: Criar `infra/variables.tf`**

```hcl
variable "cluster_name" {
  type    = string
  default = "oficina"
}

variable "namespace" {
  type    = string
  default = "oficina"
}

variable "app_image" {
  type    = string
  default = "oficina-app:latest"
}

variable "postgres_db" {
  type    = string
  default = "oficina"
}

variable "postgres_user" {
  type    = string
  default = "oficina_user"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "django_secret_key" {
  type      = string
  sensitive = true
}

variable "django_debug" {
  type    = string
  default = "False"
}

variable "django_allowed_hosts" {
  type    = string
  default = "*"
}
```

- [ ] **Step 3: Criar `infra/main.tf`**

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

resource "kind_cluster" "oficina" {
  name = var.cluster_name
}
```

- [ ] **Step 4: Criar `infra/outputs.tf`**

```hcl
output "cluster_name" {
  value       = kind_cluster.oficina.name
  description = "Nome do cluster kind criado"
}

output "cluster_endpoint" {
  value       = kind_cluster.oficina.endpoint
  description = "Endpoint da API do cluster Kubernetes"
}

output "app_port" {
  value       = 8000
  description = "Porta da aplicação — acesse via: kubectl port-forward -n oficina svc/oficina-app 8000:8000"
}
```

- [ ] **Step 5: Inicializar e validar**

```bash
cd infra
terraform init
terraform validate
```

Esperado:
```
Initializing provider plugins...
- Installing kreuzwerker/kind v0.7.x
- Installing hashicorp/kubernetes v2.35.x
Success! The configuration is valid.
```

---

## Task 2: Recursos Kubernetes (`k8s.tf`)

**Files:**
- Create: `infra/k8s.tf`

- [ ] **Step 1: Criar `infra/k8s.tf` com namespace e secret**

```hcl
# ── Namespace ────────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "oficina" {
  metadata {
    name = var.namespace
  }

  depends_on = [kind_cluster.oficina]
}

# ── Secret ───────────────────────────────────────────────────────────────────

resource "kubernetes_secret" "oficina" {
  metadata {
    name      = "oficina-secret"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  data = {
    DJANGO_SECRET_KEY = var.django_secret_key
    POSTGRES_DB       = var.postgres_db
    POSTGRES_USER     = var.postgres_user
    POSTGRES_PASSWORD = var.postgres_password
  }
}

# ── ConfigMap ─────────────────────────────────────────────────────────────────

resource "kubernetes_config_map" "oficina" {
  metadata {
    name      = "oficina-config"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  data = {
    DJANGO_DEBUG           = var.django_debug
    DJANGO_ALLOWED_HOSTS   = var.django_allowed_hosts
    DJANGO_SETTINGS_MODULE = "app.settings"
    DB_HOST                = "oficina-db"
    DB_PORT                = "5432"
    DJANGO_LOG_FILE        = "/tmp/oficina_atividades.log"
    STATIC_ROOT            = "/app/staticfiles"
  }
}

# ── PostgreSQL StatefulSet ────────────────────────────────────────────────────

resource "kubernetes_stateful_set" "postgres" {
  metadata {
    name      = "postgres"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    service_name = "postgres"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgres"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgres"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:15"

          port {
            container_port = 5432
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.oficina.metadata[0].name
            }
          }

          volume_mount {
            name       = "postgres-data"
            mount_path = "/var/lib/postgresql/data"
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            exec {
              command = ["pg_isready", "-U", "$(POSTGRES_USER)", "-d", "$(POSTGRES_DB)"]
            }
            initial_delay_seconds = 15
            period_seconds        = 10
          }
        }
      }
    }

    volume_claim_template {
      metadata {
        name = "postgres-data"
      }

      spec {
        access_modes = ["ReadWriteOnce"]

        resources {
          requests = {
            storage = "1Gi"
          }
        }
      }
    }
  }
}

# ── PostgreSQL Service (headless) ─────────────────────────────────────────────

resource "kubernetes_service" "postgres" {
  metadata {
    name      = "oficina-db"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    selector = {
      app = "postgres"
    }

    port {
      port        = 5432
      target_port = 5432
    }

    cluster_ip = "None"
  }
}

# ── App Deployment ────────────────────────────────────────────────────────────

resource "kubernetes_deployment" "oficina_app" {
  metadata {
    name      = "oficina-app"
    namespace = kubernetes_namespace.oficina.metadata[0].name
    labels = {
      app = "oficina-app"
    }
  }

  spec {
    replicas = 2

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        app = "oficina-app"
      }
    }

    template {
      metadata {
        labels = {
          app = "oficina-app"
        }
      }

      spec {
        container {
          name              = "app"
          image             = var.app_image
          image_pull_policy = "IfNotPresent"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.oficina.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.oficina.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          liveness_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }

          readiness_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          startup_probe {
            tcp_socket {
              port = "8000"
            }
            initial_delay_seconds = 3
            period_seconds        = 10
            failure_threshold     = 20
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_stateful_set.postgres,
    kubernetes_service.postgres,
  ]
}

# ── App Service ───────────────────────────────────────────────────────────────

resource "kubernetes_service" "oficina_app" {
  metadata {
    name      = "oficina-app"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    selector = {
      app = "oficina-app"
    }

    port {
      port        = 8000
      target_port = 8000
    }

    type = "ClusterIP"
  }
}

# ── HPA ───────────────────────────────────────────────────────────────────────

resource "kubernetes_horizontal_pod_autoscaler_v2" "oficina_app" {
  metadata {
    name      = "oficina-app-hpa"
    namespace = kubernetes_namespace.oficina.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.oficina_app.metadata[0].name
    }

    min_replicas = 2
    max_replicas = 10

    metric {
      type = "Resource"

      resource {
        name = "cpu"

        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }
}
```

- [ ] **Step 2: Validar a configuração completa**

```bash
cd infra
terraform validate
```

Esperado: `Success! The configuration is valid.`

- [ ] **Step 3: Verificar o plano sem aplicar (requer variáveis sensíveis)**

```bash
cd infra
terraform plan \
  -var="django_secret_key=test-key-for-plan" \
  -var="postgres_password=test-pass-for-plan"
```

Esperado: plano mostrando **10 resources to add** (kind_cluster + 9 K8s resources), nenhum erro.

---

## Task 3: `terraform.tfvars` e `.gitignore`

**Files:**
- Create: `infra/terraform.tfvars`
- Modify: `.gitignore`

- [ ] **Step 1: Criar `infra/terraform.tfvars`** com valores não-sensíveis

```hcl
cluster_name         = "oficina"
namespace            = "oficina"
app_image            = "oficina-app:latest"
postgres_db          = "oficina"
postgres_user        = "oficina_user"
django_debug         = "False"
django_allowed_hosts = "*"

# Valores sensíveis — passe via variável de ambiente:
#   export TF_VAR_django_secret_key="sua-secret-key"
#   export TF_VAR_postgres_password="sua-senha"
# Ou crie infra/secret.tfvars (já no .gitignore) e use:
#   terraform apply -var-file="secret.tfvars"
```

- [ ] **Step 2: Adicionar entradas Terraform ao `.gitignore` raiz**

Abrir `.gitignore` e adicionar ao final:

```gitignore
# Terraform
infra/.terraform/
infra/.terraform.lock.hcl
infra/terraform.tfstate
infra/terraform.tfstate.backup
infra/*.secret.tfvars
infra/secret.tfvars
```

- [ ] **Step 3: Verificar que `terraform.tfvars` NÃO está no gitignore**

```bash
git check-ignore -v infra/terraform.tfvars
```

Esperado: nenhuma saída (arquivo não está ignorado — será commitado).

---

## Task 4: `infra/README.md`

**Files:**
- Create: `infra/README.md`

- [ ] **Step 1: Criar `infra/README.md`**

```markdown
# Infraestrutura como Código — Terraform

Provisiona um cluster Kubernetes local com [kind](https://kind.sigs.k8s.io/) e
aplica todos os recursos da aplicação Oficina Mecânica.

## Recursos criados

| Recurso Terraform | Tipo K8s | Descrição |
|---|---|---|
| `kind_cluster.oficina` | — | Cluster kind local |
| `kubernetes_namespace.oficina` | Namespace | Namespace `oficina` |
| `kubernetes_secret.oficina` | Secret | Credenciais Django e PostgreSQL |
| `kubernetes_config_map.oficina` | ConfigMap | Configurações não-sensíveis |
| `kubernetes_stateful_set.postgres` | StatefulSet | PostgreSQL 15 com PVC de 1Gi |
| `kubernetes_service.postgres` | Service (headless) | DNS interno para o banco |
| `kubernetes_deployment.oficina_app` | Deployment | App Django/Gunicorn (2 réplicas) |
| `kubernetes_service.oficina_app` | Service (ClusterIP) | Expõe a API internamente |
| `kubernetes_horizontal_pod_autoscaler_v2.oficina_app` | HPA | CPU 70%, min 2 / max 10 réplicas |

## Pré-requisitos

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) >= 0.20
- [Docker](https://docs.docker.com/get-docker/) em execução
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (para acesso ao cluster após o apply)

## Como aplicar

```bash
# 1. Entrar na pasta
cd infra/

# 2. Inicializar providers
terraform init

# 3. Construir e carregar a imagem Docker no kind
cd ..
docker build -t oficina-app:latest .
cd infra/

# 4. Exportar variáveis sensíveis
export TF_VAR_django_secret_key="sua-secret-key-aqui"
export TF_VAR_postgres_password="sua-senha-aqui"

# 5. Revisar o plano
terraform plan

# 6. Aplicar (cria cluster + todos os recursos K8s)
terraform apply

# 7. Carregar a imagem no cluster kind
kind load docker-image oficina-app:latest --name oficina

# 8. Rodar as migrations
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate

# 9. Acessar a API em http://localhost:8000
kubectl port-forward -n oficina svc/oficina-app 8000:8000
```

## Como destruir

```bash
cd infra/
terraform destroy
```

Isso remove o cluster kind e todos os recursos K8s. Os dados do PostgreSQL são perdidos.

## Variáveis

| Variável | Sensível | Padrão | Descrição |
|---|---|---|---|
| `cluster_name` | não | `"oficina"` | Nome do cluster kind |
| `namespace` | não | `"oficina"` | Namespace Kubernetes |
| `app_image` | não | `"oficina-app:latest"` | Imagem Docker da aplicação |
| `postgres_db` | não | `"oficina"` | Nome do banco de dados |
| `postgres_user` | não | `"oficina_user"` | Usuário do PostgreSQL |
| `postgres_password` | **sim** | — | Senha do PostgreSQL (obrigatório) |
| `django_secret_key` | **sim** | — | SECRET_KEY do Django (obrigatório) |
| `django_debug` | não | `"False"` | Modo debug |
| `django_allowed_hosts` | não | `"*"` | Hosts permitidos |

## Alternativa com arquivo de variáveis sensíveis

```bash
# Criar arquivo local (já no .gitignore)
cat > secret.tfvars <<EOF
django_secret_key = "sua-secret-key-aqui"
postgres_password = "sua-senha-aqui"
EOF

terraform apply -var-file="secret.tfvars"
```
```

---

## Task 5: Atualizar `README.md` raiz

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Localizar a seção "Com Kubernetes (kind)"** no README raiz (por volta da linha 223) e adicionar uma nova seção logo abaixo dela:

```markdown
### Com Terraform (IaC)

O diretório `infra/` contém scripts Terraform que provisionam o cluster kind e
aplicam todos os recursos Kubernetes automaticamente.

```bash
cd infra/
terraform init
export TF_VAR_django_secret_key="sua-secret-key"
export TF_VAR_postgres_password="sua-senha"
terraform apply
kind load docker-image oficina-app:latest --name oficina
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate
kubectl port-forward -n oficina svc/oficina-app 8000:8000
```

> Consulte [`infra/README.md`](infra/README.md) para instruções completas,
> lista de recursos criados e como destruir o ambiente.
```

- [ ] **Step 2: Verificar que a seção aparece no sumário**

O sumário do README já contém um link "Com Kubernetes (kind)". Adicionar logo abaixo:

```markdown
  - [Com Terraform (IaC)](#com-terraform-iac)
```

---

## Task 6: Smoke test completo

> Pré-requisito: `terraform`, `kind` e `docker` instalados localmente.

- [ ] **Step 1: Construir a imagem Docker**

```bash
cd C:\Projetos\tech-challenge-oficina
docker build -t oficina-app:latest .
```

Esperado: `Successfully built <hash>` e `Successfully tagged oficina-app:latest`

- [ ] **Step 2: Aplicar o Terraform**

```bash
cd infra/
terraform init
terraform apply \
  -var="django_secret_key=django-insecure-test-key-for-local" \
  -var="postgres_password=localpass123" \
  -auto-approve
```

Esperado: `Apply complete! Resources: 10 added, 0 changed, 0 destroyed.`

- [ ] **Step 3: Carregar imagem e rodar migrations**

```bash
kind load docker-image oficina-app:latest --name oficina
kubectl wait --for=condition=ready pod -l app=postgres -n oficina --timeout=120s
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate
```

Esperado: migrations aplicadas sem erros.

- [ ] **Step 4: Confirmar que a API responde**

```bash
kubectl port-forward -n oficina svc/oficina-app 8000:8000 &
curl -s http://localhost:8000/api/schema/swagger-ui/ | grep -c "swagger"
```

Esperado: retorna `1` (página do Swagger encontrada).

- [ ] **Step 5: Destruir o ambiente de teste**

```bash
terraform destroy -auto-approve
```

Esperado: `Destroy complete! Resources: 10 destroyed.`
