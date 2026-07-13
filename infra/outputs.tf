output "cluster_name" {
  value       = kind_cluster.oficina.name
  description = "Nome do cluster kind criado"
}

output "cluster_endpoint" {
  value       = kind_cluster.oficina.endpoint
  description = "Endpoint da API do cluster Kubernetes"
}

output "namespace" {
  value       = var.namespace
  description = "Namespace Kubernetes da aplicacao"
}

output "app_port" {
  value       = 8000
  description = "Porta da aplicação — acesse via: kubectl port-forward -n oficina svc/oficina-app 8000:8000"
}
