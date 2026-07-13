from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase


class HealthEndpointTest(TestCase):
    def test_liveness_retorna_200(self):
        response = self.client.get('/health/live/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readiness_retorna_200_com_banco_disponivel(self):
        response = self.client.get('/health/ready/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ready'})

    @patch('app.urls.connection.cursor')
    def test_readiness_retorna_503_quando_consulta_falha(self, cursor):
        cursor.side_effect = OperationalError('database unavailable')

        response = self.client.get('/health/ready/')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    @patch('app.urls.connection.cursor')
    def test_readiness_nao_expoe_dados_sensiveis_ou_stack_trace(self, cursor):
        cursor.side_effect = OperationalError(
            'password=segredo-local host=db Traceback: detalhe interno'
        )

        response = self.client.get('/health/ready/')
        content = response.content.decode()

        self.assertEqual(response.status_code, 503)
        self.assertNotIn('segredo-local', content)
        self.assertNotIn('password', content.lower())
        self.assertNotIn('traceback', content.lower())
