# Matriz de permissoes do Cliente JWT

## Identidade

O Cliente JWT e identificado exclusivamente por `request.user.cliente_id`.
CPF, documento informado na requisicao, `request.user.id`, `created_by_id`,
`ClientPrincipal.pk` e IDs de `auth.User` nao autorizam acesso de Cliente.
Claims nao verificadas podem ser usadas apenas para escolher o validador de
JWT, nunca para autenticar nem autorizar.

`AUTH_JWT_PUBLIC_KEY_B64` deve receber a chave publica PEM do emissor codificada
em Base64. A ausencia ou ma formacao dessa variavel bloqueia tentativas de JWT
de Cliente, mas nao bloqueia endpoints publicos restantes nem SimpleJWT de
funcionarios.

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

## Respostas esperadas

| Situacao | Resposta |
|---|---|
| Sem token em `consulta-cliente` | `401` |
| JWT de Cliente invalido, expirado, issuer/audience/claims incorretos ou assinatura invalida | `401` |
| Cliente JWT em write, transicao, fila, metrica ou action GET nao autorizada | `403` |
| Cliente JWT acessando recurso de outro cliente | `404` |
| Funcionario comum acessando recurso fora do seu `created_by` legado | `404` conforme regra atual |

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

## Coexistencia com funcionarios

JWT de Cliente e SimpleJWT de funcionario coexistem na aplicacao Django.
Funcionario e staff continuam representados por `auth.User`; Cliente externo e
representado por `ClientPrincipal`, que nao herda de `auth.User`, tem `id=None`
e nunca deve ser persistido em `created_by`.
