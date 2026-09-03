# Integração entre Repositórios — Fase 3

## Visão inicial

```text
Cliente
  |
  v
API Gateway
  |-- autenticação por CPF --> Function Serverless --> banco gerenciado
  |
  `-- JWT válido --> aplicação Django no Kubernetes --> banco gerenciado
                                      |
                                      `--> logs, métricas e alertas
```

A posição definitiva do API Gateway e seus módulos Terraform depende de decisão conjunta com Sophia.

## Contratos que precisam ser definidos

### Autenticação

Entrada mínima:

```json
{
  "cpf": "00000000000"
}
```

Saída esperada em caso de sucesso:

```json
{
  "access_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

Decisao aprovada na aplicacao principal: `Cliente.ativo` indica se o cliente pode usar os fluxos integrados da Fase 3, nasce como `true` para preservar a base existente e nao altera endpoints publicos de OS.

Tokens de cliente aceitos pela aplicação usam `RS256`, `iss=oficina-auth`,
`aud=oficina-api`, `principal_type=cliente`, `token_type=access` e
`sub=cliente:<id>`. A aplicação valida a assinatura com
`AUTH_JWT_PUBLIC_KEY_B64`, que deve conter a chave pública PEM do emissor
codificada em Base64. Chaves reais não devem ser versionadas.

As demais decisões de autorização serão registradas com Lucas em RFC/ADR.

### Infraestrutura

Os módulos Terraform devem expor somente outputs necessários, por exemplo:

- Endpoint do banco.
- Identificador do cluster.
- Endpoint do API Gateway.
- Identificador da Function.
- URLs dos ambientes.

Segredos não devem ser publicados como outputs abertos nem copiados entre repositórios.

## Ambientes

| Branch | Ambiente | Regra |
|---|---|---|
| `develop` | Homologação | Deploy automático após CI e merge por PR |
| `main` | Produção | Deploy automático após CI e merge por PR aprovado |

## Ordem provisória de implantação

1. Infraestrutura do banco gerenciado.
2. Infraestrutura Kubernetes e rede.
3. Function Serverless de autenticação.
4. Aplicação principal.
5. API Gateway e rotas integradas, conforme decisão de infraestrutura.
6. Dashboards, monitores e alertas.

A ordem será revisada após a escolha da nuvem e a definição das dependências Terraform.

## Observabilidade transversal

Todos os componentes devem fornecer:

- Logs estruturados em JSON.
- **`X-Correlation-Id`** enviado pelo cliente e **encaminhado sem modificação pelo API
  Gateway**; a Function e a aplicação validam o valor, geram um UUIDv4 quando ele falta ou
  é inválido, e o devolvem no header da resposta — é dele que o cliente tira o valor a
  reusar na chamada seguinte. É o que liga o fluxo de autenticação ao de aplicação — os dois
  saem do Gateway de forma independente, e o `traceparent` sozinho não os cruza (ver
  `observabilidade/README.md` §3).
- `traceparent` / `tracestate` (W3C) para o trace técnico **dentro** de cada fluxo.
- Métricas de erro, latência e disponibilidade.
- Healthchecks quando aplicável.
- Alertas de falha no processamento de ordens de serviço.

A implementação e a ferramenta serão definidas com Luís.
