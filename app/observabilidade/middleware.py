"""
Middleware de correlação de requisições para observabilidade.

Implementa W3C Trace Context (traceparent/tracestate) conforme §5.2 da especificação
de observabilidade, gerenciando trace.id, span.id e request.id via contextvars.
"""

import logging
import time
import uuid
from typing import Callable, Optional
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from app.observabilidade.logging import (
    set_trace_context, clear_trace_context, trace_id_var, span_id_var, request_id_var
)

logger = logging.getLogger('atendimento.observabilidade.requisicao')


def _correlation_id_valido(valor: str) -> Optional[str]:
    """Valida X-Correlation-Id como UUIDv4 estrito, sem normalizar o retorno.

    ``uuid.UUID(valor, version=4)`` forca os bits de versao/variante no
    resultado -- se o valor recebido ja nao era um UUIDv4 valido, o
    round-trip para string (sempre em minusculas) diverge do valor
    recebido em minusculas, e e essa divergencia que a comparacao abaixo
    detecta. Qualquer string que nao seja um UUID bem formado cai no
    ValueError.

    A validacao e case-insensitive, mas o retorno preserva o caso exato
    que o cliente enviou -- quem gera o UUID do outro lado pode comparar
    por igualdade de string, e devolver normalizado quebraria isso em
    silencio.
    """
    if not valor:
        return None
    try:
        uuid_obj = uuid.UUID(valor, version=4)
    except (ValueError, AttributeError, TypeError):
        return None
    if str(uuid_obj) != valor.lower():
        return None
    return valor


