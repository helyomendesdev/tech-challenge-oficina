# RFC-003 — Autenticação, Autorização e Rate Limiting

| Informação | Valor |
|---|---|
| **RFC** | 003 |
| **Título** | Autenticação JWT, Autorização e Rate Limiting |
| **Status** | Aprovado |
| **Autores** | Afonso Victoriano Franco (RM373563), Hélio Mendes da Silva (RM374170), João Pedro Rodrigues Martins (RM372818), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Data** | 2026-04-28 |
| **Versão** | 1.0 |

---

## 1. Resumo

Este documento especifica o modelo de segurança da API, incluindo autenticação stateless via JWT, autorização baseada em usuário autenticado e rate limiting em múltiplos níveis.

---

## 2. Motivação

Uma API pública exposta na internet necessita:
- Identificação segura de usuários (mecânicos e administradores)
- Proteção contra abuso (brute force, scraping)
- Acesso específico para clientes consultarem suas próprias OS sem autenticação completa
- Conformidade com boas práticas de segurança (OWASP)

---

## 3. Autenticação

### 3.1 JWT (JSON Web Tokens)

A autenticação utiliza **djangorestframework-simplejwt** com dois tokens:

| Token | Validade | Uso |
|---|---|---|
| `access_token` | 30 minutos | Enviado no header `Authorization: Bearer <token>` em todas as requisições protegidas |
| `refresh_token` | 1 dia | Usado em `POST /api/token/refresh/` para obter um novo `access_token` |

### 3.2 Endpoints de Autenticação

| Método | Endpoint | Descrição | Auth |
|---|---|---|---|
| `POST` | `/api/token/` | Obtém access + refresh token | Não |
| `POST` | `/api/token/refresh/` | Renova access token | Não |

### 3.3 Payload do Token

```json
{
  "token_type": "access",
  "exp": 1714300800,
  "iat": 1714299000,
  "jti": "...",
  "user_id": 1,
  "username": "mecanico_joao"
}
```

---

## 4. Autorização

### 4.1 Endpoints Protegidos

Todos os endpoints exigem autenticação via Bearer Token, **exceto**:
- `POST /api/token/`
- `POST /api/token/refresh/`
- `GET /api/v1/ordens-servico/consulta-cliente/`

### 4.2 Isolamento por Usuário

Os registros (`created_by`) associam entidades ao usuário que as criou. As ViewSets filtram automaticamente para que um usuário só visualize recursos criados por ele, exceto administradores (futuro).

---

## 5. Rate Limiting (Throttling)

### 5.1 Níveis de Throttling

| Tipo | Limite | Aplicado em |
|---|---|---|
| **Autenticado** | 600 requisições/hora | Usuários logados (`Bearer` válido) |
| **Anônimo (geral)** | 60 requisições/hora | Requisições sem token ou token inválido |
| **Consulta pública** | 30 requisições/hora por IP | `GET /api/v1/ordens-servico/consulta-cliente/` |

### 5.2 Resposta ao Exceder Limite

```json
{
  "erro": true,
  "status_code": 429,
  "mensagem": "Request was throttled. Expected available in 3600 seconds."
}
```

### 5.3 Implementação

- Throttling global configurado em `REST_FRAMEWORK.DEFAULT_THROTTLE_CLASSES`
- Throttle customizado `ConsultaClienteThrottle` para o endpoint público, aplicado via `throttle_classes` na ViewSet

---

## 6. Segurança em Produção

Quando `DJANGO_DEBUG=False`, as seguintes proteções são ativadas:

| Proteção | Valor | Descrição |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` | Redireciona HTTP para HTTPS |
| `SECURE_HSTS_SECONDS` | `31536000` | HSTS por 1 ano |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | HSTS inclui subdomínios |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Impede MIME-type sniffing |
| `SESSION_COOKIE_SECURE` | `True` | Cookies de sessão só via HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | Cookie CSRF só via HTTPS |
| `X_FRAME_OPTIONS` | `'DENY'` | Impede embedding em iframes |

---

## 7. Auditoria de Segurança (OWASP A09)

Eventos críticos são logados via `logging.getLogger('security')`:

| Evento | Dados logados |
|---|---|
| `os_created` | os_id, status, user_id, cliente_id, veiculo_id |
| `os_updated` | os_id, status, user_id |
| `item_peca_created` | item_id, os_id, peca_id, quantidade, user_id |
| `item_peca_updated` | item_id, os_id, peca_id, quantidade, user_id |
| `item_peca_deleted` | item_id, os_id, peca_id, quantidade, user_id |

---

## 8. Decisões de Design

| Decisão | Justificativa |
|---|---|
| JWT ao invés de Session Auth | Stateless, facilita consumo por múltiplos clientes (web, mobile, Postman) |
| Rate limiting por IP no endpoint público | Protege contra enumeração de placas/CPFs por bots |
| Refresh token de 1 dia | Balanceia segurança (revogação rápida) e UX (não precisa logar toda hora) |
| Logs de auditoria em logger separado | Facilita coleta por SIEM e análise de incidentes |

---

## 9. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-04-28 | Afonso Victoriano Franco, Hélio Mendes da Silva, João Pedro Rodrigues Martins, Luís Fernando Montes, Sophia Sussa Campos Bastos | Versão inicial aprovada |
