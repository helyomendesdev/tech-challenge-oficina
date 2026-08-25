"""
Testes da camada de observabilidade.

Validam:
- Formatter JSON e injeção de trace/span/request IDs
- Middleware de correlação
- Propagação de traceparent em chamadas externas
- Limpeza de contextvars entre requisições
"""

import json
import logging
import uuid
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest
import requests
from django.http import HttpResponse
from django.test import TestCase, RequestFactory, Client
from django.test.utils import override_settings

from app.observabilidade.logging import (
    JSONFormatter, cliente_ref, set_trace_context, clear_trace_context,
    get_trace_context
)
from app.observabilidade.middleware import CorrelationIdMiddleware
from atendimento.infrastructure.external_services.simulador_orcamento_service import (
    SimuladorOrcamentoService
)


class TestJSONFormatter(TestCase):
    """Testes do formatter JSON."""

    def setUp(self):
        """Setup para capturar logs em teste."""
        self.logger = logging.getLogger('test')
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(JSONFormatter())
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)

    def tearDown(self):
        """Limpar handlers após testes."""
        self.logger.removeHandler(self.handler)
        clear_trace_context()

    def test_formatter_emits_valid_json(self):
        """Formatter deve emitir JSON válido."""
        self.logger.info('Test message')

        output = self.stream.getvalue().strip()
        data = json.loads(output)

        assert isinstance(data, dict)
        assert data['message'] == 'Test message'
        assert data['level'] == 'INFO'

    def test_formatter_includes_required_fields(self):
        """Formatter deve incluir campos obrigatórios."""
        set_trace_context(trace_id='abc123', span_id='def456', request_id='ghi789')
        self.logger.info('Test')

        data = json.loads(self.stream.getvalue().strip())

        assert 'timestamp' in data
        assert 'level' in data
        assert 'logger' in data
        assert 'message' in data
        assert 'service.name' in data
        assert 'service.environment' in data
        assert 'service.version' in data
        assert data['trace.id'] == 'abc123'
        assert data['span.id'] == 'def456'
        assert data['request.id'] == 'ghi789'

    def test_formatter_includes_error_fields(self):
        """Formatter deve incluir error.type, error.message, error.stack para erros."""
        clear_trace_context()
        set_trace_context(trace_id='trace1', span_id='span1')

        try:
            raise ValueError('Test error message')
        except ValueError:
            self.logger.error('An error occurred', exc_info=True)

        data = json.loads(self.stream.getvalue().strip())

        assert data['error.type'] == 'ValueError'
        assert data['error.message'] == 'Test error message'
        assert 'error.stack' in data
        assert 'ValueError' in data['error.stack']

    def test_formatter_includes_integration_fields(self):
        """Formatter deve incluir integracao e integracao.status."""
        clear_trace_context()
        set_trace_context(trace_id='trace2', span_id='span2')

        extra = {
            'integracao': 'simulador-orcamento',
            'integracao_status': 'sucesso',
        }
        self.logger.info('Integration call', extra=extra)

        data = json.loads(self.stream.getvalue().strip())

        assert data['integracao'] == 'simulador-orcamento'
        assert data['integracao.status'] == 'sucesso'

    def test_trace_id_mandatory_in_request_context(self):
        """trace.id deve ser obrigatório dentro de contexto de requisição."""
        set_trace_context(trace_id='mandatory123', span_id='span789')
        self.logger.info('Request processing')

        data = json.loads(self.stream.getvalue().strip())

        assert 'trace.id' in data
        assert data['trace.id'] == 'mandatory123'

    def test_formatter_without_trace_context(self):
        """Formatter deve funcionar sem contexto de trace (logs fora de requisição)."""
        clear_trace_context()
        self.logger.info('Background task')

        data = json.loads(self.stream.getvalue().strip())

        # trace.id e span.id opcionais fora de contexto de requisição
        assert 'message' in data
        assert data['message'] == 'Background task'


class TestClienteRef(TestCase):
    """Testes do helper cliente_ref."""

    @override_settings(OBSERVABILIDADE_SALT='test-salt')
    def test_cliente_ref_returns_sha256_format(self):
        """cliente_ref deve retornar formato sha256:<hex>."""
        result = cliente_ref('12345678901')

        assert result.startswith('sha256:')
        assert len(result) == 71  # 7 (sha256:) + 64 (hex)

    @override_settings(OBSERVABILIDADE_SALT='test-salt')
    def test_cliente_ref_stable_for_same_cpf(self):
        """cliente_ref deve retornar mesmo hash para mesmo CPF."""
        cpf = '12345678901'
        result1 = cliente_ref(cpf)
        result2 = cliente_ref(cpf)

        assert result1 == result2

    @override_settings(OBSERVABILIDADE_SALT='salt-1')
    def test_cliente_ref_changes_with_salt(self):
        """cliente_ref deve mudar com salt diferente."""
        cpf = '12345678901'
        result1 = cliente_ref(cpf)

        with override_settings(OBSERVABILIDADE_SALT='salt-2'):
            result2 = cliente_ref(cpf)

        assert result1 != result2

    @override_settings(OBSERVABILIDADE_SALT='test-salt')
    def test_cliente_ref_never_returns_cpf(self):
        """cliente_ref nunca deve retornar o CPF em claro."""
        cpf = '12345678901'
        result = cliente_ref(cpf)

        assert cpf not in result
        assert '12345' not in result


