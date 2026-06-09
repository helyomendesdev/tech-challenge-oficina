# PRD — Fase 2: Infraestrutura, APIs & Observabilidade

**Product Requirements Document**
**Data:** 2026-06-09
**Projeto:** Tech Challenge — Oficina Mecanica (FIAP) — Fase 2
**Versao:** 2.0 (alinhada ao enunciado oficial)
**Peso na nota:** 60% de todas as disciplinas da fase

---

## 1. Objetivo (conforme enunciado)

Evoluir a aplicacao desenvolvida na Fase 1 para garantir qualidade, resiliencia e
escalabilidade, incorporando praticas modernas de infraestrutura e automacao,
visando:

- Reduzir riscos operacionais por meio de infraestrutura escalavel
- Automatizar o provisionamento e o deploy do ambiente
- Melhorar a qualidade e a organizacao do codigo, mantendo a evolucao sustentavel
- Preparar a aplicacao para suportar grandes volumes de ordens de servico em
  horarios de pico, com escalabilidade dinamica

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

Pipeline obrigatoria deve executar em ordem:

| Passo | Descricao | Criterio de Aceite |
|-------|-----------|-------------------|
| 1. Build da aplicacao | `pip install -r requirements.txt` + `python manage.py check` | Sem erros de compilacao/dependencias |
| 2. Execucao dos testes automatizados | `pytest atendimento/tests/ -v --tb=short` | 194+ testes passando |
| 3. Build da imagem Docker | `docker build -t app .` | Imagem criada sem erros |
| 4. Deploy no cluster Kubernetes | `kubectl apply -f k8s/` | Todos os recursos criados no namespace `oficina` |
| 5. Deploy do banco de dados | `kubectl apply -f k8s/postgres-*` | StatefulSet + Service do PostgreSQL criados |
| 6. Aplicacao dos manifests YAML | `kubectl apply -f k8s/` (passo unificado com 4+5) | `kubectl get all -n oficina` mostra tudo Running |

**Arquivos:**
- `.github/workflows/ci.yml` — Trigger: push/PR em main. Passos 1, 2, 3.
  Roda rapido (< 5 min) para dar feedback ao desenvolvedor.
- `.github/workflows/cd.yml` — Trigger: merge na main. Passos 1 a 6 completos.
  Roda deploy completo apos aprovacao do PR.

### 4.4 APIs — Sophia

Requisito oficial: "Alterar/criar as seguintes APIs"

| Endpoint | Descricao | Criterio de Aceite |
|----------|-----------|-------------------|
| `POST /api/v1/ordens-servico/abrir/` | Abertura de OS: receber cliente, veiculo, servicos e pecas. Retornar ID unico da OS. | ✅ Ja implementado (Lucas) |
| `GET /api/v1/ordens-servico/{id}/status/` | Consultar status atual da OS (Recebida, Diagnostico, Aguardando Aprovacao, Execucao, Finalizada, Entregue) | ✅ Ja implementado (Lucas) |
| `POST /api/v1/orcamentos/notificacoes/` | Aprovacao de orcamento: receber notificacoes externas de aprovacao ou recusa | ✅ Ja implementado (Lucas) |
| `GET /api/v1/ordens-servico/fila/` | **Listagem de OS com ordenacao especifica:** Em Execucao > Aguardando Aprovacao > Diagnostico > Recebida. Mais antigas primeiro. Excluir (logica nao fisica) as finalizadas e entregues. | ⚠️ Verificar se a ordenacao segue exatamente esta prioridade |
| `POST /api/v1/ordens-servico/status-notificacoes/` | Atualizacao de status da OS via ferramenta externa (ex: email) | ⚠️ Verificar implementacao |

---
## 5. Entregaveis Obrigatorios (conforme enunciado)

| # | Entregavel | Responsavel | Status |
|---|------------|-------------|--------|
| 1 | Codigo-fonte refatorado (Clean Architecture + Hexagonal) | Lucas | ✅ PR #1 mergeado |
| 2 | Dockerfile e docker-compose revisados | Luis | ⚠️ Pendente |
| 3 | Manifestos Kubernetes em `/k8s/` | Helio | ⚠️ Pendente |
| 4 | Scripts Terraform em `/infra/` | Luis | ⚠️ Pendente |
| 5 | Pipeline CI/CD (`.github/workflows/`) | Helio | ⚠️ Pendente |
| 6 | README.md atualizado (descricao, arquitetura, instrucoes locais/K8s/Terraform) | Grupo | ⚠️ Pendente |
| 7 | Link collection Postman/Swagger no README | Grupo | ⚠️ Pendente |
| 8 | Video demonstrativo (YouTube/Vimeo, ate 15 min): deploy, CI/CD, APIs, escalabilidade | Grupo | ⚠️ Pendente |
| 9 | PDF de entrega no portal FIAP (link repositorio, desenho arquitetura, link video) | Grupo | ⚠️ Pendente |

---

## 6. Arquitetura Alvo

### Fluxo de Deploy (CI/CD)

```
[Dev] --> git push/PR --> GitHub Actions
                             |
                    +--------+--------+
                    |                 |
                    v                 v
                CI (rapido)       CD (completo)
              - Build app        - Build app
              - Testes (194)     - Testes (194)
              - Lint             - Build imagem Docker
                                 - Push para GHCR
                                 - kubectl apply -f k8s/
                                       |
                                       v
                              +--------+--------+
                              |                 |
                              v                 v
                         [Deployment]     [StatefulSet]
                         oficina-app      postgres
                         2-10 pods        1 pod + PVC
                              |                 |
                              v                 v
                         [Service]         [Service]
                         ClusterIP:8000    Headless:5432
                              |
                              v
                         [HPA: CPU>70%]
                         (escala 2->10)
```

### Componentes do Cluster

```
Namespace: oficina
├── Deployment: oficina-app (2-10 replicas)
│   ├── LivenessProbe: HTTP GET /
│   ├── ReadinessProbe: HTTP GET /
│   ├── StartupProbe: HTTP GET / (failureThreshold: 30)
│   ├── ConfigMap: variaveis nao sensiveis
│   ├── Secret: credenciais
│   └── Resource: requests 250m/256Mi, limits 500m/512Mi
├── Service: oficina-app (ClusterIP:8000)
├── HPA: CPU > 70% (min 2, max 10)
├── StatefulSet: postgres (1 replica)
│   ├── PVC: 1Gi (ReadWriteOnce)
│   └── LivenessProbe: pg_isready
└── Service: oficina-db (Headless:5432)
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
