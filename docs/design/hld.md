# High-Level Design (HLD) — Oficina Mecânica API

| Informação | Valor |
|---|---|
| **Documento** | High-Level Design |
| **Versão** | 1.0 |
| **Data** | 2026-04-28 |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |

---

## 1. Visão Geral

O **Oficina Mecânica API** é uma aplicação monolítica que expõe uma API REST para gerenciamento completo do ciclo operacional de uma oficina mecânica. O HLD descreve a arquitetura de alto nível, componentes principais, fluxo de dados e estratégias de segurança e deploy.

---

## 2. Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────────────┐
│  HTTP Client (Postman / Swagger UI / Frontend futuro)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ JSON / REST (Bearer JWT)
┌──────────────────────────▼──────────────────────────────────────┐
│  Nginx / Load Balancer (Fase 2)                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Gunicorn (WSGI) — 2 workers                                    │
│  Django 5.1 + Django REST Framework 3.15                        │
│                                                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │   Views    │  │Serializers │  │   Models   │  │  Signals  │ │
│  │  (DRF)     │  │+ Validação │  │  (ORM)     │  │ (Django)  │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬─────┘ │
│        │               │               │               │       │
│  ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐  ┌────▼────┐ │
│  │  Filters   │  │  Throttles │  │  Auth/JWT  │  │Exceptions│ │
│  │(django-    │  │  (rate     │  │(simplejwt) │  │(handler) │ │
│  │  filter)   │  │  limiting) │  │            │  │          │ │
│  └────────────┘  └────────────┘  └────────────┘  └──────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Django ORM
┌──────────────────────────▼──────────────────────────────────────┐
│  PostgreSQL 15                                                  │
│  + healthcheck (pg_isready)                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Componentes Principais

### 3.1 Web Application (Django/DRF)
- **Responsabilidade:** Receber requisições HTTP, autenticar, validar, processar regras de negócio e persistir dados
- **Tecnologia:** Python 3.11, Django 5.1, DRF 3.15
- **Deploy:** Container Docker com Gunicorn (2 workers)

### 3.2 Banco de Dados (PostgreSQL 15)
- **Responsabilidade:** Persistência relacional com ACID
- **Tecnologia:** PostgreSQL 15, imagem oficial Docker
- **Schema:** 8 tabelas principais (ver seção 5)

### 3.3 Documentação Interativa
- **Responsabilidade:** Documentação viva da API para desenvolvedores e avaliadores
- **Tecnologia:** `drf-spectacular` gerando OpenAPI 3.0, servido via Swagger UI e ReDoc

---

## 4. Fluxo de Dados

### 4.1 Fluxo Principal: Criação de OS

1. **Cliente HTTP** → `POST /api/v1/ordens-servico/` (Bearer JWT)
2. **ViewSet** (`OrdemServicoViewSet`) → Aplica throttling e autenticação
3. **Serializer** (`OrdemServicoSerializer`) → Valida cliente, veículo e dados
4. **Model** (`OrdemServico.save()`) → Persiste no PostgreSQL
5. **Signal** (`post_save`) → Recalcula valor total e loga auditoria
6. **Response** → JSON com OS criada (201 Created)

### 4.2 Fluxo de Segurança: Consulta Pública

1. **Cliente HTTP** → `GET /api/v1/ordens-servico/consulta-cliente/?placa=ABC1234`
2. **Throttle** (`ConsultaClienteThrottle`) → Verifica limite de 30 req/hora por IP
3. **ViewSet** → Busca OS pela placa (case-insensitive)
4. **Response** → JSON com status da OS (200 OK) ou 404

---

## 5. Modelo de Entidade-Relacionamento (ER)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Cliente   │◄──────│   Veiculo   │       │   Servico   │
├─────────────┤ 1:N   ├─────────────┤       ├─────────────┤
│ id (PK)     │       │ id (PK)     │       │ id (PK)     │
│ nome        │       │ placa (UQ)  │       │ descricao   │
│ documento   │       │ marca       │       │ valor_mao_  │
│ email       │       │ modelo      │       │   obra      │
│ telefone    │       │ ano         │       └──────┬──────┘
└──────┬──────┘       │ cliente (FK)│              │
       │              └─────────────┘              │
       │                                           │
       │  ┌────────────────────────────────────────┘
       │  │
       │  │    ┌─────────────────┐         ┌─────────────┐
       │  │    │ ItemServicoOS   │◄────────│    Peca     │
       │  │    ├─────────────────┤    N:1  ├─────────────┤
       │  └───►│ ordem_servico   │         │ id (PK)     │
       │       │ servico (FK)    │         │ nome        │
       │       │ status          │         │ valor_unit  │
       │       │ data_inicio     │         │ estoque_at  │
       │       │ data_finalizacao│         └──────┬──────┘
       │       └─────────────────┘                │
       │                                          │
       │       ┌─────────────────┐                │
       └──────►│  OrdemServico   │◄───────────────┘
               ├─────────────────┤         ┌─────────────┐
               │ id (PK)         │◄────────│ ItemPecaOS  │
               │ cliente (FK)    │   1:N   ├─────────────┤
               │ veiculo (FK)    │         │ os (FK)     │
               │ status          │         │ peca (FK)   │
               │ data_abertura   │         │ quantidade  │
               │ data_inicio_    │         │ qtd_utiliz  │
               │   execucao      │         └──────┬──────┘
               │ data_finalizacao│                │
               │ valor_total     │                │
               └─────────────────┘                │
                                                  │
                                           ┌──────▼──────┐
                                           │ConsumoItem  │
                                           │  Servico    │
                                           ├─────────────┤
                                           │ item_servico│
                                           │   _os (FK)  │
                                           │ item_peca   │
                                           │   _os (FK)  │
                                           │ quantidade  │
                                           └─────────────┘
```

---

## 6. Estratégia de Segurança

| Camada | Estratégia | Implementação |
|---|---|---|
| Transporte | HTTPS | `SECURE_SSL_REDIRECT = True` |
| Autenticação | JWT | `djangorestframework-simplejwt` |
| Autorização | Usuário autenticado | DRF `IsAuthenticated` |
| Rate Limiting | Throttling por classe | DRF `AnonRateThrottle`, `UserRateThrottle`, `ConsultaClienteThrottle` |
| Validação de entrada | Serializers + Validators | CPF/CNPJ via `validate-docbr`, placa via regex |
| Auditoria | Logs estruturados | `logging.getLogger('security')` + Signals |
| Headers de segurança | HSTS, CSP, X-Frame | Django SecurityMiddleware |

---

## 7. Estratégia de Deploy

| Ambiente | Método |
|---|---|
| **Desenvolvimento** | `docker-compose up --build` (API + PostgreSQL) |
| **Testes** | `pytest --cov=atendimento` (SQLite em memória via `settings_test.py`) |
| **Produção (Fase 2)** | Docker + Nginx reverse proxy + PostgreSQL managed |

---

## 8. Decisões de Design de Alto Nível

| Decisão | Justificativa |
|---|---|
| Monolito Django | Time pequeno, entrega rápida, transações ACID simples |
| PostgreSQL | ACID, JSONB para extensões, integração nativa com Django |
| Docker Compose | Um comando para subir toda a stack; reprodutibilidade garantida |
| JWT | Stateless; facilita múltiplos clientes futuros |
| Gunicorn | WSGI production-ready; múltiplos workers |

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial |
