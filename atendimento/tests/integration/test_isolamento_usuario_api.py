from atendimento.tests.helpers import *
class IsolamentoDadosTest(TestCase):
    def setUp(self):
        self.usuario_a = criar_usuario('tecnico_a')
        self.usuario_b = criar_usuario('tecnico_b')
        self.client_a = api_client_for_user(self.usuario_a)
        self.client_b = api_client_for_user(self.usuario_b)

        self.cliente_a = criar_cliente(usuario=self.usuario_a)
        self.cliente_b = criar_cliente(usuario=self.usuario_b, documento='111.444.777-35')
        self.veiculo_a = criar_veiculo(self.cliente_a, usuario=self.usuario_a, placa='AAA1A11')
        self.veiculo_b = criar_veiculo(self.cliente_b, usuario=self.usuario_b, placa='BBB2B22')
        self.servico_b = criar_servico(usuario=self.usuario_b)
        self.peca_b = criar_peca(usuario=self.usuario_b)
        self.os_a = criar_ordem_servico(
            self.cliente_a, self.veiculo_a, usuario=self.usuario_a
        )
        self.os_b = criar_ordem_servico(
            self.cliente_b, self.veiculo_b, usuario=self.usuario_b
        )

    def test_usuario_a_nao_ve_cliente_de_b(self):
        response = self.client_a.get('/api/v1/clientes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data['results']]
        self.assertIn(self.cliente_a.id, ids)
        self.assertNotIn(self.cliente_b.id, ids)

    def test_usuario_b_nao_ve_cliente_de_a(self):
        response = self.client_b.get('/api/v1/clientes/')
        ids = [item['id'] for item in response.data['results']]
        self.assertIn(self.cliente_b.id, ids)
        self.assertNotIn(self.cliente_a.id, ids)

    def test_usuario_a_nao_acessa_cliente_de_b_por_id(self):
        response = self.client_a.get(f'/api/v1/clientes/{self.cliente_b.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_usuario_b_nao_acessa_cliente_de_a_por_id(self):
        response = self.client_b.get(f'/api/v1/clientes/{self.cliente_a.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_ve_todos_os_clientes(self):
        staff = create_staff_user(username='staff', password='staff123')
        client_staff = api_client_for_user(staff)
        response = client_staff.get('/api/v1/clientes/')
        ids = [item['id'] for item in response.data['results']]
        self.assertIn(self.cliente_a.id, ids)
        self.assertIn(self.cliente_b.id, ids)

    def test_created_by_preenchido_automaticamente(self):
        payload = {
            'nome': 'Novo Cliente',
            'documento': '987.654.321-00',
            'email': 'novo@teste.com',
            'telefone': '11999999999',
        }
        response = self.client_a.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.usuario_a.id)

    def test_usuario_a_nao_cria_veiculo_para_cliente_de_b(self):
        payload = {
            'cliente': self.cliente_b.id,
            'placa': 'CCC3C33',
            'marca': 'VW',
            'modelo': 'Gol',
            'ano': 2020,
        }
        response = self.client_a.post('/api/v1/veiculos/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usuario_a_nao_cria_os_com_dados_de_b(self):
        payload = {'cliente': self.cliente_b.id, 'veiculo': self.veiculo_b.id}
        response = self.client_a.post('/api/v1/ordens-servico/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usuario_a_nao_adiciona_peca_em_os_de_b(self):
        payload = {'os': self.os_b.id, 'peca': self.peca_b.id, 'quantidade': 1}
        response = self.client_a.post('/api/v1/itens-pecas/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usuario_a_nao_adiciona_servico_de_b_na_os_propria(self):
        url = f'/api/v1/ordens-servico/{self.os_a.id}/servicos/'
        response = self.client_a.post(url, {'servico': self.servico_b.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Testes de API (endpoints REST)
# ---------------------------------------------------------------------------
