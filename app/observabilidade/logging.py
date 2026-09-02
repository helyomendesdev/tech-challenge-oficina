"""
Formatador JSON para observabilidade estruturada.

Emite logs em formato JSON com schema de §5.1 da especificação de observabilidade.
Injeta trace.id e span.id automaticamente via contextvars.
"""

import json
import logging
import traceback
from datetime import datetime
from contextvars import ContextVar
from hashlib import sha256
from typing import Optional
from django.conf import settings

try:  # o agente e opcional: a app roda e a suite passa sem o pacote instalado
    from newrelic.agent import get_linking_metadata as _metadados_do_agente
except Exception:  # pragma: no cover - depende do ambiente, nao da logica
    _metadados_do_agente = None

# ContextVars para armazenar trace, span, request ID, correlation ID e tracestate
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
tracestate_var: ContextVar[Optional[str]] = ContextVar('tracestate', default=None)


def cliente_ref(cpf: str) -> str:
    """
    Retorna referência do cliente em formato sha256 com salt.

    Args:
        cpf: CPF do cliente em formato string

    Returns:
        String no formato "sha256:<hex>" com salt de ambiente
    """
    # settings.OBSERVABILIDADE_SALT sempre existe: app.settings levanta
    # ImproperlyConfigured no import caso falte em ambiente nao local, entao
    # nao ha fallback inseguro aqui.
    salt = settings.OBSERVABILIDADE_SALT
    salted_cpf = f"{cpf}{salt}".encode('utf-8')
    hash_hex = sha256(salted_cpf).hexdigest()
    return f"sha256:{hash_hex}"


def trace_e_span() -> tuple:
    """De onde saem `trace.id` e `span.id`, nesta ordem de preferencia.

    Com o agente New Relic rodando, quem sabe o span corrente e ele -- os
    contextvars so conhecem o span que o middleware criou na borda, e qualquer
    span interno que o agente abrir depois ficaria de fora. Sem o agente, o
    middleware e a unica fonte.
    """
    if _metadados_do_agente is not None:
        try:
            metadados = _metadados_do_agente() or {}
            if metadados.get("trace.id"):
                return metadados.get("trace.id"), metadados.get("span.id")
        except Exception:  # pragma: no cover - o log nunca derruba a requisicao
            pass
    return trace_id_var.get(), span_id_var.get()


class JSONFormatter(logging.Formatter):
    """
    Formatador que emite logs em JSON estruturado com schema de observabilidade.

    Injeta automaticamente trace.id, span.id e request.id via contextvars.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Formata um registro de log em JSON.

        Campos obrigatórios:
        - timestamp: ISO 8601 com timezone
        - level: nível do log
        - logger: nome do logger
        - message: mensagem de log
        - service.name, service.environment, service.version
        - trace.id: ID do trace (obrigatório em requisição)
        - span.id: ID do span (obrigatório em requisição)
        - request.id: ID único da requisição

        Campos condicionais:
        - Para erro: error.type, error.message, error.stack
        - Para integração: integracao, integracao.status
        - HTTP: http.method, http.route, http.status_code, duration_ms
        """

        log_data = {
            'timestamp': datetime.now().astimezone().isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'service.name': getattr(settings, 'SERVICE_NAME', 'oficina-api'),
            'service.environment': getattr(settings, 'SERVICE_ENVIRONMENT', 'dev'),
            'service.version': getattr(settings, 'SERVICE_VERSION', '1.0.0'),
        }

        # Injetar trace.id e span.id: agente New Relic primeiro, contextvars depois
        trace_id, span_id = trace_e_span()
        request_id = request_id_var.get()
        correlation_id = correlation_id_var.get()

        if trace_id:
            log_data['trace.id'] = trace_id
        if span_id:
            log_data['span.id'] = span_id
        if request_id:
            log_data['request.id'] = request_id
        if correlation_id:
            log_data['correlation.id'] = correlation_id

        # Adicionar campos HTTP se presentes no registro
        if hasattr(record, 'http_method'):
            log_data['http.method'] = record.http_method
        if hasattr(record, 'http_route'):
            log_data['http.route'] = record.http_route
        if hasattr(record, 'http_status_code'):
            log_data['http.status_code'] = record.http_status_code
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms

        # Adicionar campos de negócio se presentes
        if hasattr(record, 'os_id'):
            log_data['os.id'] = record.os_id
        if hasattr(record, 'os_status_anterior'):
            log_data['os.status_anterior'] = record.os_status_anterior
        if hasattr(record, 'os_status_novo'):
            log_data['os.status_novo'] = record.os_status_novo
        if hasattr(record, 'cliente_ref'):
            log_data['cliente.ref'] = record.cliente_ref

        # Adicionar campos de integração se presentes
        # Evento de negocio: o adapter manda o dicionario inteiro, senao o
        # fallback sem agente perderia duracao, erroTipo e ambiente pelo caminho.
        evento_negocio = getattr(record, 'evento_negocio', None)
        if isinstance(evento_negocio, dict):
            for chave, valor in evento_negocio.items():
                if valor is not None:
                    log_data[chave] = valor

        if hasattr(record, 'integracao'):
            log_data['integracao'] = record.integracao
            if hasattr(record, 'integracao_status'):
                log_data['integracao.status'] = record.integracao_status

        # Adicionar informações de erro se presente
        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            log_data['error.type'] = exc_type.__name__ if exc_type else 'Unknown'
            log_data['error.message'] = str(exc_value) if exc_value else ''
            log_data['error.stack'] = traceback.format_exc()

        return json.dumps(log_data, ensure_ascii=False)


def get_trace_context() -> dict:
    """
    Obtém o contexto de trace atual (trace.id, span.id, request.id).

    Returns:
        Dicionário com as variáveis de contexto atuais
    """
    return {
        'trace_id': trace_id_var.get(),
        'span_id': span_id_var.get(),
        'request_id': request_id_var.get(),
    }


def set_trace_context(trace_id: Optional[str] = None, span_id: Optional[str] = None,
                      request_id: Optional[str] = None, correlation_id: Optional[str] = None,
                      tracestate: Optional[str] = None):
    """
    Define o contexto de trace (usar em middleware).

    Args:
        trace_id: ID do trace (W3C format)
        span_id: ID do span (W3C format)
        request_id: ID único da requisição
        correlation_id: ID de correlação (X-Correlation-Id)
        tracestate: tracestate W3C recebido do chamador, para propagar adiante
    """
    if trace_id:
        trace_id_var.set(trace_id)
    if span_id:
        span_id_var.set(span_id)
    if request_id:
        request_id_var.set(request_id)
    if correlation_id:
        correlation_id_var.set(correlation_id)
    if tracestate:
        tracestate_var.set(tracestate)


def clear_trace_context():
    """
    Limpa o contexto de trace (usar no fim da requisição).

    Necessário para evitar vazamento de contexto entre requisições em
    ambientes com thread pool.
    """
    trace_id_var.set(None)
    span_id_var.set(None)
    request_id_var.set(None)
    correlation_id_var.set(None)
    tracestate_var.set(None)
