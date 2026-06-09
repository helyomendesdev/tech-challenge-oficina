from atendimento.tests.helpers import *
class OrdemServicoTransicaoTest(TestCase):
    """Testa os métodos de transição de estado do modelo OrdemServico."""

    def setUp(self):
        self.usuario = criar_usuario(username='tecnico_trans')
        self.cliente = criar_cliente(usuario=self.usuario, documento='49.648.573/0001-22')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='TRS1A11')
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.usuario)

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
        criar_item_servico_os(self.os, servico, self.usuario)
        with self.assertRaises(ValidationError):
            self.os.finalizar()

    def test_finalizar_com_peca_nao_utilizada_levanta_erro(self):
        from django.core.exceptions import ValidationError
        self._os_em('EXECUCAO')
        peca = criar_peca(usuario=self.usuario, estoque_atual=5)
        criar_item_peca_os(
            self.os,
            peca,
            usuario=self.usuario,
            quantidade=2,
            quantidade_utilizada=1,
        )
        with self.assertRaises(ValidationError):
            self.os.finalizar()

    def test_repository_save_nao_finaliza_com_servico_pendente(self):
        from atendimento.domain.exceptions import RegraFinalizacaoOrdemServicoError
        from atendimento.infrastructure.repositories.django_ordem_servico_repository import (
            DjangoOrdemServicoRepository,
        )

        self._os_em('EXECUCAO')
        servico = criar_servico(usuario=self.usuario)
        criar_item_servico_os(self.os, servico, self.usuario)
        self.os.status = 'FINALIZADA'

        with self.assertRaises(RegraFinalizacaoOrdemServicoError):
            DjangoOrdemServicoRepository().save(self.os)

        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'EXECUCAO')
        self.assertIsNone(self.os.data_finalizacao)

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

class OrdemServicoAPITest(TestCase):
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

class OrdemServicoCRUDAdministrativoFase1Test(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_crud')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='153.509.460-56')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='CRD1A11')

    def test_ordem_servico_crud_legado(self):
        create = self.client.post(
            '/api/v1/ordens-servico/',
            {'cliente': self.cliente.id, 'veiculo': self.veiculo.id},
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ordem_id = create.data['id']

        list_response = self.client.get('/api/v1/ordens-servico/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        detail = self.client.get(f'/api/v1/ordens-servico/{ordem_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        update = self.client.patch(
            f'/api/v1/ordens-servico/{ordem_id}/',
            {'veiculo': self.veiculo.id},
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)

        delete = self.client.delete(f'/api/v1/ordens-servico/{ordem_id}/')
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Testes de Filtros (django-filter)
# ---------------------------------------------------------------------------

class FiltroOrdemServicoTest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico')
        self.client = api_client_for_user(self.user)

        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)

        self.os_recebida = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.user, status='RECEBIDA'
        )
        self.os_execucao = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.user, status='EXECUCAO'
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
        response = self.client.get('/api/v1/clientes/', {'search': 'helio'})
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

class ItemServicoOSModelTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico2')
        self.cliente = criar_cliente(usuario=self.usuario, documento='12.340.546/0001-50')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E27')
        self.servico = criar_servico(usuario=self.usuario)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.usuario)

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
        item_peca = criar_item_peca_os(self.os, peca, usuario=self.usuario, quantidade=5)
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
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.usuario)
        self.client = api_client_for_user(self.usuario)
        self.url_list = f'/api/v1/ordens-servico/{self.os.pk}/servicos/'

    def test_adicionar_servico_a_os(self):
        response = self.client.post(self.url_list, {'servico': self.servico.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'PENDENTE')
        self.assertIsNone(response.data['data_inicio'])
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

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
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(ItemServicoOS.objects.filter(pk=item.pk).exists())
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 0.00)

    def test_nao_remover_servico_em_execucao(self):
        item = criar_item_servico_os(self.os, self.servico, self.usuario, status='EM_EXECUCAO')
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(ItemServicoOS.objects.filter(pk=item.pk).exists())

    def test_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro3')
        os_outro = criar_ordem_servico(self.cliente, self.veiculo, usuario=outro)
        item = criar_item_servico_os(os_outro, self.servico, outro)
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item.pk}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action iniciar em ItemServicoOS
# ---------------------------------------------------------------------------

class TransicaoStatusAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario(username='tecnico_api_trans')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user, documento='73.834.979/0001-09')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user, placa='TRS2B22')
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)

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
        criar_item_servico_os(self.os, servico, self.user)
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
        os_outro = criar_ordem_servico(self.cliente, self.veiculo, usuario=outro)
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
