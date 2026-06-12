from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Cliente, Veiculo, OrdemServico, Peca, Servico, ItemPecaOS, ItemServicoOS, ConsumoItemServico


# ---------------------------------------------------------------------------
# Helpers de criação de dados de teste
# ---------------------------------------------------------------------------

def criar_usuario(username='tecnico', password='senha@123'):  # NOSONAR
    return User.objects.create_user(username=username, password=password)  # nosec B106,B107 # NOSONAR


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


def criar_item_servico_os(os, servico, usuario=None, status='PENDENTE', **kwargs):
    return ItemServicoOS.objects.create(
        ordem_servico=os,
        servico=servico,
        created_by=usuario,
        status=status,
        **kwargs
    )


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
        ItemServicoOS.objects.create(
            ordem_servico=self.os, servico=servico, created_by=self.usuario
        )
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

    def test_calculo_total_peca_e_servico(self):
        servico = criar_servico(usuario=self.usuario)
        ItemServicoOS.objects.create(
            ordem_servico=self.os, servico=servico, created_by=self.usuario
        )
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
        OrdemServico.objects.filter(pk=self.os.pk).update(status='AGUARDANDO')
        self.os.refresh_from_db()
        self.os.aprovar_orcamento()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_inicio_execucao)

    def test_timestamps_ao_finalizar_os(self):
        OrdemServico.objects.filter(pk=self.os.pk).update(status='EXECUCAO')
        self.os.refresh_from_db()
        self.os.finalizar()
        self.os.refresh_from_db()
        self.assertIsNotNone(self.os.data_finalizacao)


