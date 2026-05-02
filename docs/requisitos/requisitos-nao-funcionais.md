# Requisitos Não Funcionais — Oficina Mecânica API

| Informação | Valor |
|---|---|
| **Documento** | Requisitos Não Funcionais |
| **Versão** | 1.0 |
| **Data** | 2026-04-28 |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |

---

## 1. Introdução

Este documento descreve os requisitos não funcionais (RNFs) que definem qualidades do sistema como performance, segurança, disponibilidade e manutenibilidade.

---

## 2. Performance

### RNF001 — Tempo de Resposta
**Prioridade:** Alta

O sistema deve responder 95% das requisições em até **500ms** em condições normais de carga (até 50 requisições simultâneas).

**Métrica:** Latência P95 ≤ 500ms

### RNF002 — Throughput
**Prioridade:** Média

O sistema deve suportar **100 requisições/segundo** em pico sem degradação perceptível.

---

## 3. Disponibilidade

### RNF003 — Uptime
**Prioridade:** Alta

O sistema deve garantir **99,5% de disponibilidade** (máximo de 3,6 horas de indisponibilidade por mês).

---

## 4. Segurança

### RNF004 — Autenticação e Autorização
**Prioridade:** Alta

Todas as APIs (exceto endpoints de autenticação e consulta pública) devem exigir autenticação via JWT. Tokens devem expirar em 30 minutos (access) e 1 dia (refresh).

### RNF005 — Proteção contra Abuso
**Prioridade:** Alta

O sistema deve implementar rate limiting:
- 600 req/hora para usuários autenticados
- 60 req/hora para acessos anônimos
- 30 req/hora por IP no endpoint público de consulta de OS

### RNF006 — Conformidade OWASP Top 10
**Prioridade:** Alta

O sistema deve ser auditado contra o OWASP Top 10 2021. Meta: **9/10 categorias conformantes**, 1 parcialmente conformante.

### RNF007 — Proteção em Produção
**Prioridade:** Alta

Em produção (`DEBUG=False`), o sistema deve ativar:
- Redirecionamento HTTPS
- HSTS (1 ano)
- Cookies seguros
- Proteção contra clickjacking (X-Frame-Options: DENY)

---

## 5. Manutenibilidade

### RNF008 — Cobertura de Testes
**Prioridade:** Alta

O sistema deve manter cobertura de testes automatizados de **no mínimo 80%**.

**Métrica atual:** 88% (76 testes passando)

### RNF009 — Código Limpo
**Prioridade:** Média

O código deve passar em análise estática (SAST) sem bugs, vulnerabilidades ou code smells críticos. Meta: SonarQube Rating A em todas as dimensões.

**Métrica atual:** 0 bugs, 0 vulnerabilidades, 0 code smells

---

## 6. Usabilidade

### RNF010 — Documentação da API
**Prioridade:** Média

A API deve ser documentada automaticamente em OpenAPI 3.0, acessível via Swagger UI e ReDoc.

### RNF011 — Formato Padronizado de Erros
**Prioridade:** Média

Todos os erros da API devem seguir um formato JSON padronizado contendo: `erro`, `status_code`, `mensagem` e, quando aplicável, `campos`.

---

## 7. Escalabilidade

### RNF012 — Escalabilidade Horizontal
**Prioridade:** Baixa

A arquitetura deve permitir, em fases futuras, a execução de múltiplas instâncias da aplicação atrás de um load balancer.

---

## 8. Portabilidade

### RNF013 — Containerização
**Prioridade:** Alta

A aplicação deve executar completamente via Docker Compose com um único comando (`docker-compose up --build`), sem necessidade de configuração manual de ambiente.

---

## 9. Tabela de Rastreabilidade

| Requisito | Implementado em | Status |
|---|---|---|
| RNF001 | Gunicorn + PostgreSQL + índices Django ORM | Parcialmente medido |
| RNF002 | Arquitetura monolítica + Gunicorn (2 workers) | Parcialmente medido |
| RNF003 | Docker Compose + healthchecks | Configurado |
| RNF004 | `djangorestframework-simplejwt` | Conforme |
| RNF005 | `throttles.py` + config DRF | Conforme |
| RNF006 | SonarQube SAST + `pentest.py` | 9/10 conformes |
| RNF007 | `settings.py` (modo produção) | Conforme |
| RNF008 | `pytest` + `pytest-cov` | 88% — Conforme |
| RNF009 | SonarQube Community 26.4 | Rating A — Conforme |
| RNF010 | `drf-spectacular` + Swagger UI | Conforme |
| RNF011 | `exceptions.py` + handler DRF | Conforme |
| RNF012 | Stateless JWT + PostgreSQL externo | Preparado para Fase 2 |
| RNF013 | `docker-compose.yml` + `Dockerfile` | Conforme |
