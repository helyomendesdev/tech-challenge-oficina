# 🔧 Oficina Mecânica API

API REST para gerenciamento de uma oficina mecânica, desenvolvida como entrega do **Tech Challenge Fase 1** da pós-graduação em Software Architecture na FIAP.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.1-092E20?style=flat&logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.15-red?style=flat)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)
![Cobertura](https://img.shields.io/badge/Cobertura-88%25-brightgreen?style=flat)
![Testes](https://img.shields.io/badge/Testes-76%20passando-brightgreen?style=flat)
![SonarQube](https://img.shields.io/badge/SonarQube-A%20Rating-brightgreen?style=flat&logo=sonarqube&logoColor=white)
![OWASP](https://img.shields.io/badge/OWASP%20Top%2010-Conformante-brightgreen?style=flat)

---

## Sumário

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Como Rodar](#como-rodar)
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

---

## Visão Geral

O sistema permite que uma oficina mecânica gerencie seu ciclo operacional completo:

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
- **Filtros avançados** por status, data, valor, nome e estoque em todos os endpoints
- **Rate limiting** global e específico por endpoint

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
| Infraestrutura | Docker + Docker Compose |

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

### Fluxo de uma Ordem de Serviço

```
RECEBIDA → DIAGNOSTICO → AGUARDANDO → EXECUCAO → FINALIZADA → ENTREGUE
                                          ↑              ↑
                               data_inicio_execucao  data_finalizacao
                                  (auto-preenchido)  (auto-preenchido)
```

> Transições fora do fluxo acima são rejeitadas com `HTTP 400`.

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

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas credenciais e uma SECRET_KEY segura

# 3. Suba os containers (banco + API)
docker-compose up --build

# 4. Em outro terminal, crie o superusuário
docker exec -it oficina_app python manage.py createsuperuser

# 5. (Opcional) Carregue dados de exemplo
docker exec oficina_app python manage.py loaddata initial_data.json
docker exec oficina_app python manage.py loaddata seed_data.json
```

A API estará disponível em `http://localhost:8000`.

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
| `PATCH` | `/api/v1/ordens-servico/{id}/` | Avançar status / adicionar serviços | Sim |
| `DELETE` | `/api/v1/ordens-servico/{id}/` | Remover OS | Sim |
| `GET` | `/api/v1/ordens-servico/consulta-cliente/` | Consultar OS por placa ou CPF/CNPJ | **Não** |

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

---

## Filtros e Busca

Todos os endpoints suportam **paginação** (20 itens/página por padrão).

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

| Token | Validade |
|---|---|
| `access_token` | 30 minutos |
| `refresh_token` | 1 dia |

---

## Regras de Negócio

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
| **Serviço iniciado** (`/iniciar/`) | Status do serviço → `EM_EXECUCAO`; peças informadas são consumidas atomicamente; se for o primeiro serviço a iniciar em OS `AGUARDANDO`, a OS avança para `EXECUCAO` |
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
| Total de testes | **76 passando** |
| Cobertura geral | **88 %** |
| SonarQube Bugs | **0** |
| SonarQube Vulnerabilidades | **0** |
| SonarQube Code Smells | **0** |
| SonarQube Security Rating | **A** |
| OWASP Top 10 | **9/10 conformantes** · 1/10 parcialmente |

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
- **Iniciar serviço:** Peças consumidas atomicamente, cascade OS AGUARDANDO → EXECUCAO, erros de disponibilidade e estado
- **Finalizar serviço:** Tempo calculado, cascade OS → FINALIZADA, gate de peças não utilizadas
- **Métricas:** `tempo_execucao_minutos`, `pecas_consumidas`, filtro por serviço, isolamento por usuário

> 📄 Relatório completo de qualidade e segurança: [docs/relatorio_qualidade_seguranca.md](docs/relatorio_qualidade_seguranca.md)

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
3. Execute **Autenticação → Obter Token** — o token é salvo automaticamente
4. Todas as demais requisições já utilizam o token via Bearer

---

## Estrutura do Projeto

```
tech-challenge-fase-1-oficina/
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
│   ├── signals.py               # Signals post_save/post_delete para recálculo de totais
│   ├── tests.py                 # 76 testes (modelo + API + filtros + execução de serviços + métricas)
│   ├── migrations/              # Histórico de schema do banco
│   └── fixtures/
│       ├── initial_data.json    # Dado base (1 cliente, 1 veículo...)
│       └── seed_data.json       # Dados de exemplo para desenvolvimento
├── docs/
│   ├── images/                  # Diagramas e screenshots da API
│   └── relatorio_qualidade_seguranca.md  # Relatório SAST (SonarQube) + OWASP Top 10
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

A aplicação passa por análise estática de segurança (SAST via **SonarQube Community**) e mapeamento contra o **OWASP Top 10 (2021)** a cada ciclo de desenvolvimento.

| Dimensão | Resultado |
|---|---|
| Cobertura de testes | **88 %** (meta ≥ 80 %) |
| Testes passando | **76 / 76** |
| Bugs (SonarQube) | **0** — Rating A |
| Vulnerabilidades (SonarQube) | **0** — Rating A |
| Code Smells (SonarQube) | **0** — dívida técnica 0 min |
| Duplicação de código | **0,0 %** |
| OWASP Top 10 | **9/10 conformantes** · 1/10 parcialmente |

📄 **[Ver relatório completo → docs/relatorio_qualidade_seguranca.md](docs/relatorio_qualidade_seguranca.md)**

O relatório detalha:
- Análise SAST (SonarQube) com todos os issues identificados e resolvidos
- Avaliação de cada categoria OWASP Top 10
- Métricas de cobertura por módulo
- Code smells corrigidos e plano de remediação priorizado

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

*Tech Challenge Fase 1 — Pós-graduação Software Architecture · FIAP*
