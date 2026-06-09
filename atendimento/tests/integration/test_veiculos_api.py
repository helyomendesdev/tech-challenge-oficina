from atendimento.tests.helpers import *
class VeiculoValidacaoLegadaAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_validacao')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)
        self.peca = criar_peca(usuario=self.user)

    def test_criar_veiculo_rejeita_placa_invalida(self):
        payload = {
            'cliente': self.cliente.id,
            'placa': 'ABC123',
            'marca': 'VW',
            'modelo': 'Gol',
            'ano': 2020,
        }
        response = self.client.post('/api/v1/veiculos/', payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class VeiculoCRUDAdministrativoFase1Test(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_crud')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='153.509.460-56')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='CRD1A11')

    def test_veiculo_crud_completo(self):
        payload = {
            'cliente': self.cliente.id,
            'placa': 'crd2b22',
            'marca': 'Fiat',
            'modelo': 'Uno',
            'ano': 2021,
        }

        create = self.client.post('/api/v1/veiculos/', payload)
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(create.data['placa'], 'CRD2B22')
        veiculo_id = create.data['id']

        list_response = self.client.get('/api/v1/veiculos/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'/api/v1/veiculos/{veiculo_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            f'/api/v1/veiculos/{veiculo_id}/',
            {'modelo': 'Palio'},
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data['modelo'], 'Palio')

        delete = self.client.delete(f'/api/v1/veiculos/{veiculo_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

class VeiculoAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_veiculo')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user)

    def test_criar_veiculo_placa_upper(self):
        payload = {'cliente': self.cliente.id, 'placa': 'abc1234', 'marca': 'VW', 'modelo': 'Gol', 'ano': 2020}
        response = self.client.post('/api/v1/veiculos/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['placa'], 'ABC1234')
        self.assertEqual(response.data['created_by'], self.user.id)
