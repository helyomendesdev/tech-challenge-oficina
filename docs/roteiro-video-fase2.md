# Roteiro do vídeo — Fase 2

Duração planejada: **14 minutos e 30 segundos**. Limite: 15 minutos. Prepare o
ambiente antes da gravação, mas mostre evidências reais e não simule saídas.

## Preparação antes de gravar

```powershell
git switch fase-2-testes
git status
docker version
kubectl version --client
kind version
terraform version

.\scripts\kind-deploy.ps1
python .\scripts\smoke_test.py
```

Deixe o port-forward ativo:

```powershell
kubectl port-forward -n oficina service/oficina-app 8000:8000
```

Importe `postman_collection.json` e `postman_environment.json`. Não grave
tokens ou credenciais reais.

## Cronograma

| Tempo | Conteúdo | Evidência |
|---|---|---|
| 00:00–00:40 | Problema e objetivos das Fases 1 e 2 | README e domínio |
| 00:40–01:40 | Arquitetura, código e abordagem híbrida | Camadas novas e legado |
| 01:40–02:20 | Docker e PostgreSQL | Dockerfile, Compose e healthchecks |
| 02:20–03:00 | CI/CD | Workflows; sem alegar verde sem abrir a execução |
| 03:00–04:20 | Kubernetes e readiness | Pods, Services, Deployment e StatefulSet |
| 04:20–08:00 | APIs | JWT, abertura, status, orçamento, notificação e fila |
| 08:00–08:40 | Métricas de serviço | Por OS e média por tipo |
| 08:40–11:40 | Metrics Server e HPA | Antes, carga, scale-up e scale-down |
| 11:40–13:30 | Terraform | Plan/apply/destroy e limitações |
| 13:30–14:30 | Segurança, números e conclusão | Checklist e pendências |

## Comandos durante a gravação

### Estado e arquitetura

```powershell
git branch --show-current
git rev-parse --short HEAD
git status
Get-ChildItem atendimento\domain,atendimento\application,atendimento\infrastructure,atendimento\interfaces
```

Explique que a arquitetura é híbrida e incremental: fluxos novos usam use
cases e ports; models, signals, serializers e ViewSets legados preservam
contratos existentes.

### Docker, CI/CD e checks

```powershell
docker compose config
python manage.py check --settings=app.settings_test
python manage.py makemigrations --check --dry-run --settings=app.settings_test
python manage.py spectacular --validate --file schema.yml --settings=app.settings_test
```

Mostre `.github/workflows/ci.yml` e `cd.yml`. Se a execução remota não estiver
aberta e verde, declare que o status está pendente.

### Kubernetes, banco e aplicação Ready

```powershell
kubectl get nodes
kubectl get pods -n oficina
kubectl get services -n oficina
kubectl get deployments -n oficina
kubectl get statefulsets -n oficina
kubectl exec -n oficina deployment/oficina-app -- python manage.py migrate --check
kubectl get deployment oficina-app -n oficina -o jsonpath='{.status.readyReplicas}/{.status.replicas}'
```

### APIs

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live/
Invoke-RestMethod http://127.0.0.1:8000/health/ready/
Invoke-WebRequest http://127.0.0.1:8000/api/schema/ | Select-Object StatusCode
python .\scripts\smoke_test.py
```

No Postman, execute:

1. obtenção do JWT;
2. criação dos serviços e peças necessários;
3. `POST /api/v1/ordens-servico/abrir/`;
4. `GET /api/v1/ordens-servico/{id}/status/`;
5. aprovação em `POST /api/v1/simulacao/orcamento/`;
6. em outra OS preparada, recusa no mesmo endpoint;
7. `POST /api/v1/ordens-servico/status-notificacoes/`;
8. `GET /api/v1/ordens-servico/fila/`;
9. `GET /api/v1/ordens-servico/{id}/metricas/`;
10. `GET /api/v1/ordens-servico/metricas/tempo-medio/`.

Use IDs retornados na própria gravação; não fixe IDs históricos.

### Metrics Server e HPA

```powershell
kubectl get deployment metrics-server -n kube-system
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top pods -n oficina
kubectl get hpa oficina-app-hpa -n oficina

$env:HPA_LOAD_SECONDS='90'
$env:HPA_SCALE_DOWN_TIMEOUT='180'
python .\scripts\hpa_load_test.py
```

Só declare conformidade completa se a saída terminar com `HPA_TEST=PASS`,
`maximum > initial` e `final = minReplicas`.

### Contingência para scale-down demorado

Não corte nem afirme que reduziu. Mostre o estado real:

```powershell
kubectl get hpa oficina-app-hpa -n oficina
kubectl describe hpa oficina-app-hpa -n oficina
kubectl get deployment oficina-app -n oficina
kubectl top pods -n oficina
```

Diga: “O scale-up foi observado, mas o scale-down ainda está dentro da janela
de estabilização/reconciliação e não concluiu no tempo do vídeo”. Registre a
execução completa depois e só anexe como evidência se houver `HPA_TEST=PASS`.

### Terraform

```powershell
Push-Location infra
$env:TF_VAR_postgres_password = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:TF_VAR_django_secret_key = python -c "import secrets; print(secrets.token_urlsafe(48))"
terraform fmt -check -recursive
terraform init
terraform validate
terraform plan
Pop-Location
```

Explique que `infra/deploy.ps1` executa cluster → build → load → recursos →
migrations → aplicação → Metrics Server → HPA → smoke. O apply completo pode
exceder o tempo do vídeo; mostre apenas evidência real de execução anterior.

Depois da demonstração:

```powershell
Push-Location infra
terraform destroy
Pop-Location
kind get clusters
```

## Encerramento

Apresente somente: 210 testes, 3 subtests, cobertura 94,52%, 34 caminhos/60
operações OpenAPI e 76 requests Postman. Cite pendências sem inventar URLs:

- `PENDENTE_LINK_REPOSITORIO`
- `PENDENTE_LINK_POSTMAN`
- `PENDENTE_LINK_VIDEO`
- `PENDENTE_ACESSO_SOAT_ARCHITECTURE`
