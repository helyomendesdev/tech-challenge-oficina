"""
Testes de integração do contrato X-Correlation-Id.

Validam, contra o test client do Django e um endpoint real da aplicação:
- Eco do valor válido recebido do cliente
- Substituição de valor inválido por um UUIDv4 novo
- Geração de UUIDv4 novo quando o header está ausente
- Presença de correlation.id na linha de log da requisição
- Propagação de X-Correlation-Id nas chamadas saintes
- Propagação (nunca fabricação) de tracestate nas chamadas saintes
"""

import json
import logging
import uuid
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import TestCase

from app.observabilidade.logging import JSONFormatter, clear_trace_context, set_trace_context
from atendimento.infrastructure.external_services.simulador_orcamento_service import (
    SimuladorOrcamentoService,
)
from atendimento.tests.helpers import api_client_for_user, create_user


class CorrelacaoIdApiTest(TestCase):
    """Testes do contrato X-Correlation-Id via requisição HTTP real."""

    def setUp(self):
        clear_trace_context()

    def tearDown(self):
        clear_trace_context()

    def test_valor_valido_e_ecoado_na_resposta(self):
        """UUIDv4 valido enviado pelo cliente deve ser devolvido identico."""
        correlation_id = str(uuid.uuid4())

        response = self.client.get('/health/live/', HTTP_X_CORRELATION_ID=correlation_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Correlation-Id'], correlation_id)

    def test_valor_valido_em_maiusculas_e_ecoado_sem_normalizar(self):
        """UUIDv4 valido em maiusculas volta byte-a-byte como o cliente mandou.

        A validacao e case-insensitive, mas quem gera o UUID do outro lado
        (a Lambda) pode comparar por igualdade de string -- devolver
        normalizado em minusculas quebraria essa comparacao em silencio.
        """
        correlation_id_maiusculas = str(uuid.uuid4()).upper()

        response = self.client.get(
            '/health/live/', HTTP_X_CORRELATION_ID=correlation_id_maiusculas
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Correlation-Id'], correlation_id_maiusculas)

    def test_valor_invalido_e_substituido_por_uuid4_novo(self):
        """Valor que nao e UUIDv4 estrito nunca deve voltar na resposta."""
        valor_invalido = 'nao-e-um-uuid-v4-valido'

        response = self.client.get('/health/live/', HTTP_X_CORRELATION_ID=valor_invalido)

        self.assertEqual(response.status_code, 200)
        recebido = response['X-Correlation-Id']
        self.assertNotEqual(recebido, valor_invalido)
        uuid_obj = uuid.UUID(recebido, version=4)
        self.assertEqual(str(uuid_obj), recebido.lower())

    def test_uuid_bem_formado_mas_de_outra_versao_e_substituido(self):
        """UUID sintaticamente valido, mas de versao != 4, tambem e recusado.

        ``uuid.UUID(valor, version=4)`` nao rejeita um UUIDv1 por si só --
        ele forca os bits de versao/variante no resultado. E a checagem de
        round-trip (comparar o resultado formatado com o valor original)
        que detecta que o valor recebido nao era realmente um UUIDv4.
        """
        uuid_v1 = str(uuid.uuid1())

        response_a = self.client.get('/health/live/', HTTP_X_CORRELATION_ID=uuid_v1)
        response_b = self.client.get('/health/live/', HTTP_X_CORRELATION_ID=uuid_v1)

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        recebido_a = response_a['X-Correlation-Id']
        recebido_b = response_b['X-Correlation-Id']
        self.assertNotEqual(recebido_a, uuid_v1)
        # Um UUIDv4 novo e aleatorio a cada chamada -- se o valor viesse de
        # uma transformacao deterministica do v1 recusado (em vez de um
        # `uuid.uuid4()` de verdade), as duas respostas sairiam identicas.
        self.assertNotEqual(recebido_a, recebido_b)
        uuid_obj = uuid.UUID(recebido_a, version=4)
        self.assertEqual(str(uuid_obj), recebido_a.lower())

    def test_ausencia_gera_uuid4_novo(self):
        """Sem o header, a aplicacao gera um UUIDv4 novo."""
        response = self.client.get('/health/live/')

        self.assertEqual(response.status_code, 200)
        recebido = response['X-Correlation-Id']
        uuid_obj = uuid.UUID(recebido, version=4)
        self.assertEqual(str(uuid_obj), recebido.lower())

    def test_log_de_requisicao_traz_correlation_id(self):
        """A linha de log da requisicao deve trazer correlation.id e os campos http.*."""
        correlation_id = str(uuid.uuid4())
        logger = logging.getLogger('atendimento.observabilidade.requisicao')
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        nivel_anterior = logger.level
        logger.setLevel(logging.INFO)
        try:
            response = self.client.get('/health/live/', HTTP_X_CORRELATION_ID=correlation_id)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(nivel_anterior)

        self.assertEqual(response.status_code, 200)
        linhas = [linha for linha in stream.getvalue().splitlines() if linha.strip()]
        self.assertTrue(linhas, 'nenhuma linha de log de requisicao foi emitida')

        dados = json.loads(linhas[-1])

        self.assertEqual(dados['correlation.id'], correlation_id)
        self.assertEqual(dados['http.method'], 'GET')
        self.assertEqual(dados['http.route'], 'health/live/')
        self.assertEqual(dados['http.status_code'], 200)
        self.assertIn('duration_ms', dados)
        self.assertIsNotNone(dados['duration_ms'])


class CorrelacaoIdChamadaSainteTest(TestCase):
    """Testes de propagação do correlation.id nas chamadas saintes."""

    def setUp(self):
        clear_trace_context()

    def tearDown(self):
        clear_trace_context()

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_chamada_sainte_leva_correlation_id_e_tracestate(self, mock_post):
        """A chamada HTTP sainte deve levar X-Correlation-Id."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        correlation_id = str(uuid.uuid4())
        set_trace_context(trace_id='a' * 32, span_id='b' * 16, correlation_id=correlation_id)

        SimuladorOrcamentoService().enviar_decisao(1, 'APROVADA')

        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers['X-Correlation-Id'], correlation_id)

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_tracestate_recebido_e_propagado_na_chamada_sainte(self, mock_post):
        """tracestate recebido do chamador de entrada deve ser propagado intacto.

        O contrato e de propagacao, nao de fabricacao -- o tracestate.id que
        esta aplicacao le do header de entrada precisa reaparecer, literal, na
        chamada sainte.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        tracestate_recebido = 'newrelic=abc123,outrovendor=def456'
        set_trace_context(
            trace_id='c' * 32, span_id='d' * 16, tracestate=tracestate_recebido,
        )

        SimuladorOrcamentoService().enviar_decisao(1, 'APROVADA')

        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers['tracestate'], tracestate_recebido)

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_sem_tracestate_recebido_nada_e_fabricado(self, mock_post):
        """Sem tracestate na entrada, a chamada sainte nao inventa um valor.

        Escrever um tracestate fabricado atropelaria o que um vendor (ex.:
        o agente New Relic) guarda nesse header -- por isso a chave precisa
        ficar de fora quando nada foi recebido para propagar.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        correlation_id = str(uuid.uuid4())
        set_trace_context(trace_id='e' * 32, span_id='f' * 16, correlation_id=correlation_id)

        SimuladorOrcamentoService().enviar_decisao(1, 'APROVADA')

        headers = mock_post.call_args[1]['headers']
        self.assertNotIn('tracestate', headers)

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_middleware_sem_tracestate_nao_fabrica(self, mock_post):
        """Requisicao real, sem header tracestate, ate a chamada sainte.

        Diferente de ``test_sem_tracestate_recebido_nada_e_fabricado`` (que
        seta a contextvar na mao e so exercita a camada de servico), este
        caso passa pelo middleware de verdade via o test client, contra o
        endpoint real que dispara a chamada sainte dentro do proprio ciclo
        da requisicao -- nenhuma contextvar e setada manualmente em lugar
        nenhum do caminho. E o ponto onde uma fabricacao de tracestate
        dentro do middleware (em vez de na camada de servico) seria pega.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        usuario = create_user()
        client = api_client_for_user(usuario)

        response = client.post(
            '/api/v1/simulacao/orcamento/',
            {'ordem_servico_id': 1, 'decisao': 'APROVADO'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        headers = mock_post.call_args[1]['headers']
        self.assertNotIn('tracestate', headers)

    @patch('atendimento.infrastructure.external_services.simulador_orcamento_service.requests.post')
    def test_tracestate_recebido_propagado_ponta_a_ponta(self, mock_post):
        """Requisicao real com header tracestate ate a chamada sainte.

        Mesma montagem de ``test_middleware_sem_tracestate_nao_fabrica``
        (test client, endpoint real, nenhuma contextvar setada na mao),
        mas desta vez o cliente manda um tracestate valido -- e ele precisa
        reaparecer intacto na chamada sainte, fechando a cobertura ponta a
        ponta que ate aqui so existia setando a contextvar direto na
        camada de servico.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'ok'}
        mock_post.return_value = mock_response

        usuario = create_user()
        client = api_client_for_user(usuario)

        response = client.post(
            '/api/v1/simulacao/orcamento/',
            {'ordem_servico_id': 1, 'decisao': 'APROVADO'},
            format='json',
            HTTP_TRACESTATE='newrelic=abc123',
        )

        self.assertEqual(response.status_code, 200)
        headers = mock_post.call_args[1]['headers']
        self.assertEqual(headers['tracestate'], 'newrelic=abc123')
