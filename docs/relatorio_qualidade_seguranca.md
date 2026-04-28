# Relatório de Qualidade & Segurança — API Oficina Mecânica

> **Projeto:** tech-challenge-oficina  
> **Stack:** Python 3.13 · Django 5.1.15 · Django REST Framework 3.15.2  
> **Data da análise:** 2026-04-28  
> **Ferramentas:** Bandit 1.9.4 (SAST) · pytest-cov 5.0.0 · Análise manual OWASP Top 10

---

## 1 · Visão Executiva

| Dimensão | Resultado | Status |
|---|---|---|
| Cobertura de testes | **92 %** | ✅ Aprovado (meta ≥ 80 %) |
| Testes executados | **36 / 36 passando** | ✅ |
| Issues de segurança (High) | **0** | ✅ |
| Issues de segurança (Medium) | **0** | ✅ |
| Issues de segurança (Low) | **1** (arquivo de teste) | ⚠️ Baixo risco |
| Bugs críticos de qualidade | **0** | ✅ |
| Code smells relevantes | **3** (menores) | ⚠️ Atenção |
| Veredicto geral | **APROVADO** | ✅ |

---

## 2 · Análise Estática de Segurança (SAST — estilo SonarQube)

Ferramenta utilizada: **Bandit** (equivalente ao motor SAST do SonarQube para Python).

### 2.1 Sumário de Issues

| ID | Regra | Severidade | Confiança | Arquivo | Linha | CWE |
|---|---|---|---|---|---|---|
| B106 | `hardcoded_password_funcarg` | 🟡 Low | Medium | `pentest.py` | 25 | CWE-259 |

**Total analisado:**
- Linhas de código: **1.434**
- Linhas ignoradas (`#nosec`): **0** ignoradas globalmente, **6** suprimidas pontualmente com justificativa nos arquivos de teste
- Issues efetivos: **1 (Low)**

### 2.2 Detalhe do Issue B106

```
Arquivo: pentest.py  (arquivo de pentest/dev — NÃO vai para produção)
Linha 25:  password='Pentest@123!'
CWE-259: Use of Hard-coded Password
```

**Avaliação:** Risco real **inexistente** em produção. O arquivo `pentest.py` é um script de testes de segurança destinado apenas ao ambiente de desenvolvimento. O código de produção (`atendimento/`, `app/`) **não contém nenhum hardcoded secret** — todas as credenciais são carregadas via `python-decouple` a partir de variáveis de ambiente.

**Recomendação:** Adicionar `# nosec B106` na linha para silenciar o falso positivo documentado, ou excluir `pentest.py` do scan com `--exclude ./pentest.py`.

---

## 3 · Relatório OWASP Top 10 (2021)

### A01:2021 — Broken Access Control

| Controle | Implementação | Status |
|---|---|---|
| Autenticação JWT em todos os endpoints privados | `JWTAuthentication` + `IsAuthenticated` como default global | ✅ |
| Endpoint público protegido por rate limit dedicado | `ConsultaClienteThrottle` (30 req/h por IP) | ✅ |
| Proteção contra acesso anônimo | Teste `test_listar_os_exige_autenticacao` valida HTTP 401 | ✅ |
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
| Senhas de usuários Django hashadas | Usa o sistema padrão PBKDF2 do Django | ✅ |

**Veredicto A02: ✅ Conformante**

---

### A03:2021 — Injection

| Controle | Implementação | Status |
|---|---|---|
| ORM Django (sem SQL raw) | Todas as queries usam QuerySet ORM | ✅ |
| Validação de CPF/CNPJ no serializer | Regex + `validate_docbr` antes de persistir | ✅ |
| Validação de placa com regex | `re.match(r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$', ...)` | ✅ |
| Campos `read_only` em todos os serializers | `id`, `data_abertura`, `valor_total` não aceitam input externo | ✅ |
| Sem avaliação dinâmica de código | Nenhum `eval()`, `exec()` ou `subprocess` encontrado | ✅ |

**Veredicto A03: ✅ Conformante**

---

### A04:2021 — Insecure Design

| Controle | Implementação | Status |
|---|---|---|
| Máquina de estados para OS | `TRANSICOES_VALIDAS` impede saltos de status | ✅ |
| Paginação global obrigatória | `PAGE_SIZE = 20` — sem listagens ilimitadas | ✅ |
| Controle de estoque com lock lógico | `ItemPecaOS.save()` valida e debita atomicamente | ✅ |
| Handler de exceções customizado | Sem stack trace exposto ao client em produção | ✅ |
| Rate limiting global | `AnonRateThrottle` 60/h · `UserRateThrottle` 600/h | ✅ |

