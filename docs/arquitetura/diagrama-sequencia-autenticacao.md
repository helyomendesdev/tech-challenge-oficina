# Diagrama de Sequência — Autenticação por CPF e Primeiro Consumo Protegido

| Informação | Valor |
|---|---|
| **Documento** | Diagrama de sequência — fluxo de autenticação (Fase 3) |
| **Versão** | 1.0 |
| **Data** | 2026-09-09 |
| **Autores** | Grupo 80 — Hélio Mendes da Silva (RM374170), Lucas Marques (RM369825), Luís Fernando Montes (RM367183), Sophia Sussa Campos Bastos (RM371864) |
| **Ambiente retratado** | AWS us-east-1, stage `homologacao` do API Gateway |

---

## 1. O que este documento cobre

Dois fluxos que **saem do API Gateway de forma independente** — não uma cadeia única (ver
[ADR-007 §1](../adrs/adr-007-correlacao-w3c-trace-context.md)):

1. **Autenticação** (`POST /auth`): o cliente informa o CPF, a Lambda de autenticação
   (repositório `tech-challenge-oficina-auth`) confere existência e situação do cliente no RDS e
   devolve um JWT RS256.
2. **Primeiro consumo protegido** (`GET /api/v1/veiculos/`, por exemplo): o cliente apresenta o
   JWT, o API Gateway encaminha pelo VPC Link até o ALB interno e os pods Django validam a
   assinatura com a chave pública em `atendimento/authentication.py`.

Componentes e nomes vêm do ambiente real de homologação. O que ainda não está provisionado ou
está fora deste repositório aparece indicado.

## 2. Fluxo 1 — Autenticação por CPF

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (app ou Postman)
    participant APIGW as API Gateway REST<br/>stage homologacao
    participant Lambda as Lambda Python 3.11<br/>tech-challenge-oficina-auth
    participant SM as Secrets Manager
    participant RDS as RDS PostgreSQL 17<br/>oficina-postgres

    Cliente->>APIGW: POST /homologacao/auth<br/>{"cpf": "00000000000"}<br/>X-Correlation-Id (opcional)
    APIGW->>Lambda: Invoke (proxy)<br/>headers encaminhados sem modificação

    Lambda->>Lambda: Valida dígito verificador do CPF
    alt CPF malformado
        Lambda-->>APIGW: 400 {"erro": true, ...}
        APIGW-->>Cliente: 400 Bad Request
    end

    Lambda->>SM: GetSecretValue oficina-auth<br/>(credenciais do usuário oficina_auth)
    SM-->>Lambda: usuário e senha do banco
    Lambda->>SM: GetSecretValue oficina-auth-jwt-key<br/>(chave RSA privada)
    SM-->>Lambda: chave privada PEM

    Lambda->>RDS: SELECT id, ativo FROM atendimento_cliente<br/>WHERE documento = :cpf
    alt RDS ou Secrets Manager indisponível
        Lambda-->>APIGW: 503 Service Unavailable
        APIGW-->>Cliente: 503
    else CPF não cadastrado ou cliente inativo
        RDS-->>Lambda: 0 linhas, ou ativo = false
        Note over Lambda: motivo vai só para o log<br/>(auth.motivo = nao_encontrado | inativo)<br/>a resposta é 401 genérica — RFC-004 §4
        Lambda-->>APIGW: 401 Unauthorized
        APIGW-->>Cliente: 401
    else cliente existe e ativo
        RDS-->>Lambda: id = 42, ativo = true
        Lambda->>Lambda: Assina JWT RS256<br/>iss=oficina-auth, aud=oficina-api<br/>sub=cliente:42, cliente_id=42 (inteiro)<br/>principal_type=cliente, token_type=access<br/>iat, exp=+900s, jti=UUID
        Lambda-->>APIGW: 200 {"access_token": "...", "token_type": "Bearer", "expires_in": 900}<br/>X-Correlation-Id devolvido
        APIGW-->>Cliente: 200 OK
    end