class CorrelationIdMiddleware(MiddlewareMixin):
    """
    Middleware que gerencia IDs de correlação para requisições.

    Lê e valida headers W3C traceparent (formato: 00-trace-span-flags)
    e X-Request-Id, gerando UUIDs quando ausentes. Injeta valores em
    contextvars para acesso nos logs sem passar parâmetro.

    Conforme §5.2 da especificação:
    1. Lê traceparent e X-Request-Id da requisição
    2. Gera UUIDv4 para X-Request-Id se ausente
    3. Extrai trace.id e span.id do traceparent (W3C format)
    4. Guarda em contextvars para o formatter injetar
    5. Devolve X-Request-Id no header da resposta
    """

    def process_request(self, request: HttpRequest) -> None:
        """
        Processa requisição de entrada: lê/gera IDs de correlação.

        Args:
            request: Objeto HttpRequest do Django
        """
        # Marca o inicio do processamento para medir duration_ms na resposta.
        request._observabilidade_inicio = time.monotonic()

        # W3C Trace Context: formato 00-traceId-spanId-flags
        # https://www.w3.org/TR/trace-context/
        traceparent = request.headers.get('traceparent', '')
        trace_id = None
        span_id = None

        parent_span_id = None
        if traceparent:
            # Validar formato W3C (esperado: 00-32hex-16hex-2hex)
            parts = traceparent.split('-')
            if len(parts) >= 3 and parts[0] == '00':
                trace_id = parts[1]  # 32 caracteres hex
                # O span que chega no traceparent e o do CHAMADOR -- em W3C ele e
                # o parent-id, nao o nosso. Reaproveita-lo faria todo log desta
                # requisicao se apresentar como o span de quem nos chamou, e o
                # painel de trace ligaria as linhas ao span errado.
                parent_span_id = parts[2][:16]

        # O trace atravessa os componentes: so se gera quando nao veio.
        if not trace_id:
            trace_id = uuid.uuid4().hex  # 32 hex chars

        # O span e sempre nosso, tenha vindo pai ou nao.
        span_id = uuid.uuid4().hex[:16]  # 16 hex chars

        # X-Request-Id: identificador de negócio da requisição
        request_id = request.headers.get('X-Request-Id')
        if not request_id:
            request_id = str(uuid.uuid4())

        # X-Correlation-Id: so aceita UUIDv4 estrito vindo do cliente; valor
        # recusado nunca chega ao contextvar, ao log ou a resposta -- gera-se
        # um novo UUIDv4 no lugar.
        correlation_id = _correlation_id_valido(request.headers.get('X-Correlation-Id', ''))
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # tracestate: opaco, so propaga o que o chamador mandou -- nunca se
        # fabrica um valor aqui. Ausente fica None, e nada e escrito por cima
        # do que um vendor (ex.: o agente New Relic) possa depender ali.
        tracestate = request.headers.get('tracestate') or None

        # Guardar em contextvars para acesso em logs
        set_trace_context(
            trace_id=trace_id, span_id=span_id, request_id=request_id,
            correlation_id=correlation_id, tracestate=tracestate,
        )

        # Attachar ao request object para acesso posterior se necessário
        request.trace_id = trace_id
        request.span_id = span_id
        request.parent_span_id = parent_span_id
        request.request_id = request_id
        request.correlation_id = correlation_id
        request.tracestate = tracestate

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Processa resposta de saída: injeta X-Request-Id no header.

        Args:
            request: Objeto HttpRequest do Django
            response: Objeto HttpResponse do Django

        Returns:
            HttpResponse com X-Request-Id adicionado
        """
        # Devolver X-Request-Id no header da resposta
        if hasattr(request, 'request_id'):
            response['X-Request-Id'] = request.request_id

        # Devolver X-Correlation-Id no header da resposta
        if hasattr(request, 'correlation_id'):
            response['X-Correlation-Id'] = request.correlation_id

        # Devolver traceparent formatado conforme W3C
        if hasattr(request, 'trace_id') and hasattr(request, 'span_id'):
            traceparent = f"00-{request.trace_id}-{request.span_id}-01"
            response['traceparent'] = traceparent

        self._logar_requisicao(request, response)

        return response

    def _logar_requisicao(self, request: HttpRequest, response: HttpResponse) -> None:
        """Emite uma linha de log por requisicao, com correlation.id no contexto."""
        duration_ms = None
        inicio = getattr(request, '_observabilidade_inicio', None)
        if inicio is not None:
            duration_ms = round((time.monotonic() - inicio) * 1000, 2)

        resolver_match = getattr(request, 'resolver_match', None)
        rota = getattr(resolver_match, 'route', None) if resolver_match else None
        if not rota:
            rota = request.path

        logger.info(
            'Requisicao processada',
            extra={
                'http_method': request.method,
                'http_route': rota,
                'http_status_code': response.status_code,
                'duration_ms': duration_ms,
            },
        )

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        """
        Chamado quando ocorre exceção não tratada na view.

        Args:
            request: Objeto HttpRequest do Django
            exception: Exceção que foi lançada
        """
        # Contextvars será limpado em process_response mesmo em caso de erro
        # devido ao middleware do Django garantir sua execução

    def process_view(self, request: HttpRequest, view_func: Callable,
                     view_args: tuple, view_kwargs: dict) -> None:
        """
        Chamado depois de process_request, antes da view.

        Poderia ser usado para logging de entrada, mas não necessário
        para correlação — mantido para documentação.
        """
        pass

    def process_template_response(self, request: HttpRequest, response):
        """
        Chamado para respostas com templates (não usado aqui, mas deve retornar response).
        """
        return response

    # Nota: Django chama process_exception antes de process_response em erro,
    # mas process_response é sempre chamado por último para limpeza.
    # Usar try/finally em process_response para garantir limpeza.

    def __call__(self, request: HttpRequest):
        """
        Garante limpeza de contextvars ao final da requisição.

        O middleware é callable, permitindo usar try/finally para
        garantir limpeza mesmo em caso de erro.
        """
        try:
            response = super().__call__(request)
            return response
        finally:
            # Limpar contextvars ao final da requisição para evitar
            # vazamento entre requisições em thread pool
            clear_trace_context()
