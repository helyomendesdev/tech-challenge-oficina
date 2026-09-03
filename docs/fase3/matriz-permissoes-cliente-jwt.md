# Matriz de permissoes do Cliente JWT

## Identidade

O Cliente JWT e identificado exclusivamente por `request.user.cliente_id`.
CPF, documento informado na requisicao, `request.user.id`, `created_by_id`,
`ClientPrincipal.pk` e IDs de `auth.User` nao autorizam acesso de Cliente.

## Matriz

| Area | Endpoint | Cliente JWT | Funcionario | Staff |
|---|---|---|---|---|
| Auth | `/api/token/`, `/api/token/refresh/` | Publico para SimpleJWT de funcionario | Publico | Publico |
| Veiculos | `GET /api/v1/veiculos/` | Lista somente veiculos com `cliente_id` do token | Mantem filtro por `created_by` | Todos |
| Veiculos | `GET /api/v1/veiculos/{id}/` | Somente veiculo proprio; outro cliente vira `404` | Mantem filtro por `created_by` | Todos |
| Veiculos | `POST`, `PUT`, `PATCH`, `DELETE` | Negado | Permitido conforme regra atual | Permitido |
| OS | `GET /api/v1/ordens-servico/` | Lista somente OS com `cliente_id` do token | Mantem filtro por `created_by` | Todas |
| OS | `GET /api/v1/ordens-servico/{id}/` | Somente OS propria; outro cliente vira `404` | Mantem filtro por `created_by` | Todas |
| OS | `GET /api/v1/ordens-servico/{id}/status/` | Somente status de OS propria; outro cliente vira `404` | Mantem regra atual | Todas |
| OS | `GET /api/v1/ordens-servico/consulta-cliente/` | Autenticado; ignora documento para autorizacao e retorna somente OS do `cliente_id` | Consulta operacional por identificador | Consulta operacional por identificador |
| OS actions | transicoes, fila, metricas, abertura, simulacao e notificacoes | Negado | Mantem regra atual | Mantem regra atual |
| Clientes | CRUD | Negado | Mantem regra atual | Mantem regra atual |
| Servicos/Pecas/Itens | CRUD e actions | Negado | Mantem regra atual | Mantem regra atual |
| Publicos restantes | health, schema, Swagger, ReDoc | Sem mudanca | Sem mudanca | Sem mudanca |

## Consulta-cliente

`consulta-cliente` nao aceita mais acesso anonimo. O parametro
`identificador` permanece por compatibilidade para funcionarios, mas para
Cliente JWT e legado/depreciado: pode ser enviado, porem nao define nem amplia
o escopo. A autorizacao usa somente `cliente_id` do token.

Exemplo ficticio:

```http
GET /api/v1/ordens-servico/consulta-cliente/ HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.exemplo.assinatura
```
