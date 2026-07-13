# Provisionamento local com Terraform

Este diretório cria um cluster Kind e os mesmos recursos funcionais do caminho
`k8s/`: namespace, ConfigMap, Secret, PostgreSQL, migrations, aplicação,
Services e HPA. O script `deploy.ps1` coordena os passos imperativos que não
cabem bem no grafo Terraform: build/load da imagem, instalação do Metrics
Server e smoke tests.

## Pré-requisitos

- Terraform >= 1.6
- Docker em execução
- Kind
- kubectl
- Python 3.11+

## Recursos gerenciados pelo Terraform

| Recurso | Finalidade |
|---|---|
| `kind_cluster.oficina` | Cluster Kubernetes local |
| `kubernetes_namespace.oficina` | Namespace `oficina` |
| `kubernetes_secret.oficina` | Credenciais recebidas por variáveis sensíveis |
| `kubernetes_config_map.oficina` | Configuração HTTP local, incluindo `SECURE_SSL_REDIRECT=False` |
| `kubernetes_stateful_set.postgres` | PostgreSQL com PVC, probes e recursos |
| `kubernetes_service.postgres` | Service headless do banco |
| `kubernetes_job_v1.migrate` | Migrations antes da aplicação |
| `kubernetes_deployment.oficina_app` | Aplicação com resources e probes HTTP |
| `kubernetes_service.oficina_app` | Service ClusterIP da API |
| `kubernetes_horizontal_pod_autoscaler_v2.oficina_app` | HPA CPU 50%, mínimo 2, máximo 6 |

O Metrics Server é instalado pelo orquestrador usando o manifesto oficial e o
patch Kind existente em `k8s/metrics-server-kind-patch.yaml`.

## Variáveis

| Nome | Sensível | Padrão | Descrição |
|---|---|---|---|
| `cluster_name` | não | `oficina` | Nome do cluster Kind |
| `namespace` | não | `oficina` | Namespace Kubernetes |
| `app_image` | não | `oficina-app:latest` | Imagem local da aplicação |
| `postgres_db` | não | `oficina` | Banco PostgreSQL |
| `postgres_user` | não | `oficina_user` | Usuário PostgreSQL |
| `postgres_password` | sim | nenhum | Senha com no mínimo 16 caracteres |
| `django_secret_key` | sim | nenhum | Chave com no mínimo 32 caracteres |
| `django_debug` | não | `False` | Debug do Django |
| `django_allowed_hosts` | não | `*` | Hosts aceitos no Kind local |

As variáveis sensíveis estão marcadas com `sensitive = true`. Ainda assim,
valores de recursos podem existir no state local; por isso `*.tfstate`, planos
e `terraform.secret.tfvars` permanecem no `.gitignore`.

## Como fornecer valores sensíveis

Recomendado para uma validação local efêmera no PowerShell:

```powershell
$env:TF_VAR_postgres_password = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:TF_VAR_django_secret_key = python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Alternativamente, crie `infra/terraform.secret.tfvars`, que já é ignorado:

```hcl
postgres_password = "valor-local-com-16-ou-mais-caracteres"
django_secret_key = "valor-local-com-32-ou-mais-caracteres"
```

Nesse caso, passe `-var-file=terraform.secret.tfvars` aos comandos Terraform.
O orquestrador usa `TF_VAR_*`; para ele, prefira variáveis de ambiente.

## Sequência de provisionamento

Execute a partir de `infra/`:

```powershell
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan
.\deploy.ps1
```

O script falha se encontrar um cluster com o mesmo nome que não pertença ao
state atual. Ele executa, de forma explícita:

1. `terraform apply -target=kind_cluster.oficina`;
2. `docker build`;
3. `kind load docker-image`;
4. `terraform apply` completo;
5. espera PostgreSQL, migration Job e aplicação;
6. instala e valida Metrics Server;
7. espera o HPA apresentar métrica numérica;
8. executa `scripts/smoke_test.py`.

O `-target` é usado somente para resolver a fronteira inevitável entre criar o
cluster e carregar uma imagem local antes de criar o Deployment. O apply final
concilia todo o grafo.

## Validação

```powershell
kubectl get pods -n oficina
kubectl get services -n oficina
kubectl get deployments -n oficina
kubectl get statefulsets -n oficina
kubectl get hpa -n oficina
kubectl top pods -n oficina
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate --check
python ..\scripts\smoke_test.py
```

O smoke test valida liveness, readiness, OpenAPI, obtenção de JWT e uma chamada
autenticada, removendo o usuário efêmero ao final.

## Destruição

```powershell
terraform destroy
kind get clusters
kubectl config get-contexts
```

O destroy remove o cluster Kind e, com ele, Metrics Server, PVC e todos os
dados locais. Essa perda é esperada e restrita ao ambiente acadêmico local.

## Limitações conhecidas

- Docker build e Kind image load são imperativos e ficam no orquestrador.
- Metrics Server usa o manifesto oficial e `--kubelet-insecure-tls`, adequado
  somente ao Kind local.
- Metrics Server não aparece como recurso individual no state, mas é removido
  junto com o cluster gerenciado.
- Não há registry, cloud, Ingress, Helm ou infraestrutura externa.
