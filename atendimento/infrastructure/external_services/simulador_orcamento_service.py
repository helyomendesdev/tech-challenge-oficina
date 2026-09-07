import logging
import requests
from django.conf import settings
from app.observabilidade.logging import trace_id_var, span_id_var, correlation_id_var, tracestate_var

logger = logging.getLogger(__name__)


class SimuladorOrcamentoService:
    """
    Simula um sistema externo responsável pela aprovação ou recusa
    de orçamentos de clientes.

    Este serviço representa um consumidor externo da API da oficina.
    Ele realiza uma chamada HTTP real para o webhook de notificações
    de orçamento, enviando a decisão tomada pelo cliente.

    Fluxo simulado:

        Cliente
          |
          v
        SimuladorOrcamentoService
          |
          | HTTP POST
          v
        Webhook da API Oficina
          |
          v
        ProcessarRespostaOrcamentoUseCase

    Observação:
        Este serviço existe apenas para simular uma integração externa.
        O FakeNotificationAdapter continua sendo utilizado como fallback
        nos fluxos internos da aplicação.
    """

    def enviar_decisao(
        self,
        ordem_servico_id: int,
        decisao: str,
        motivo: str = "",
        authorization: str | None = None,
    ) -> dict:
        payload = {
            "ordem_servico_id": ordem_servico_id,
            "decisao": decisao,
            "origem": "simulador_cliente",
            "motivo": motivo,
        }

        headers = {}

        # Propagar W3C Trace Context conforme §5.2
        trace_id = trace_id_var.get()
        span_id = span_id_var.get()
        correlation_id = correlation_id_var.get()
        tracestate = tracestate_var.get()
        if trace_id and span_id:
            headers["traceparent"] = f"00-{trace_id}-{span_id}-01"

        # tracestate e opaco: so propaga o que foi recebido do chamador,
        # nunca fabrica um valor novo -- o agente New Relic tambem guarda
        # estado de vendor nesse header, e sobrescrever atropelaria isso.
        if tracestate:
            headers["tracestate"] = tracestate

        # Propagar X-Correlation-Id conforme §5.2
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id

        if authorization:
            headers["Authorization"] = authorization

        try:
            response = requests.post(
                settings.WEBHOOK_ORCAMENTO_URL,
                json=payload,
                headers=headers,
                timeout=5,
            )

            response.raise_for_status()

            # Log de sucesso de integração (§5.1)
            extra = {
                'integracao': 'simulador-orcamento',
                'integracao_status': 'sucesso',
            }
            logger.info(
                f"Integração com simulador de orçamento bem-sucedida: OS {ordem_servico_id}",
                extra=extra
            )

            return response.json()

        except requests.exceptions.HTTPError:
            try:
                erro = response.json()
            except ValueError:
                erro = {"mensagem": response.text}

            # Log de erro HTTP de integração (§5.1)
            extra = {
                'integracao': 'simulador-orcamento',
                'integracao_status': 'erro',
            }
            logger.error(
                f"Erro HTTP na integração com simulador: {response.status_code}",
                extra=extra,
                exc_info=True
            )

            return {
                "erro": True,
                "status_code": response.status_code,
                "detalhes": erro,
            }

        except requests.exceptions.RequestException as exc:
            # Log de erro de conexão de integração (§5.1)
            extra = {
                'integracao': 'simulador-orcamento',
                'integracao_status': 'erro',
            }
            logger.error(
                f"Falha ao comunicar com o webhook: {exc}",
                extra=extra,
                exc_info=True
            )

            return {
                "erro": True,
                "status_code": 503,
                "mensagem": f"Falha ao comunicar com o webhook: {exc}",
            }
