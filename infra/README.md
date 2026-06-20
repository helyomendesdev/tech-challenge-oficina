# infra/

Provisionamento local com Terraform: cria um cluster kind e aplica todos os recursos Kubernetes da aplicação Oficina.

## Recursos criados

| Recurso Terraform | Tipo K8s | Descrição |
|---|---|---|
| `kind_cluster.oficina` | Cluster (kind) | Cluster Kubernetes local via Docker |
| `kubernetes_namespace.oficina` | Namespace | Namespace isolado `oficina` |
| `kubernetes_secret.oficina` | Secret | Credenciais do banco e Django secret key |
| `kubernetes_config_map.oficina` | ConfigMap | Variáveis de ambiente da aplicação (Django) |
| `kubernetes_stateful_set.postgres` | StatefulSet | Banco de dados PostgreSQL com volume persistente de 1Gi |
| `kubernetes_service.postgres` | Service (Headless) | Serviço headless `oficina-db` para o StatefulSet |
| `kubernetes_deployment.oficina_app` | Deployment | Aplicação Django/Gunicorn (`oficina-app:latest`) |
| `kubernetes_service.oficina_app` | Service (ClusterIP) | Serviço interno da app na porta 8000 |
| `kubernetes_horizontal_pod_autoscaler_v2.oficina_app` | HPA | Escalonamento automático: CPU 70%, mín 2 / máx 10 réplicas |

## Pré-requisitos

- **Terraform** >= 1.6
- **Docker** >= 20.10
- **kind** >= 0.20
- **kubectl** >= 1.27

## Como aplicar

### 1. Inicializar o Terraform

```bash
terraform init
```

### 2. Fornecer as variáveis sensíveis

**Opção A — variáveis de ambiente:**

```bash
export TF_VAR_postgres_password="sua_senha_aqui"
export TF_VAR_django_secret_key="sua_secret_key_aqui"
```

**Opção B — arquivo `terraform.secret.tfvars` (não versionado):**

```hcl
postgres_password = "sua_senha_aqui"
django_secret_key = "sua_secret_key_aqui"
```

Se usar o arquivo, passe `-var-file` nos comandos seguintes:

```bash
terraform plan  -var-file="terraform.secret.tfvars"
terraform apply -var-file="terraform.secret.tfvars"
```

### 3. Planejar

```bash
# Com TF_VAR_*
terraform plan

# Com arquivo de variáveis (Opção B)
terraform plan -var-file="terraform.secret.tfvars"
```

### 4. Aplicar

```bash
# Com TF_VAR_*
terraform apply

# Com arquivo de variáveis (Opção B)
terraform apply -var-file="terraform.secret.tfvars"
```

### 5. Carregar a imagem da aplicação no cluster

O kind não acessa o registry local automaticamente. Construa a imagem e carregue-a:

```bash
docker build -t oficina-app:latest .. && kind load docker-image oficina-app:latest --name oficina
```

### 6. Executar as migrations do Django

```bash
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate
```

### 7. Acessar a API

O serviço da app é ClusterIP (acesso interno). Use port-forward para expor localmente:

```bash
kubectl port-forward -n oficina svc/oficina-app 8000:8000
```

A API ficará disponível em `http://localhost:8000`.

## Variáveis

| Nome | Tipo | Sensível | Default | Descrição |
|---|---|---|---|---|
| `cluster_name` | string | não | `"oficina"` | Nome do cluster kind |
| `namespace` | string | não | `"oficina"` | Namespace Kubernetes da aplicação |
| `app_image` | string | não | `"oficina-app:latest"` | Imagem Docker da aplicação |
| `postgres_db` | string | não | `"oficina"` | Nome do banco de dados |
| `postgres_user` | string | não | `"oficina_user"` | Usuário do banco de dados |
| `postgres_password` | string | sim | — | Senha do banco de dados |
| `django_secret_key` | string | sim | — | Secret key do Django |
| `django_debug` | string | não | `"False"` | Modo debug do Django |
| `django_allowed_hosts` | string | não | `"*"` | Hosts permitidos pelo Django |

## Como destruir

```bash
terraform destroy
```

Isso remove o cluster kind e todos os recursos Kubernetes, incluindo o PVC com os dados do PostgreSQL. Os dados do banco são perdidos permanentemente.