class TestCorrelationIdMiddleware(TestCase):
    """Testes do middleware de correlação."""

    def setUp(self):
        """Setup para testes de middleware."""
        self.factory = RequestFactory()
        self.middleware = CorrelationIdMiddleware(lambda x: MagicMock(status_code=200))
        self.client = Client()
        clear_trace_context()

    def tearDown(self):
        """Limpar após testes."""
        clear_trace_context()

    def test_middleware_generates_x_request_id_if_absent(self):
        """Middleware deve gerar X-Request-Id quando ausente."""
        request = self.factory.get('/')

        response = MagicMock()
        self.middleware.process_request(request)
        result = self.middleware.process_response(request, response)

        assert hasattr(request, 'request_id')
        assert request.request_id
        # UUID válido tem 36 caracteres com hífens
        assert len(request.request_id) == 36

    def test_middleware_reuses_existing_x_request_id(self):
        """Middleware deve reaproveitar X-Request-Id quando presente."""
        expected_id = str(uuid.uuid4())
        request = self.factory.get('/', HTTP_X_REQUEST_ID=expected_id)

        self.middleware.process_request(request)

        assert request.request_id == expected_id

    def test_middleware_returns_x_request_id_in_response(self):
        """Middleware deve devolver X-Request-Id no header da resposta."""
        request_id = str(uuid.uuid4())
        request = self.factory.get('/', HTTP_X_REQUEST_ID=request_id)

        response = MagicMock()
        self.middleware.process_request(request)
        self.middleware.process_response(request, response)

        response.__setitem__.assert_any_call('X-Request-Id', request_id)

    def test_middleware_generates_trace_id_and_span_id(self):
        """Middleware deve gerar trace.id e span.id quando traceparent ausente."""
        request = self.factory.get('/')

        self.middleware.process_request(request)

        assert hasattr(request, 'trace_id')
        assert hasattr(request, 'span_id')
        assert len(request.trace_id) == 32  # 32 hex chars
        assert len(request.span_id) == 16   # 16 hex chars

    def test_middleware_herda_o_trace_e_guarda_o_span_recebido_como_pai(self):
        """O trace atravessa; o span que chega e do chamador, nao nosso."""
        trace_id = 'a' * 32
        span_do_chamador = 'b' * 16
        traceparent = f"00-{trace_id}-{span_do_chamador}-01"

        request = self.factory.get('/', HTTP_TRACEPARENT=traceparent)
        self.middleware.process_request(request)

        assert request.trace_id == trace_id, "o trace tem de ser herdado"
        assert request.parent_span_id == span_do_chamador
        assert request.span_id != span_do_chamador, (
            "reaproveitar o span recebido faz todo log da requisicao se "
            "apresentar como o span de quem chamou"
        )
        assert len(request.span_id) == 16


    def test_middleware_gera_span_novo_a_cada_requisicao(self):
        """Duas requisicoes no mesmo trace nao podem compartilhar span."""
        trace_id = 'c' * 32
        traceparent = f"00-{trace_id}-{'d' * 16}-01"

        spans = []
        for _ in range(2):
            request = self.factory.get('/', HTTP_TRACEPARENT=traceparent)
            self.middleware.process_request(request)
            spans.append(request.span_id)

        assert spans[0] != spans[1]


    def test_traceparent_devolvido_aponta_para_o_nosso_span(self):
        """O que propagamos adiante tem de nos declarar como pai."""
        trace_id = 'e' * 32
        request = self.factory.get(
            '/', HTTP_TRACEPARENT=f"00-{trace_id}-{'f' * 16}-01"
        )
        self.middleware.process_request(request)
        response = self.middleware.process_response(request, HttpResponse())

        assert response['traceparent'] == f"00-{trace_id}-{request.span_id}-01"

    def test_middleware_stores_ids_in_contextvars(self):
        """Middleware deve armazenar IDs em contextvars."""
        request_id = str(uuid.uuid4())
        request = self.factory.get('/', HTTP_X_REQUEST_ID=request_id)

        self.middleware.process_request(request)

        context = get_trace_context()
        assert context['request_id'] == request_id
        assert context['trace_id'] is not None
        assert context['span_id'] is not None

    def test_middleware_clears_contextvars_after_request(self):
        """Middleware deve limpar contextvars ao fim da requisição."""
        request = self.factory.get('/')
        response = MagicMock()

        # Configurar trace context
        self.middleware.process_request(request)
        context_before = get_trace_context()
        assert context_before['trace_id'] is not None

        # Limpar após response (simulando fim de requisição)
        clear_trace_context()
        context_after = get_trace_context()

        assert context_after['trace_id'] is None
        assert context_after['span_id'] is None
        assert context_after['request_id'] is None

    def test_middleware_does_not_leak_between_requests(self):
        """Middleware não deve vazar contexto entre requisições."""
        # Primeira requisição
        request1 = self.factory.get('/')
        self.middleware.process_request(request1)
        id1 = request1.request_id

        # Limpar (fim de requisição)
        clear_trace_context()

        # Segunda requisição
        request2 = self.factory.get('/')
        self.middleware.process_request(request2)
        id2 = request2.request_id

        # IDs devem ser diferentes
        assert id1 != id2