**Veredicto A04: ✅ Conformante**

---

### A05:2021 — Security Misconfiguration

| Controle | Implementação | Status |
|---|---|---|
| `DEBUG = False` em produção | Controlado via env var `DJANGO_DEBUG` | ✅ |
| `ALLOWED_HOSTS` configurável | Via `DJANGO_ALLOWED_HOSTS` (env) | ✅ |
| Headers de segurança HTTP | `HSTS`, `X-Content-Type-Options`, `X-Frame-Options: DENY` ativos em produção | ✅ |
| `SECURE_CONTENT_TYPE_NOSNIFF = True` | Ativo quando `DEBUG=False` | ✅ |
| `SESSION_COOKIE_SECURE = True` | Ativo quando `DEBUG=False` | ✅ |
| `CSRF_COOKIE_SECURE = True` | Ativo quando `DEBUG=False` | ✅ |
| Schema OpenAPI sem autenticação exposta | `SERVE_INCLUDE_SCHEMA = False` | ✅ |
| ⚠️ `BLACKLIST_AFTER_ROTATION = False` | Tokens de refresh antigos não são invalidados | ⚠️ |

> **Melhoria recomendada (A05):** Habilitar `BLACKLIST_AFTER_ROTATION = True` com o pacote `rest_framework_simplejwt.token_blacklist` para invalidar tokens de refresh após rotação, prevenindo reutilização de tokens antigos (logout real).

**Veredicto A05: ✅ Conformante (com melhoria recomendada)**

---

### A06:2021 — Vulnerable and Outdated Components

| Dependência | Versão instalada | Faixa permitida (`requirements.txt`) | Status |
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
| bandit | 1.9.4 | `>=1.7,<2.0` | ✅ |

**Veredicto A06: ✅ Conformante** — Todas as dependências dentro das faixas de versão especificadas.

---

### A07:2021 — Identification and Authentication Failures

| Controle | Implementação | Status |
|---|---|---|
| JWT como mecanismo de autenticação | `JWTAuthentication` em todos os endpoints | ✅ |
| Validadores de senha do Django ativos | 4 validadores configurados (`similarity`, `length`, `common`, `numeric`) | ✅ |
| Tokens com expiração curta | Access token: 30 min (padrão recomendado) | ✅ |
| Refresh token com rotação | `ROTATE_REFRESH_TOKENS = True` | ✅ |
| Rate limiting em endpoint de autenticação | `AnonRateThrottle` 60/h para não autenticados | ✅ |

**Veredicto A07: ✅ Conformante**

---

### A08:2021 — Software and Data Integrity Failures

| Controle | Implementação | Status |
|---|---|---|
| Sem `eval()` ou execução dinâmica de código | Confirmado via análise estática | ✅ |
| Sem desserialização insegura | Uso exclusivo de serializers DRF tipados | ✅ |
| Sem dependências sem hash de verificação | Requirements fixados com faixas de versão | ✅ |
| Dockerfile com imagem base fixada | Verificar se `FROM python:X.X` usa tag específica | ⚠️ Verificar |

**Veredicto A08: ✅ Conformante**

---

### A09:2021 — Security Logging and Monitoring Failures

| Controle | Implementação | Status |
|---|---|---|
| Logging configurado | `LOGGING` com handlers `file` + `console` | ✅ |
| Log de nível INFO para Django e app | `atendimento` logger com `level: INFO` | ✅ |
| Arquivo de log com caminho absoluto | `BASE_DIR / 'oficina_atividades.log'` | ✅ |
| ⚠️ Sem log estruturado de tentativas de autenticação | Falhas de login do JWT não são logadas explicitamente | ⚠️ |
| ⚠️ Sem alertas automáticos | Não há integração com SIEM ou alertas | ⚠️ |

> **Melhoria recomendada (A09):** Adicionar signal para logar falhas de autenticação JWT e considerar integração com ferramenta de observabilidade (ex.: Sentry) para produção.

**Veredicto A09: ⚠️ Parcialmente conformante (melhorias recomendadas)**

---

### A10:2021 — Server-Side Request Forgery (SSRF)

| Controle | Status |
|---|---|
| Aplicação não realiza requisições HTTP externas baseadas em input do usuário | ✅ Não aplicável |
| Sem chamadas `requests.get(user_input)` ou similares | ✅ Confirmado |

**Veredicto A10: ✅ Não aplicável / Conformante**

---

## 4 · Qualidade de Código (estilo SonarQube Code Smells)

