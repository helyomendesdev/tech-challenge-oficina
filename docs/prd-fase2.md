# PRD — Fase 2: Infraestrutura, APIs & Observabilidade

**Product Requirements Document**
**Data:** 2026-06-09
**Projeto:** Tech Challenge — Oficina Mecanica (FIAP)
**Versao:** 1.0

---

## 1. Objetivo

Evoluir o sistema de gestao de ordens de servico (MVP Fase 1) para uma arquitetura
escalavel, resiliente e automatizada, aplicando Clean Architecture, containerizacao,
orquestracao Kubernetes, Infrastructure as Code e pipeline CI/CD.

---

## 2. Escopo

### 2.1 Dentro do escopo (Fase 2)

| Area | Item | Responsavel |
|------|------|-------------|
| Arquitetura | Refatoracao para Clean/Hexagonal Architecture | Lucas ✅ |
| APIs | Ordenacao da fila de OS por status + antiguidade | Sophia |
| APIs | Exclusao logica de OS finalizadas/entregues da listagem | Sophia |
| APIs | Endpoint de aprovacao/rejeicao de orcamento via notificacao externa | Sophia |
| APIs | Atualizacao de status via ferramenta externa (ex: email) | Sophia |
| Container | Dockerfile e docker-compose revisados | Luis |
| K8s | Deployments, Services, ConfigMaps, Secrets, HPA | Helio |
| IaC | Terraform para provisionamento (cluster + banco) | Luis |
| CI/CD | Pipeline GitHub Actions (build, testes, Docker, deploy) | Helio |
| Docs | README.md atualizado com arquitetura e instrucoes | Grupo |
| Docs | Collection Postman atualizada | Grupo |
| Video | Video demonstrativo ate 15 min (YouTube/Vimeo) | Grupo |
| Entrega | PDF no portal FIAP | Grupo |

### 2.2 Fora do escopo (Fase 3 ou posterior)

- OpenTelemetry / observabilidade (Jaeger, Prometheus, Loki)
- Kubernetes Parte II (Helm, EKS avancado, logging EFK)
- Autenticacao com provedores externos (OAuth2 social)
- Frontend / aplicativo mobile
- Multi-tenancy completo
- Ambiente de staging/producao reais (apenas local/minikube/kind)

---

## 3. O que ja existe (legado aproveitavel)

### 3.1 Codigo

| Componente | Situacao |
|------------|----------|
| Models Django (OrdemServico, Cliente, Veiculo, Peca, etc.) | Existentes. Models ainda tem logica de negocio (precisa migrar para use cases) |
| Views antigas (CRUDs) | Funcionando em `/api/v1/` via ViewSets. Serao mantidas para compatibilidade |
| Autenticacao JWT (SimpleJWT) | Implementada e funcional |
| Validacao CPF/CNPJ/Placa | Implementada via validate_docbr |
| Dockerfile | Existente (python:3.11-slim + gunicorn) |
| docker-compose.yml | Existente (postgres + web) |
| Testes (194) | 194 testes passando, 78% cobertura |
| Postman Collection | Existente (`postman_collection.json`) |
| Documentacao DDD | Event Storming, C4 Model, ADRs, RFCs, HLD, LLD |

### 3.2 Clean Architecture (entregue por Lucas)

```
atendimento/
  domain/              -- Regras de negocio puras (sem framework)
  application/
    ports/             -- Contratos (Protocol)
    use_cases/         -- 7 casos de uso com DI
    dtos.py            -- DTOs de entrada/saida
  infrastructure/
    repositories/      -- 5 repositorios Django ORM
    factories.py       -- Composicao raiz (DI)
    notifications/     -- Adapter de notificacao
    transactions/      -- Gerenciador de transacoes
  interfaces/
    api/               -- Views, serializers, urls (novos endpoints)
```

---

## 4. O que precisa ser construido

### 4.1 Kubernetes (`/k8s/`) — Helio

| Artefato | Descricao | Criterio de Aceite |
|----------|-----------|-------------------|
| `k8s/namespace.yaml` | Namespace dedicado `oficina` | `kubectl apply -f` cria o namespace |
| `k8s/configmap.yaml` | Variaveis nao sensiveis (DEBUG=False, DJANGO_SETTINGS_MODULE) | Pod enxerga via env var |
| `k8s/secret.yaml` | Credenciais (DB password, SECRET_KEY, tokens) | Criado via `kubectl apply -f` ou `kubectl create secret` |
| `k8s/deployment.yaml` | Deployment da app (2+ replicas, probes, resource limits) | Rolling update sem downtime |
| `k8s/service.yaml` | Service ClusterIP para comunicacao interna | `kubectl get svc` lista o servico |
| `k8s/hpa.yaml` | HPA escalando de 2 a 10 pods por CPU > 70% | `kubectl get hpa` mostra metricas |
| `k8s/postgres-statefulset.yaml` | StatefulSet do PostgreSQL com PersistentVolume | Dados persistem apos restart do pod |
| `k8s/postgres-service.yaml` | Service para o banco | App conecta via nome do servico |

