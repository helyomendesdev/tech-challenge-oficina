# ADR-001 — Uso do Django com Django REST Framework

| Informação | Valor |
|---|---|
| **ADR** | 001 |
| **Título** | Uso do Django 5.1 com Django REST Framework 3.15 |
| **Status** | Aceito |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Contexto

O Tech Challenge da Fase 1 exige a construção de uma API REST completa para gerenciamento de uma oficina mecânica. O time precisa entregar em poucas semanas um sistema funcional com autenticação, CRUDs, regras de negócio, filtros e testes.

## 2. Decisão

Utilizar **Django 5.1** como framework web e **Django REST Framework (DRF) 3.15** como toolkit para construção da API REST.

## 3. Justificativa

| Critério | Avaliação |
|---|---|
| **Produtividade** | Django ORM, admin, migrations e DRF Serializers/ViewSets aceleram drasticamente o desenvolvimento |
| **Maturidade** | Django existe há 20 anos; DRF é o padrão de facto para APIs REST em Python |
| **Segurança** | Proteção built-in contra SQL Injection, XSS, CSRF; DRF suporta autenticação JWT nativamente |
| **Ecossistema** | Bibliotecas maduras: `django-filter`, `djangorestframework-simplejwt`, `drf-spectacular` |
| **Testabilidade** | `pytest-django` e `django.test` oferecem suporte completo a testes unitários e de integração |
| **Curva de aprendizado** | A equipe já possui familiaridade com Python e Django |

## 4. Consequências

### Positivas
- Desenvolvimento rápido com scaffolding automático (migrations, admin, serializers)
- ORM robusto com suporte a transações, signals e raw queries quando necessário
- Documentação automática da API via OpenAPI 3.0 (`drf-spectacular`)

### Negativas
- Monolito pode se tornar um "big ball of mud" se não houver separação de responsabilidades
- Overhead do Django para APIs simples (comparado a FastAPI)
- ORM pode gerar queries N+1 se não usar `select_related` / `prefetch_related`

## 5. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| **FastAPI** | Menor ecossistema de bibliotecas; requer mais setup para admin e ORM completo |
| **Flask + SQLAlchemy** | Mais flexível, mas exige configuração manual de muitos componentes que Django já tem prontos |
| **Spring Boot (Java)** | Curva de aprendizado maior para o time; maior verbosidade |

## 6. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial |
