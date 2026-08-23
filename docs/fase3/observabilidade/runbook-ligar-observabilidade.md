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

1. Acesse `newrelic.com` e crie a conta pela opção de **free tier**.
2. **Não** informe cartão de crédito. O plano gratuito é perpétuo: 100 GB/mês de
   ingestão e 1 usuário *full platform*. Se a tela pedir cartão, você entrou pelo
   fluxo de trial pago — volte e escolha o plano gratuito.
3. Escolha a **região do data center** (US ou EU). A escolha é **definitiva** e
   muda o endpoint de ingestão; use **US**, que é o padrão e o que a maioria dos
   exemplos da documentação assume.
4. Confirme o e-mail de verificação.

### O que anotar depois

| Item | Onde encontrar | Para que serve |
|---|---|---|
| **License key** (tipo *Ingest - License*) | Administration → API keys | Autentica a ingestão do agente |
| **Account ID** | Administration → Access management, ou na URL | Requisito L1 da Lambda |

> A *User key* **não** serve para ingestão. Se o agente não reportar e não houver
> erro visível, o primeiro suspeito é ter copiado a chave errada.

### Onde a chave **não** pode entrar

- Nunca em arquivo versionado — nem em `.env.example`, nem em manifesto, nem em
  `docs/`.
- No cluster, vive num `Secret`. Localmente, vive no `.env`, que já está no
  `.gitignore`.

---

## 2. Rodar localmente com APM

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

## 3. Gerar tráfego

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

## 4. Cluster local (kind)

O `scripts/kind-deploy.sh` já sobe cluster, banco, migration e aplicação. Para a
observabilidade faltam duas coisas.

### 4.1 Secret da licença

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

### 4.2 Integração de Kubernetes (`nri-bundle`)

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

## 5. Conferir que chegou

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

## 6. Ordem que economiza retrabalho

1. Conta criada e chave em mãos
2. Aplicação instrumentada localmente, com trace e log chegando
3. Eventos de negócio no ar
4. Gerador de carga populando
5. D1, D2 e D3 montados
6. Só então cluster real, RDS, Lambda e os painéis que dependem deles

Montar painel antes do passo 3 significa montar duas vezes.
