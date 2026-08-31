# Runbook — Ligar a observabilidade

Passo a passo para sair de zero até ver trace, log e dashboard com dado real.
Complementa a §10 do [README da frente](README.md).

> **Estado deste runbook:** os comandos abaixo **não foram executados contra um
> cluster real** — foram escritos a partir da documentação da ferramenta e do que
> os manifestos do repositório já fazem. Rode um passo de cada vez e confira a
> saída antes de seguir. Onde a saída real divergir, corrija aqui.

---

## 1. Criar a conta New Relic

Esta parte é manual e leva poucos minutos.

1. Acesse `newrelic.com/signup`. A tela chama-se **"Create your free account"** e
   pede só dois campos: **Company Email** e **Name**. O botão é
   **"Get Started Free"**. Há também "Or sign up with" — Google, GitHub, GitLab e
   Bitbucket.
2. Apesar do rótulo *Company Email*, e-mail pessoal costuma ser aceito. Se for
   recusado, use o cadastro pelo GitHub.
3. Confirme o e-mail de verificação.

O plano gratuito é perpétuo: 100 GB/mês de ingestão e 1 usuário *full platform*.
A própria página declara **"No credit card required"** — não há etapa de
pagamento neste fluxo.

> **Região do data center:** não há escolha na tela de cadastro. Se ela aparecer
> em alguma etapa posterior, a decisão é definitiva e muda o endpoint de
> ingestão. Conferido em 2026-08-23; a descrição anterior deste runbook mandava
> escolher a região no cadastro, o que não corresponde à tela real.

### O que anotar depois

| Item | Onde encontrar | Para que serve |
|---|---|---|
| **License key** (tipo *Ingest - License*) | Administration → API keys | Autentica a ingestão do agente |
| **Account ID** | Administration → Access management, ou na URL | Requisito L1 da Lambda |

> A *User key* **não** serve para ingestão. Se o agente não reportar e não houver
> erro visível, o primeiro suspeito é ter copiado a chave errada.

### Confirmar a chave antes de ligar qualquer coisa

**Faça este passo sempre.** Chave errada não produz erro visível: o agente sobe,
a aplicação funciona, e o painel simplesmente fica vazio. Descobrir isso depois
de subir Docker, cluster e gerador custa horas de procura no lugar errado.

Uma requisição responde em segundos, mandando uma linha de log de teste:

```bash
curl -s -o /dev/null -w "HTTP %{http_code}
"   -X POST "https://log-api.newrelic.com/log/v1"   -H "Api-Key: $NEW_RELIC_LICENSE_KEY"   -H "Content-Type: application/json"   -d '{"message":"teste de ingestao","service.name":"oficina-api","logtype":"teste-setup"}'
```

| Resposta | Significado |
|---|---|
| `HTTP 202` | Chave válida e ingestão funcionando |
| `HTTP 403` | Chave recusada — tipo errado, ou região errada |

Trocando o host por `log-api.eu.newrelic.com`, o mesmo teste diz **em que região
a conta vive**: a região certa devolve 202 e a outra devolve 403.

**Conferido em 2026-08-23 nesta conta:** US devolveu 202, EU devolveu 403 — a
conta é **US**, e é esse o endpoint de todos os componentes.

### Como reconhecer a chave certa

| Sinal | License key de ingestão |
|---|---|
| Comprimento | 40 caracteres |
| Sufixo | termina em `NRAL` |
| Teste de ingestão | devolve `202` |

Um valor com comprimento diferente é outra coisa — foi o que aconteceu na
primeira tentativa aqui: 64 caracteres hexadecimais, recusados com 403 nas duas
regiões.

### Onde a chave **não** pode entrar

- Nunca em arquivo versionado — nem em `.env.example`, nem em manifesto, nem em
  `docs/`.
- No cluster, vive num `Secret`. Localmente, vive no `.env`, que já está no
  `.gitignore`.

---

## 2. Gerar e aplicar o salt de pseudonimização (`OBSERVABILIDADE_SALT`)

`cliente.ref` (§5.1 do [README da frente](README.md)) é um hash do CPF com este
salt. Com o mesmo salt em dois ambientes, o mesmo CPF produz o mesmo hash em
homologação e produção, e o pseudônimo vira um identificador estável —
reversível por quem tiver uma lista de CPFs para comparar. Por isso o salt
**precisa ser diferente por ambiente**, e vem sempre de Secret, nunca de
ConfigMap nem de arquivo versionado.

### Gerar um valor

Mesmo gerador que o `kind-deploy.sh`/`kind-deploy.ps1` já usa para
`DJANGO_SECRET_KEY`:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Gere um valor novo por ambiente — local, homologação e produção usam três
salts diferentes entre si, nunca o mesmo valor copiado de um para o outro.

### Onde ele vive

| Ambiente | Onde | Como |
|---|---|---|
| Local | `.env` (não versionado) | `OBSERVABILIDADE_SALT=<valor gerado>` — o `.env.example` já traz a variável comentada |
| Cluster | Secret `oficina-secret` | ver comando abaixo |

No cluster, a variável entra no mesmo Secret `oficina-secret` que o
`deployment.yaml` já injeta via `envFrom: secretRef` — não crie um Secret à
parte, como se faz para a license key do New Relic no passo 5.1. O
`kind-deploy.sh`/`kind-deploy.ps1` não gera `OBSERVABILIDADE_SALT` sozinho —
só cuida de `DJANGO_SECRET_KEY` e das credenciais do Postgres —, então este
passo é manual e roda **depois** do deploy inicial já ter criado o Secret:

