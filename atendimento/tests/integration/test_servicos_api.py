from atendimento.tests.helpers import *
class ServicoValidacaoLegadaAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_validacao')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)
        self.peca = criar_peca(usuario=self.user)

    def test_criar_servico_rejeita_valor_negativo(self):
        payload = {
            'descricao': 'Servico invalido',
            'valor_mao_de_obra': '-1.00',
        }
        response = self.client.post('/api/v1/servicos/', payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class ServicoCRUDAdministrativoFase1Test(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_crud')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='153.509.460-56')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='CRD1A11')

    def test_servico_crud_completo(self):
        create = self.client.post(
            '/api/v1/servicos/',
            {'descricao': 'Alinhamento', 'valor_mao_de_obra': '120.00'},
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        servico_id = create.data['id']

        list_response = self.client.get('/api/v1/servicos/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'/api/v1/servicos/{servico_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            f'/api/v1/servicos/{servico_id}/',
            {'valor_mao_de_obra': '130.00'},
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data['valor_mao_de_obra'], '130.00')

        delete = self.client.delete(f'/api/v1/servicos/{servico_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
