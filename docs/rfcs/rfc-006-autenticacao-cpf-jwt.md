# RFC-006 — Estratégia de Autenticação: CPF + JWT

| Informação | Valor |
|---|---|
| **RFC** | 006 |
| **Título** | Autenticação via CPF com JWT RS256 |
| **Status** | Aprovado |
| **Autores** | Hélio Mendes (RM374170), Lucas Marques (RM369825) |
| **Data** | 2026-09-08 |
| **Versão** | 1.0 |

---

## 1. Objetivo

Definir a estratégia de autenticação para a Fase 3, utilizando CPF do cliente e JWT RS256, garantindo segurança e evitando enumeração de usuários.

## 2. Motivação

O desafio exige autenticação via CPF. A implementação precisa:
- Validar CPF com dígitos verificadores
- Consultar existência e status do cliente no banco
- Gerar JWT válido para APIs protegidas
- Evitar que o endpoint se torne um oráculo de enumeração

## 3. Fluxo de Autenticação

```
Cliente → API Gateway (POST /auth) → Lambda → RDS (SELECT id, ativo)
                                        → Secrets Manager (jwt-private-key)
                                        → JWT RS256 (iss=oficina-auth, aud=oficina-api, exp=900s)
                                        → Retorna { access_token, token_type, expires_in }
```

## 4. Decisões Técnicas

### 4.1 Por que JWT RS256?

| Critério | RS256 | HS256 |
|---|---|---|
| Segurança | Chave pública/privada | Chave compartilhada |
| Risco de vazamento | Baixo (privada fica só na Lambda) | Alto (todos os serviços têm a chave) |
| Recomendação OWASP | Sim | Não para microserviços |

### 4.2 Claims do JWT

```json
{
  "iss": "oficina-auth",
  "aud": "oficina-api",
  "sub": "cliente:{id}",
  "cliente_id": 42,
  "principal_type": "cliente",
  "token_type": "access",
  "iat": 1693500000,
  "exp": 1693500900,
  "jti": "uuid-v4"
}
```

### 4.3 Por que erro genérico?

Clientes inexistentes e inativos retornam o mesmo erro (401). Motivo: evitar que o endpoint seja usado para descobrir quem é cliente da oficina e quem está inativo (enumeração).

### 4.4 Validação no Django

O Django valida o JWT usando a chave pública (`AUTH_JWT_PUBLIC_KEY_B64`). A chave privada nunca sai da Lambda de autenticação.

## 5. Segurança

| Ameaça | Mitigação |
|---|---|
| CPF em logs | Nunca logar CPF. Cliente entra como `cliente.ref` (SHA-256 com salt) |
| SQL Injection | Consulta parametrizada (`WHERE cpf = %s`) |
| JWT expirado | Expiração de 900 segundos (15 min) |
| Chave vazada | Privada fica apenas na Lambda, no Secrets Manager |
| Enumeração | Mesmo erro 401 para CPF inexistente e cliente inativo |

## 6. Impacto

| Área | Mudança |
|---|---|
| Repo `auth` | Lambda Python 3.11 com handler POST /auth |
| Repo principal | `AUTH_JWT_PUBLIC_KEY_B64` no ConfigMap/Secret |
| API Gateway | Rota POST /auth → Lambda (AWS_PROXY) |
| RDS | Tabela `atendimento_cliente` com campo `ativo` |

## 7. Alternativas Consideradas

| Alternativa | Por que não foi escolhida |
|---|---|
| Autenticação por e-mail | O enunciado exige CPF |
| HS256 | Menor segurança (chave compartilhada) |
| OAuth 2.0 completo | Overhead desnecessário para o escopo |
| Sessão stateful | Não escala horizontalmente |

## 8. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-09-08 | Hélio Mendes, Lucas Marques | Versão inicial |
