from atendimento.tests.helpers import *
class ClienteAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico')
        self.client = api_client_for_user(self.user)

    def test_criar_cliente_com_cpf_valido(self):
        payload = {
            'nome': 'João Silva',
            'documento': '529.982.247-25',
            'email': 'joao@teste.com',
            'telefone': '11988887777',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['documento'], '52998224725')
        self.assertEqual(response.data['created_by'], self.user.id)

    def test_criar_cliente_com_cnpj_valido(self):
        payload = {
            'nome': 'Oficina Parceira LTDA',
            'documento': '06.740.113/9659-03',
            'email': 'oficina@teste.com',
            'telefone': '1133334444',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['documento'], '06740113965903')
        self.assertEqual(response.data['created_by'], self.user.id)

    def test_criar_cliente_com_cpf_invalido(self):
        payload = {
            'nome': 'João Inválido',
            'documento': '111.111.111-11',
            'email': 'joao@teste.com',
            'telefone': '11988887777',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_criar_cliente_duplicado(self):
        criar_cliente(usuario=self.user)
        payload = {
            'nome': 'Outro Nome',
            'documento': '529.982.247-25',
            'email': 'outro@teste.com',
            'telefone': '11988887777',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class ClienteCRUDAdministrativoFase1Test(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_crud')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='153.509.460-56')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='CRD1A11')

    def test_cliente_crud_completo(self):
        payload = {
            'nome': 'Cliente CRUD',
            'documento': '529.982.247-25',
            'email': 'crud@teste.com',
            'telefone': '11911112222',
        }

        create = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        cliente_id = create.data['id']

        list_response = self.client.get('/api/v1/clientes/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'/api/v1/clientes/{cliente_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            f'/api/v1/clientes/{cliente_id}/',
            {'telefone': '11933334444'},
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data['telefone'], '11933334444')

        delete = self.client.delete(f'/api/v1/clientes/{cliente_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
