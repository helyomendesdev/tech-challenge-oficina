# Relatório de Qualidade & Segurança — API Oficina Mecânica

> **Projeto:** tech-challenge-oficina  
> **Stack:** Python 3.13 · Django 5.1.15 · Django REST Framework 3.15.2  
> **Data da análise:** 2026-05-01  
> **Ferramentas:** SonarQube Community 26.4.0 (SAST) · pytest-cov 5.0.0 · Análise manual OWASP Top 10

---

## 1 · Visão Executiva

### 1.1 Resultados SonarQube — Análise Final

| Métrica | Valor | Rating | Status |
|---|---|---|---|
| Bugs | **0** | A | ✅ |
| Vulnerabilidades | **0** | A | ✅ |
| Code Smells | **0** | A | ✅ |
| Security Hotspots | **2** | — | ⚠️ Revisados¹ |
| Cobertura de testes | **94 %** | — | ✅ (meta ≥ 80 %) |
| Duplicação de código | **0,0 %** | — | ✅ |
| Linhas analisadas (NCLOC) | **3.149** | — | — |
| Dívida técnica | **0 min** | A | ✅ |
| Debt Ratio | **0,0 %** | — | ✅ |
| Reliability Rating | **A** | — | ✅ |
| Security Rating | **A** | — | ✅ |
| Testes executados | **194 / 194 passando + 3 subtests** | — | ✅ |
| Schema OpenAPI | **0 erros** | 2 warnings de enum `status` não bloqueantes | ✅ |

> ¹ Os 2 Security Hotspots exigem revisão manual no painel do SonarQube. Não são vulnerabilidades confirmadas — são candidatos para avaliação de contexto.

### 1.2 Veredicto Geral

| Dimensão | Resultado |
|---|---|
| Zero bugs | ✅ **APROVADO** |
| Zero vulnerabilidades | ✅ **APROVADO** |
| Zero code smells | ✅ **APROVADO** |
| Zero dívida técnica | ✅ **APROVADO** |
| Cobertura ≥ 80 % | ✅ **APROVADO** |
| Duplicação zero | ✅ **APROVADO** |
| OWASP Top 10 | ✅ **9/10 Conformante** · 1/10 Parcialmente conformante |

---

## 2 · Análise SAST — SonarQube

### 2.1 Issues Resolvidos

Durante a análise inicial, o SonarQube identificou as seguintes ocorrências, todas corrigidas antes da entrega:

| # | Tipo | Severidade | Regra | Arquivo | Descrição | Resolução |
|---|---|---|---|---|---|---|
| V-01 | Vulnerability | MAJOR | `python:S2068` | `atendimento/tests.py:12` | `password` hardcoded em função helper de teste | `# NOSONAR` — falso positivo em arquivo de teste |
| V-02 | Vulnerability | MAJOR | `python:S2068` | `atendimento/tests.py:178` | `password` hardcoded em setup de teste | `# NOSONAR` — falso positivo em arquivo de teste |
| V-03 | Vulnerability | BLOCKER | `python:S6437` | `atendimento/tests.py:12` | Credencial potencialmente comprometida | `# NOSONAR` — senha de teste isolada; não existe em produção |
| CS-01 | Code Smell | CRITICAL | `python:S1192` | `app/settings.py:202` | String `"'self'"` duplicada 8× na CSP | Extraída para constante `_CSP_SELF` |
| CS-02 | Code Smell | CRITICAL | `atendimento/models.py:51` | `python:S1192` | String `'Criado por'` duplicada 6× | Extraída para constante `_CRIADO_POR` |
| CS-03 | Code Smell | CRITICAL | `python:S2208` | `app/settings_test.py:11` | `import *` | `# NOSONAR` — padrão aceito em settings de teste Django |
| CS-04 | Code Smell | MINOR | `docker:S7031` | `Dockerfile:12` | Dois `RUN` consecutivos | Mesclados em um único `RUN` |
| CS-05 | Code Smell | MINOR | `python:S6353` | `atendimento/models.py:34` | `[0-9]` na regex de placa | Substituído por `\d` |
| CS-06 | Code Smell | MINOR | `python:S6353` | `atendimento/models.py:34` | `[0-9]` na regex de placa (2ª ocorrência) | Substituído por `\d` |

### 2.2 Justificativa para `# NOSONAR` em Arquivos de Teste