class TestSimuladorOrcamentoIntegration(TestCase):
    """Testes da integração com simulador de orçamento."""

    def setUp(self):
        """Setup para testes de integração."""
        self.service = SimuladorOrcamentoService()
        self.logger = logging.getLogger('atendimento.infrastructure.external_services.simulador_orcamento_service')
        self.stream = StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(JSONFormatter())
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.DEBUG)
        clear_trace_context()

    def tearDown(self):
        """Limpar após testes."""
        self.logger.removeHandler(self.handler)
        clear_trace_context()

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_integration_log_on_success(self, mock_post):
        """Deve emitir log de integração sucesso."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        set_trace_context(trace_id='trace1', span_id='span1')
        self.service.enviar_decisao(1, 'APROVADA')

        logs = self.stream.getvalue()
        data = json.loads(logs.strip())

        assert data['integracao'] == 'simulador-orcamento'
        assert data['integracao.status'] == 'sucesso'

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_integration_log_on_http_error(self, mock_post):
        """Deve emitir log de integração erro HTTP."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'erro': 'not found'}
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        set_trace_context(trace_id='trace2', span_id='span2')
        result = self.service.enviar_decisao(1, 'RECUSADA')

        logs = self.stream.getvalue()
        data = json.loads(logs.strip())

        assert data['integracao'] == 'simulador-orcamento'
        assert data['integracao.status'] == 'erro'
        assert result['erro'] is True

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_integration_log_on_request_exception(self, mock_post):
        """Deve emitir log de integração erro RequestException."""
        mock_post.side_effect = requests.exceptions.ConnectionError('Connection failed')

        set_trace_context(trace_id='trace3', span_id='span3')
        result = self.service.enviar_decisao(1, 'RECUSADA')

        logs = self.stream.getvalue()
        if logs:
            data = json.loads(logs.strip())
            assert data['integracao'] == 'simulador-orcamento'
            assert data['integracao.status'] == 'erro'

        assert result['erro'] is True
        assert result['status_code'] == 503

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_integration_propagates_traceparent(self, mock_post):
        """Deve propagar traceparent na chamada HTTP."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        set_trace_context(trace_id='abc123def456789', span_id='xyz789abc123')
        self.service.enviar_decisao(1, 'APROVADA')

        # Verificar que traceparent foi enviado
        call_args = mock_post.call_args
        headers = call_args[1]['headers']

        assert 'traceparent' in headers
        assert 'abc123def456789' in headers['traceparent']


class TimestampDoLogTest(TestCase):
    """O timestamp precisa carregar offset -- §5.1 mostra `-03:00` no exemplo."""

    def _linha(self) -> dict:
        formatter = JSONFormatter()
        registro = logging.LogRecord(
            name='atendimento.ordens', level=logging.INFO,
            pathname=__file__, lineno=1,
            msg='Ordem de servico transicionada', args=(), exc_info=None,
        )
        return json.loads(formatter.format(registro))

    def test_timestamp_tem_offset_de_fuso(self):
        from datetime import datetime

        timestamp = self._linha()['timestamp']
        # Sem offset o New Relic assume UTC e a linha desloca 3 horas no painel.
        assert datetime.fromisoformat(timestamp).utcoffset() is not None, (
            f"timestamp sem fuso: {timestamp}"
        )

    def test_timestamp_tem_precisao_de_milissegundo(self):
        timestamp = self._linha()['timestamp']
        segundos = timestamp.split('T')[1]
        assert '.' in segundos, f"timestamp sem fracao de segundo: {timestamp}"
