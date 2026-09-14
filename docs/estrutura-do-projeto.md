# Estrutura do Projeto

Visão geral do repositório `tech-challenge-oficina`. Referenciado a partir do
[`README.md`](../README.md).

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
│   ├── authentication.py        # ClienteJWTAuthentication (JWT RS256 externo)
│   ├── permissions.py           # ClienteJWTViewSetPermission e afins
│   ├── signals.py               # Signals legados limpos; estoque fica em ItemPecaOS
│   ├── tests/
│   │   ├── application/         # Testes dos use cases da Fase 2
│   │   ├── domain/              # Policies, services e value objects
│   │   └── integration/         # APIs, isolamento, saúde e métricas
│   ├── domain/                  # DDD tático: enums, policies, VOs, exceptions e services puros
│   ├── application/             # DTOs, ports e use cases sem dependência de HTTP/ORM
│   ├── infrastructure/          # Repositories Django ORM, transactions e notificação fake
│   ├── interfaces/              # APIViews/serializers/urls dos endpoints novos
│   ├── migrations/               # Histórico de schema do banco
│   └── fixtures/
│       ├── initial_data.json    # Dado base (1 cliente, 1 veículo...)
│       └── seed_data.json       # Dados de exemplo para desenvolvimento
├── docs/
│   ├── adrs/                    # Decisões arquiteturais
│   ├── arquitetura/             # C4, arquitetura híbrida e diagramas de nuvem/sequência
│   ├── requisitos/              # Requisitos funcionais e não funcionais
│   ├── regras-de-negocio.md     # Máquina de estados, validações e automações (detalhado)
│   ├── estrutura-do-projeto.md  # Este arquivo
│   ├── variaveis-de-ambiente.md # Referência completa do .env
│   ├── operacao.md              # Rate limiting, simulação de orçamento, limitações e segurança
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
