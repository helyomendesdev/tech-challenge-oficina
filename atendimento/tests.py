from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Cliente, Veiculo, OrdemServico, Peca, Servico, ItemPecaOS


# ---------------------------------------------------------------------------
# Helpers de criação de dados de teste
# ---------------------------------------------------------------------------

def criar_cliente(**kwargs):
    defaults = {
        'nome': 'Hélio Teste',
        'documento': '529.982.247-25',  # CPF válido
        'email': 'helio@teste.com',
        'telefone': '11999999999',
    }
    defaults.update(kwargs)
    return Cliente.objects.create(**defaults)


def criar_veiculo(cliente, **kwargs):
    defaults = {
        'placa': 'GTI2E26',
        'marca': 'Volkswagen',
        'modelo': 'Golf GTI',
        'ano': 2026,
    }
    defaults.update(kwargs)
    return Veiculo.objects.create(cliente=cliente, **defaults)


def criar_peca(**kwargs):
    defaults = {'nome': 'Pastilha de Freio', 'valor_unitario': 90.00, 'estoque_atual': 10}
    defaults.update(kwargs)
    return Peca.objects.create(**defaults)


def criar_servico(**kwargs):
    defaults = {'descricao': 'Troca de óleo', 'valor_mao_de_obra': 150.00}
    defaults.update(kwargs)
    return Servico.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Testes de Modelos (regras de negócio puras)
# ---------------------------------------------------------------------------

class OrdemServicoModelTest(TestCase):
    def setUp(self):
        self.cliente = criar_cliente()
        self.veiculo = criar_veiculo(self.cliente)
        self.peca = criar_peca()
        self.os = OrdemServico.objects.create(cliente=self.cliente, veiculo=self.veiculo)

    # C6 CORRIGIDO: setUp agora passa documento e todos os campos obrigatórios

    def test_calculo_total_com_peca(self):
        """Total da OS deve refletir o valor da peça adicionada."""
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=1)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 90.00)

    def test_calculo_total_com_multiplas_pecas(self):
        """Total deve somar todas as peças da OS."""
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=2)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 180.00)

    def test_calculo_total_com_servico(self):
        """Total deve incluir o valor de mão de obra dos serviços."""
        servico = criar_servico()
        self.os.servicos.add(servico)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

    def test_calculo_total_peca_e_servico(self):
        """Total deve combinar serviços e peças."""
        servico = criar_servico()
        self.os.servicos.add(servico)
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=1)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 240.00)  # 150 + 90

    def test_baixa_estoque_automatica(self):
        """Estoque deve ser debitado ao adicionar peça à OS."""
        ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=3)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 7)  # 10 - 3

    def test_devolucao_estoque_ao_remover_peca(self):
        """Estoque deve ser devolvido ao remover peça da OS."""
        item = ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=3)
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 10)  # voltou para 10

    def test_estoque_insuficiente_levanta_erro(self):
        """Deve lançar ValidationError ao solicitar mais do que o estoque disponível."""
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=999)

    def test_timestamps_ao_mudar_status_para_execucao(self):
        """data_inicio_execucao deve ser preenchida automaticamente ao ir para EXECUCAO."""
        self.os.status = 'EXECUCAO'
        self.os.save()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_inicio_execucao)

    def test_timestamps_ao_finalizar_os(self):
        """data_finalizacao deve ser preenchida automaticamente ao ir para FINALIZADA."""
        self.os.status = 'EXECUCAO'
        self.os.save()
        self.os.status = 'FINALIZADA'
        self.os.save()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_finalizacao)


# ---------------------------------------------------------------------------
# Testes de API (endpoints REST)
# ---------------------------------------------------------------------------

class OrdemServicoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tecnico', password='senha@123')  # nosec B106
        self.client.force_authenticate(user=self.user)

        self.cliente = criar_cliente()
        self.veiculo = criar_veiculo(self.cliente)
        self.peca = criar_peca()
        self.os = OrdemServico.objects.create(cliente=self.cliente, veiculo=self.veiculo)

    def test_listar_os_exige_autenticacao(self):
        """Endpoint de listagem deve exigir token JWT."""
        cliente_anonimo = APIClient()
        response = cliente_anonimo.get('/api/v1/ordens-servico/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_criar_os(self):
        """Deve criar uma nova OS com status RECEBIDA."""
        payload = {'cliente': self.cliente.id, 'veiculo': self.veiculo.id}
        response = self.client.post('/api/v1/ordens-servico/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'RECEBIDA')

    def test_avanco_status_valido(self):
        """Deve permitir transição RECEBIDA → DIAGNOSTICO."""
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'status': 'DIAGNOSTICO'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'DIAGNOSTICO')

    def test_transicao_status_invalida(self):
        """Não deve permitir salto de status (ex.: RECEBIDA → ENTREGUE)."""
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'status': 'ENTREGUE'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_cliente_por_placa(self):
        """Endpoint público deve retornar OS pela placa do veículo."""
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.veiculo.placa}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_por_documento(self):
        """Endpoint público deve retornar OS pelo CPF/CNPJ do cliente."""
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': self.cliente.documento}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_consulta_cliente_sem_identificador(self):
        """Deve retornar 400 se o identificador não for informado."""
        response = self.client.get('/api/v1/ordens-servico/consulta-cliente/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_consulta_cliente_nao_encontrado(self):
        """Deve retornar 404 para identificador inexistente."""
        response = self.client.get(
            '/api/v1/ordens-servico/consulta-cliente/',
            {'identificador': '000.000.000-00'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ClienteAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tecnico', password='senha@123')  # nosec B106
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
        """Não deve permitir cadastrar dois clientes com o mesmo CPF."""
        criar_cliente()  # CPF 529.982.247-25
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
        self.user = User.objects.create_user(username='tecnico', password='senha@123')  # nosec B106
        self.client.force_authenticate(user=self.user)

        self.cliente = criar_cliente()
        self.veiculo = criar_veiculo(self.cliente)

        # Cria OS em estados diferentes para testar filtros
        self.os_recebida = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, status='RECEBIDA'
        )
        self.os_execucao = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, status='EXECUCAO'
        )

    def test_filtrar_por_status_recebida(self):
        """?status=RECEBIDA deve retornar apenas OS nesse estado."""
        response = self.client.get('/api/v1/ordens-servico/', {'status': 'RECEBIDA'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_retornados = [item['id'] for item in response.data['results']]
        self.assertIn(self.os_recebida.id, ids_retornados)
        self.assertNotIn(self.os_execucao.id, ids_retornados)

    def test_filtrar_por_status_execucao(self):
        """?status=EXECUCAO deve retornar apenas OS em execução."""
        response = self.client.get('/api/v1/ordens-servico/', {'status': 'EXECUCAO'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids_retornados = [item['id'] for item in response.data['results']]
        self.assertIn(self.os_execucao.id, ids_retornados)
        self.assertNotIn(self.os_recebida.id, ids_retornados)

    def test_filtrar_por_cliente(self):
        """?cliente=<id> deve retornar apenas OS daquele cliente."""
        response = self.client.get('/api/v1/ordens-servico/', {'cliente': self.cliente.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_ordenar_por_valor_total(self):
        """?ordering=valor_total deve retornar OS em ordem crescente de valor."""
        response = self.client.get('/api/v1/ordens-servico/', {'ordering': 'valor_total'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_busca_cliente_por_nome(self):
        """?search=<nome> em /clientes/ deve fazer busca parcial case-insensitive."""
        response = self.client.get('/api/v1/clientes/', {'search': 'hélio'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_filtrar_peca_por_nome_parcial(self):
        """?nome=pastilha em /pecas/ deve fazer busca parcial (icontains)."""
        criar_peca(nome='Pastilha de Freio Dianteira')
        criar_peca(nome='Filtro de Óleo')
        response = self.client.get('/api/v1/pecas/', {'nome': 'pastilha'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_filtrar_pecas_com_estoque_minimo(self):
        """?estoque_min=5 deve retornar apenas peças com estoque >= 5."""
        criar_peca(nome='Peca A', estoque_atual=10)
        criar_peca(nome='Peca B', estoque_atual=2)
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
        self.user = User.objects.create_user(username='tecnico', password='senha@123')  # nosec B106
        self.client.force_authenticate(user=self.user)

    def test_erro_validacao_retorna_campo_estruturado(self):
        """Erros de validação devem retornar 'campos' como dict, não como string."""
        payload = {
            'nome': 'João',
            'documento': '111.111.111-11',  # CPF inválido
            'email': 'joao@teste.com',
            'telefone': '11999999999',
        }
        response = self.client.post('/api/v1/clientes/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # O erro deve ter a chave 'campos' com dict estruturado, não string bruta
        self.assertIn('campos', response.data)
        self.assertIsInstance(response.data['campos'], dict)
        self.assertIn('erro', response.data)
        self.assertIn('status_code', response.data)

    def test_erro_autenticacao_retorna_mensagem_simples(self):
        """Erros de autenticação (401) devem retornar 'mensagem' como string."""
        cliente_anonimo = APIClient()
        response = cliente_anonimo.get('/api/v1/clientes/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('mensagem', response.data)
        self.assertIsInstance(response.data['mensagem'], str)
        self.assertNotIn('campos', response.data)

    def test_erro_404_retorna_mensagem_simples(self):
        """Erros 404 devem retornar 'mensagem' como string."""
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
        cliente = criar_cliente()
        payload = {'nome': 'Nome Atualizado', 'documento': cliente.documento}
        response = self.client.patch(f'/api/v1/clientes/{cliente.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class VeiculoAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tecnico_veiculo', password='senha@123')  # nosec B106
        self.client.force_authenticate(user=self.user)
        self.cliente = criar_cliente()

    def test_criar_veiculo_placa_upper(self):
        payload = {'cliente': self.cliente.id, 'placa': 'abc1234', 'marca': 'VW', 'modelo': 'Gol', 'ano': 2020}
        response = self.client.post('/api/v1/veiculos/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['placa'], 'ABC1234')


class ItemPecaOSAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='tecnico_item', password='senha@123')  # nosec B106
        self.client.force_authenticate(user=self.user)
        self.cliente = criar_cliente()
        self.veiculo = criar_veiculo(self.cliente)
        self.os = OrdemServico.objects.create(cliente=self.cliente, veiculo=self.veiculo)
        self.peca = criar_peca(estoque_atual=10)

    def test_adicionar_peca_estoque_insuficiente(self):
        payload = {'os': self.os.id, 'peca': self.peca.id, 'quantidade': 11}
        response = self.client.post('/api/v1/itens-pecas/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_peca_estoque_insuficiente(self):
        item = ItemPecaOS.objects.create(os=self.os, peca=self.peca, quantidade=5)
        self.peca.refresh_from_db()  # estoque_atual goes to 5 due to signals/save
        payload = {'quantidade': 15}
        response = self.client.patch(f'/api/v1/itens-pecas/{item.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)