```bash
kubectl patch secret oficina-secret \
  --namespace oficina \
  --type merge \
  -p "{\"stringData\":{\"OBSERVABILIDADE_SALT\":\"$OBSERVABILIDADE_SALT\"}}"
```

Passe o valor por variável de ambiente, nunca digitado no comando — o
histórico do shell guarda o que você digita.

### Se faltar

Em ambiente **não local**, faltar `OBSERVABILIDADE_SALT` não é um modo de uso
válido — diferente da license key do New Relic. A aplicação **não sobe**: a
inicialização falha com `ImproperlyConfigured`. Se o pod não fica `Ready` e o
log de erro cita essa exceção, o suspeito é este passo, não o deploy em si.

### Rotação

Trocar o salt muda o hash de **todo** CPF de uma vez. O `cliente.ref` gravado
antes da rotação deixa de bater com o `cliente.ref` gerado depois para o mesmo
cliente — eventos e logs antigos param de correlacionar com os novos.
Rotacione só quando o motivo justificar perder essa correlação (ex.: suspeita
de vazamento do salt), nunca como manutenção de rotina.

---

## 3. Rodar localmente com APM

O `.env` é o único lugar onde a chave entra:

```
NEW_RELIC_LICENSE_KEY=<sua-chave-de-ingestao>
NEW_RELIC_APP_NAME=oficina-api-hml
```

Suba normalmente:

```bash
docker compose up --build
```

O entrypoint diz em qual modo subiu:

```
INFO: subindo sob o agente New Relic (NEW_RELIC_LICENSE_KEY presente)
```

Se a linha disser `subindo sem APM`, a variável não chegou ao container —
confira o `env_file` do serviço no `docker-compose.yml`.

**Deixar a chave vazia é um modo de uso válido**, não um erro: a aplicação sobe
sem APM e todo o resto (log JSON, correlação, eventos de negócio pelo fallback de
log) continua funcionando. É assim que quem não é desta frente roda o projeto.

---

## 4. Gerar tráfego

Sem histórico, o dashboard aparece vazio na hora de gravar o vídeo. O gerador
existe para isso:

```bash
python scripts/gerar_carga_observabilidade.py \
    --base-url http://localhost:8000 \
    --usuario admin --senha admin \
    --duracao 600 --taxa 12
```

Duas regras:

- **Rode sempre contra homologação.** As falhas de `--falhas` são erros de
  verdade; em produção acionariam o alerta A1.
- **Instrumente antes de gerar.** O gerador produz tráfego, não eventos de
  negócio. Rodar antes de o item 6 da §8 estar no ar popula APM, log e banco,
  mas **não** D1 e D2.

Detalhes na §9.1 do [README da frente](README.md).

---

## 5. Cluster local (kind)

O `scripts/kind-deploy.sh` já sobe cluster, banco, migration e aplicação. Para a
observabilidade faltam duas coisas.

### 5.1 Secret da licença

O `deployment.yaml` referencia o secret `newrelic-license` como **opcional**, então
o cluster sobe sem ele. Para ligar o APM:

```bash
kubectl create secret generic newrelic-license \
  --namespace oficina \
  --from-literal="NEW_RELIC_LICENSE_KEY=$NEW_RELIC_LICENSE_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
```

Passe a chave por variável de ambiente, nunca digitada no comando — o histórico do
shell guarda o que você digita.

### 5.2 Integração de Kubernetes (`nri-bundle`)

É o que entrega CPU, memória, HPA e reinícios por pod (§5.3), **sem** instrumentar
código. Instalação por Helm; confira os parâmetros na documentação da ferramenta
antes de rodar, porque os nomes de valor mudam entre versões do chart.

O que precisa ficar verdadeiro ao final:

- o cluster reporta com um nome que **separa ambientes** (`oficina-hml` /
  `oficina-prd`) — os painéis filtram por `clusterName`, e nome repetido mistura
  os dois no mesmo gráfico;
- a coleta de log do cluster está ligada, já que é ela que recolhe o `stdout` da
  aplicação (e é por isso que o agente **não** encaminha log — ver §6.4 do
  [RFC-004](../../rfcs/rfc-004-logs-estruturados-json.md));
- `egress` 443 liberado para o endpoint da ferramenta (requisito da infra).

---

## 6. Conferir que chegou

Antes de montar painel, confirme que o dado existe:

| Sinal | Como conferir |
|---|---|
| APM | A aplicação aparece na lista de serviços, com transações por rota |
| Trace | Uma transação abre e mostra o span de banco como filho |
| Log | Uma linha de log traz `trace.id`, e o trace correspondente lista a linha |
| Evento de negócio | Consulta em `OrdemServicoEvento` devolve linhas após o gerador rodar |
| Kubernetes | `K8sContainerSample` devolve pods do cluster |

Se APM aparece mas log não correlaciona, o suspeito é a §6.3 do
[RFC-004](../../rfcs/rfc-004-logs-estruturados-json.md): `trace.id` vindo de fonte
errada.

Se o evento de negócio não aparece **e** não há erro, o suspeito é o logger — ver
§6.5 do mesmo RFC. Ausência silenciosa é o modo de falha típico desta frente.

---

## 7. Ordem que economiza retrabalho

1. Conta criada e chave em mãos
2. Aplicação instrumentada localmente, com trace e log chegando
3. Eventos de negócio no ar
4. Gerador de carga populando
5. D1, D2 e D3 montados
6. Só então cluster real, RDS, Lambda e os painéis que dependem deles

Montar painel antes do passo 3 significa montar duas vezes.
