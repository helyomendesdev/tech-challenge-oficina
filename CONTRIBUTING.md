# Contribuição

Este projeto usa Pull Requests obrigatórios e separação entre homologação e produção.

## Branches

- `main`: produção.
- `develop`: homologação.
- `feature/<descricao>`: novas funcionalidades.
- `fix/<descricao>`: correções.
- `chore/<descricao>`: manutenção, documentação e configuração.

## Fluxo de trabalho

1. Atualize sua base a partir de `develop`.
2. Crie uma branch curta com o prefixo adequado.
3. Faça mudanças pequenas e testáveis.
4. Abra Pull Request para `develop`.
5. Aguarde o CI e pelo menos uma aprovação.
6. Resolva todas as conversas antes do merge.
7. Para produção, abra Pull Request de `develop` para `main`.

Commits diretos e force push em `develop` e `main` não são permitidos.

## Requisitos do Pull Request

- Descrever problema, solução e forma de validação.
- Relacionar mudanças aos requisitos da Fase 3 quando aplicável.
- Não incluir senhas, tokens, chaves ou arquivos `.env`.
- Atualizar documentação e testes quando houver mudança de comportamento.
- Manter o pipeline verde.

## Validação local da aplicação

```bash
python manage.py check --settings=app.settings_test
python -m pytest atendimento/tests/ -q

docker build -t oficina-app:local .
```

As variáveis de teste necessárias estão documentadas em `.env.example` e no workflow de CI.

## Responsabilidades da Fase 3

- Hélio Mendes: nomes, estrutura, governança e organização dos repositórios.
- Luís Fernando Montes: observabilidade.
- Lucas Marques: autenticação serverless por CPF e JWT.
- Sophia Sussa Campos Bastos: infraestrutura em nuvem.
