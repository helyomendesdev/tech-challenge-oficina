# 🔧 Oficina Mecânica API

API REST para gerenciamento do ciclo operacional de uma oficina mecânica — clientes, veículos,
peças, serviços e ordens de serviço com máquina de estados. Desenvolvida para o **Tech Challenge
FIAP** (pós-graduação em Software Architecture). Dois tipos de usuário consomem a API: o
**funcionário da oficina**, autenticado com JWT emitido pelo próprio Django (`/api/token/`), e o
**cliente**, autenticado com um JWT emitido por uma Lambda externa a partir do CPF (repositório
[`tech-challenge-oficina-auth`](https://github.com/helyomendesdev/tech-challenge-oficina-auth)).

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.1-092E20?style=flat&logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.15-red?style=flat)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-EKS%20%2F%20kind-326CE5?style=flat&logo=kubernetes&logoColor=white)
[![CI](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/ci.yml?branch=main&label=CI&logo=github)](https://github.com/helyomendesdev/tech-challenge-oficina/actions/workflows/ci.yml)
[![CD](https://img.shields.io/github/actions/workflow/status/helyomendesdev/tech-challenge-oficina/cd.yml?branch=main&label=CD&logo=github)](https://github.com/helyomendesdev/tech-challenge-oficina/actions/workflows/cd.yml)
![Cobertura](https://img.shields.io/badge/Cobertura-94.52%25-brightgreen?style=flat)
![Testes](https://img.shields.io/badge/Testes-210%20passando-brightgreen?style=flat)

## Sumário

- [Tecnologias](#tecnologias)
- [Arquitetura](#arquitetura)
- [Como executar](#como-executar)
- [Deploy e ambientes](#deploy-e-ambientes)
- [Exemplos de uso da API](#exemplos-de-uso-da-api)
- [Swagger e Postman](#swagger-e-postman)
- [Referência rápida de endpoints](#referência-rápida-de-endpoints)
- [Regras de negócio](#regras-de-negócio)
- [Testes e qualidade](#testes-e-qualidade)
- [Documentação](#documentação)
- [Repositórios relacionados](#repositórios-relacionados)
- [Equipe](#equipe)

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem / framework | Python 3.11+, Django 5.1 + Django REST Framework 3.15 |
| Banco de dados | PostgreSQL 15 (RDS gerenciado na AWS) |
| Infraestrutura | Docker + Docker Compose · Kubernetes (EKS na AWS, kind local) · Terraform (IaC) |
| Autenticação | `djangorestframework-simplejwt` (funcionário) + JWT RS256 externo validado em `atendimento/authentication.py` (cliente) |
| Observabilidade | New Relic APM/Logs/Custom Events, correlação W3C Trace Context |
| CI/CD | GitHub Actions (`ci.yml`, `cd.yml`) → build, testes, Docker, push ECR, deploy EKS |
| Qualidade | `pytest-django` + `pytest-cov`, SonarQube Community 26.4, `drf-spectacular` (OpenAPI 3.0) |

---

## Arquitetura

```mermaid
flowchart LR
    Cliente(["Cliente<br/>(app/Postman)"]) -->|"POST /auth<br/>Bearer JWT cliente"| APIGW["API Gateway"]
    Func(["Funcionário<br/>(Swagger/Postman)"]) -->|"Bearer JWT<br/>/api/token/"| APIGW
    APIGW -->|"ANY /{proxy+}<br/>VPC Link"| ALB["ALB interno"]
    ALB --> PODS["Pods Django<br/>(Deployment, HPA 2–6)"]
    PODS --> RDS[("RDS PostgreSQL 15")]
    PODS -.->|"APM, logs, custom events"| NR["New Relic"]
    LAMBDA["Lambda CPF→JWT<br/>(repo auth)"] --- APIGW
```

Este é um recorte simplificado. O diagrama completo de componentes (VPC, subnets, Secrets
Manager, ECR, GitHub Actions, New Relic) está em
[`docs/arquitetura/diagrama-componentes-nuvem.md`](docs/arquitetura/diagrama-componentes-nuvem.md).
Os fluxos de autenticação e de abertura de OS, passo a passo, estão em
[`docs/arquitetura/diagrama-sequencia-autenticacao.md`](docs/arquitetura/diagrama-sequencia-autenticacao.md)
e [`docs/arquitetura/diagrama-sequencia-abertura-os.md`](docs/arquitetura/diagrama-sequencia-abertura-os.md).
O C4 Model (Contexto → Container → Componente → Sequência) está em
[`docs/arquitetura/c4-model.md`](docs/arquitetura/c4-model.md), com as imagens renderizadas em
[`docs/images/`](docs/images/).

A aplicação em si é um monolito modular Django com Clean Architecture/Hexagonal pragmática: os
fluxos legados (Fase 1) continuam em `models.py`/`serializers.py`/`views.py`, e os fluxos novos da
Fase 2 (abertura de OS, fila operacional, aprovação de orçamento) vivem em `domain/`,
`application/`, `infrastructure/` e `interfaces/` dentro do app `atendimento`. Detalhes em
[`docs/arquitetura/arquitetura-hexagonal-clean-fase2.md`](docs/arquitetura/arquitetura-hexagonal-clean-fase2.md).

---

## Como executar

### Com Docker (recomendado)

```bash
git clone https://github.com/helyomendesdev/tech-challenge-oficina.git
cd tech-challenge-oficina
cp .env.example .env
# Edite o .env com uma SECRET_KEY segura e as demais credenciais
docker compose up --build
docker exec -it oficina_app python manage.py createsuperuser
# Opcional: dados de exemplo
docker exec oficina_app python manage.py loaddata initial_data.json seed_data.json
```

A API estará em `http://localhost:8000`.

### Sem Docker

```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # defina DJANGO_SECRET_KEY, POSTGRES_PASSWORD e DB_HOST=localhost
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Kubernetes (kind) e Terraform

Para um cluster local completo (Deployment, HPA, Secret dinâmico, smoke test) ou provisionamento
via Terraform, use `scripts/kind-deploy.ps1`/`.sh` ou `infra/deploy.ps1` — comandos e detalhes em
[`infra/README.md`](infra/README.md).

---

## Deploy e ambientes

O CI (`ci.yml`) roda em todo push/PR: instala dependências, `python manage.py check`, os 210
testes com `pytest-django` e um build Docker de validação. O CD (`cd.yml`) dispara em push para
`main` e `develop`: build da imagem → autenticação AWS → push no ECR (tag = git sha) →
`kubectl set image` no EKS → `rollout status`.

A autenticação AWS do CD tem dois modos, escolhidos pelo secret `AWS_ROLE_ARN`: **OIDC** (role
IAM, sem chave estática) quando ele está definido, e **credenciais temporárias do AWS Academy**
(`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) quando não está. Como o
Academy não permite criar provider OIDC, o modo usado de fato é o segundo — e as credenciais
expiram a cada sessão do laboratório, então precisam ser reatualizadas nos secrets antes de cada
deploy. Detalhes em [ADR-006](docs/adrs/adr-006-cicd-aws-ecr-eks.md).

**Configurado × validado (12/09/2026):**

| Item | Configurado | Validado |
|---|---|---|
| CI: build, `check`, 210 testes, Docker build | ✅ | ✅ check verde em `main` |
| CD: build → ECR → `kubectl set image` | ✅ | ❌ nenhuma execução verde do `cd.yml` atual; depende de secrets AWS válidos |
| Deploy em **homologação** (EKS + RDS + API Gateway) | ✅ | ✅ manual, em 08/09/2026 (imagem no ECR e Deployment atualizados à mão; fluxo API Gateway → ALB → EKS → RDS testado ponta a ponta) |
| Deploy em **produção** | parcial | ❌ nenhum recurso de produção foi provisionado; `main` → `producao` existe só como environment e `SERVICE_ENVIRONMENT` |
| Observabilidade (New Relic) | ✅ | parcial — APM, eventos e dashboard com dados em 08/09; logs e CPU/memória do cluster dependem de PRs abertos no repositório k8s |

Como a infraestrutura é efêmera, "validado" significa que funcionou na sessão indicada, não que
esteja no ar agora.

A infraestrutura roda em **AWS Academy** (conta de estudante, `us-east-1`) e é **efêmera** — a
sessão do laboratório expira em poucas horas e `terraform destroy` faz parte da rotina. Por isso
nenhuma URL fixa aparece neste repositório: o `<api-id>` do API Gateway muda a cada recriação.
Motivos em [RFC-005](docs/rfcs/rfc-005-escolha-nuvem-aws.md).

| Branch | Ambiente | `SERVICE_ENVIRONMENT` | App no New Relic |
|---|---|---|---|
| `develop` | Homologação | `homologacao` | `oficina-api-hml` |
| `main` | Produção (**não provisionado**) | `producao` | `oficina-api-prd` (sem dados) |

**Padrão de URL na AWS:** `https://<api-id>.execute-api.us-east-1.amazonaws.com/homologacao/`
(hoje só o ambiente de homologação está provisionado). Localmente, a base é `http://localhost:8000`.
Para descobrir o `<api-id>` da sessão atual: `aws apigateway get-rest-apis --query "items[].{id:id,name:name}"`.

Onde cada componente vive e quem o provisiona:
[`docs/arquitetura/diagrama-componentes-nuvem.md`](docs/arquitetura/diagrama-componentes-nuvem.md).

---

## Exemplos de uso da API

Todos os exemplos usam `http://localhost:8000` como base. Na AWS, troque pela URL do stage
(`https://<api-id>.execute-api.us-east-1.amazonaws.com/homologacao`) e prefixe o caminho do
`/auth` e do `proxy` conforme a tabela acima. Os corpos e campos abaixo vêm de
`atendimento/serializers.py`, `atendimento/views.py` e `atendimento/authentication.py`. Os
tokens abaixo são fictícios (formato ilustrativo, não credenciais reais).

### 1. Login do funcionário

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "SENHA_DO_ENV"}'
```

```json
{ "refresh": "TOKEN_REFRESH_FICTICIO", "access": "TOKEN_ACCESS_FICTICIO" }
```

### 2. Cadastrar cliente

```bash
curl -X POST http://localhost:8000/api/v1/clientes/ \
  -H "Authorization: Bearer TOKEN_ACCESS_FICTICIO" \
  -H "Content-Type: application/json" \
  -d '{"nome": "Carlos Mendes", "documento": "52998224725", "email": "EMAIL_DO_CLIENTE", "telefone": "TELEFONE_DO_CLIENTE"}'
```

```json
{ "id": 3, "nome": "Carlos Mendes", "documento": "52998224725", "ativo": true, "criado_em": "2026-09-11T12:00:00Z" }
```

### 3. Cadastrar veículo do cliente

```bash
curl -X POST http://localhost:8000/api/v1/veiculos/ \
  -H "Authorization: Bearer TOKEN_ACCESS_FICTICIO" \
  -H "Content-Type: application/json" \
  -d '{"cliente": 3, "placa": "MNO3456", "marca": "HYUNDAI", "modelo": "HB20", "ano": 2020}'
```

```json
{ "id": 4, "cliente": 3, "placa": "MNO3456", "marca": "HYUNDAI", "modelo": "HB20", "ano": 2020 }
```

### 4. Abrir Ordem de Serviço

```bash
curl -X POST http://localhost:8000/api/v1/ordens-servico/ \
  -H "Authorization: Bearer TOKEN_ACCESS_FICTICIO" \
  -H "Content-Type: application/json" \
  -d '{"cliente": 3, "veiculo": 4}'
```

```json
{ "id": 6, "status": "RECEBIDA", "cliente": 3, "veiculo": 4, "valor_total": "0.00" }
```

### 5. Avançar o status da OS (máquina de estados)

Transições não usam `PATCH` — cada uma tem um endpoint próprio
(ver [Regras de negócio](#regras-de-negócio)):

```bash
curl -X POST http://localhost:8000/api/v1/ordens-servico/6/iniciar-diagnostico/ \
  -H "Authorization: Bearer TOKEN_ACCESS_FICTICIO"
```

```json
{ "id": 6, "status": "DIAGNOSTICO", "valor_total": "0.00" }
```

### 6. Aprovar orçamento

Após `finalizar-diagnostico/` a OS chega a `AGUARDANDO`; a partir daí:

```bash
curl -X POST http://localhost:8000/api/v1/ordens-servico/6/aprovar-orcamento/ \
  -H "Authorization: Bearer TOKEN_ACCESS_FICTICIO"
```

```json
{ "id": 6, "status": "EXECUCAO", "data_inicio_execucao": "2026-09-11T12:05:00Z" }
```

### 7. Autenticação de cliente por CPF (Lambda, via API Gateway)

```bash
curl -X POST https://<api-id>.execute-api.us-east-1.amazonaws.com/homologacao/auth \
  -H "Content-Type: application/json" \
  -d '{"cpf": "15350946056"}'
```

```json
{ "access_token": "TOKEN_RS256_CLIENTE_FICTICIO", "token_type": "Bearer", "expires_in": 900 }
```

### 8. Chamada protegida com o token de cliente

`ClienteJWTAuthentication` identifica o cliente por `cliente_id`; o veículo de outro cliente nunca
aparece na lista:

```bash
curl http://localhost:8000/api/v1/veiculos/ \
  -H "Authorization: Bearer TOKEN_RS256_CLIENTE_FICTICIO"
```

```json
{ "count": 1, "next": null, "previous": null, "results": [
  { "id": 4, "placa": "MNO3456", "marca": "HYUNDAI", "modelo": "HB20", "ano": 2020 }
] }
```

### 9. Ação fora do escopo do cliente → 403

Cliente JWT só tem `list`/`retrieve` liberado em veículos e OS, e nenhuma action em clientes
(`cliente_jwt_allowed_actions`, `atendimento/views.py`):

```bash
curl -X POST http://localhost:8000/api/v1/clientes/ \
  -H "Authorization: Bearer TOKEN_RS256_CLIENTE_FICTICIO" \
  -H "Content-Type: application/json" \
  -d '{"nome": "Outro Cliente", "documento": "12345678909", "email": "EMAIL_TESTE", "telefone": "TELEFONE_TESTE"}'
```

```json
{ "erro": true, "status_code": 403, "mensagem": "Você não tem permissão para executar essa ação." }
```

---

## Swagger e Postman

| Interface | URL |
|---|---|
| Swagger UI | `http://localhost:8000/api/schema/swagger-ui/` |
| ReDoc | `http://localhost:8000/api/schema/redoc/` |
| Schema OpenAPI (JSON) | `http://localhost:8000/api/schema/` |

O schema validado tem **34 caminhos e 60 operações**; Swagger e ReDoc são derivados dele.

Para testar com Postman: importe [`postman_collection.json`](postman_collection.json) e
[`postman_environment.json`](postman_environment.json) (**File → Import**, selecione os dois
arquivos), escolha o environment **"Oficina Local"** e rode **Autenticação → Obter Token** — o
token é salvo automaticamente para as demais 76 requisições da collection.

---

## Referência rápida de endpoints

| Método | Rota | Quem pode |
|---|---|---|
| `POST` | `/api/token/`, `/api/token/refresh/` | Público |
| `GET/POST/PUT/PATCH/DELETE` | `/api/v1/clientes/` | Funcionário |
| `GET/POST/PUT/PATCH/DELETE` | `/api/v1/veiculos/` | Funcionário (escrita) · Cliente JWT (`list`/`retrieve` do próprio) |
| `GET/POST/PUT/DELETE` | `/api/v1/servicos/`, `/api/v1/pecas/` | Funcionário |
| `GET/POST/PUT/PATCH/DELETE` | `/api/v1/ordens-servico/` | Funcionário (escrita) · Cliente JWT (`list`/`retrieve` do próprio) |
| `GET` | `/api/v1/ordens-servico/consulta-cliente/` | Público (funcionário: por placa/CPF) · Cliente JWT (próprias OS) |
| `POST` | `/api/v1/ordens-servico/{id}/{iniciar-diagnostico,finalizar-diagnostico,aprovar-orcamento,recusar-orcamento,finalizar,entregar,cancelar}/` | Funcionário |
| `POST` | `/api/v1/ordens-servico/abrir/`, `GET /{id}/status/`, `GET /fila/` | Funcionário |
| `POST` | `/api/v1/simulacao/orcamento/`, `/api/v1/orcamentos/notificacoes/`, `/status-notificacoes/` | Funcionário |
| `GET/POST/PUT/DELETE` | `/api/v1/itens-pecas/` | Funcionário |
| `GET/POST/DELETE` + `/iniciar/`, `/finalizar/` | `/api/v1/ordens-servico/{os_id}/servicos/...` | Funcionário |
| `GET` | `/api/v1/ordens-servico/{os_id}/metricas/`, `/metricas/tempo-medio/` | Funcionário |
| `GET` | `/health/live/`, `/health/ready/` | Público (probes) |

Filtros, busca e ordenação de cada recurso (ex.: `?status=`, `?cliente=`, `?estoque_zerado=true`,
`?ordering=`) estão documentados no Swagger de cada endpoint.

---

## Regras de negócio

```mermaid
stateDiagram-v2
    [*] --> RECEBIDA
    RECEBIDA --> DIAGNOSTICO: iniciar-diagnostico
    DIAGNOSTICO --> AGUARDANDO: finalizar-diagnostico
    AGUARDANDO --> EXECUCAO: aprovar-orcamento
    AGUARDANDO --> DIAGNOSTICO: recusar-orcamento
    AGUARDANDO --> CANCELADA: cancelar
    EXECUCAO --> FINALIZADA: finalizar
    FINALIZADA --> ENTREGUE: entregar
    ENTREGUE --> [*]
    CANCELADA --> [*]
```

- O status da OS **não pode ser alterado via `PATCH`** — cada seta acima é um endpoint dedicado.
- `documento` do cliente exige CPF (11 dígitos) ou CNPJ (14 dígitos) com dígito verificador válido.
- `placa` aceita formato antigo (`ABC1234`) ou Mercosul (`ABC1D23`).
- Peça adicionada a uma OS debita o estoque automaticamente; removida, devolve.
- Cada serviço dentro da OS tem ciclo próprio (`PENDENTE → EM_EXECUCAO → CONCLUIDO`); a OS só
  finaliza quando todos os serviços estão concluídos e todas as peças foram consumidas.
- `valor_total = Σ(serviços) + Σ(peças × quantidade)`, recalculado a cada mudança.
- Cliente JWT só acessa `list`/`retrieve` de veículos e OS do próprio `cliente_id`; qualquer outra
  action recebe `403`.

Detalhamento completo (validações, automações, gates de finalização, rate limiting e o simulador
de orçamento) em [`docs/regras-de-negocio.md`](docs/regras-de-negocio.md).

---

## Testes e qualidade

```bash
source .venv/bin/activate
pytest --cov=atendimento --cov-report=term-missing        # rodar com cobertura
pytest --cov=atendimento --cov-report=xml:coverage.xml    # relatório para o SonarQube
```

| Métrica | Valor |
|---|---|
| Testes | **210 passando** + 3 subtests |
| Cobertura | **94,52%** (meta ≥ 80%) |
| Schema OpenAPI | 34 caminhos · 60 operações · validação sem erros |
| SonarQube (relatório histórico) | 0 bugs · 0 vulnerabilidades · 0 code smells · Rating A |
| OWASP Top 10 (avaliação histórica) | 9/10 conformantes · 1/10 parcialmente |

Os testes cobrem modelo (cálculo de total, estoque, timestamps), API (CRUD, JWT, transições
válidas/inválidas), o endpoint público de consulta, filtros, formato de erros, isolamento por
usuário/cliente JWT e os fluxos de serviço por OS (iniciar/finalizar, métricas). Relatório
completo em [`docs/relatorio_qualidade_seguranca.md`](docs/relatorio_qualidade_seguranca.md); o
SonarQube não foi reexecutado nesta revisão documental, então os números do relatório são
históricos e não devem ser confundidos com os checks locais atuais.

---

## Documentação

| Categoria | Onde está |
|---|---|
| Estrutura do repositório | [`docs/estrutura-do-projeto.md`](docs/estrutura-do-projeto.md) |
| Variáveis de ambiente (completo) | [`docs/variaveis-de-ambiente.md`](docs/variaveis-de-ambiente.md) |
| Operação (limitações, segurança em produção) | [`docs/operacao.md`](docs/operacao.md) |
| Regras de negócio (completo) | [`docs/regras-de-negocio.md`](docs/regras-de-negocio.md) |
| ADRs | [001 Django+DRF](docs/adrs/adr-001-django-drf.md) · [002 PostgreSQL](docs/adrs/adr-002-postgresql.md) · [003 Docker](docs/adrs/adr-003-docker.md) · [004 Monolito](docs/adrs/adr-004-monolito.md) · [005 Hexagonal/Clean](docs/adrs/adr-005-arquitetura-hexagonal-clean.md) · [006 CI/CD AWS](docs/adrs/adr-006-cicd-aws-ecr-eks.md) · [007 Trace Context](docs/adrs/adr-007-correlacao-w3c-trace-context.md) · [008 New Relic](docs/adrs/adr-008-observabilidade-new-relic.md) |
| RFCs | [001 Estado da OS](docs/rfcs/rfc-001-estado-os.md) · [002 Estoque](docs/rfcs/rfc-002-controle-estoque.md) · [003 JWT/Throttling](docs/rfcs/rfc-003-autenticacao-jwt.md) · [004 Logs JSON](docs/rfcs/rfc-004-logs-estruturados-json.md) · [005 Escolha da nuvem](docs/rfcs/rfc-005-escolha-nuvem-aws.md) · [006 Auth CPF+JWT](docs/rfcs/rfc-006-autenticacao-cpf-jwt.md) |
| Design e requisitos | [HLD](docs/design/hld.md) · [LLD](docs/design/lld.md) · [DAS](docs/das/design-approval-sheet.md) · [Requisitos Funcionais](docs/requisitos/requisitos-funcionais.md) · [Requisitos Não Funcionais](docs/requisitos/requisitos-nao-funcionais.md) |
| Fase 2 — entrega | [Matriz de requisitos](docs/matriz-requisitos-fase1-fase2.md) · [Checklist de entrega](docs/checklist-entrega-fase2.md) · [Justificativa do banco](docs/justificativa-banco-dados.md) |
| Fase 3 — repositórios e observabilidade | [Estrutura dos repositórios](docs/fase3/estrutura-repositorios.md) · [Integração entre repositórios](docs/fase3/integracao-repositorios.md) · [Matriz de permissões Cliente JWT](docs/fase3/matriz-permissoes-cliente-jwt.md) · [Observabilidade](docs/fase3/observabilidade/README.md) |
| DDD | [Domain Storytelling](https://miro.com/app/board/uXjVHZ-qZuY=/?share_link_id=271439252192) · [Event Storming](https://miro.com/app/board/uXjVGyBSvFg=/?share_link_id=970374301740) · [Linguagem Ubíqua](https://www.notion.so/Linguaguem-Ub-qua-Fase-1-Grupo-26-353ca0515ab080f08a7ce45530779ed8?pvs=21) |

---

## Repositórios relacionados

Grupo 80 — todos em `github.com/helyomendesdev`:

- [`tech-challenge-oficina`](https://github.com/helyomendesdev/tech-challenge-oficina) — esta aplicação Django, executada no EKS.
- [`tech-challenge-oficina-auth`](https://github.com/helyomendesdev/tech-challenge-oficina-auth) — autenticação serverless por CPF e emissão de JWT.
- [`tech-challenge-oficina-k8s`](https://github.com/helyomendesdev/tech-challenge-oficina-k8s) — infraestrutura Kubernetes.
- [`tech-challenge-oficina-database`](https://github.com/helyomendesdev/tech-challenge-oficina-database) — banco gerenciado (RDS) provisionado por Terraform.

---

## Equipe

### Grupo 80 — Fase 3 (atual)

| Nome | RM | Fase 3 |
|---|---|---|
| Hélio Mendes da Silva | RM374170 | nomes, estrutura e governança dos repositórios |
| Lucas Marques | RM369825 | autenticação |
| Luís Fernando Montes | RM367183 | observabilidade |
| Sophia Sussa Campos Bastos | RM371864 | infraestrutura |

### Grupo 13 — Fase 2 (anterior)

| Nome | RM |
|---|---|
| Afonso Victoriano Franco | RM373563 |
| Hélio Mendes da Silva | RM374170 |
| João Pedro Rodrigues Martins | RM372818 |
| Luís Fernando Montes | RM367183 |
| Sophia Sussa Campos Bastos | RM371864 |

---

*Tech Challenge — Fases 1, 2 e 3 — Pós-graduação Software Architecture · FIAP · Grupo 26 (Fase 1) → Grupo 13 (Fase 2) → Grupo 80 (Fase 3)*
