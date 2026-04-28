from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Cliente, Veiculo, OrdemServico, Peca, Servico, ItemPecaOS


# ---------------------------------------------------------------------------
# Helpers de criação de dados de teste
# ---------------------------------------------------------------------------

def criar_usuario(username='tecnico', password='senha@123'):
    return User.objects.create_user(username=username, password=password)  # nosec B106,B107


def criar_cliente(usuario=None, **kwargs):
    defaults = {
        'nome': 'Hélio Teste',
        'documento': '529.982.247-25',
        'email': 'helio@teste.com',
        'telefone': '11999999999',
    }
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Cliente.objects.create(**defaults)


def criar_veiculo(cliente, usuario=None, **kwargs):
    defaults = {
        'placa': 'GTI2E26',
        'marca': 'Volkswagen',
        'modelo': 'Golf GTI',
        'ano': 2026,
    }
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Veiculo.objects.create(cliente=cliente, **defaults)


def criar_peca(usuario=None, **kwargs):
    defaults = {'nome': 'Pastilha de Freio', 'valor_unitario': 90.00, 'estoque_atual': 10}
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Peca.objects.create(**defaults)


def criar_servico(usuario=None, **kwargs):
    defaults = {'descricao': 'Troca de óleo', 'valor_mao_de_obra': 150.00}
    defaults.update(kwargs)
    if usuario:
        defaults['created_by'] = usuario
    return Servico.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Testes de Modelos (regras de negócio puras)
# ---------------------------------------------------------------------------

class OrdemServicoModelTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.cliente = criar_cliente(usuario=self.usuario)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.usuario
        )

    def test_calculo_total_com_peca(self):
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=1, created_by=self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 90.00)

    def test_calculo_total_com_multiplas_pecas(self):
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=2, created_by=self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 180.00)

    def test_calculo_total_com_servico(self):
        servico = criar_servico(usuario=self.usuario)
        self.os.servicos.add(servico)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

    def test_calculo_total_peca_e_servico(self):
        servico = criar_servico(usuario=self.usuario)
        self.os.servicos.add(servico)
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=1, created_by=self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 240.00)

    def test_baixa_estoque_automatica(self):
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=3, created_by=self.usuario)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 7)

    def test_devolucao_estoque_ao_remover_peca(self):
        item = ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=3, created_by=self.usuario)
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 10)

    def test_estoque_insuficiente_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=999, created_by=self.usuario)

    def test_timestamps_ao_mudar_status_para_execucao(self):
        self.os.status = 'EXECUCAO'
        self.os.save()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_inicio_execucao)

    def test_timestamps_ao_finalizar_os(self):
        self.os.status = 'EXECUCAO'
        self.os.save()
        self.os.status = 'FINALIZADA'
        self.os.save()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_finalizacao)


# ---------------------------------------------------------------------------
# Testes de Isolamento por Usuário (OWASP A01)
# ---------------------------------------------------------------------------

class IsolamentoDadosTest(TestCase):
    def setUp(self):
        self.usuario_a = criar_usuario('tecnico_a')
        self.usuario_b = criar_usuario('tecnico_b')
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.usuario_a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.usuario_b)

        self.cliente_a = criar_cliente(usuario=self.usuario_a)
        self.cliente_b = criar_cliente(usuario=self.usuario_b, documento='111.444.777-35')

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
        staff = User.objects.create_user('staff', password='staff123', is_staff=True)  # nosec B106
        client_staff = APIClient()
        client_staff.force_authenticate(user=staff)
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


# ---------------------------------------------------------------------------
# Testes de API (endpoints REST)
# ---------------------------------------------------------------------------

class OrdemServicoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico')
        self.client.force_authenticate(user=self.user)

        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.peca = criar_peca(usuario=self.user)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.user
        )

    def test_listar_os_exige_autenticacao(self):
        cliente_anonimo = APIClient()
        response = cliente_anonimo.get('/api/v1/ordens-servico/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_criar_os(self):
        payload = {'cliente': self.cliente.id, 'veiculo': self.veiculo.id}
        response = self.client.post('/api/v1/ordens-servico/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'RECEBIDA')
        self.assertEqual(response.data['created_by'], self.user.id)

    def test_avanco_status_valido(self):
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'status': 'DIAGNOSTICO'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'DIAGNOSTICO')

    def test_transicao_status_invalida(self):
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'status': 'ENTREGUE'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_cliente_por_placa(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.veiculo.placa}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_documento(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.cliente.documento}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_sem_identificador(self):
        response = self.client.get('/api/v1/ordens-servico/consulta-cliente/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_cliente_nao_encontrado(self):
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '000.000.000-00'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ClienteAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico')
        self.client.force_authenticate(user=self.user)

    def test_criar_cliente_com_cpf_valido(self):
        payload = {
            'nome': 'João Silva',
            'documento': '529.982.247-25',
            'email': 'joao@teste.com',
            'telefone': '11988887777',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
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


# ---------------------------------------------------------------------------
# Testes de Filtros (django-filter)
# ---------------------------------------------------------------------------

class FiltroOrdemServicoTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico')
        self.client.force_authenticate(user=self.user)

        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)

        self.os_recebida = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, status='RECEBIDA', created_by=self.user
        )
        self.os_execucao = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, status='EXECUCAO', created_by=self.user
        )

    def test_filtrar_por_status_recebida(self):
        response = self.client.get('/api/v1/ordens-servico/', {'status': 'RECEBIDA'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_retornados = [item['id'] for item in response.data['results']]
        self.assertIn(self.os_recebida.id, ids_retornados)
        self.assertNotIn(self.os_execucao.id, ids_retornados)

    def test_filtrar_por_status_execucao(self):
        response = self.client.get('/api/v1/ordens-servico/', {'status': 'EXECUCAO'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_retornados = [item['id'] for item in response.data['results']]
        self.assertIn(self.os_execucao.id, ids_retornados)
        self.assertNotIn(self.os_recebida.id, ids_retornados)

    def test_filtrar_por_cliente(self):
        response = self.client.get('/api/v1/ordens-servico/', {'cliente': self.cliente.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_ordenar_por_valor_total(self):
        response = self.client.get('/api/v1/ordens-servico/', {'ordering': 'valor_total'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_busca_cliente_por_nome(self):
        response = self.client.get('/api/v1/clientes/', {'search': 'hélio'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_filtrar_peca_por_nome_parcial(self):
        criar_peca(usuario=self.user, nome='Pastilha de Freio Dianteira')
        criar_peca(usuario=self.user, nome='Filtro de Óleo')
        response = self.client.get('/api/v1/pecas/', {'nome': 'pastilha'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filtrar_pecas_com_estoque_minimo(self):
        criar_peca(usuario=self.user, nome='Peca A', estoque_atual=10)
        criar_peca(usuario=self.user, nome='Peca B', estoque_atual=2)
        response = self.client.get('/api/v1/pecas/', {'estoque_min': 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data['results']:
            self.assertGreaterEqual(item['estoque_atual'], 5)


# ---------------------------------------------------------------------------
# Testes do Handler de Exceções (formato estruturado de erros)
# ---------------------------------------------------------------------------

class ExceptionHandlerTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico')
        self.client.force_authenticate(user=self.user)

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


class VeiculoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico_veiculo')
        self.client.force_authenticate(user=self.user)
        self.cliente = criar_cliente(usuario=self.user)

    def test_criar_veiculo_placa_upper(self):
        payload = {'cliente': self.cliente.id, 'placa': 'abc1234', 'marca': 'VW', 'modelo': 'Gol', 'ano': 2020}
        response = self.client.post('/api/v1/veiculos/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['placa'], 'ABC1234')
        self.assertEqual(response.data['created_by'], self.user.id)


class ItemPecaOSAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario('tecnico_item')
        self.client.force_authenticate(user=self.user)
        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.user
        )
        self.peca = criar_peca(usuario=self.user, estoque_atual=10)

    def test_adicionar_peca_estoque_insuficiente(self):
        payload = {'os': self.os.id, 'peca': self.peca.id, 'quantidade': 11}
        response = self.client.post('/api/v1/itens-pecas/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_peca_estoque_insuficiente(self):
        item = ItemPecaOS.objects.create(
            os=self.os, peca=self.peca, quantidade=5, created_by=self.user
        )
        self.peca.refresh_from_db()
        payload = {'quantidade': 15}
        response = self.client.patch(f'/api/v1/itens-pecas/{item.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
