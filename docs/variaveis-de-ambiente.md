# Variáveis de Ambiente

Referência completa das variáveis usadas pela aplicação. Fonte da verdade: [`.env.example`](../.env.example)
— copie para `.env` e preencha antes de subir a aplicação. Resumo no [`README.md`](../README.md).

> **Segurança:** o arquivo `.env` está no `.gitignore` e **nunca deve ser commitado**. Use
> `.env.example` como template — ele contém apenas nomes, sem valores sensíveis.

## Django e banco

| Variável | Padrão (exemplo) | Descrição |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(obrigatório)* | Chave secreta do Django — nunca commitar |
| `DJANGO_DEBUG` | `False` | `True` apenas em desenvolvimento local |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos, separados por vírgula |
| `SECURE_SSL_REDIRECT` | `False` | `True` em produção atrás de TLS |
| `POSTGRES_DB` | `oficina_db` | Nome do banco de dados |
| `POSTGRES_USER` | `admin` | Usuário do PostgreSQL |
| `POSTGRES_PASSWORD` | *(obrigatório)* | Senha do PostgreSQL — nunca commitar |
| `DB_HOST` | `db` | Host do banco (`db` no Docker, `localhost` fora) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Origens permitidas para o frontend |

## Integrações da Fase 3

| Variável | Padrão (exemplo) | Descrição |
|---|---|---|
| `WEBHOOK_ORCAMENTO_URL` | `http://localhost:8000/api/v1/orcamentos/notificacoes/` | URL usada pelo simulador de aprovação/recusa de orçamento (ver [`docs/regras-de-negocio.md`](regras-de-negocio.md)) |
| `AUTH_JWT_PUBLIC_KEY_B64` | *(vazio)* | Chave pública PEM (Base64) do emissor `oficina-auth`, usada por `ClienteJWTAuthentication` para validar o JWT RS256 do cliente. Nunca versionar a chave real |

## Observabilidade (Fase 3)

| Variável | Padrão (exemplo) | Descrição |
|---|---|---|
| `SERVICE_NAME` | `oficina-api` | Nome do serviço nos logs e no New Relic |
| `SERVICE_ENVIRONMENT` | `homologacao` | Filtro obrigatório em todo widget e alerta — ver `docs/fase3/observabilidade/README.md` §4 |
| `SERVICE_VERSION` | `1.0.0` | Versão reportada nos eventos |
| `OBSERVABILIDADE_SALT` | *(obrigatório, único por ambiente)* | Salt do hash de `cliente.ref`. Precisa diferir entre homologação e produção — com o mesmo salt, o mesmo CPF gera o mesmo hash nos dois ambientes e o pseudônimo deixa de proteger o dado |
| `NEW_RELIC_LICENSE_KEY` | *(vazio)* | Chave "Ingest - License" (não a User Key). Deixe vazio para rodar sem APM — a aplicação sobe normalmente e o entrypoint avisa em qual modo subiu |
| `NEW_RELIC_APP_NAME` | `oficina-api-hml` | Nome da aplicação no New Relic APM |
| `NEW_RELIC_DISTRIBUTED_TRACING_ENABLED` | `true` | Habilita distributed tracing |
| `NEW_RELIC_APPLICATION_LOGGING_FORWARDING_ENABLED` | `false` | Mantido `false` em todo ambiente: no cluster, a integração de Kubernetes já recolhe o stdout, e os dois ligados duplicam a linha; localmente, o encaminhamento do agente ignora o formatter JSON. Para conferir o log local, leia o stdout do container |
