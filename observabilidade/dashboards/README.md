# Dashboards como código

JSON dos dashboards da frente de Observabilidade, no formato que o New Relic
importa e exporta. Consultas de referência e o porquê de cada painel estão na
§6 de [`docs/fase3/observabilidade/README.md`](../../docs/fase3/observabilidade/README.md).

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `oficina-operacao-homologacao.json` | D1, D2, D3 e D4 do ambiente de homologação |

## Como importar

1. `one.newrelic.com` → **Dashboards** → **Import dashboard**
2. Colar o conteúdo do arquivo
3. Conferir que os widgets trazem dado; se algum vier vazio, ver "O que exige o quê" abaixo

Para **exportar** depois de editar pela interface: menu `...` do dashboard →
**Copy JSON**, e substituir o arquivo aqui. O JSON exportado traz `guid` e `id`
de cada widget; eles podem ficar — são ignorados na importação para outra conta.

## Antes de importar em outra conta

O campo `accountIds` de cada widget aponta para a conta onde o dashboard nasceu
(`8430077`). Importando em outra conta, é preciso trocar — a importação não
falha com o valor errado, ela só devolve widget vazio, que é o modo de falha
mais caro de diagnosticar.

## Produção

Este arquivo é o de **homologação**. A versão de produção é a mesma com a troca
descrita na §4 da especificação:

| Onde | Homologação | Produção |
|---|---|---|
| `OrdemServicoEvento`, `Log` | `service.environment = 'homologacao'` | `'producao'` |
| `Transaction` | `appName = 'oficina-api-hml'` | `'oficina-api-prd'` |
| `K8sContainerSample` | `clusterName = 'oficina-hml'` | `'oficina-prd'` |

**Não** faça isso com *facet* nem com `LIKE 'oficina-api%'`: facet separa a
visualização mas mantém os dois ambientes na mesma consulta, e o `LIKE` casaria
com os dois sufixos, misturando ambientes no mesmo percentil.

## O que exige o quê

| Painel | Depende de | Estado em 2026-08-23 |
|---|---|---|
| D1 — volume diário | `OrdemServicoEvento` emitido pela aplicação | ✅ dado real |
| D2 — tempo por status | idem, mais `data_ultima_transicao` | ✅ dado real |
| D3 — falhas de OS | idem, evento `FALHA` | ✅ dado real |
| D3 — erros de integração | log da aplicação chegando ao New Relic | depende do encaminhamento (ver abaixo) |
| D4 — latência | APM da aplicação | ✅ dado real |
| D5 — Kubernetes | `nri-bundle` no cluster | pendente — infra |
| D6 — autenticação | Lambda com a layer do New Relic | pendente — frente do Lucas |

### O widget de log e o encaminhamento

`NEW_RELIC_APPLICATION_LOGGING_FORWARDING_ENABLED` é **assimétrico de propósito**:

- **No Kubernetes: `false`.** Quem recolhe o `stdout` é a integração do cluster.
  Com o encaminhamento do agente também ligado, a mesma linha chega duas vezes e
  todo painel que conta linha conta dobrado.
- **Local (`docker compose`): `true`.** Não existe coletor nenhum no compose, então
  sem o encaminhamento do agente o log simplesmente não sai da máquina — e o
  widget de integração fica vazio sem que nada indique o motivo.

## Duas armadilhas do D2

**`FINALIZADA` só aparece se a consulta incluir `CONCLUSAO`.** A transição
`FINALIZADA → ENTREGUE` é emitida como evento `CONCLUSAO`, não `TRANSICAO`.
Filtrar só `evento = 'TRANSICAO'` — como a §6 da especificação fazia até
2026-08-23 — exclui em silêncio o tempo gasto no último status, e o painel mostra
quatro faixas onde deveria mostrar cinco. Ninguém percebe olhando o gráfico.

**A janela de 7 dias mistura rodadas de aceleração diferente.** O gerador comprime
o tempo pelo fator `--aceleracao`, então uma rodada de demonstração a 150000 e
outra realista a 3600 produzem durações em escalas incompatíveis, e a média entre
elas não significa nada. Em produção o problema não existe — é artefato do
gerador. Para conferir o painel depois de gerar carga, estreite a janela para
cobrir só a última rodada.

## D5 e D6

Ficam fora deste arquivo enquanto não houver dado por trás. Painel vazio num
dashboard entregue é pior que painel ausente: quem olha não sabe se o sistema
está saudável ou se a coleta está quebrada.
