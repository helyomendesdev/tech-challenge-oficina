# Alertas

Política **`Oficina — Produção`**, com as oito condições da §7 de
[`docs/fase3/observabilidade/README.md`](../../docs/fase3/observabilidade/README.md).

| Arquivo | Conteúdo |
|---|---|
| `condicoes.json` | Definição de cada condição: NRQL, operador, limiar, janela |
| `runbooks.md` | Um runbook por alerta — o que significa, onde olhar, o que fazer |

## Por que não há JSON de importação

Dashboard se importa e exporta como JSON. **Condição de alerta não.** No New Relic
ela se cria pela interface, por Terraform ou pela API NerdGraph. O
`condicoes.json` deste diretório é a **fonte** dessas definições, não um artefato
que o New Relic consuma: quem cria, cria a partir dele.

Manter as definições aqui vale porque a condição criada na interface não guarda
histórico nem justificativa. O limiar de 5% de A2 é uma escolha, e uma escolha sem
registro vira número mágico que ninguém ousa mexer.

## Estado em 2026-08-23

| # | Alerta | Severidade | Dado disponível |
|---|---|---|---|
| **A1** | Falha no processamento de OS *(exigido)* | Crítico | ✅ |
| A2 | Taxa de erro da API | Crítico | ✅ |
| A3 | Latência degradada | Aviso | ✅ |
| A4 | Endpoint fora do ar | Crítico | ❌ URL pública de produção |
| A5 | Saturação de memória do pod | Aviso | ❌ `nri-bundle` no cluster |
| A6 | Pod em CrashLoop | Crítico | ❌ `nri-bundle` no cluster |
| A7 | Falha de autenticação sistêmica | Crítico | ❌ Lambda com a layer |
| A8 | Banco saturado | Aviso | ❌ integração AWS do RDS |

Os três que já têm dado são criáveis hoje. Os cinco restantes dependem de
infraestrutura de outras frentes — **criar antes disso produz condição que nunca
avalia**, o que é pior que condição ausente: o painel de alertas mostra tudo verde
e ninguém sabe que a coleta não existe.

## Duas decisões embutidas

**`incidentPreference: PER_CONDITION`.** Agrupa incidentes por condição. Com
`PER_POLICY`, um pod saturado e uma falha de ordem de serviço viram o mesmo
incidente, e o segundo problema fica escondido atrás do primeiro.

**Toda condição filtra ambiente na própria NRQL.** Não é decoração: o gerador de
carga com `--falhas` produz eventos `FALHA` legítimos, e sem o filtro um teste em
homologação dispara alerta de produção. O alerta perderia credibilidade justamente
na véspera da gravação.

## O que falta decidir

**Canal de notificação.** A §7 fala em "canal do grupo (e-mail e/ou webhook)", mas
o destino concreto não está definido. Sem destino, a condição dispara e ninguém
recebe — estado que parece configurado e não é.

## Como criar

Pela interface: **Alerts** → **Alert conditions** → **New alert condition** →
*NRQL* → colar a consulta de `condicoes.json`, aplicar operador, limiar e janela, e
apontar a URL de runbook para a âncora correspondente em `runbooks.md`.

Depois de criar, **confirme que a condição avalia**: uma condição sobre tipo de
evento inexistente fica em silêncio permanente sem sinalizar erro.
