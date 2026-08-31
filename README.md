# 🔧 Oficina Mecânica API

API REST para gerenciamento de uma oficina mecânica, desenvolvida como entrega do **Tech Challenge — Fases 1 e 2** da pós-graduação em Software Architecture na FIAP (Grupo 26 → Grupo 13).

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.1-092E20?style=flat&logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.15-red?style=flat)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-kind-326CE5?style=flat&logo=kubernetes&logoColor=white)
![CI](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/ci.yml?branch=main&label=CI&logo=github)
![CD](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/cd.yml?branch=main&label=CD&logo=github)
![Cobertura](https://img.shields.io/badge/Cobertura-94.52%25-brightgreen?style=flat)
![Testes](https://img.shields.io/badge/Testes-210%20passando-brightgreen?style=flat)

---

## Sumário

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Como Rodar](#como-rodar)
  - [Com Docker (recomendado)](#com-docker-recomendado)
  - [Com Kubernetes (kind)](#com-kubernetes-kind)
  - [Com Terraform (IaC)](#com-terraform-iac)
- [CI/CD](#cicd)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Endpoints da API](#endpoints-da-api)
- [Filtros e Busca](#filtros-e-busca)
- [Autenticação](#autenticação)
- [Regras de Negócio](#regras-de-negócio)
- [Rate Limiting](#rate-limiting)
- [Formato de Erros](#formato-de-erros)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Qualidade e Segurança](#qualidade-e-segurança)
- [Limitações conhecidas](#limitações-conhecidas)
- [Documentação de Entrega](#documentação-de-entrega)
- [Fase 3 — Operação corporativa](#fase-3--operação-corporativa)
- [Equipe](#equipe)

---

## Visão Geral

O sistema permite que uma oficina mecânica gerencie seu ciclo operacional completo,
com evolucao para infraestrutura escalavel na Fase 2:

- Cadastro de **clientes** (PF com CPF ou PJ com CNPJ) com validação de dígito verificador
- Cadastro de **veículos** vinculados a clientes (placas no formato antigo e Mercosul)
- Catálogo de **serviços** (mão de obra) e **peças** com controle de estoque
- Abertura e acompanhamento de **Ordens de Serviço** com máquina de estados validada
- **Rastreamento de execução por serviço**: cada serviço dentro de uma OS possui ciclo próprio (PENDENTE → EM_EXECUCAO → CONCLUIDO) com data de início, finalização e tempo calculado
- **Consumo de peças por serviço**: peças alocadas na OS são vinculadas ao serviço que as consume; a OS só pode ser finalizada quando todas as peças foram utilizadas
- **Baixa automática de estoque** ao adicionar/remover peças de uma OS
- **Cálculo automático do valor total** da OS (serviços + peças)
- Endpoint **público** para o cliente consultar o status da OS pela placa ou CPF/CNPJ
- **Métricas de serviço** por OS: tempo de execução, peças consumidas, filtro por serviço
- **Tempo médio por tipo de serviço**, considerando somente execuções concluídas válidas
- **Filtros e ordenação** nos recursos administrativos que expõem FilterSets
- **Rate limiting** global e específico por endpoint

### Fase 1 — Base funcional

A Fase 1 estabelece o domínio da oficina: clientes, veículos, catálogo de
serviços e peças, estoque, ordens de serviço, orçamento, máquina de estados,
JWT, consulta pública, documentação e testes automatizados.

### Fase 2 — Evolução da aplicação

A Fase 2 evolui o sistema com foco em qualidade, resiliência e escalabilidade:

- **Refatoração arquitetural**: Clean Architecture/Hexagonal pragmática com separação de camadas (`domain`, `application`, `infrastructure`, `interfaces`)
- **APIs revisadas**: abertura unificada de OS, consulta de status com isolamento por usuário, fila operacional ordenada, aprovação externa de orçamento e atualização de status via notificações
- **Conteinerização**: Dockerfile e docker-compose revisados para desenvolvimento local
- **Orquestração K8s**: manifests para Deployment, Services, ConfigMap, StatefulSet, Secret dinâmico, Metrics Server e HPA de 2–6 pods com alvo de CPU em 50%
- **Infraestrutura como Código**: Terraform provisiona cluster kind e aplica todos os recursos K8s
- **CI/CD**: workflows GitHub Actions versionados para CI e deploy efêmero em Kind; o status da execução remota deve ser conferido no GitHub antes da entrega

### Fase 3 — Operação corporativa

A Fase 3 separa a solução em quatro repositórios com CI/CD independente,
governança por Pull Request e deploy para homologação e produção na AWS:

- [`tech-challenge-oficina`](https://github.com/helyomendesdev/tech-challenge-oficina): aplicação Django executada no EKS.
- [`tech-challenge-oficina-auth`](https://github.com/helyomendesdev/tech-challenge-oficina-auth): autenticação serverless por CPF e emissão de JWT.
- [`tech-challenge-oficina-k8s`](https://github.com/helyomendesdev/tech-challenge-oficina-k8s): infraestrutura Kubernetes.
- [`tech-challenge-oficina-database`](https://github.com/helyomendesdev/tech-challenge-oficina-database): banco gerenciado (RDS) provisionado por Terraform.

**Reponsabilidades:**
- Hélio Mendes — nomes, estrutura e governança dos repositórios
- Luís Fernando Montes — observabilidade
- Lucas Marques — autenticação
- Sophia Sussa Campos Bastos — infraestrutura

**CI/CD AWS (novo):**
```
GitHub Actions (push main)
  → docker build
  → auth AWS via OIDC (role IAM, sem secrets estáticos)
  → push ECR (tag = git sha)
  → update kubeconfig EKS
  → kubectl set image + rollout status
```

Ambientes criados: `homologacao` e `producao` em todos os repositórios.
A divisão do API Gateway e dos módulos Terraform deve ser confirmada entre
Hélio e Sophia antes de fechar os repositórios de infraestrutura.

Documentos: [`docs/adrs/adr-006-cicd-aws-ecr-eks.md`](docs/adrs/adr-006-cicd-aws-ecr-eks.md) e [`docs/fase3/estrutura-repositorios.md`](docs/fase3/estrutura-repositorios.md).

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Framework | Django 5.1 + Django REST Framework 3.15 |
| Banco de dados | PostgreSQL 15 |
| Autenticação | JWT via `djangorestframework-simplejwt` |
| Documentação | OpenAPI 3.0 via `drf-spectacular` (Swagger UI + ReDoc) |
| Filtros | `django-filter` |
| Validação de documentos | `validate-docbr` (CPF/CNPJ) |
| Segurança (env vars) | `python-decouple` |
| CORS | `django-cors-headers` |
| Servidor WSGI | `gunicorn` (produção) |
| Análise de segurança (SAST) | `SonarQube Community 26.4` |
| Testes | `pytest-django` + `pytest-cov` |
| Infraestrutura | Docker + Docker Compose + Kubernetes (kind) + Terraform (IaC) |

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────┐
│  HTTP Client (Postman / Swagger UI / Frontend)                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │ JSON / REST (Bearer JWT)
┌──────────────────────────▼───────────────────────────────────────┐
│  Gunicorn (WSGI) — 2 workers                                     │
│  app/urls.py — Roteamento raiz (JWT + API v1 + Swagger)          │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│  atendimento/urls.py — DefaultRouter (6 ViewSets)                │
│                                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Filters    │  │Serializers │  │  Throttles │  │ Exceptions │  │
│  │(django-fil │  │+ state     │  │  (rate     │  │ (handler   │  │
│  │ter)        │  │machine     │  │  limiting) │  │ estruturado│  │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Models + Signals                                         │   │
│  │  • timezone, signals únicos                               │   │
│  │  • ItemPecaOS.save() + delete() (fonte de verdade)        │   │
│  │  • calcular_total() anti-recursão (via .update())         │   │
│  └──────────────────────────┬────────────────────────────────┘   │
└─────────────────────────────┼────────────────────────────────────┘
                              │ Django ORM (select_related / prefetch_related)
┌─────────────────────────────▼────────────────────────────────────┐
│  PostgreSQL 15                                                    │
│  + healthcheck (pg_isready) + condition: service_healthy          │
└──────────────────────────────────────────────────────────────────┘
```

### Fase 2 — Arquitetura híbrida pragmática

Na Fase 2, o projeto evolui de um monolito Django tradicional para um
**monolito modular Django com Clean Architecture/Arquitetura Hexagonal
pragmática e DDD tático**. A proposta não é vender uma Clean Architecture pura:
Django, DRF e o ORM continuam presentes como parte consciente da solução,
enquanto os fluxos críticos novos passam a ter dependências mais bem separadas.

As camadas adicionadas no app `atendimento` são:

| Camada | Responsabilidade |
|---|---|
| `domain` | Regras puras de negócio: enums, policies, exceptions, value objects e services. |
| `application` | Use cases, DTOs e ports que orquestram os fluxos principais sem depender de HTTP ou ORM. |
| `infrastructure` | Adapters concretos: repositories com Django ORM, transações e notificações simuladas. |
| `interfaces` | Adapters de entrada HTTP/DRF: serializers, views e urls dos endpoints novos. |

O escopo desta refatoração é a camada de código da aplicação. Artefatos de
Kubernetes, Terraform e esteiras CI/CD pertencem a outro escopo de infraestrutura
e não foram alterados nesta etapa.

Nessa organização, Django/DRF atua como **adapter de entrada**, os use cases
concentram os fluxos de aplicação, os repositories isolam o acesso ao Django
ORM e o domínio concentra as regras independentes de framework.

`atendimento/models.py` foi preservado por compatibilidade com migrations,
Django Admin, serializers antigos, endpoints da Fase 1 e testes existentes. Os
fluxos críticos da Fase 2 foram migrados para use cases, DTOs, ports,
repositories e APIViews finas. Algumas regras legadas permanecem
temporariamente em `models.py`, `signals.py`, ModelSerializers antigos e
ViewSets antigos; isso é uma decisão consciente de refatoração incremental para
não quebrar contratos já validados.

Próximos passos naturais são migrar actions antigas para use cases, reduzir
signals, mover gradualmente cálculo e estoque para serviços/use cases, avaliar
entities puras e mappers, e reorganizar ports caso o projeto cresça.

### Fluxo de uma Ordem de Serviço

```
RECEBIDA → DIAGNOSTICO → AGUARDANDO → EXECUCAO → FINALIZADA → ENTREGUE
                                          ↑              ↑
                               data_inicio_execucao  data_finalizacao
                                  (auto-preenchido)  (auto-preenchido)
```

> Transições fora do fluxo acima são rejeitadas com `HTTP 400`.
> O status da OS **não pode ser alterado via PATCH**. Use os endpoints dedicados listados em [Máquina de estados da Ordem de Serviço](#máquina-de-estados-da-ordem-de-serviço).

### C4 Model

#### Nível 1 — Contexto

![Diagrama de Contexto](docs/images/1%20-%20C4Context.png)

#### Nível 2 — Container

![Diagrama de Container](docs/images/2%20-%20C4Container.png)

#### Nível 3 — Componente

![Diagrama de Componente](docs/images/3-%20C4Component.png)

#### Nível 4 — Sequência (Iniciar Serviço)

![Diagrama de Sequência](docs/images/4%20-%20SequenceDiagram.png)

> Os diagramas acima foram gerados a partir dos códigos Mermaid disponíveis em [`docs/arquitetura/c4-model.md`](docs/arquitetura/c4-model.md).

### Infraestrutura provisionada (Fase 3)

```
┌──────────────────────────────────────────────────────────────────────┐
│  AWS Academy — EKS, ECR, RDS, ALB, VPC, API Gateway                 │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  EKS Cluster — Namespace: oficina                              │  │
│  │                                                                │  │
│  │  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐      │  │
│  │  │  ConfigMap   │   │   Secret     │   │     HPA       │      │  │
│  │  │ oficina-cfg  │   │ oficina-sec  │   │  2 → 6 pods   │      │  │
│  │  │ (env vars)   │   │ (credenciais)│   │  CPU > 50%    │      │  │
│  │  └──────────────┘   └──────────────┘   └───────────────┘      │  │
│  │                                                                │  │
│  │  ┌───────────────────────┐      ┌───────────────────────┐     │  │
│  │  │  Deployment           │      │  RDS PostgreSQL 15    │     │  │
│  │  │  oficina-app          │      │  (gerenciado)         │     │  │
│  │  │  2+ réplicas          │      │                       │     │  │
│  │  │  gunicorn :8000       │      └───────────────────────┘     │  │
│  │  │  probes HTTP health   │                                    │  │
│  │  └──────────┬────────────┘                                    │  │
│  │             │ :8000                                            │  │
│  │  ┌──────────▼────────────┐                                    │  │
│  │  │  ALB (interno)        │                                    │  │
│  │  │  oficina-app:8000     │                                    │  │
│  │  └───────────────────────┘                                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### Fluxo de deploy (CI/CD)

```
Push/PR ──► CI (ci.yml)
             │ 1. Build (pip install)
             │ 2. Django check
             │ 3. 210 testes (pytest-django)
             ▼
Merge main ──► CD (cd.yml)
             │ 1. Docker build
             │ 2. Auth AWS via OIDC (role IAM)
             │ 3. Push ECR (tag = git sha)
             │ 4. Update kubeconfig EKS
             │ 5. kubectl set image + rollout status
             ▼
EKS Cluster pronto — ALB interno → API Gateway → aplicação
```

Para desenvolvimento local, o script `scripts/kind-deploy.sh` ainda funciona
como alternativa ao deploy AWS ( Kind + Metrics Server local).

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/)

> Para rodar sem Docker: Python 3.11+ e PostgreSQL 15+

---

## Como Rodar

### Com Docker (recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/helyomendesdev/tech-challenge-oficina.git
cd tech-challenge-oficina

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais e uma SECRET_KEY segura

# 3. Suba os containers (banco + API)
docker compose up --build

# 4. Em outro terminal, crie o superusuário
docker exec -it oficina_app python manage.py createsuperuser

# 5. (Opcional) Carregue dados de exemplo
docker exec oficina_app python manage.py loaddata initial_data.json
docker exec oficina_app python manage.py loaddata seed_data.json
```

A API estará disponível em `http://localhost:8000`.

### Com Kubernetes (kind)

O deploy local cria ou reutiliza com segurança o cluster `oficina`, constrói e
carrega a imagem, gera Secrets locais dinamicamente, executa migrations,
instala o Metrics Server e aguarda todos os rollouts.

**Windows PowerShell:**

```powershell
.\scripts\kind-deploy.ps1
python .\scripts\smoke_test.py
python .\scripts\hpa_load_test.py
```

**Linux / GitHub Actions:**

```bash
chmod +x scripts/kind-deploy.sh
./scripts/kind-deploy.sh
python scripts/smoke_test.py
python scripts/hpa_load_test.py
```

O teste de HPA registra réplicas e CPU antes, durante e depois da carga, e
falha se não observar tanto scale-up quanto scale-down. O CD executa deploy,
smoke e validação das métricas em todo push; o teste completo de HPA fica no
gatilho manual `workflow_dispatch` por levar alguns minutos.

O repositório não contém um Secret aplicável. Os scripts criam
`oficina-secret` com valores aleatórios ou variáveis de ambiente. Em cluster
reutilizado, o Secret existente é preservado para manter compatibilidade com o
volume persistente do PostgreSQL e o deploy falha se encontrar `CHANGE_ME_*`.

Para inspecionar o ambiente manualmente:

```bash
kubectl get nodes
kubectl get pods -A
kubectl get pods,services,deployments,statefulsets,hpa -n oficina
kubectl top nodes
kubectl top pods -n oficina
kubectl port-forward -n oficina svc/oficina-app 8000:8000
```

### Com Terraform (IaC)

Provisiona o cluster Kind e os recursos Kubernetes via Terraform. Como a
imagem precisa existir dentro do cluster antes do Deployment, o script
`infra/deploy.ps1` explicita a ordem cluster → build → load → recursos →
migrations → aplicação → Metrics Server → HPA → smoke. Consulte
[`infra/README.md`](infra/README.md) para detalhes.

```powershell
cd infra

# 1. Valide a configuração
terraform fmt -check -recursive
terraform init
terraform validate

# 2. Forneça segredos apenas no ambiente local
$env:TF_VAR_postgres_password = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:TF_VAR_django_secret_key = python -c "import secrets; print(secrets.token_urlsafe(48))"

# 3. Revise o plano e execute o fluxo reproduzível
terraform plan
.\deploy.ps1

# 4. Destrua após a demonstração
terraform destroy
```

Na última validação local registrada, o plano apresentou `10 to add`, o apply
criou os dez recursos gerenciados e o destroy removeu os dez. Essa evidência
local não substitui o status do workflow remoto.

---

## CI/CD

O projeto utiliza **GitHub Actions** para integração e entrega contínuas:

| Pipeline | Trigger | Etapas |
|----------|---------|--------|
| **CI** | push/PR em `main` ou `feat/*` | Dependências → Django check → testes → Docker build → relatório JUnit |
| **CD** | push em `main` | Docker build → auth AWS (OIDC) → push ECR → deploy EKS → rollout status |

Os arquivos dos workflows foram validados contra os scripts locais. Pipeline
verde é evidência externa e deve ser confirmado no GitHub antes da entrega.

Badges de status:
[![CI](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/ci.yml?branch=main&label=CI&logo=github)](https://github.com/helyomendesdev/tech-challenge-oficina/actions/workflows/ci.yml)
[![CD](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/cd.yml?branch=main&label=CD&logo=github)](https://github.com/helyomendesdev/tech-challenge-oficina/actions/workflows/cd.yml)

### Sem Docker (desenvolvimento local)

```bash
# 1. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env: defina DJANGO_SECRET_KEY, POSTGRES_PASSWORD e DB_HOST=localhost

# 4. Aplique as migrations e crie o superusuário
python manage.py migrate
python manage.py createsuperuser

# 5. Inicie o servidor de desenvolvimento
python manage.py runserver
```

---

## Variáveis de Ambiente

Copie `.env.example` para `.env` e preencha os valores antes de iniciar a aplicação.

| Variável | Padrão (exemplo) | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(obrigatório)* | Chave secreta do Django — nunca commitar |
| `DJANGO_DEBUG` | `False` | `True` apenas em desenvolvimento local |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos, separados por vírgula |
| `POSTGRES_DB` | `oficina_db` | Nome do banco de dados |
| `POSTGRES_USER` | `admin` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | *(obrigatório)* | Senha do PostgreSQL — nunca commitar |
| `DB_HOST` | `db` | Host do banco (`db` no Docker, `localhost` fora) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Origens permitidas para o frontend |

> **Segurança:** O arquivo `.env` está no `.gitignore` e **nunca deve ser commitado**.
> Use `.env.example` como template — ele contém apenas nomes, sem valores sensíveis.

---

## Endpoints da API

O schema validado contém **34 caminhos e 60 operações OpenAPI**. Swagger e
ReDoc são derivados desse mesmo schema, evitando uma contagem manual paralela.

### Documentação interativa

| Interface | URL |
|---|---|
| Swagger UI | http://localhost:8000/api/schema/swagger-ui/ |
| ReDoc | http://localhost:8000/api/schema/redoc/ |
| Schema OpenAPI (JSON) | http://localhost:8000/api/schema/ |

### Referência rápida

#### Autenticação

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/token/` | Obter `access` + `refresh` token | Não |
| `POST` | `/api/token/refresh/` | Renovar `access` token | Não |

#### Clientes

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/clientes/` | Listar clientes (paginado, filtrado) |
| `POST` | `/api/v1/clientes/` | Cadastrar cliente (CPF ou CNPJ) |
| `GET` | `/api/v1/clientes/{id}/` | Detalhar cliente |
| `PUT` | `/api/v1/clientes/{id}/` | Atualizar cliente |
| `PATCH` | `/api/v1/clientes/{id}/` | Atualizar parcialmente |
| `DELETE` | `/api/v1/clientes/{id}/` | Remover cliente |

#### Veículos

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/veiculos/` | Listar veículos (paginado) |
| `POST` | `/api/v1/veiculos/` | Cadastrar veículo |
| `GET` | `/api/v1/veiculos/{id}/` | Detalhar veículo |
| `PUT` | `/api/v1/veiculos/{id}/` | Atualizar veículo |
| `PATCH` | `/api/v1/veiculos/{id}/` | Atualizar parcialmente |
| `DELETE` | `/api/v1/veiculos/{id}/` | Remover veículo |

#### Serviços

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/servicos/` | Listar serviços |
| `POST` | `/api/v1/servicos/` | Cadastrar serviço |
| `GET` | `/api/v1/servicos/{id}/` | Detalhar serviço |
| `PUT` | `/api/v1/servicos/{id}/` | Atualizar serviço |
| `DELETE` | `/api/v1/servicos/{id}/` | Remover serviço |

#### Peças

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/pecas/` | Listar peças com saldo de estoque (filtrado) |
| `POST` | `/api/v1/pecas/` | Cadastrar peça |
| `GET` | `/api/v1/pecas/{id}/` | Detalhar peça e saldo |
| `PUT` | `/api/v1/pecas/{id}/` | Atualizar peça |
| `DELETE` | `/api/v1/pecas/{id}/` | Remover peça |

#### Ordens de Serviço

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/ordens-servico/` | Listar todas as OS (paginado, filtrado) | Sim |
| `POST` | `/api/v1/ordens-servico/` | Abrir nova OS | Sim |
| `GET` | `/api/v1/ordens-servico/{id}/` | Detalhar OS | Sim |
| `PUT` | `/api/v1/ordens-servico/{id}/` | Atualizar OS | Sim |
| `PATCH` | `/api/v1/ordens-servico/{id}/` | Atualizar campos da OS (exceto status — use endpoints dedicados) | Sim |
| `DELETE` | `/api/v1/ordens-servico/{id}/` | Remover OS | Sim |
| `GET` | `/api/v1/ordens-servico/consulta-cliente/` | Consultar OS por placa ou CPF/CNPJ | **Não** |

#### Fase 2 — novos endpoints

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/v1/ordens-servico/abrir/` | Abertura completa de OS via use case | Sim |
| `GET` | `/api/v1/ordens-servico/{id}/status/` | Consulta de status da OS com isolamento por usuário | Sim |
| `GET` | `/api/v1/ordens-servico/fila/` | Fila operacional: EXECUCAO, AGUARDANDO, DIAGNOSTICO e RECEBIDA | Sim |
| `POST` | `/api/v1/orcamentos/notificacoes/` | Simula aprovação ou recusa externa de orçamento | Sim |
| `POST` | `/api/v1/ordens-servico/status-notificacoes/` | Simula atualização externa de status validada por policies | Sim |
| `POST` | `/api/v1/simulacao/orcamento/` | Simula sistema externo responsável pela aprovação ou recusa de orçamentos de clientes. | Sim |


#### Itens de Peças (OS)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/itens-pecas/` | Listar itens de peças |
| `POST` | `/api/v1/itens-pecas/` | Adicionar peça à OS (debita estoque automaticamente) |
| `GET` | `/api/v1/itens-pecas/{id}/` | Detalhar item |
| `PUT` | `/api/v1/itens-pecas/{id}/` | Atualizar item (ajusta estoque pela diferença) |
| `DELETE` | `/api/v1/itens-pecas/{id}/` | Remover peça da OS (devolve ao estoque) |

#### Serviços por OS (execução)

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/ordens-servico/{os_id}/servicos/` | Listar serviços da OS com status e datas | Sim |
| `POST` | `/api/v1/ordens-servico/{os_id}/servicos/` | Adicionar serviço à OS | Sim |
| `GET` | `/api/v1/ordens-servico/{os_id}/servicos/{id}/` | Detalhar serviço | Sim |
| `DELETE` | `/api/v1/ordens-servico/{os_id}/servicos/{id}/` | Remover serviço (somente PENDENTE) | Sim |
| `POST` | `/api/v1/ordens-servico/{os_id}/servicos/{id}/iniciar/` | Iniciar execução (aceita `data_inicio` e `pecas`) | Sim |
| `POST` | `/api/v1/ordens-servico/{os_id}/servicos/{id}/finalizar/` | Finalizar serviço (aceita `data_finalizacao`) | Sim |

#### Métricas de Serviço

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/ordens-servico/{os_id}/metricas/` | Tempo de execução e peças consumidas por serviço da OS | Sim |
| `GET` | `/api/v1/ordens-servico/{os_id}/metricas/?servico={id}` | Filtrar métricas por serviço específico | Sim |
| `GET` | `/api/v1/ordens-servico/metricas/tempo-medio/` | Média de execução, em minutos, agrupada por tipo de serviço | Sim |

O tempo médio considera somente itens com status `CONCLUIDO`, início e
finalização preenchidos e duração não negativa. Tipos de serviço sem nenhuma
execução válida não são retornados. Usuários comuns visualizam somente dados
de suas próprias ordens; usuários staff mantêm a visão administrativa global.

---

## Filtros e Busca

Os endpoints de listagem base usam **paginação** de 20 itens por padrão. Actions
com resposta própria, como métricas e alguns fluxos da Fase 2, podem retornar
listas não paginadas conforme seu contrato documentado no OpenAPI.

### Ordens de Serviço — `/api/v1/ordens-servico/`

| Parâmetro | Exemplo | Descrição |
|---|---|---|
| `status` | `?status=EXECUCAO` | Filtrar por status (pode repetir para múltiplos) |
| `cliente` | `?cliente=5` | Filtrar pelo ID do cliente |
| `veiculo` | `?veiculo=3` | Filtrar pelo ID do veículo |
| `data_abertura_after` | `?data_abertura_after=2026-01-01` | OS abertas a partir de |
| `data_abertura_before` | `?data_abertura_before=2026-12-31` | OS abertas até |
| `valor_total_min` | `?valor_total_min=500` | Valor total mínimo |
| `valor_total_max` | `?valor_total_max=2000` | Valor total máximo |
| `ordering` | `?ordering=-data_abertura` | Ordenar (prefixo `-` para decrescente) |

### Clientes — `/api/v1/clientes/`

| Parâmetro | Exemplo | Descrição |
|---|---|---|
| `nome` | `?nome=joão` | Busca parcial, sem distinção de maiúsculas |
| `documento` | `?documento=52998224725` | Filtro exato por CPF/CNPJ |
| `search` | `?search=silva` | Busca geral (nome, documento, email) |
| `ordering` | `?ordering=nome,-criado_em` | Ordenação |

### Peças — `/api/v1/pecas/`

| Parâmetro | Exemplo | Descrição |
|---|---|---|
| `nome` | `?nome=pastilha` | Busca parcial por nome |
| `estoque_min` | `?estoque_min=5` | Apenas peças com estoque ≥ 5 |
| `estoque_zerado` | `?estoque_zerado=true` | Apenas peças sem estoque |
| `ordering` | `?ordering=-estoque_atual` | Ordenação |

---

## Autenticação

Os endpoints administrativos exigem **Bearer Token (JWT)**. As exceções
intencionais são healthchecks, schema/documentação, emissão/renovação de token
e consulta pública de OS.

**Obtendo o token:**

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "seu_usuario", "password": "sua_senha"}'
```

**Usando o token:**

```bash
curl http://localhost:8000/api/v1/clientes/ \
  -H "Authorization: Bearer <access_token>"
```

| Token | Validade |
|---|---|
| `access_token` | 30 minutos |
| `refresh_token` | 1 dia |

---

## Regras de Negócio

### Máquina de estados da Ordem de Serviço

O status da OS **não pode ser alterado via PATCH**. Cada transição é acionada por um endpoint dedicado:

| Endpoint | Transição |
|---|---|
| `POST /api/v1/ordens-servico/{id}/iniciar-diagnostico/` | RECEBIDA → DIAGNOSTICO | 
| `POST /api/v1/ordens-servico/{id}/finalizar-diagnostico/` | DIAGNOSTICO → AGUARDANDO | 
| `POST /api/v1/ordens-servico/{id}/aprovar-orcamento/` | AGUARDANDO → EXECUCAO |
| `POST /api/v1/ordens-servico/{id}/recusar-orcamento/` | AGUARDANDO → DIAGNOSTICO | 
| `POST /api/v1/ordens-servico/{id}/finalizar/` | EXECUCAO → FINALIZADA |
| `POST /api/v1/ordens-servico/{id}/entregar/` | FINALIZADA → ENTREGUE |
| `POST /api/v1/ordens-servico/{id}/cancelar/` | AGUARDANDO → CANCELADA |

```
RECEBIDA → DIAGNOSTICO → AGUARDANDO ┬→ EXECUCAO → FINALIZADA → ENTREGUE
                                     ├→ DIAGNOSTICO (recusado, loop)
                                     └→ CANCELADA
```

### Validações de entrada

| Campo | Regra |
|---|---|
| `documento` (Cliente) | CPF válido (11 dígitos) ou CNPJ válido (14 dígitos), com validação de dígito verificador |
| `placa` (Veículo) | Formato antigo `ABC1234` ou Mercosul `ABC1D23` |
| `quantidade` (ItemPecaOS) | Não pode exceder o `estoque_atual` da peça |
| `status` (OrdemServico) | Apenas transições do fluxo definido são permitidas |

### Automações

| Evento | Efeito automático |
|---|---|
| OS muda para `EXECUCAO` | `data_inicio_execucao` preenchida com o timestamp atual |
| OS muda para `FINALIZADA` | `data_finalizacao` preenchida com o timestamp atual |
| Peça **adicionada** a uma OS | `estoque_atual` decrementado; `valor_total` recalculado |
| Peça **atualizada** em uma OS | Diferença de quantidade ajustada no estoque; `valor_total` recalculado |
| Peça **removida** de uma OS | `estoque_atual` devolvido; `valor_total` recalculado |
| Serviço adicionado/removido de uma OS | `valor_total` da OS recalculado |
| **Serviço iniciado** (`/iniciar/`) | Permitido somente quando a OS está em `EXECUCAO`; status do serviço → `EM_EXECUCAO`; peças informadas são consumidas atomicamente sem nova baixa de estoque |
| **Serviço finalizado** (`/finalizar/`) | Status do serviço → `CONCLUIDO`; se for o último serviço ativo e todas as peças da OS foram consumidas, a OS avança automaticamente para `FINALIZADA` |

### Gates de finalização

| Condição bloqueante | HTTP |
|---|---|
| Tentar avançar OS para `FINALIZADA` via `PATCH` com serviços não concluídos | `400` |
| Tentar avançar OS para `FINALIZADA` via `PATCH` com peças não consumidas | `400` |
| Chamar `/finalizar/` em serviço que não está `EM_EXECUCAO` | `400` |
| Último serviço tenta finalizar mas há peças não consumidas na OS | `400` |

### Cálculo do valor total

```
valor_total = Σ(servicos.valor_mao_de_obra) + Σ(itens_pecas.peca.valor_unitario × quantidade)
```

---

## Rate Limiting

| Tipo de acesso | Limite |
|---|---|
| Usuários autenticados | 600 requisições/hora |
| Acessos anônimos (geral) | 60 requisições/hora |
| Endpoint público `/consulta-cliente` | **30 requisições/hora por IP** |

Ao exceder o limite, a API retorna `HTTP 429 Too Many Requests`.

---
### Simulação de aprovação/recusa de orçamento

Foi implementado um simulador que representa um sistema externo responsável por aprovar ou recusar um orçamento.

Fluxo:

Cliente
    ↓
POST /api/v1/simulacao/orcamento/
    ↓
SimuladorOrcamentoService
    ↓
POST HTTP
/api/v1/orcamentos/notificacoes/
    ↓
ProcessarRespostaOrcamentoUseCase


O simulador reutiliza o token JWT da requisição para autenticar a chamada HTTP ao webhook interno, reproduzindo o fluxo de uma integração protegida por autenticação.
Diferentemente do FakeNotificationAdapter utilizado nos fluxos internos, o simulador realiza uma chamada HTTP real utilizando a biblioteca requests, representando uma integração externa.
WEBHOOK_ORCAMENTO_URL: URL utilizada pelo simulador para enviar notificações de orçamento. Em desenvolvimento, o valor padrão é http://localhost:8000/api/v1/orcamentos/notificacoes/. Em ambientes como Docker Compose, Kubernetes ou produção, configure essa variável para o endereço da API.

A API possui dois endpoints relacionados ao orçamento:

- `/api/v1/simulacao/orcamento/`
  Responsável por simular um sistema externo.

- `/api/v1/orcamentos/notificacoes/`
  Responsável por receber efetivamente a notificação e processar a mudança de status.

---

## Formato de Erros

Todos os erros seguem um formato padronizado:

**Erro de validação de campo (400):**
```json
{
  "erro": true,
  "status_code": 400,
  "mensagem": "Erro de validação. Verifique os campos informados.",
  "campos": {
    "documento": "Este número de CPF é inválido.",
    "email": "Insira um endereço de email válido."
  }
}
```

**Erro geral (401 / 403 / 404):**
```json
{
  "erro": true,
  "status_code": 401,
  "mensagem": "As credenciais de autenticação não foram fornecidas."
}
```

---

## Testes

```bash
# Ativar o ambiente virtual
source .venv/bin/activate

# Rodar todos os testes com cobertura
pytest --cov=atendimento --cov-report=term-missing

# Gerar relatório XML para o SonarQube
pytest --cov=atendimento --cov-report=xml:coverage.xml
```

**Resultado atual:**

| Métrica | Valor |
|---|---|
| Total de testes | **210 passando** |
| Subtests | **3 passando** |
| Cobertura geral | **94,52%** |
| OpenAPI | **34 caminhos · 60 operações · validação sem erros** |
| SonarQube Bugs *(relatório histórico)* | **0** |
| SonarQube Vulnerabilidades *(relatório histórico)* | **0** |
| SonarQube Code Smells *(relatório histórico)* | **0** |
| SonarQube Security Rating *(relatório histórico)* | **A** |
| OWASP Top 10 *(avaliação histórica)* | **9/10 conformantes** · 1/10 parcialmente |

Os testes cobrem:

- **Modelo:** Cálculo de total (peças, serviços, combinados), baixa e devolução de estoque, timestamps automáticos, erro de estoque insuficiente, `tempo_execucao_minutos`
- **API:** Criação de OS, autenticação JWT, transições de status válidas e inválidas
- **Endpoint público:** Consulta por placa, CPF/CNPJ, identificador ausente, não encontrado
- **Filtros:** Filtro por status, cliente, nome parcial, estoque mínimo, ordenação
- **Erros:** Formato estruturado por campo (400), mensagem simples (401, 404)
- **Clientes:** CPF válido/inválido, duplicidade de documento
- **Veículos:** Normalização de placa para maiúsculas
- **Itens de Peças:** Estoque insuficiente em inserção e atualização
- **Serviços por OS (CRUD):** Adicionar, listar, remover, isolamento por usuário
- **Iniciar serviço:** Peças consumidas atomicamente sem nova baixa de estoque, bloqueio quando a OS não está em EXECUCAO, erros de disponibilidade e estado
- **Finalizar serviço:** Tempo calculado, cascade OS → FINALIZADA, gate de peças não utilizadas
- **Métricas:** `tempo_execucao_minutos`, `pecas_consumidas`, filtro por serviço, isolamento por usuário
- **Fase 2:** Abertura completa de OS, status, fila operacional, aprovação/recusa simulada, notificação de status e isolamento para usuário comum, staff e superuser

> 📄 Relatório completo de qualidade e segurança: [docs/relatorio_qualidade_seguranca.md](docs/relatorio_qualidade_seguranca.md)

---

## Testando com Postman

O repositório inclui uma collection e um environment Postman prontos para uso:

| Arquivo | Descrição |
|---|---|
| `postman_collection.json` | **76 requests** organizados por recurso, incluindo casos de erro |
| `postman_environment.json` | Variáveis de ambiente (base_url, credenciais, tokens) |

**Passos:**

1. No Postman: **File → Import** → selecione os dois arquivos
2. Selecione o environment **"Oficina Local"**
3. Execute **Autenticação → Obter Token** — o token é salvo automaticamente
4. Todas as demais requisições já utilizam o token via Bearer

---

## Estrutura do Projeto

```
tech-challenge-oficina/
├── app/                         # Configuração Django
│   ├── settings.py              # Configurações de produção (via .env)
│   ├── settings_test.py         # Configurações de teste (SQLite em memória)
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── atendimento/                 # App principal
│   ├── models.py                # Entidades + validadores + signals
│   ├── serializers.py           # Serialização, validação e máquina de estados
│   ├── views.py                 # ViewSets (controllers) com filtros e throttling
│   ├── filters.py               # FilterSets django-filter (OS, Cliente, Peça)
│   ├── throttles.py             # Rate limiting customizado (consulta pública)
│   ├── urls.py                  # Roteamento da API
│   ├── admin.py                 # Django Admin customizado
│   ├── exceptions.py            # Handler de erros com formato estruturado
│   ├── signals.py               # Signals legados limpos; estoque fica em ItemPecaOS
│   ├── tests/
│   │   ├── application/         # Testes dos use cases da Fase 2
│   │   ├── domain/              # Policies, services e value objects
│   │   └── integration/         # APIs, isolamento, saúde e métricas
│   ├── domain/                  # DDD tático: enums, policies, VOs, exceptions e services puros
│   ├── application/             # DTOs, ports e use cases sem dependência de HTTP/ORM
│   ├── infrastructure/          # Repositories Django ORM, transactions e notificação fake
│   ├── interfaces/              # APIViews/serializers/urls dos endpoints novos
│   ├── migrations/              # Histórico de schema do banco
│   └── fixtures/
│       ├── initial_data.json    # Dado base (1 cliente, 1 veículo...)
│       └── seed_data.json       # Dados de exemplo para desenvolvimento
├── docs/
│   ├── adrs/                    # Decisões arquiteturais
│   ├── arquitetura/             # C4 e arquitetura híbrida
│   ├── requisitos/              # Requisitos funcionais e não funcionais
│   └── relatorio_qualidade_seguranca.md  # Relatório histórico SAST/OWASP
├── k8s/                         # Manifests da aplicação e banco
├── infra/                       # Terraform e orquestrador PowerShell
├── scripts/                     # Deploy Kind, smoke e prova do HPA
├── .github/workflows/           # CI e CD
├── docker-compose.yml           # PostgreSQL + Gunicorn (healthcheck incluído)
├── Dockerfile
├── requirements.txt
├── pytest.ini                   # Configuração do pytest
├── .env.example                 # Template de variáveis de ambiente
├── manage.py
├── postman_collection.json      # Collection Postman completa
└── postman_environment.json     # Environment Postman (local)
```

---

## Qualidade e Segurança

O repositório preserva um relatório histórico de análise estática com
**SonarQube Community** e mapeamento **OWASP Top 10 (2021)**. O SonarQube não
foi reexecutado nesta revisão documental; portanto, esses resultados não devem
ser confundidos com os checks locais atuais.

| Dimensão | Resultado |
|---|---|
| Cobertura de testes | **94,52%** (meta ≥ 80%) |
| Testes passando | **210 / 210 + 3 subtests** |
| Schema OpenAPI | **34 caminhos · 60 operações · validação sem erros** |
| Bugs (relatório histórico SonarQube) | **0** — Rating A |
| Vulnerabilidades (relatório histórico SonarQube) | **0** — Rating A |
| Code Smells (relatório histórico SonarQube) | **0** — dívida técnica 0 min |
| Duplicação (relatório histórico) | **0,0%** |
| OWASP Top 10 (avaliação histórica) | **9/10 conformantes** · 1/10 parcialmente |

📄 **[Ver relatório completo → docs/relatorio_qualidade_seguranca.md](docs/relatorio_qualidade_seguranca.md)**

O relatório detalha:
- Análise SAST (SonarQube) com todos os issues identificados e resolvidos
- Avaliação de cada categoria OWASP Top 10
- Métricas de cobertura por módulo
- Code smells corrigidos e plano de remediação priorizado

---

## Limitações conhecidas

- O ambiente AWS Academy é temporário; recursos podem ser encerrados entre sessões.
- O Metrics Server usa `--kubelet-insecure-tls`, aceitável apenas no Kind local.
- Build/load da imagem e instalação do Metrics Server são etapas imperativas
  nos orquestradores, embora a ordem esteja documentada.
- A arquitetura é híbrida e incremental: models, signals, ModelSerializers e
  ViewSets legados coexistem com use cases e ports da Fase 2.
- Metas de performance, disponibilidade e throughput não possuem ensaio atual
  comprovado; permanecem parciais na matriz de requisitos.
- PR, compartilhamento com a organização, publicação da collection, vídeo e
  PDF dependem de ações humanas listadas no checklist de entrega.

---

## Segurança em Produção

Com `DJANGO_DEBUG=False` no `.env`, as seguintes proteções são ativadas automaticamente:

- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 31536000` (HSTS por 1 ano)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `X_FRAME_OPTIONS = 'DENY'`

---

## Documentação de Entrega

A documentação completa do projeto está organizada na pasta `docs/`:

### Entrega final da Fase 2

| Documento | Descrição |
|---|---|
| [Matriz de requisitos](docs/matriz-requisitos-fase1-fase2.md) | Evidências, resultados e status das Fases 1 e 2 |
| [Checklist de entrega](docs/checklist-entrega-fase2.md) | Ações técnicas e externas ainda necessárias |
| [Roteiro do vídeo](docs/roteiro-video-fase2.md) | Demonstração de até 15 minutos, comandos e contingência do HPA |

### Arquitetura

| Documento | Descrição |
|---|---|
| [C4 Model](docs/arquitetura/c4-model.md) | Diagramas de Contexto, Container, Componente e Código (com código PlantUML para renderização) |

### Especificações Técnicas

| Documento | Descrição |
|---|---|
| [RFC-001 — Máquina de Estados da OS](docs/rfcs/rfc-001-estado-os.md) | Especificação do ciclo de vida da Ordem de Serviço e serviços |
| [RFC-002 — Controle de Estoque](docs/rfcs/rfc-002-controle-estoque.md) | Especificação da baixa automática e consumo de peças por serviço |
| [RFC-003 — Autenticação e Rate Limiting](docs/rfcs/rfc-003-autenticacao-jwt.md) | Especificação de JWT, throttling e segurança |
| [ADR-001 — Django + DRF](docs/adrs/adr-001-django-drf.md) | Decisão de arquitetura: framework web |
| [ADR-002 — PostgreSQL](docs/adrs/adr-002-postgresql.md) | Decisão de arquitetura: banco de dados |
| [ADR-003 — Docker](docs/adrs/adr-003-docker.md) | Decisão de arquitetura: containerização |
| [ADR-004 — Monolito](docs/adrs/adr-004-monolito.md) | Decisão de arquitetura: monolito para Fase 1 |

### Design

| Documento | Descrição |
|---|---|
| [High-Level Design (HLD)](docs/design/hld.md) | Visão de alto nível da arquitetura, fluxo de dados e ER |
| [Low-Level Design (LLD)](docs/design/lld.md) | Detalhamento de módulos, APIs, banco de dados e regras de negócio |
| [Design Approval Sheet (DAS)](docs/das/design-approval-sheet.md) | Checklist de aprovação do design com rastreabilidade completa |

### Requisitos

| Documento | Descrição |
|---|---|
| [Requisitos Funcionais](docs/requisitos/requisitos-funcionais.md) | RF001–RF017 com critérios de aceitação e rastreabilidade |
| [Requisitos Não Funcionais](docs/requisitos/requisitos-nao-funcionais.md) | RNF001–RNF013 com métricas e conformidade |

---

### Artefatos de Domain-Driven Design (DDD)

**Domain Storytelling**

[Clique aqui para ser redirecionado para a documentação do Domain Storytelling](https://miro.com/app/board/uXjVHZ-qZuY=/?share_link_id=271439252192)

**Event Storming**

[Clique aqui para ser redirecionado para a documentação do Event Storming](https://miro.com/app/board/uXjVGyBSvFg=/?share_link_id=970374301740)

**Linguagem Ubíqua**

[Clique aqui para ser redirecionado para a linguagem ubíqua](https://www.notion.so/Linguaguem-Ub-qua-Fase-1-Grupo-26-353ca0515ab080f08a7ce45530779ed8?pvs=21)

---

## Equipe

### Grupo 13 — Fase 2 e Fase 3 (atual)

| Nome | RM | Fase 3 |
|---|---|---|
| Hélio Mendes da Silva | RM374170 | nomes, estrutura e governança dos repositórios |
| Lucas Marques | RM369825 | autenticação |
| Luís Fernando Montes | RM367183 | observabilidade |
| Sophia Sussa Campos Bastos | RM371864 | infraestrutura |

### Grupo 26 — Fase 1 (original)

| Nome | RM |
|---|---|
| Afonso Victoriano Franco | RM373563 |
| Hélio Mendes da Silva | RM374170 |
| João Pedro Rodrigues Martins | RM372818 |
| Luís Fernando Montes | RM367183 |
| Sophia Sussa Campos Bastos | RM371864 |

---

*Tech Challenge — Fases 1, 2 e 3 — Pós-graduação Software Architecture · FIAP · Grupo 26 (Fase 1) → Grupo 13 (Fases 2 e 3)*
