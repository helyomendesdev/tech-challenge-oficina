from atendimento.tests.helpers import *
class ExceptionHandlerTest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico')
        self.client = api_client_for_user(self.user)

    def test_erro_validacao_retorna_campo_estruturado(self):
        payload = {
            'nome': 'João',
            'documento': '111.111.111-11',
            'email': 'joao@teste.com',
            'telefone': '11999999999',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('campos', response.data)
        self.assertIsInstance(response.data['campos'], dict)
        self.assertIn('erro', response.data)
        self.assertIn('status_code', response.data)

    def test_erro_autenticacao_retorna_mensagem_simples(self):
        cliente_anonimo = APIClient()
        response = cliente_anonimo.get('/api/v1/clientes/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('mensagem', response.data)
        self.assertIsInstance(response.data['mensagem'], str)
        self.assertNotIn('campos', response.data)

    def test_erro_404_retorna_mensagem_simples(self):
        response = self.client.get('/api/v1/clientes/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('mensagem', response.data)
        self.assertIsInstance(response.data['mensagem'], str)

    def test_domain_error_global_retorna_400_padronizado(self):
        from atendimento.domain.exceptions import DomainError
        from atendimento.exceptions import custom_exception_handler

        response = custom_exception_handler(DomainError('Regra violada.'), {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['erro'], True)
        self.assertEqual(response.data['status_code'], status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['mensagem'], 'Regra violada.')

    def test_ordem_servico_nao_encontrada_global_retorna_404(self):
        from atendimento.domain.exceptions import OrdemServicoNaoEncontradaError
        from atendimento.exceptions import custom_exception_handler

        response = custom_exception_handler(
            OrdemServicoNaoEncontradaError('Ordem de servico nao encontrada.'),
            {},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['erro'], True)
        self.assertEqual(response.data['status_code'], status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.data['mensagem'],
            'Ordem de servico nao encontrada.',
        )

    def test_django_validation_error_global_retorna_400(self):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from atendimento.exceptions import custom_exception_handler

        response = custom_exception_handler(
            DjangoValidationError({'quantidade': ['Quantidade invalida.']}),
            {},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['erro'], True)
        self.assertEqual(response.data['status_code'], status.HTTP_400_BAD_REQUEST)
        self.assertIn('campos', response.data)
        self.assertEqual(response.data['campos']['quantidade'], 'Quantidade invalida.')

    def test_criar_cliente_com_tamanho_documento_invalido(self):
        payload = {'nome': 'Teste', 'documento': '123', 'email': 'a@a.com', 'telefone': '11'}
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_criar_cliente_com_cnpj_invalido(self):
        payload = {'nome': 'Teste CNPJ', 'documento': '11.111.111/1111-11', 'email': 'b@b.com', 'telefone': '11'}
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_cliente_mesmo_documento(self):
        cliente = criar_cliente(usuario=self.user)
        payload = {'nome': 'Nome Atualizado', 'documento': cliente.documento}
        response = self.client.patch(f'/api/v1/clientes/{cliente.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
