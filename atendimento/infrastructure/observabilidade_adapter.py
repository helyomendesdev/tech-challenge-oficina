"""Adapter real de observabilidade — emissão para New Relic.

Implementa ObservabilidadePort para registrar custom events em New Relic ou em JSON
quando o agente não está disponível. O enriquecimento de traceId e service.environment
acontece aqui, baseado em contextvars.
"""

import logging
from typing import Any

from app.observabilidade.logging import trace_e_span
from django.conf import settings

# Import defensivo: a aplicação roda sem o pacote newrelic instalado
try:
    from newrelic.agent import record_custom_event, application
except ImportError:
    record_custom_event = None
    application = None

# Sob `atendimento` de proposito: o LOGGING de settings configura handler para
# `django` e `atendimento`. Um logger de raiz propria nao tem handler nenhum, e
# o evento sumia em silencio -- que hoje e o unico caminho, sem o agente.
logger = logging.getLogger('atendimento.observabilidade')


class ObservabilidadeAdapter:
    """Adapter real para emissão de custom events de negócio.

    Com New Relic disponível, emite via record_custom_event('OrdemServicoEvento', {...}).
    Sem o agente, emite como log JSON estruturado usando o formatter existente.
    """

    def registrar_evento_ordem_servico(self, evento_dict: dict[str, Any]) -> None:
        """Registra um evento de transição de OS em New Relic ou log JSON.

        Args:
            evento_dict: Dicionário com os campos do evento (conforme ObservabilidadePort)
        """
        # Enriquecer o evento com traceId e service.environment
        trace_id, span_id = trace_e_span()
        service_environment = getattr(settings, 'SERVICE_ENVIRONMENT', 'dev')

        evento_completo = {
            **evento_dict,
            'traceId': trace_id,
            'service.environment': service_environment,
        }

        if record_custom_event is not None and application is not None:
            # New Relic disponível E ativo: emitir custom event.
            # Checar `application` evita o descarte silencioso do SDK quando
            # o agente está instalado mas inativo (ver review do Luís no PR #19).
            try:
                record_custom_event('OrdemServicoEvento', evento_completo)
            except Exception as e:
                # Log de fallback se o agente falhar (não deve quebrar a requisição)
                logger.warning(
                    f"Falha ao registrar custom event no New Relic: {e}",
                    exc_info=True
                )
                self._emitir_como_log_json(evento_completo)
        else:
            # Fallback: emitir como log JSON estruturado
            self._emitir_como_log_json(evento_completo)

    def _emitir_como_log_json(self, evento: dict[str, Any]) -> None:
        """Emite o evento como log JSON estruturado (fallback sem New Relic).

        Usa o formatter JSONFormatter de app/observabilidade/logging.py que
        já injeta trace.id, span.id e request.id automaticamente.
        """
        # O dicionario inteiro vai no extra: sem isso o fallback perderia
        # duracaoStatusSegundos, erroTipo, traceId e service.environment, que sao
        # justamente os campos que D2 e D3 consomem.
        logger.info(
            f"Evento de ordem de servico: {evento.get('evento')}",
            extra={
                'evento_negocio': evento,
                'os_id': evento.get('osId'),
                'os_status_anterior': evento.get('statusAnterior'),
                'os_status_novo': evento.get('statusNovo'),
            },
        )
