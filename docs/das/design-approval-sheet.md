# Design Approval Sheet (DAS) — Fase 1

| Informação | Valor |
|---|---|
| **Projeto** | Tech Challenge Fase 1 — Oficina Mecânica API |
| **Grupo** | 26 |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |
| **Status** | ✅ Aprovado |

---

## 1. Objetivo

Este documento consolida a aprovação do design arquitetural e técnico da Fase 1 do Tech Challenge, garantindo que todos os requisitos funcionais e não funcionais estão endereçados.

---

## 2. Checklist de Aprovação

### 2.1 Arquitetura

| # | Item | Status | Evidência |
|---|---|---|---|
| 1 | C4 Model documentado (Context, Container, Component, Code) | ✅ | `docs/arquitetura/c4-model.md` |
| 2 | RFCs aprovadas e revisadas | ✅ | `docs/rfcs/rfc-001`, `rfc-002`, `rfc-003` |
| 3 | ADRs registradas com justificativas | ✅ | `docs/adrs/adr-001` a `adr-004` |
| 4 | HLD e LLD completos | ✅ | `docs/design/hld.md`, `lld.md` |
| 5 | Requisitos funcionais rastreados | ✅ | `docs/requisitos/requisitos-funcionais.md` |
| 6 | Requisitos não funcionais rastreados | ✅ | `docs/requisitos/requisitos-nao-funcionais.md` |

### 2.2 Implementação

| # | Item | Status | Evidência |
|---|---|---|---|
| 7 | API REST funcional com CRUD completo | ✅ | `atendimento/views.py`, `urls.py` |
| 8 | Autenticação JWT implementada | ✅ | `djangorestframework-simplejwt` + `auth_views.py` |
| 9 | Máquina de estados da OS validada | ✅ | `serializers.py` + `models.py` |
| 10 | Controle de estoque com baixa automática | ✅ | `ItemPecaOS.save()` / `delete()` |
| 11 | Consumo de peças por serviço (atômico) | ✅ | `ItemServicoOSViewSet.iniciar()` |
| 12 | Cálculo automático do valor total | ✅ | `OrdemServico.calcular_total()` + Signals |
| 13 | Consulta pública de OS | ✅ | `OrdemServicoViewSet.consulta_cliente()` |
| 14 | Rate limiting implementado | ✅ | `throttles.py` + config DRF |
| 15 | Filtros avançados por status, data, valor | ✅ | `filters.py` |

### 2.3 Qualidade e Segurança

| # | Item | Status | Evidência |
|---|---|---|---|
| 16 | Cobertura de testes ≥ 80% | ✅ | 94% (`pytest --cov`) |
| 17 | Testes passando | ✅ | 194/194 passando + 3 subtests |
| 18 | Análise SAST (SonarQube) | ✅ | 0 bugs, 0 vulnerabilidades, Rating A |
| 19 | OWASP Top 10 avaliado | ✅ | 9/10 conformes, 1 parcial |
| 20 | Formato padronizado de erros | ✅ | `exceptions.py` |
| 21 | Logs de auditoria de segurança | ✅ | `signals.py` (security logger) |
| 22 | Proteções de produção (HTTPS, HSTS) | ✅ | `settings.py` (modo DEBUG=False) |
| 23 | Schema OpenAPI válido | ✅ | 0 erros; 2 warnings não bloqueantes de enum `status` |

### 2.4 Documentação e Entrega

| # | Item | Status | Evidência |
|---|---|---|---|
| 23 | README completo e atualizado | ✅ | `README.md` |
| 24 | Documentação interativa (Swagger/ReDoc) | ✅ | `drf-spectacular` |
| 25 | Collection Postman incluída | ✅ | `postman_collection.json` |
| 26 | Docker Compose funcional | ✅ | `docker-compose.yml` |
| 27 | Variáveis de ambiente documentadas | ✅ | `.env.example` |
| 28 | Domain Storytelling vinculado | ✅ | Link no README |
| 29 | Event Storming vinculado | ✅ | Link no README |
| 30 | Linguagem Ubíqua vinculada | ✅ | Link no README |

---

## 3. Resumo de Conformidade

| Categoria | Itens | Aprovados | % |
|---|---|---|---|
| Arquitetura | 6 | 6 | 100% |
| Implementação | 9 | 9 | 100% |
| Qualidade e Segurança | 7 | 7 | 100% |
| Documentação e Entrega | 8 | 8 | 100% |
| **Total** | **30** | **30** | **100%** |

---

## 4. Riscos Identificados e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Monolito se tornar difícil de escalar | Média | Médio | Código modularizado em app Django separado; preparado para extração futura |
| Estoque inconsistente em concorrência | Baixa | Alto | Uso de `save()` com validação + possível evolução para `select_for_update()` |
| Falta de notificações ao cliente | Alta | Médio | Planejado para Fase 2 (integração com sistema de e-mail/SMS) |
| Ausência de relatórios gerenciais | Média | Médio | Planejado para Fase 2 (dashboard e exportação PDF) |
| Falta de CI/CD automatizado | Média | Baixo | Planejado para Fase 2 (GitHub Actions + deploy automatizado) |

---

## 5. Próximos Passos (Fase 2)

1. **Notificações:** Integrar com serviço de e-mail/SMS para alertar cliente quando OS mudar de status
2. **Relatórios:** Dashboard com métricas de produtividade, faturamento e estoque
3. **CI/CD:** Pipeline GitHub Actions com testes, SAST e deploy automatizado
4. **Escalabilidade:** Avaliação de extração de módulos para microsserviços (ex: estoque, faturamento)
5. **Cache:** Introduzir Redis para cache de consultas frequentes (ex: catálogo de peças)

---

## 6. Aprovações

| Função | Nome | Data | Assinatura |
|---|---|---|---|
| Arquiteto de Software | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) | 2026-04-28 | ✅ Aprovado |
| Tech Lead | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) | 2026-04-28 | ✅ Aprovado |
| Product Owner | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) | 2026-04-28 | ✅ Aprovado |

---

## 7. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial — Aprovação Fase 1 |
