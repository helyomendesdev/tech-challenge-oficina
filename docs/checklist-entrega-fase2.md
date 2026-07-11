# Checklist de entrega — Fase 2

Itens externos só devem ser marcados após confirmação humana na plataforma.

## Código e repositório

- [x] Branch conferida: `fase-2-testes`.
- [ ] Pull request aberto e revisado: `PENDENTE_LINK_REPOSITORIO`.
- [ ] Pipeline CI/CD verde confirmado no GitHub.
- [ ] Repositório compartilhado com `soat-architecture`:
  `PENDENTE_ACESSO_SOAT_ARCHITECTURE`.
- [ ] Links do README, PR e artefatos revisados.

## APIs e Postman

- [x] Collection local válida, com 76 requests.
- [x] Swagger e ReDoc derivados do schema validado.
- [ ] Collection publicada em workspace acessível.
- [ ] Link público ou compartilhável: `PENDENTE_LINK_POSTMAN`.
- [ ] APIs críticas demonstradas: JWT, abertura, status, orçamento,
  notificação externa, fila e métricas.

## Ambiente e infraestrutura

- [x] Dockerfile e Docker Compose revisados.
- [x] Deploy local em Kind validado com aplicação e PostgreSQL Ready.
- [x] Metrics Server e `kubectl top pods` validados.
- [ ] HPA demonstrado com CPU, scale-up e scale-down.
- [x] Terraform demonstrado com plan/apply/destroy local.
- [x] Destruição do cluster/state confirmada após a validação.

## Vídeo

- [ ] Vídeo publicado.
- [ ] Link: `PENDENTE_LINK_VIDEO`.
- [ ] Duração menor ou igual a 15 minutos.
- [ ] Áudio, terminal e editor legíveis.
- [ ] Esperas e limitações do HPA apresentadas honestamente.
- [ ] Nenhum segredo, token ou senha real aparece na gravação.

## Documento final

- [ ] PDF final gerado.
- [ ] Links do repositório, Postman e vídeo incluídos no PDF.
- [ ] Matriz de requisitos anexada ou referenciada.
- [ ] Números consistentes: 210 testes, 3 subtests, 94,52% de cobertura,
  34 caminhos/60 operações OpenAPI e 76 requests Postman.
- [ ] Integrantes, turma e grupo revisados.

## Evidências mínimas

- Saída de `pytest --cov=atendimento --cov-report=term-missing --cov-fail-under=80`.
- Saída da validação do OpenAPI.
- Saídas de `kubectl get ...`, `kubectl top pods` e `kubectl get hpa`.
- Linha `SMOKE_TEST=PASS`.
- Linha `HPA_TEST=PASS` — pendente nesta revisão.
- Resumo de Terraform plan, apply e destroy.
- URL e status da execução remota dos workflows.