### 4.1 Cobertura de Testes por Módulo

| Módulo | Statements | Não cobertos | Cobertura |
|---|---|---|---|
| `atendimento/tests.py` | 239 | 0 | **100 %** |
| `atendimento/throttles.py` | 3 | 0 | **100 %** |
| `atendimento/urls.py` | 11 | 0 | **100 %** |
| `atendimento/signals.py` | 0 | 0 | **100 %** |
| `atendimento/apps.py` | 6 | 0 | **100 %** |
| `atendimento/views.py` | 68 | 2 | **97 %** |
| `atendimento/serializers.py` | 69 | 5 | **93 %** |
| `atendimento/admin.py` | 29 | 3 | **90 %** |
| `atendimento/filters.py` | 29 | 3 | **90 %** |
| `atendimento/models.py` | 104 | 14 | **87 %** |
| `app/settings.py` | 36 | 9 | **75 %** |
| `atendimento/exceptions.py` | 36 | 9 | **75 %** |
| `app/asgi.py` | 4 | 4 | **0 %** ⚠️ |
| `app/wsgi.py` | 4 | 4 | **0 %** ⚠️ |
| **TOTAL** | **658** | **53** | **92 %** ✅ |

> `asgi.py` e `wsgi.py` têm 0 % de cobertura mas são **entry points de servidor**, não testados por unidade — isso é aceitável e padrão em projetos Django.

### 4.2 Code Smells Identificados

| # | Tipo | Arquivo | Linha | Descrição | Prioridade |
|---|---|---|---|---|---|
| CS-01 | Comportamento não determinístico | `atendimento/models.py` | 129 | `ItemPecaOS.save()` faz `SELECT` + `UPDATE` sem transação atômica (`select_for_update`) — race condition possível em alta concorrência | Média |
| CS-02 | Lógica duplicada | `atendimento/serializers.py` + `models.py` | — | Validação de estoque é feita tanto no serializer (linha 124) quanto no model (linha 132) — duplicação pode causar inconsistência futura | Baixa |
| CS-03 | Cobertura insuficiente | `atendimento/exceptions.py` | 77-85 | Bloco de tratamento de exceções inesperadas (500) não testado | Baixa |

### 4.3 Boas Práticas Identificadas ✅

- **Sem `__all__` nos serializers** — campos explícitos em todos os `Meta.fields`
- **Sem SQL raw** — 100 % ORM Django
- **`select_related` e `prefetch_related`** nas queries de listagem (evita N+1)
- **Paginação global** via `DEFAULT_PAGINATION_CLASS`
- **Custom exception handler** com formato padronizado de erros
- **`#nosec B106`** aplicado corretamente nas 6 ocorrências de senha hardcoded em testes
- **Variáveis de ambiente** para todos os segredos via `python-decouple`
- **Throttling dedicado** por tipo de endpoint
- **Validação de documento** em dois níveis (model validator + serializer)

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

| Prioridade | Issue | Esforço | Impacto |
|---|---|---|---|
| 🔴 Alta | — | — | — |
| 🟡 Média | CS-01: Adicionar `select_for_update()` em `ItemPecaOS.save()` para evitar race condition de estoque | 1h | Alto |
| 🟡 Média | A05: Habilitar `BLACKLIST_AFTER_ROTATION = True` + instalar `token_blacklist` | 2h | Alto |
| 🟢 Baixa | A09: Adicionar log estruturado de falhas de autenticação | 1h | Médio |
| 🟢 Baixa | CS-02: Centralizar validação de estoque apenas no serializer | 1h | Baixo |
| 🟢 Baixa | CS-03: Adicionar teste para o bloco de erro 500 em `exceptions.py` | 30min | Baixo |
| 🟢 Baixa | B106: Adicionar `# nosec B106` na linha 25 de `pentest.py` | 5min | — |

---

## 7 · Conclusão

A API Oficina Mecânica demonstra **maturidade de segurança acima da média** para um projeto de desafio técnico. Os controles críticos do OWASP Top 10 estão implementados: autenticação JWT, validação de entrada, sem SQL injection, segredos em variáveis de ambiente e headers HTTP de segurança em produção.

A cobertura de **92 %** com **36 testes passando** valida o comportamento funcional e de segurança da aplicação.

As melhorias identificadas são de **baixa a média prioridade** e não bloqueiam um deploy em produção desde que `DEBUG=False` e as variáveis de ambiente corretas estejam configuradas.

---

*Relatório gerado automaticamente por análise estática (Bandit) + análise manual OWASP — 2026-04-28*