```

### Regras que o diagrama codifica

| Passo | Regra | Onde está |
|---|---|---|
| 3–4 | CPF com dígito verificador inválido é `400` antes de qualquer acesso a segredo ou banco | Lambda (`tech-challenge-oficina-auth`) |
| 5–8 | Dois segredos distintos: credencial do banco e chave de assinatura. Nenhum vive em variável de ambiente nem em repositório | Secrets Manager `oficina-auth` e `oficina-auth-jwt-key` |
| 9 | A Lambda lê apenas a tabela `atendimento_cliente`, com o usuário `oficina_auth`, de dentro das subnets privadas; o security group do RDS aceita só EKS e Lambda | Repositório `tech-challenge-oficina-database` |
| 12–14 | CPF inexistente e cliente inativo recebem o **mesmo** `401`. Devolver `404` ou `403` transformaria o endpoint em oráculo de enumeração de clientes | [RFC-004 §4, regra 4](../rfcs/rfc-004-logs-estruturados-json.md) |
| 17 | `cliente_id` é inteiro e `sub` é `cliente:<id>`; a aplicação rejeita qualquer outra forma | `atendimento/authentication.py` (`_validate_claims`) |
| 18 | `expires_in` = 900 s. Não há refresh token para cliente — expirou, autentica de novo | Contrato em [`docs/fase3/integracao-repositorios.md`](../fase3/integracao-repositorios.md) |

## 3. Fluxo 2 — Primeiro consumo protegido com o token

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente (JWT em mão)
    participant APIGW as API Gateway REST<br/>ANY /{proxy+}
    participant VPCL as VPC Link
    participant ALB as ALB interno oficina-alb<br/>:8000
    participant Node as NodePort 30080<br/>(nodes do EKS oficina-eks)
    participant MW as CorrelationIdMiddleware<br/>app/observabilidade/middleware.py
    participant Auth as ClienteJWTAuthentication<br/>atendimento/authentication.py
    participant K8sSecret as Secret k8s oficina-auth<br/>AUTH_JWT_PUBLIC_KEY_B64
    participant View as VeiculoViewSet<br/>atendimento/views.py
    participant RDS as RDS PostgreSQL 17

    Cliente->>APIGW: GET /homologacao/api/v1/veiculos/<br/>header Authorization com o JWT de cliente (esquema Bearer)<br/>X-Correlation-Id (o mesmo do /auth)
    APIGW->>VPCL: encaminha ANY /{proxy+}
    VPCL->>ALB: HTTP :8000
    ALB->>Node: NodePort 30080 → Service oficina-app → pod Django

    Node->>MW: requisição entra no pod
    MW->>MW: lê traceparent, X-Request-Id e X-Correlation-Id<br/>gera UUIDv4 quando ausente ou inválido<br/>guarda em contextvars

    MW->>Auth: DRF chama authenticate()
    Auth->>Auth: _looks_like_cliente_jwt()<br/>decodifica sem verificar assinatura só para<br/>distinguir de token SimpleJWT de funcionário
    Auth->>K8sSecret: settings.AUTH_JWT_PUBLIC_KEY_B64<br/>(montado como env a partir do Secret)
    K8sSecret-->>Auth: chave pública PEM em Base64
    Auth->>Auth: jwt.decode(RS256, iss=oficina-auth,<br/>aud=oficina-api, require=sub, cliente_id,<br/>principal_type, token_type, iss, aud, iat, exp, jti)

    alt assinatura inválida, expirado, claim faltando ou malformada
        Auth-->>MW: AuthenticationFailed
        MW-->>Cliente: 401 {"erro": true, "status_code": 401, ...}<br/>X-Request-Id e X-Correlation-Id no header
    else token válido
        Auth->>RDS: SELECT ... FROM atendimento_cliente WHERE id = cliente_id
        alt cliente não existe mais ou ativo = false
            Auth-->>MW: AuthenticationFailed (Cliente inativo)
            MW-->>Cliente: 401
        else cliente ativo
            RDS-->>Auth: Cliente
            Auth-->>View: ClientPrincipal(cliente_id, cliente)
            View->>View: ClienteJWTViewSetPermission<br/>action em cliente_jwt_allowed_actions? (list, retrieve)
            alt action não permitida ao cliente (create, update, destroy, transições)
                View-->>Cliente: 403 Forbidden
            else list ou retrieve
                View->>RDS: SELECT ... FROM atendimento_veiculo<br/>WHERE cliente_id = principal.cliente_id
                RDS-->>View: veículos do próprio cliente
                View-->>MW: 200 (VeiculoClienteJWTSerializer)
                MW-->>Cliente: 200 OK<br/>X-Request-Id, X-Correlation-Id, traceparent nos headers
            end
        end
    end
```