### 4.2 Terraform (`/infra/`) — Luis

| Artefato | Descricao |
|----------|-----------|
| `infra/main.tf` | Provider + cluster K8s (local/kind ou cloud) |
| `infra/variables.tf` | Variaveis de configuracao |
| `infra/outputs.tf` | Outputs (endpoint do cluster, kubeconfig) |
| `infra/database.tf` | Recurso de banco de dados |

### 4.3 CI/CD (`.github/workflows/`) — Helio

| Artefato | Descricao | Criterio de Aceite |
|----------|-----------|-------------------|
| `.github/workflows/ci.yml` | Trigger: push/PR na main. Etapas: lint, test, build | Workflow passa verde no GitHub |
| `.github/workflows/cd.yml` | Trigger: merge na main. Etapas: build Docker, push registry, deploy K8s | Deploy executa apos merge |

### 4.4 APIs — Sophia

| Endpoint | Descricao | Criterio de Aceite |
|----------|-----------|-------------------|
| `GET /api/v1/ordens-servico/fila/` | Ordenacao: Em Execucao > Aguardando Aprovacao > Diagnostico > Recebida. Mais antigas primeiro. Excluir finalizadas/entregues. | Resposta ordenada e filtrada conforme especificacao |
| `POST /api/v1/orcamentos/notificacoes/` | Receber aprovacao/rejeicao externa do orcamento | OS atualiza status conforme resposta |
| `POST /api/v1/ordens-servico/status-notificacoes/` | Atualizar status via ferramenta externa (email) | Status alterado apos notificacao |

---

## 5. Arquitetura Alvo

```
[Usuario] --> [GitHub Actions] --> [Docker Registry]
                                       |
                                       v
                               [Cluster K8s]
                              /              \
                    [Deployment]         [PostgreSQL]
                    (2-10 pods)         (StatefulSet)
                          |
                    [Service:8000]
                          |
                    [HPA: CPU>70%]
```

### Fluxo de Deploy

```
1. Push/PR na main
2. GitHub Actions:
   a. Lint + Testes (194 testes)
   b. Build imagem Docker
   c. Push para registry (Docker Hub / GHCR)
   d. Aplicar manifests K8s (`kubectl apply -f k8s/`)
3. HPA gerencia escala automatica
```

---

## 6. Nao requisitos (deliberadamente excluido)

- Nao havera frontend (apenas API REST)
- Nao havera autenticacao OAuth externa
- Nao havera ambiente de producao real (apenas local/minikube/kind)
- Nao havera monitoramento OpenTelemetry (postergado)
- Nao havera migracao dos models Django (logica de negocio nos models sera tratada na Fase 3)

---

## 7. Criterios de aceite gerais

1. **Testes:** 194+ testes existentes continuam passando apos todas as alteracoes
2. **Docker:** `docker-compose up` sobe app + banco sem erros
3. **K8s:** `kubectl apply -f k8s/` cria todos os recursos. `kubectl get pods` mostra pods Running
4. **Terraform:** `terraform apply` provisiona o ambiente sem erros
5. **CI/CD:** Pipeline executa completa no GitHub Actions (build, testes, deploy)
6. **APIs:** Colecao Postman atualizada funciona contra os endpoints
7. **README:** Instrucoes claras para execucao local, K8s e Terraform
8. **Video:** Demonstracao de ate 15 min mostrando deploy, CI/CD e consumo das APIs

---

## 8. Riscos

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Docker Compose quebra com novas dependecias | Baixa | Alto | Testar apos cada alteracao |
| Manifestos K8s desatualizados vs docker-compose | Media | Medio | Sincronizar configs (env vars, volumes) |
| GitHub Actions sem acesso ao cluster | Alta | Alto | Usar kind ou minikube no workflow |
| Prazo curto para video + PDF | Alta | Alto | Gravar video incrementalmente |

---

## 9. Glossario

| Termo | Definicao |
|-------|-----------|
| OS | Ordem de Servico |
| HPA | Horizontal Pod Autoscaler (escala automatica K8s) |
| IaC | Infrastructure as Code (Terraform) |
| CI/CD | Integracao Continua / Entrega Continua |
| GHCR | GitHub Container Registry |
| Kind | Kubernetes in Docker (cluster local para dev/teste) |
