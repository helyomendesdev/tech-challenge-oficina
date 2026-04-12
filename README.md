# Oficina Mecânica API

API REST para gerenciamento de uma oficina mecânica, desenvolvida como entrega do **Tech Challenge Fase 1** da pós-graduação em Software Architecture na FIAP.

## Sumário

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Como Rodar](#como-rodar)
- [Endpoints da API](#endpoints-da-api)
- [Autenticação](#autenticação)
- [Regras de Negócio](#regras-de-negócio)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Visão Geral

O sistema permite que uma oficina mecânica gerencie seu ciclo operacional completo:

- Cadastro de **clientes** (PF com CPF ou PJ com CNPJ)
- Cadastro de **veículos** vinculados a clientes
- Catálogo de **serviços** (mão de obra) e **peças** com controle de estoque
- Abertura e acompanhamento de **Ordens de Serviço** com status progressivo
- **Baixa automática de estoque** ao adicionar peças a uma OS
- **Cálculo automático do valor total** da OS (serviços + peças)
- Endpoint **público** para o cliente consultar o status da OS pela placa ou CPF/CNPJ

---

## Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| Framework | Django 5.1 + Django REST Framework |
| Banco de dados | PostgreSQL 15 |
| Autenticação | JWT via `djangorestframework-simplejwt` |
| Documentação | OpenAPI 3.0 via `drf-spectacular` (Swagger UI + ReDoc) |
| Validação de documentos | `validate-docbr` (CPF/CNPJ) |
| Análise de segurança | `bandit` |
| Testes | `pytest-django` + `pytest-cov` |
| Infraestrutura | Docker + Docker Compose |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   Cliente HTTP                       │
│         (Postman / Swagger UI / Frontend)            │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────┐
│              Django REST Framework                   │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────┐  │
│  │  Views   │  │ Serializers │  │  Permissions   │  │
│  │(ViewSets)│  │(Validação)  │  │  (JWT Auth)    │  │
│  └────┬─────┘  └──────┬──────┘  └────────────────┘  │
│       │               │                              │
│  ┌────▼───────────────▼──────────────────────────┐  │
│  │                 Models + Signals               │  │
│  │  (Regras de negócio, cálculos, estoque)        │  │
│  └────────────────────┬──────────────────────────┘  │
└───────────────────────┼─────────────────────────────┘
                        │ Django ORM
┌───────────────────────▼─────────────────────────────┐
│                  PostgreSQL 15                       │
└─────────────────────────────────────────────────────┘
```

### Fluxo de uma Ordem de Serviço

```
RECEBIDA → DIAGNOSTICO → AGUARDANDO → EXECUCAO → FINALIZADA → ENTREGUE
                                          ↑               ↑
                               data_inicio_execucao  data_finalizacao
                               (auto-preenchido)     (auto-preenchido)
```

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/)

> Para rodar sem Docker: Python 3.11+ e PostgreSQL 15+

---

## Como Rodar

### Com Docker (recomendado)

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd tech-challenge-fase-1-oficina

# 2. Suba os containers (banco + API)
docker-compose up --build

# 3. Em outro terminal, crie o superusuário
docker exec -it oficina_app python manage.py createsuperuser

# 4. Carregue os dados de exemplo
docker exec oficina_app python manage.py loaddata initial_data.json
docker exec oficina_app python manage.py loaddata seed_data.json
```

A API estará disponível em `http://localhost:8000`.

### Sem Docker

```bash
# Crie e ative o virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
export POSTGRES_DB=oficina_db
export POSTGRES_USER=admin
export POSTGRES_PASSWORD=admin_pass
export DB_HOST=localhost

# Aplique as migrations e crie o superusuário
python manage.py migrate
python manage.py createsuperuser

# Carregue os dados de exemplo
python manage.py loaddata initial_data.json
python manage.py loaddata seed_data.json

# Inicie o servidor
python manage.py runserver
```

---

## Endpoints da API

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
| `POST` | `/api/token/` | Obter access + refresh token | Não |
| `POST` | `/api/token/refresh/` | Renovar access token | Não |

#### Clientes

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/clientes/` | Listar clientes |
| `POST` | `/api/v1/clientes/` | Cadastrar cliente |
| `GET` | `/api/v1/clientes/{id}/` | Detalhar cliente |
| `PUT` | `/api/v1/clientes/{id}/` | Atualizar cliente |
| `PATCH` | `/api/v1/clientes/{id}/` | Atualizar parcialmente |
| `DELETE` | `/api/v1/clientes/{id}/` | Remover cliente |

#### Veículos

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/veiculos/` | Listar veículos |
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
| `PATCH` | `/api/v1/servicos/{id}/` | Atualizar parcialmente |
| `DELETE` | `/api/v1/servicos/{id}/` | Remover serviço |

#### Peças

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/pecas/` | Listar peças com estoque |
| `POST` | `/api/v1/pecas/` | Cadastrar peça |
| `GET` | `/api/v1/pecas/{id}/` | Detalhar peça e saldo |
| `PUT` | `/api/v1/pecas/{id}/` | Atualizar peça |
| `PATCH` | `/api/v1/pecas/{id}/` | Atualizar parcialmente |
| `DELETE` | `/api/v1/pecas/{id}/` | Remover peça |

#### Ordens de Serviço

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `GET` | `/api/v1/ordens-servico/` | Listar todas as OS | Sim |
| `POST` | `/api/v1/ordens-servico/` | Abrir nova OS | Sim |
| `GET` | `/api/v1/ordens-servico/{id}/` | Detalhar OS | Sim |
| `PUT` | `/api/v1/ordens-servico/{id}/` | Atualizar OS | Sim |
| `PATCH` | `/api/v1/ordens-servico/{id}/` | Avançar status / adicionar serviços | Sim |
| `DELETE` | `/api/v1/ordens-servico/{id}/` | Remover OS | Sim |
| `GET` | `/api/v1/ordens-servico/consulta-cliente/` | Consultar OS por placa ou CPF/CNPJ | **Não** |

#### Itens de Peças (OS)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/itens-pecas/` | Listar itens |
| `POST` | `/api/v1/itens-pecas/` | Adicionar peça à OS (baixa estoque) |
| `GET` | `/api/v1/itens-pecas/{id}/` | Detalhar item |
| `PUT` | `/api/v1/itens-pecas/{id}/` | Atualizar item |
| `DELETE` | `/api/v1/itens-pecas/{id}/` | Remover peça da OS |

---

## Autenticação

Todos os endpoints exigem autenticação via **Bearer Token (JWT)**, exceto a consulta pública de OS.

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

O `access_token` expira em 5 minutos. Use o `refresh_token` para renová-lo sem precisar se autenticar novamente.

---

## Regras de Negócio

### Validações de entrada

| Campo | Regra |
|---|---|
| `documento` (Cliente) | CPF válido (11 dígitos) ou CNPJ válido (14 dígitos), sem pontuação |
| `placa` (Veículo) | Formato antigo `ABC1234` ou Mercosul `ABC1D23` |
| `quantidade` (ItemPecaOS) | Não pode exceder o `estoque_atual` da peça |

### Automações

| Evento | Efeito automático |
|---|---|
| OS muda para `EXECUCAO` | `data_inicio_execucao` preenchida com o timestamp atual |
| OS muda para `FINALIZADA` | `data_finalizacao` preenchida com o timestamp atual |
| Peça adicionada a uma OS | `estoque_atual` decrementado; `valor_total` da OS recalculado |
| Peça removida de uma OS | `valor_total` da OS recalculado |
| Serviço adicionado/removido de uma OS | `valor_total` da OS recalculado |

### Cálculo do valor total

```
valor_total = Σ(servicos.valor_mao_de_obra) + Σ(itens_pecas.peca.valor_unitario × quantidade)
```

---

## Testes

```bash
# Rodar todos os testes
docker exec oficina_app pytest

# Com relatório de cobertura
docker exec oficina_app pytest --cov=atendimento --cov-report=term-missing

# Análise de segurança
docker exec oficina_app bandit -r atendimento/
```

Os testes seguem o padrão **AAA (Arrange → Act → Assert)** e cobrem:

- Cálculo automático do total de uma OS com peças
- Baixa automática de estoque ao adicionar peça a uma OS

---

## Testando com Postman

O repositório inclui uma collection e um environment Postman prontos para uso:

| Arquivo | Descrição |
|---|---|
| `postman_collection.json` | Todos os endpoints organizados por recurso, incluindo casos de erro |
| `postman_environment.json` | Variáveis de ambiente (base_url, credenciais, tokens) |

**Passos:**

1. No Postman: **File → Import** → selecione os dois arquivos
2. Selecione o environment **"Oficina Local"**
3. Preencha as variáveis `username` e `password`
4. Execute **Autenticação → Obter Token** — o token é salvo automaticamente
5. Todas as demais requisições já utilizam o token via Bearer

---

## Estrutura do Projeto

```
tech-challenge-fase-1-oficina/
├── app/                        # Configuração Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
├── atendimento/                # App principal
│   ├── models.py               # Entidades + validadores + signals
│   ├── serializers.py          # Serialização e validação de entrada
│   ├── views.py                # ViewSets (controllers)
│   ├── urls.py                 # Roteamento da API
│   ├── admin.py                # Django Admin customizado
│   ├── exceptions.py           # Handler de erros padronizado
│   ├── tests.py                # Testes unitários (padrão AAA)
│   ├── signals.py              # Recálculo automático de totais
│   ├── migrations/             # Histórico de schema do banco
│   └── fixtures/
│       ├── initial_data.json   # Dado base (1 cliente, 1 veículo...)
│       └── seed_data.json      # Dados de exemplo para desenvolvimento
├── docker-compose.yml          # PostgreSQL + Django
├── Dockerfile
├── requirements.txt
├── manage.py
├── postman_collection.json     # Collection Postman completa
└── postman_environment.json    # Environment Postman (local)
```

---

## Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `POSTGRES_DB` | `oficina_db` | Nome do banco de dados |
| `POSTGRES_USER` | `admin` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | `admin_pass` | Senha do PostgreSQL |
| `DB_HOST` | `db` | Host do banco (nome do serviço Docker) |