class OrdemServicoTransicaoTest(TestCase):
    """Testa os métodos de transição de estado do modelo OrdemServico."""

    def setUp(self):
        self.usuario = criar_usuario(username='tecnico_trans')
        self.cliente = criar_cliente(usuario=self.usuario, documento='49.648.573/0001-22')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='TRS1A11')
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.usuario
        )

    def _os_em(self, status_alvo):
        """Helper: força o status sem passar pelos guards de domínio."""
        OrdemServico.objects.filter(pk=self.os.pk).update(status=status_alvo)
        self.os.refresh_from_db()

    # --- iniciar_diagnostico ---

    def test_iniciar_diagnostico_de_recebida(self):
        self.os.iniciar_diagnostico()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'DIAGNOSTICO')

    def test_iniciar_diagnostico_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        self._os_em('DIAGNOSTICO')
        with self.assertRaises(ValidationError):
            self.os.iniciar_diagnostico()

    # --- finalizar_diagnostico ---

    def test_finalizar_diagnostico_de_diagnostico(self):
        self._os_em('DIAGNOSTICO')
        self.os.finalizar_diagnostico()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'AGUARDANDO')

    def test_finalizar_diagnostico_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.finalizar_diagnostico()

    # --- aprovar_orcamento ---

    def test_aprovar_orcamento_de_aguardando(self):
        self._os_em('AGUARDANDO')
        self.os.aprovar_orcamento()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'EXECUCAO')
        self.assertIsNotNone(self.os.data_inicio_execucao)

    def test_aprovar_orcamento_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.aprovar_orcamento()

    # --- recusar_orcamento ---

    def test_recusar_orcamento_volta_para_diagnostico(self):
        self._os_em('AGUARDANDO')
        self.os.recusar_orcamento()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'DIAGNOSTICO')

    def test_recusar_orcamento_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.recusar_orcamento()

    # --- finalizar ---

    def test_finalizar_de_execucao(self):
        self._os_em('EXECUCAO')
        self.os.finalizar()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'FINALIZADA')
        self.assertIsNotNone(self.os.data_finalizacao)

    def test_finalizar_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.finalizar()

    def test_finalizar_com_servico_nao_concluido_levanta_erro(self):
        from django.core.exceptions import ValidationError
        self._os_em('EXECUCAO')
        servico = criar_servico(usuario=self.usuario)
        ItemServicoOS.objects.create(
            ordem_servico=self.os, servico=servico, created_by=self.usuario
        )
        with self.assertRaises(ValidationError):
            self.os.finalizar()

    # --- entregar ---

    def test_entregar_de_finalizada(self):
        self._os_em('FINALIZADA')
        self.os.entregar()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'ENTREGUE')

    def test_entregar_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.entregar()

    # --- cancelar ---

    def test_cancelar_de_aguardando(self):
        self._os_em('AGUARDANDO')
        self.os.cancelar()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'CANCELADA')

    def test_cancelar_status_errado_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.os.cancelar()

    # --- fluxo completo ---

    def test_recusar_e_reenviar_orcamento(self):
        self._os_em('AGUARDANDO')
        self.os.recusar_orcamento()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'DIAGNOSTICO')
        self.os.finalizar_diagnostico()
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'AGUARDANDO')


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
        staff = User.objects.create_user('staff', password='staff123', is_staff=True)  # nosec B106 # NOSONAR
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

    def test_status_ignorado_em_patch(self):
        """status é read-only: PATCH com status não deve alterar o valor."""
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'status': 'ENTREGUE'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'RECEBIDA')

    def test_status_ignorado_em_patch_campo_valido(self):
        """PATCH de outros campos funciona normalmente."""
        response = self.client.patch(
            f'/api/v1/ordens-servico/{self.os.id}/',
            {'veiculo': self.veiculo.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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


class ItemServicoOSModelTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico2')
        self.cliente = criar_cliente(usuario=self.usuario, documento='12.340.546/0001-50')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E27')
        self.servico = criar_servico(usuario=self.usuario)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.usuario
        )

    def test_item_servico_os_criado_como_pendente(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario)
        self.assertEqual(item.status, 'PENDENTE')
        self.assertIsNone(item.data_inicio)
        self.assertIsNone(item.data_finalizacao)

    def test_tempo_execucao_minutos_retorna_none_sem_timestamps(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario)
        self.assertIsNone(item.tempo_execucao_minutos)

    def test_tempo_execucao_minutos_calcula_corretamente(self):
        from django.utils import timezone
        import datetime
        inicio = timezone.now()
        fim = inicio + datetime.timedelta(hours=1)
        item = criar_item_servico_os(
            self.os, self.servico, self.usuario,
            data_inicio=inicio, data_finalizacao=fim
        )
        self.assertAlmostEqual(item.tempo_execucao_minutos, 60.0, places=1)

    def test_criar_item_servico_os_recalcula_total_os(self):
        criar_item_servico_os(self.os, self.servico, self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

    def test_deletar_item_servico_os_recalcula_total_os(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)
        item.delete()
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 0.00)

    def test_quantidade_utilizada_padrao_zero(self):
        peca = criar_peca(usuario=self.usuario)
        item_peca = ItemPecaOS.objects.create(
            os=self.os, peca=peca, quantidade=5, created_by=self.usuario
        )
        self.assertEqual(item_peca.quantidade_utilizada, 0)


# ---------------------------------------------------------------------------
# Testes de API CRUD para ItemServicoOS (rotas aninhadas)
# ---------------------------------------------------------------------------

class ItemServicoOSCRUDTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico3')
        self.cliente = criar_cliente(usuario=self.usuario, documento='16.827.912/0001-01')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E28')
        self.servico = criar_servico(usuario=self.usuario)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.usuario
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)
        self.url_list = f'/api/v1/ordens-servico/{self.os.pk}/servicos/'

    def test_adicionar_servico_a_os(self):
        response = self.client.post(self.url_list, {'servico': self.servico.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'PENDENTE')
        self.assertIsNone(response.data['data_inicio'])

    def test_listar_servicos_da_os(self):
        criar_item_servico_os(self.os, self.servico, self.usuario)
        response = self.client.get(self.url_list)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)

    def test_detalhar_servico_da_os(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario)
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item.pk}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], item.pk)

    def test_remover_servico_pendente(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario)
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ItemServicoOS.objects.filter(pk=item.pk).exists())

    def test_nao_remover_servico_em_execucao(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario, status='EM_EXECUCAO')
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ItemServicoOS.objects.filter(pk=item.pk).exists())

    def test_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro3')
        os_outro = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=outro
        )
        item = criar_item_servico_os(os_outro, self.servico, outro)
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item.pk}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action iniciar em ItemServicoOS
# ---------------------------------------------------------------------------

class IniciarServicoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico4')
        self.cliente = criar_cliente(usuario=self.usuario, documento='67.501.780/0001-96')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E29')
        self.servico = criar_servico(usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario, estoque_atual=10)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo,
            created_by=self.usuario, status='EXECUCAO'
        )
        self.item_peca = ItemPecaOS.objects.create(
            os=self.os, peca=self.peca, quantidade=5, created_by=self.usuario
        )
        self.item = criar_item_servico_os(self.os, self.servico, self.usuario)
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)
        self.url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{self.item.pk}/iniciar/'

    def test_iniciar_sem_pecas_muda_status_para_em_execucao(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'EM_EXECUCAO')
        self.assertIsNotNone(self.item.data_inicio)

    def test_iniciar_usa_data_fornecida(self):
        data = '2026-05-01T11:00:00Z'
        response = self.client.post(self.url, {'data_inicio': data}, format='json')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(
            self.item.data_inicio.strftime('%Y-%m-%dT%H:%M:%SZ'), data
        )

    def test_iniciar_servico_nao_altera_status_da_os(self):
        """Com a OS já em EXECUCAO (após aprovar_orcamento), iniciar serviço não muda o status da OS."""
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'EXECUCAO')

    def test_iniciar_com_pecas_registra_consumo(self):
        payload = {'pecas': [{'item_peca_os_id': self.item_peca.pk, 'quantidade': 3}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.item_peca.refresh_from_db()
        self.assertEqual(self.item_peca.quantidade_utilizada, 3)
        self.assertEqual(ConsumoItemServico.objects.filter(item_servico_os=self.item).count(), 1)

    def test_iniciar_com_quantidade_acima_do_disponivel_retorna_400(self):
        # Partially consume so disponivel=2, then request 3 (>2 but <=5)
        ItemPecaOS.objects.filter(pk=self.item_peca.pk).update(quantidade_utilizada=3)
        self.item_peca.refresh_from_db()
        payload = {'pecas': [{'item_peca_os_id': self.item_peca.pk, 'quantidade': 3}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Quantidade indisponível', response.data['erro'])

    def test_iniciar_peca_de_outra_os_retorna_400(self):
        outra_os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.usuario
        )
        peca_outra = criar_peca(usuario=self.usuario, estoque_atual=5)
        item_outra = ItemPecaOS.objects.create(
            os=outra_os, peca=peca_outra, quantidade=3, created_by=self.usuario
        )
        payload = {'pecas': [{'item_peca_os_id': item_outra.pk, 'quantidade': 1}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('não pertence', response.data['erro'])

    def test_iniciar_servico_ja_iniciado_retorna_400(self):
        self.item.status = 'EM_EXECUCAO'
        self.item.save()
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_iniciar_em_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro4')
        os_outro = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=outro
        )
        item_outro = criar_item_servico_os(os_outro, self.servico, outro)
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item_outro.pk}/iniciar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action finalizar em ItemServicoOS
# ---------------------------------------------------------------------------

class FinalizarServicoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico5')
        self.cliente = criar_cliente(usuario=self.usuario, documento='77.411.263/0001-08')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E30')
        self.servico = criar_servico(usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario, estoque_atual=10)
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo,
            created_by=self.usuario, status='EXECUCAO'
        )
        self.item_peca = ItemPecaOS.objects.create(
            os=self.os, peca=self.peca, quantidade=5, created_by=self.usuario
        )
        self.item = criar_item_servico_os(
            self.os, self.servico, self.usuario, status='EM_EXECUCAO'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)
        self.url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{self.item.pk}/finalizar/'

    def _usar_todas_as_pecas(self):
        ItemPecaOS.objects.filter(pk=self.item_peca.pk).update(quantidade_utilizada=5)

    def test_finalizar_sem_pecas_pendentes_muda_status_para_concluido(self):
        self._usar_todas_as_pecas()
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'CONCLUIDO')
        self.assertIsNotNone(self.item.data_finalizacao)

    def test_finalizar_usa_data_fornecida(self):
        self._usar_todas_as_pecas()
        data = '2026-05-01T15:00:00Z'
        response = self.client.post(self.url, {'data_finalizacao': data}, format='json')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(
            self.item.data_finalizacao.strftime('%Y-%m-%dT%H:%M:%SZ'), data
        )

    def test_finalizar_ultimo_servico_transita_os_para_finalizada(self):
        self._usar_todas_as_pecas()
        self.client.post(self.url, {}, format='json')
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'FINALIZADA')
        self.assertIsNotNone(self.os.data_finalizacao)

    def test_finalizar_bloqueado_se_pecas_nao_utilizadas(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('peças não utilizadas', response.data['erro'])

    def test_finalizar_nao_transita_os_se_ainda_ha_servico_ativo(self):
        self._usar_todas_as_pecas()
        servico2 = criar_servico(usuario=self.usuario)
        criar_item_servico_os(self.os, servico2, self.usuario, status='EM_EXECUCAO')
        self.client.post(self.url, {}, format='json')
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'EXECUCAO')

    def test_finalizar_servico_pendente_retorna_400(self):
        servico_pendente = criar_servico(usuario=self.usuario)
        item_pendente = criar_item_servico_os(self.os, servico_pendente, self.usuario)
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item_pendente.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_os_sem_itens_pecas_finaliza_normalmente(self):
        os_sem_pecas = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo,
            created_by=self.usuario, status='EXECUCAO'
        )
        item = criar_item_servico_os(os_sem_pecas, self.servico, self.usuario, status='EM_EXECUCAO')
        url = f'/api/v1/ordens-servico/{os_sem_pecas.pk}/servicos/{item.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        os_sem_pecas.refresh_from_db()
        self.assertEqual(os_sem_pecas.status, 'FINALIZADA')

    def test_finalizar_em_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro5')
        os_outro = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=outro
        )
        servico2 = criar_servico(usuario=outro)
        item_outro = criar_item_servico_os(os_outro, servico2, outro, status='EM_EXECUCAO')
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item_outro.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action metricas em OrdemServicoViewSet
# ---------------------------------------------------------------------------

