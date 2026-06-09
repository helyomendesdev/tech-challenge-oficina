from atendimento.tests.helpers import *
class PecaValidacaoLegadaAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_validacao')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)
        self.peca = criar_peca(usuario=self.user)

    def test_criar_peca_rejeita_valor_negativo(self):
        payload = {
            'nome': 'Peca invalida',
            'valor_unitario': '-1.00',
            'estoque_atual': 1,
        }
        response = self.client.post('/api/v1/pecas/', payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_criar_peca_rejeita_estoque_negativo(self):
        payload = {
            'nome': 'Peca invalida',
            'valor_unitario': '10.00',
            'estoque_atual': -1,
        }
        response = self.client.post('/api/v1/pecas/', payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adicionar_item_peca_rejeita_quantidade_negativa(self):
        payload = {
            'os': self.os.id,
            'peca': self.peca.id,
            'quantidade': -1,
        }
        response = self.client.post('/api/v1/itens-pecas/', payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class PecaCRUDAdministrativoFase1Test(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_crud')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='153.509.460-56')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='CRD1A11')

    def test_peca_crud_completo(self):
        create = self.client.post(
            '/api/v1/pecas/',
            {'nome': 'Filtro CRUD', 'valor_unitario': '45.00', 'estoque_atual': 5},
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        peca_id = create.data['id']

        list_response = self.client.get('/api/v1/pecas/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'/api/v1/pecas/{peca_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            f'/api/v1/pecas/{peca_id}/',
            {'estoque_atual': 7},
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data['estoque_atual'], 7)

        delete = self.client.delete(f'/api/v1/pecas/{peca_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
