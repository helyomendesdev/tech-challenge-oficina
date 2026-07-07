import datetime
import json

from django.utils import timezone
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from atendimento.tests.helpers import (
    api_client_for_user,
    criar_cliente,
    criar_item_servico_os,
    criar_ordem_servico,
    criar_servico,
    criar_usuario,
    criar_veiculo,
)


class TempoMedioServicosAPITest(TestCase):
    url = '/api/v1/ordens-servico/metricas/tempo-medio/'

    def setUp(self):
        self.usuario = criar_usuario(username='metricas_media')
        self.cliente = criar_cliente(
            usuario=self.usuario,
            documento='529.982.247-25',
        )
        self.veiculo = criar_veiculo(
            self.cliente,
            usuario=self.usuario,
            placa='AVG1A23',
        )
        self.servico = criar_servico(
            usuario=self.usuario,
            descricao='Alinhamento',
        )
        self.client = api_client_for_user(self.usuario)

    def criar_execucao(
        self,
        servico=None,
        duracao_minutos=60,
        data_inicio=True,
        data_finalizacao=True,
        usuario=None,
        cliente=None,
        veiculo=None,
    ):
        usuario = usuario or self.usuario
        cliente = cliente or self.cliente
        veiculo = veiculo or self.veiculo
        servico = servico or self.servico
        ordem = criar_ordem_servico(cliente, veiculo, usuario=usuario)
        inicio = timezone.now()
        fim = inicio + datetime.timedelta(minutes=duracao_minutos)
        return criar_item_servico_os(
            ordem,
            servico,
            usuario,
            status='CONCLUIDO',
            data_inicio=inicio if data_inicio else None,
            data_finalizacao=fim if data_finalizacao else None,
        )

    def test_uma_execucao_concluida(self):
        self.criar_execucao(duracao_minutos=45)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{
            'servico_id': self.servico.id,
            'descricao': self.servico.descricao,
            'quantidade_execucoes': 1,
            'tempo_medio_minutos': 45.0,
        }])

    def test_multiplas_execucoes_do_mesmo_servico(self):
        self.criar_execucao(duracao_minutos=30)
        self.criar_execucao(duracao_minutos=30)

        response = self.client.get(self.url)

        self.assertEqual(response.data[0]['quantidade_execucoes'], 2)

    def test_media_de_duracoes_diferentes(self):
        self.criar_execucao(duracao_minutos=30)
        self.criar_execucao(duracao_minutos=90)

        response = self.client.get(self.url)

        self.assertEqual(response.data[0]['tempo_medio_minutos'], 60.0)

    def test_multiplos_tipos_de_servico(self):
        outro_servico = criar_servico(
            usuario=self.usuario,
            descricao='Balanceamento',
        )
        self.criar_execucao(self.servico, duracao_minutos=20)
        self.criar_execucao(outro_servico, duracao_minutos=40)

        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            {item['servico_id'] for item in response.data},
            {self.servico.id, outro_servico.id},
        )

    def test_execucao_sem_inicio_e_ignorada(self):
        self.criar_execucao(data_inicio=False)

        response = self.client.get(self.url)

        self.assertEqual(response.data, [])

    def test_execucao_sem_finalizacao_e_ignorada(self):
        self.criar_execucao(data_finalizacao=False)

        response = self.client.get(self.url)

        self.assertEqual(response.data, [])

    def test_duracao_negativa_e_ignorada(self):
        self.criar_execucao(duracao_minutos=-5)

        response = self.client.get(self.url)

        self.assertEqual(response.data, [])

    def test_servico_sem_execucao_nao_e_retornado(self):
        response = self.client.get(self.url)

        self.assertEqual(response.data, [])

    def test_autenticacao_e_obrigatoria(self):
        response = APIClient().get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_isolamento_entre_usuarios(self):
        self.criar_execucao(duracao_minutos=30)
        outro_usuario = criar_usuario(username='metricas_outro')
        outro_cliente = criar_cliente(
            usuario=outro_usuario,
            documento='01.339.513/0001-08',
        )
        outro_veiculo = criar_veiculo(
            outro_cliente,
            usuario=outro_usuario,
            placa='OUT2B34',
        )
        outro_servico = criar_servico(
            usuario=outro_usuario,
            descricao='Servico de outro usuario',
        )
        self.criar_execucao(
            outro_servico,
            duracao_minutos=120,
            usuario=outro_usuario,
            cliente=outro_cliente,
            veiculo=outro_veiculo,
        )

        response = self.client.get(self.url)

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['servico_id'], self.servico.id)

    def test_openapi_documenta_resposta(self):
        response = APIClient().get(
            '/api/schema/',
            HTTP_ACCEPT='application/json',
        )
        schema = json.loads(response.content)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        operation = schema['paths'][self.url]['get']
        response_schema = operation['responses']['200']['content'][
            'application/json'
        ]['schema']
        self.assertEqual(response_schema['type'], 'array')
        component_name = response_schema['items']['$ref'].rsplit('/', 1)[-1]
        properties = schema['components']['schemas'][component_name]['properties']
        self.assertEqual(set(properties), {
            'servico_id',
            'descricao',
            'quantidade_execucoes',
            'tempo_medio_minutos',
        })

    def test_endpoint_antigo_de_metricas_preserva_contrato(self):
        item = self.criar_execucao(duracao_minutos=75)
        response = self.client.get(
            f'/api/v1/ordens-servico/{item.ordem_servico_id}/metricas/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(response.data[0]), {
            'id', 'servico', 'descricao', 'status', 'data_inicio',
            'data_finalizacao', 'tempo_execucao_minutos', 'pecas_consumidas',
        })
        self.assertEqual(response.data[0]['tempo_execucao_minutos'], 75.0)