class MetricasServicoTest(TestCase):
    def setUp(self):
        from django.utils import timezone
        import datetime
        self.usuario = criar_usuario(username='tecnico6')
        self.cliente = criar_cliente(usuario=self.usuario, documento='01.339.513/0001-08')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E31')
        self.servico1 = criar_servico(usuario=self.usuario, descricao='Troca de Óleo')
        self.servico2 = criar_servico(usuario=self.usuario, descricao='Alinhamento')
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo,
            created_by=self.usuario, status='EXECUCAO'
        )

        inicio = timezone.now()
        fim1 = inicio + datetime.timedelta(hours=1)
        fim2 = inicio + datetime.timedelta(hours=3)

        self.item1 = criar_item_servico_os(
            self.os, self.servico1, self.usuario,
            status='CONCLUIDO', data_inicio=inicio, data_finalizacao=fim1
        )
        self.item2 = criar_item_servico_os(
            self.os, self.servico2, self.usuario,
            status='CONCLUIDO', data_inicio=inicio, data_finalizacao=fim2
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.usuario)
        self.url = f'/api/v1/ordens-servico/{self.os.pk}/metricas/'

    def test_metricas_retorna_todos_os_servicos_da_os(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        descricoes = {item['servico']: item['descricao'] for item in response.data}
        self.assertEqual(descricoes[self.servico1.pk], self.servico1.descricao)
        self.assertEqual(descricoes[self.servico2.pk], self.servico2.descricao)

    def test_metricas_calcula_tempo_execucao(self):
        response = self.client.get(self.url)
        tempos = {item['servico']: item['tempo_execucao_minutos'] for item in response.data}
        self.assertAlmostEqual(tempos[self.servico1.pk], 60.0, places=0)
        self.assertAlmostEqual(tempos[self.servico2.pk], 180.0, places=0)

    def test_metricas_filtro_por_servico(self):
        response = self.client.get(self.url, {'servico': self.servico1.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['servico'], self.servico1.pk)

    def test_metricas_servico_pendente_retorna_tempo_null(self):
        servico_extra = criar_servico(usuario=self.usuario)
        item_pendente = criar_item_servico_os(self.os, servico_extra, self.usuario)
        response = self.client.get(self.url, {'servico': item_pendente.servico_id})
        tempos_null = [
            item['tempo_execucao_minutos']
            for item in response.data
            if item['id'] == item_pendente.pk
        ]
        self.assertIn(None, tempos_null)

    def test_metricas_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro6')
        os_outro = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=outro
        )
        url = f'/api/v1/ordens-servico/{os_outro.pk}/metricas/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_metricas_inclui_pecas_consumidas(self):
        peca = criar_peca(usuario=self.usuario, estoque_atual=5)
        item_peca = ItemPecaOS.objects.create(
            os=self.os, peca=peca, quantidade=3, created_by=self.usuario
        )
        ConsumoItemServico.objects.create(
            item_servico_os=self.item1,
            item_peca_os=item_peca,
            quantidade=2,
        )
        response = self.client.get(self.url, {'servico': self.servico1.pk})
        consumos = response.data[0]['pecas_consumidas']
        self.assertEqual(len(consumos), 1)
        self.assertEqual(consumos[0]['quantidade'], 2)
        self.assertIn('peca', consumos[0])
        self.assertEqual(consumos[0]['peca'], peca.nome)


# ---------------------------------------------------------------------------
# Testes de integração para endpoints de transição de status
# ---------------------------------------------------------------------------

class TransicaoStatusAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = criar_usuario(username='tecnico_api_trans')
        self.client.force_authenticate(user=self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='73.834.979/0001-09')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='TRS2B22')
        self.os = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=self.user
        )

    def _os_em(self, status_alvo):
        OrdemServico.objects.filter(pk=self.os.pk).update(status=status_alvo)
        self.os.refresh_from_db()

    def test_iniciar_diagnostico_retorna_200_e_status_correto(self):
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/iniciar-diagnostico/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'DIAGNOSTICO')

    def test_iniciar_diagnostico_status_invalido_retorna_400(self):
        self._os_em('DIAGNOSTICO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/iniciar-diagnostico/'
        )
        self.assertEqual(response.status_code, 400)

    def test_finalizar_diagnostico_retorna_200_e_status_correto(self):
        self._os_em('DIAGNOSTICO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/finalizar-diagnostico/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'AGUARDANDO')

    def test_aprovar_orcamento_retorna_200_e_status_correto(self):
        self._os_em('AGUARDANDO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/aprovar-orcamento/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'EXECUCAO')

    def test_recusar_orcamento_retorna_200_e_volta_para_diagnostico(self):
        self._os_em('AGUARDANDO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/recusar-orcamento/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'DIAGNOSTICO')

    def test_finalizar_retorna_200_e_status_correto(self):
        self._os_em('EXECUCAO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/finalizar/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'FINALIZADA')

    def test_finalizar_com_servico_pendente_retorna_400(self):
        self._os_em('EXECUCAO')
        servico = criar_servico(usuario=self.user)
        ItemServicoOS.objects.create(
            ordem_servico=self.os, servico=servico, created_by=self.user
        )
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/finalizar/'
        )
        self.assertEqual(response.status_code, 400)

    def test_entregar_retorna_200_e_status_correto(self):
        self._os_em('FINALIZADA')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/entregar/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ENTREGUE')

    def test_cancelar_retorna_200_e_status_correto(self):
        self._os_em('AGUARDANDO')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/cancelar/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'CANCELADA')

    def test_cancelar_status_invalido_retorna_400(self):
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/cancelar/'
        )
        self.assertEqual(response.status_code, 400)

    def test_acao_exige_autenticacao(self):
        anonimo = APIClient()
        response = anonimo.post(
            f'/api/v1/ordens-servico/{self.os.id}/iniciar-diagnostico/'
        )
        self.assertEqual(response.status_code, 401)

    def test_acao_em_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro_trans')
        os_outro = OrdemServico.objects.create(
            cliente=self.cliente, veiculo=self.veiculo, created_by=outro
        )
        response = self.client.post(
            f'/api/v1/ordens-servico/{os_outro.id}/iniciar-diagnostico/'
        )
        self.assertEqual(response.status_code, 404)

    def test_fluxo_completo_happy_path(self):
        self.client.post(f'/api/v1/ordens-servico/{self.os.id}/iniciar-diagnostico/')
        self.client.post(f'/api/v1/ordens-servico/{self.os.id}/finalizar-diagnostico/')
        self.client.post(f'/api/v1/ordens-servico/{self.os.id}/aprovar-orcamento/')
        self.client.post(f'/api/v1/ordens-servico/{self.os.id}/finalizar/')
        response = self.client.post(
            f'/api/v1/ordens-servico/{self.os.id}/entregar/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ENTREGUE')