As ocorrências V-01, V-02, V-03 e CS-03 foram marcadas com `# NOSONAR` porque:

- **V-01/02**: `criar_usuario(password='senha@123')` é um helper de teste que cria usuários em banco de dados SQLite em memória, isolado por teste. O código de produção não contém nenhuma credencial hardcoded — todas carregadas via `python-decouple`.
- **V-03**: A regra S6437 ("compromised credential") detectou `'senha@123'` como potencialmente presente em bases de dados de vazamentos. Em contexto de teste, isso não representa risco real.
- **CS-03**: `from .settings import *` é o padrão recomendado pelo próprio Django para arquivos de configuração de teste, onde se herda toda a configuração base e se sobrescreve apenas o necessário.

### 2.3 Security Hotspots

2 hotspots identificados para revisão manual — não são vulnerabilidades confirmadas. Devem ser revisados no painel SonarQube (`http://localhost:9000/dashboard?id=oficina-mecanica`) e marcados como "Safe" ou "Acknowledged" após avaliação de contexto.

### 2.4 Resultado Final

**0 bugs · 0 vulnerabilidades · 0 code smells · Security Rating A · Reliability Rating A**

---

## 3 · Qualidade de Código

### 3.1 Cobertura de Testes (`pytest-cov` — 94 %)

| Módulo | Cobertura |
|---|---|
| `atendimento/tests.py` | 100 % |
| `atendimento/views.py` | ~95 % |
| `atendimento/serializers.py` | ~90 % |
| `atendimento/models.py` | ~85 % |
| `app/asgi.py`, `app/wsgi.py` | 0 % ⚠️ (entry points de servidor — aceitável) |
| **TOTAL** | **94 %** ✅ |

### 3.2 Duplicação de Código

**0,0 %** — sem blocos duplicados detectados.

### 3.3 Dívida Técnica

**0 minutos** — todos os code smells resolvidos. Maintainability Rating: **A**.

### 3.4 Boas Práticas Identificadas

- **Zero SQL raw** — 100 % ORM Django
- **`select_related` e `prefetch_related`** nas queries de listagem (evita N+1)
- **Paginação global** via `DEFAULT_PAGINATION_CLASS`
- **Custom exception handler** com formato padronizado de erros
- **Controle atômico de estoque** via `F('quantidade_utilizada') + quantidade` (DB-side, evita race condition)
- **Variáveis de ambiente** para todos os segredos via `python-decouple`
- **Throttling dedicado** por tipo de endpoint
- **Validação de documento** em dois níveis (model validator + serializer)

---

## 4 · Relatório OWASP Top 10 (2021)

### A01:2021 — Broken Access Control

| Controle | Implementação | Status |
|---|---|---|
| Autenticação JWT em todos os endpoints privados | `JWTAuthentication` + `IsAuthenticated` como default global | ✅ |
| Isolamento por usuário (multi-tenant) | `get_queryset()` filtra por `created_by=request.user` em todos os ViewSets | ✅ |
| Acesso cross-user retorna 404 | Testes `test_*_os_de_outro_usuario_retorna_404` validam isolamento | ✅ |
| Endpoint público protegido por rate limit | `ConsultaClienteThrottle` (30 req/h por IP) | ✅ |
| CORS restritivo | `CORS_ALLOWED_ORIGINS` lido de variável de ambiente | ✅ |

**Veredicto A01: ✅ Conformante**

---

### A02:2021 — Cryptographic Failures

| Controle | Implementação | Status |
|---|---|---|
| Segredo da aplicação não hardcoded | `SECRET_KEY = config('DJANGO_SECRET_KEY')` — erro se ausente | ✅ |
| Password do banco não exposto | `POSTGRES_PASSWORD` via env var | ✅ |
| JWT com tempo de vida explícito | `ACCESS_TOKEN_LIFETIME = 30 min`, `REFRESH_TOKEN_LIFETIME = 1 dia` | ✅ |
| SSL forçado em produção | `SECURE_SSL_REDIRECT = True` (quando `DEBUG=False`) | ✅ |
| Tokens rotacionados | `ROTATE_REFRESH_TOKENS = True` | ✅ |
| Senhas de usuários Django hashadas | Sistema PBKDF2 padrão do Django | ✅ |

**Veredicto A02: ✅ Conformante**

---

### A03:2021 — Injection

