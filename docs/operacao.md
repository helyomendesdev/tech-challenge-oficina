# Operação — Limitações e Segurança em Produção

Referenciado a partir do [`README.md`](../README.md). Para rate limiting e o fluxo do simulador
de orçamento, ver [`docs/regras-de-negocio.md`](regras-de-negocio.md).

## Limitações conhecidas

- O ambiente AWS Academy é temporário; recursos podem ser encerrados entre sessões.
- O CD (`cd.yml`) está configurado com OIDC e fallback por credenciais temporárias do Academy,
  mas não tem execução verde: depende de secrets AWS atualizados a cada sessão. O deploy em
  homologação foi feito manualmente em 08/09/2026.
- Produção não foi provisionada; `main` → `producao` existe só como convenção de branch,
  environment e `SERVICE_ENVIRONMENT`.
- O Metrics Server usa `--kubelet-insecure-tls`, aceitável apenas no Kind local.
- Build/load da imagem e instalação do Metrics Server são etapas imperativas nos orquestradores
  locais, embora a ordem esteja documentada.
- A arquitetura é híbrida e incremental: models, signals, ModelSerializers e ViewSets legados
  coexistem com use cases e ports da Fase 2.
- Metas de performance, disponibilidade e throughput não possuem ensaio atual comprovado;
  permanecem parciais na matriz de requisitos.
- PR, compartilhamento com a organização, publicação da collection, vídeo e PDF dependem de
  ações humanas listadas no checklist de entrega.

## Segurança em produção

Com `DJANGO_DEBUG=False` no `.env`, as seguintes proteções são ativadas automaticamente
(`app/settings.py`):

- `SECURE_SSL_REDIRECT = True`
- `SECURE_HSTS_SECONDS = 31536000` (HSTS por 1 ano)
- `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `X_FRAME_OPTIONS = 'DENY'`
