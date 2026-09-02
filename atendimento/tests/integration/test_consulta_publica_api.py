from atendimento.tests.helpers import *
class ConsultaPublicaAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico')
        self.client = api_client_for_user(self.user)

        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.peca = criar_peca(usuario=self.user)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)
        self.cliente_cnpj = criar_cliente(
            usuario=self.user,
            documento='12.340.546/0001-50',
            email='empresa@teste.com',
        )
        self.veiculo_cnpj = criar_veiculo(
            self.cliente_cnpj,
            usuario=self.user,
            placa='EMP1A23',
        )
        self.os_cnpj = criar_ordem_servico(
            self.cliente_cnpj, self.veiculo_cnpj, usuario=self.user
        )

    def test_consulta_cliente_por_placa(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.veiculo.placa}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_placa_minuscula_sem_jwt(self):
        cliente_anonimo = APIClient()
        response = cliente_anonimo.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.veiculo.placa.lower()}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_documento(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.cliente.documento}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_cpf_sem_pontuacao(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '52998224725'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_documento_formatado(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '529.982.247-25'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_cnpj_com_e_sem_pontuacao(self):
        response_formatado = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '12.340.546/0001-50'}
        )
        response_sem_pontuacao = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '12340546000150'}
        )

        self.assertEqual(response_formatado.status_code, status.HTTP_200_OK)
        self.assertEqual(response_sem_pontuacao.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_nao_expoe_dados_administrativos(self):
        servico = criar_servico(usuario=self.user)
        criar_item_servico_os(self.os, servico, self.user)
        criar_item_peca_os(self.os, self.peca, usuario=self.user, quantidade=1)

        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.veiculo.placa}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data['results'][0]
        self.assertNotIn('created_by', item)
        self.assertNotIn('cliente', item)
        self.assertNotIn('ativo', item)
        self.assertIn('veiculo', item)
        self.assertIn('servicos', item)
        self.assertIn('pecas', item)
        self.assertEqual(len(item['servicos']), 1)
        self.assertEqual(len(item['pecas']), 1)

    def test_consulta_cliente_mantem_allowany_e_throttle_especifico(self):
        from rest_framework.permissions import AllowAny
        from atendimento.throttles import ConsultaClienteThrottle
        from atendimento.views import OrdemServicoViewSet

        action_kwargs = OrdemServicoViewSet.consulta_cliente.kwargs

        self.assertEqual(action_kwargs['permission_classes'], [AllowAny])
        self.assertEqual(action_kwargs['throttle_classes'], [ConsultaClienteThrottle])

    def test_consulta_cliente_sem_identificador(self):
        response = self.client.get('/api/v1/ordens-servico/consulta-cliente/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_cliente_nao_encontrado(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '000.000.000-00'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