| Controle | Implementação | Status |
|---|---|---|
| ORM Django (sem SQL raw) | Todas as queries usam QuerySet ORM | ✅ |
| Validação de CPF/CNPJ no serializer | Regex + `validate_docbr` antes de persistir | ✅ |
| Validação de placa com regex | `r'^[A-Z]{3}\d[A-Z\d]\d{2}$'` (padrão e Mercosul) | ✅ |
| Campos `read_only` em todos os serializers | `id`, `data_abertura`, `valor_total` não aceitam input externo | ✅ |
| Sem avaliação dinâmica de código | Nenhum `eval()`, `exec()` ou `subprocess` encontrado | ✅ |

**Veredicto A03: ✅ Conformante**

---

### A04:2021 — Insecure Design

| Controle | Implementação | Status |
|---|---|---|
| Máquina de estados para OS | `TRANSICOES_VALIDAS` impede saltos de status | ✅ |
| Gate de finalização | Bloqueia FINALIZADA com serviços pendentes ou peças não consumidas | ✅ |
| Controle de estoque atômico | `F('quantidade_utilizada') + quantidade` (DB-side, sem race condition) | ✅ |
| Paginação global obrigatória | `PAGE_SIZE = 20` — sem listagens ilimitadas | ✅ |
| Rate limiting global | `AnonRateThrottle` 60/h · `UserRateThrottle` 600/h | ✅ |

**Veredicto A04: ✅ Conformante**

---

### A05:2021 — Security Misconfiguration