### Regras que o diagrama codifica

| Passo | Regra | Onde está |
|---|---|---|
| 1–4 | Nada chega ao pod sem passar por API Gateway → VPC Link → ALB interno → NodePort. O ALB não tem IP público; a única porta de entrada é o Gateway | Repositório `tech-challenge-oficina-k8s` |
| 6 | O middleware é o **primeiro** item de `MIDDLEWARE`; tudo que a requisição loga a partir daqui carrega `trace.id`, `span.id`, `request.id` e `correlation.id` | `app/observabilidade/middleware.py`, [RFC-004 §7](../rfcs/rfc-004-logs-estruturados-json.md) |
| 8 | A pré-inspeção sem assinatura serve apenas para decidir **qual** autenticador trata o token. A autorização nunca depende dela | `ClienteJWTAuthentication._looks_like_cliente_jwt` |
| 9–11 | A chave pública entra pelo Secret Kubernetes `oficina-auth`; a chave privada nunca sai do Secrets Manager da Lambda | `k8s/` no repositório `tech-challenge-oficina-k8s`; `app/settings.py` (`AUTH_JWT_PUBLIC_KEY_B64`) |
| 15–17 | Mesmo com JWT válido, o cliente precisa continuar existindo e ativo no banco no momento da chamada. Desativar um cliente revoga o acesso sem esperar os 900 s | `ClienteJWTAuthentication._get_cliente_ativo` |
| 19–22 | Cliente só acessa `list` e `retrieve` de veículos e ordens **próprios**; o filtro é por `cliente_id` do token, e nenhum parâmetro da requisição amplia o escopo | `OwnedQuerySetMixin.get_cliente_queryset`, [`docs/fase3/matriz-permissoes-cliente-jwt.md`](../fase3/matriz-permissoes-cliente-jwt.md) |

## 4. O funcionário não passa por aqui

Funcionários continuam usando `POST /api/token/` (SimpleJWT, HS256, access de 30 min + refresh
de 1 dia), servido pela própria aplicação Django. Os dois esquemas coexistem na mesma lista
`DEFAULT_AUTHENTICATION_CLASSES`: `ClienteJWTAuthentication` devolve `None` quando o token não
tem cara de token de cliente, e o DRF passa ao autenticador seguinte. Ver
[RFC-003](../rfcs/rfc-003-autenticacao-jwt.md) para o fluxo do funcionário.

## 5. Correlação entre os dois fluxos

Os dois fluxos geram traces distintos (trace A na Lambda, trace B na aplicação). O que os liga,
quando a investigação precisa cruzá-los, é o **`X-Correlation-Id`**: o cliente envia o mesmo
valor nas duas chamadas (ou reaproveita o que a Lambda devolveu no passo 18 do fluxo 1), o
Gateway encaminha sem modificar, e Lambda e aplicação registram o valor em `correlation.id` no
log. Detalhes em [ADR-007](../adrs/adr-007-correlacao-w3c-trace-context.md) e em
[`docs/fase3/observabilidade/README.md` §3](../fase3/observabilidade/README.md).

## 6. Referências

- [`docs/fase3/integracao-repositorios.md`](../fase3/integracao-repositorios.md) — contrato de `/auth` e status esperados
- [`docs/fase3/matriz-permissoes-cliente-jwt.md`](../fase3/matriz-permissoes-cliente-jwt.md) — matriz de permissões do Cliente JWT
- [`docs/arquitetura/diagrama-componentes-nuvem.md`](diagrama-componentes-nuvem.md) — onde cada componente deste diagrama vive na AWS
- `atendimento/authentication.py`, `atendimento/permissions.py`, `app/observabilidade/middleware.py`

## 7. Histórico de Revisões

| Versão | Data | Autor | Descrição |
|---|---|---|---|
| 1.0 | 2026-09-09 | Luís Fernando Montes | Versão inicial, a partir do ambiente de homologação e de `atendimento/authentication.py` |
