# Estrutura de Repositórios — Fase 3

## Objetivo

Separar aplicação, autenticação e infraestrutura em quatro repositórios com limites claros, CI/CD independente e deploy automático para homologação e produção.

## Repositórios

| Repositório | Escopo | Responsável principal |
|---|---|---|
| `tech-challenge-oficina` | Aplicação Django executada no Kubernetes | Equipe de aplicação |
| `tech-challenge-oficina-auth` | Function Serverless para validar CPF, consultar cliente e emitir JWT | Lucas Marques |
| `tech-challenge-oficina-k8s` | Cluster Kubernetes, rede, escalabilidade e componentes de entrada definidos em conjunto com infraestrutura | Sophia Sussa Campos Bastos |
| `tech-challenge-oficina-database` | Banco gerenciado e recursos relacionados provisionados por Terraform | Sophia Sussa Campos Bastos |

Hélio Mendes é responsável pelos nomes, estrutura, governança Git e padronização dos repositórios. Luís Fernando Montes é responsável pela observabilidade transversal.

## Limites iniciais

### Aplicação principal

Contém:

- Código Django e regras de negócio.
- Dockerfile da aplicação.
- Testes automatizados.
- Configuração necessária para executar no Kubernetes.
- Healthchecks e emissão de logs estruturados.

Não deve provisionar cluster ou banco gerenciado.

### Autenticação serverless

Contém:

- Validação de CPF.
- Consulta de existência e status do cliente.
- Emissão de JWT.
- Testes e empacotamento da Function.
- Infraestrutura estritamente necessária à própria Function, caso o grupo aprove esse limite.

### Infraestrutura Kubernetes

Contém:

- Terraform do cluster Kubernetes.
- Rede e escalabilidade do cluster.
- Configuração de homologação e produção.
- Integração com o API Gateway, se esse limite for aprovado com Sophia.

### Infraestrutura do banco

Contém:

- Terraform do banco gerenciado.
- Rede, parâmetros, backups e políticas do banco.
- Outputs consumidos de forma segura pelos demais ambientes.
- Documentação do modelo e das decisões de persistência.

## Decisões pendentes com infraestrutura

Antes de fechar os módulos e o CD, Hélio e Sophia devem confirmar:

1. Provedor de nuvem.
2. Serviço Kubernetes gerenciado.
3. Serviço de banco gerenciado.
4. Local do Terraform do API Gateway.
5. Forma de comunicação entre Gateway, Function e aplicação.
6. Estratégia de estado remoto do Terraform.
7. Nomes e isolamento dos ambientes de homologação e produção.
8. Outputs publicados entre os repositórios.

## Governança obrigatória

- `develop`: homologação.
- `main`: produção.
- Mudanças entram exclusivamente por Pull Request.
- Pelo menos uma aprovação por Pull Request.
- CI obrigatório antes do merge.
- Force push e exclusão de `develop` e `main` bloqueados.
- Deploy de homologação a partir de `develop`.
- Deploy de produção a partir de `main`.

As proteções remotas serão configuradas depois da autenticação do GitHub CLI e da criação dos repositórios.