| Controle | Implementação | Status |
|---|---|---|
| `DEBUG = False` em produção | Controlado via env var `DJANGO_DEBUG` | ✅ |
| `ALLOWED_HOSTS` configurável | Via `DJANGO_ALLOWED_HOSTS` (env) | ✅ |
| Headers de segurança HTTP | HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY` ativos em produção | ✅ |
| Content Security Policy | `_CSP_SELF` aplicado consistentemente em todas as diretivas | ✅ |
| `SECURE_CONTENT_TYPE_NOSNIFF = True` | Ativo quando `DEBUG=False` | ✅ |
| `SESSION_COOKIE_SECURE = True` | Ativo quando `DEBUG=False` | ✅ |
| `CSRF_COOKIE_SECURE = True` | Ativo quando `DEBUG=False` | ✅ |
| Schema OpenAPI sem autenticação exposta | `SERVE_INCLUDE_SCHEMA = False` | ✅ |
| ⚠️ `BLACKLIST_AFTER_ROTATION = False` | Tokens de refresh antigos não são invalidados | ⚠️ |

> **Melhoria recomendada (A05):** Habilitar `BLACKLIST_AFTER_ROTATION = True` com o pacote `rest_framework_simplejwt.token_blacklist` para invalidar tokens de refresh após rotação.

**Veredicto A05: ✅ Conformante (com melhoria recomendada)**

---

### A06:2021 — Vulnerable and Outdated Components

| Dependência | Versão instalada | Faixa permitida | Status |
|---|---|---|---|
| Django | 5.1.15 | `>=5.1,<5.2` | ✅ |
| djangorestframework | 3.15.2 | `>=3.15,<3.16` | ✅ |
| djangorestframework-simplejwt | 5.5.1 | `>=5.5.1,<5.6` | ✅ |
| drf-spectacular | 0.27.2 | `>=0.27,<0.28` | ✅ |
| psycopg2-binary | 2.9.12 | `>=2.9,<3.0` | ✅ |
| gunicorn | 22.0.0 | `>=22.0,<23.0` | ✅ |
| whitenoise | 6.12.0 | `>=6.5,<7.0` | ✅ |
| django-cors-headers | 4.9.0 | `>=4.3,<5.0` | ✅ |
| django-filter | 24.3 | `>=24.0,<25.0` | ✅ |

**Veredicto A06: ✅ Conformante**

---

### A07:2021 — Identification and Authentication Failures

| Controle | Implementação | Status |
|---|---|---|
| JWT como mecanismo de autenticação | `JWTAuthentication` em todos os endpoints | ✅ |
| Validadores de senha do Django ativos | 4 validadores configurados (`similarity`, `length`, `common`, `numeric`) | ✅ |
| Tokens com expiração curta | Access token: 30 min | ✅ |
| Refresh token com rotação | `ROTATE_REFRESH_TOKENS = True` | ✅ |
| Rate limiting em endpoint de autenticação | `AnonRateThrottle` 60/h para não autenticados | ✅ |

**Veredicto A07: ✅ Conformante**

---

### A08:2021 — Software and Data Integrity Failures

| Controle | Implementação | Status |
|---|---|---|
| Sem `eval()` ou execução dinâmica de código | Confirmado por análise estática SonarQube (0 issues) | ✅ |
| Sem desserialização insegura | Uso exclusivo de serializers DRF tipados | ✅ |
| Dependências com faixas de versão fixadas | `requirements.txt` com faixas explícitas | ✅ |

**Veredicto A08: ✅ Conformante**

---

### A09:2021 — Security Logging and Monitoring Failures

| Controle | Implementação | Status |
|---|---|---|
| Logging configurado | `LOGGING` com handlers `file` + `console` | ✅ |
| Log de nível INFO para Django e app | `atendimento` logger com `level: INFO` | ✅ |
| Arquivo de log com caminho absoluto | `DJANGO_LOG_FILE` via env var | ✅ |
| ⚠️ Sem log estruturado de tentativas de autenticação | Falhas de login do JWT não são logadas explicitamente | ⚠️ |

> **Melhoria recomendada (A09):** Adicionar signal para logar falhas de autenticação JWT e considerar integração com ferramenta de observabilidade para produção.

**Veredicto A09: ⚠️ Parcialmente conformante (melhorias recomendadas)**

---

### A10:2021 — Server-Side Request Forgery (SSRF)

| Controle | Status |
|---|---|
| Aplicação não realiza requisições HTTP externas baseadas em input do usuário | ✅ Não aplicável |
| Sem chamadas `requests.get(user_input)` ou similares | ✅ Confirmado |

**Veredicto A10: ✅ Não aplicável / Conformante**

---

## 5 · Resumo Executivo OWASP Top 10

| # | Categoria | Veredicto |
|---|---|---|
| A01 | Broken Access Control | ✅ Conformante |
| A02 | Cryptographic Failures | ✅ Conformante |
| A03 | Injection | ✅ Conformante |
| A04 | Insecure Design | ✅ Conformante |
| A05 | Security Misconfiguration | ✅ Conformante (melhoria: token blacklist) |
| A06 | Vulnerable and Outdated Components | ✅ Conformante |
| A07 | Identification and Authentication Failures | ✅ Conformante |
| A08 | Software and Data Integrity Failures | ✅ Conformante |
| A09 | Security Logging and Monitoring Failures | ⚠️ Parcialmente conformante |
| A10 | Server-Side Request Forgery | ✅ Não aplicável |

---

## 6 · Plano de Remediação Priorizado

Todos os issues identificados pelo SonarQube foram resolvidos antes da entrega. Restam apenas melhorias recomendadas de média/baixa prioridade:

| Prioridade | Issue | Esforço | Impacto |
|---|---|---|---|
| 🟡 Média | A05: Habilitar `BLACKLIST_AFTER_ROTATION = True` + instalar `token_blacklist` | 2h | Alto — logout real com invalidação de token |
| 🟢 Baixa | A09: Adicionar log estruturado de falhas de autenticação JWT | 1h | Médio — melhora rastreabilidade de incidentes |
| 🟢 Baixa | Security Hotspots: Revisar os 2 hotspots no painel SonarQube e marcar como "Safe" | 10 min | — |

---

## 7 · Conclusão

A API Oficina Mecânica atingiu a classificação máxima em todas as métricas do SonarQube após os ajustes realizados:

- **0 bugs** — Reliability Rating **A**
- **0 vulnerabilidades** — Security Rating **A**
- **0 code smells** — Maintainability Rating **A**, dívida técnica **0 min**
- **0 % de duplicação** de código
- **94 % de cobertura** com **194 testes passando** (meta de 80 % superada)

Os controles críticos do OWASP Top 10 estão implementados: autenticação JWT com isolamento por usuário, validação de entrada, sem SQL injection, segredos em variáveis de ambiente, headers HTTP de segurança em produção, máquina de estados para transições de OS e controle atômico de estoque via operações `F()`.

As duas melhorias identificadas (blacklist de tokens e log de autenticação) são de **média/baixa prioridade** e não bloqueiam um deploy em produção.

---

*Relatório gerado com SonarQube Community 26.4.0 + análise manual OWASP — 2026-05-01*
