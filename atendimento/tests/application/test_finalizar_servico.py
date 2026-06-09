from atendimento.tests.helpers import *
class FinalizarServicoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico5')
        self.cliente = criar_cliente(usuario=self.usuario, documento='77.411.263/0001-08')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E30')
        self.servico = criar_servico(usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario, estoque_atual=10)
        self.os = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.usuario, status='EXECUCAO'
        )
        self.item_peca = criar_item_peca_os(
            self.os, self.peca, usuario=self.usuario, quantidade=5
        )
        self.item = criar_item_servico_os(
            self.os,
            self.servico,
            self.usuario,
            status='EM_EXECUCAO',
            data_inicio=timezone.now(),
        )
        self.client = api_client_for_user(self.usuario)
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
        import datetime

        inicio = datetime.datetime(
            2026, 5, 1, 14, 0, 0, tzinfo=datetime.timezone.utc
        )
        ItemServicoOS.objects.filter(pk=self.item.pk).update(data_inicio=inicio)
        self._usar_todas_as_pecas()
        data = '2026-05-01T15:00:00Z'
        response = self.client.post(self.url, {'data_finalizacao': data}, format='json')
        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(
            self.item.data_finalizacao.strftime('%Y-%m-%dT%H:%M:%SZ'), data
        )

    def test_finalizar_rejeita_data_anterior_ao_inicio(self):
        import datetime

        inicio = datetime.datetime(
            2026, 5, 1, 15, 0, 0, tzinfo=datetime.timezone.utc
        )
        ItemServicoOS.objects.filter(pk=self.item.pk).update(data_inicio=inicio)
        self._usar_todas_as_pecas()

        response = self.client.post(
            self.url,
            {'data_finalizacao': '2026-05-01T14:00:00Z'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'EM_EXECUCAO')
        self.assertIsNone(self.item.data_finalizacao)

    def test_finalizar_calcula_tempo_execucao_apos_finalizar(self):
        import datetime

        inicio = timezone.now() - datetime.timedelta(minutes=75)
        ItemServicoOS.objects.filter(pk=self.item.pk).update(data_inicio=inicio)
        self._usar_todas_as_pecas()

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertGreaterEqual(self.item.tempo_execucao_minutos, 74)
        self.assertLessEqual(self.item.tempo_execucao_minutos, 76)

    def test_finalizar_ultimo_servico_transita_os_para_finalizada(self):
        self._usar_todas_as_pecas()
        self.client.post(self.url, {}, format='json')
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'FINALIZADA')
        self.assertIsNotNone(self.os.data_finalizacao)

    def test_finalizar_bloqueado_se_pecas_nao_utilizadas(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('pecas nao utilizadas', response.data['mensagem'])

    def test_finalizar_nao_transita_os_se_ainda_ha_servico_ativo(self):
        self._usar_todas_as_pecas()
        servico2 = criar_servico(usuario=self.usuario)
        criar_item_servico_os(
            self.os,
            servico2,
            self.usuario,
            status='EM_EXECUCAO',
            data_inicio=timezone.now(),
        )
        self.client.post(self.url, {}, format='json')
        self.os.refresh_from_db()
        self.assertEqual(self.os.status, 'EXECUCAO')

    def test_finalizar_servico_pendente_retorna_400(self):
        servico_pendente = criar_servico(usuario=self.usuario)
        item_pendente = criar_item_servico_os(self.os, servico_pendente, self.usuario)
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item_pendente.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_finalizar_servico_em_execucao_sem_inicio_retorna_400(self):
        servico_sem_inicio = criar_servico(usuario=self.usuario)
        item_sem_inicio = criar_item_servico_os(
            self.os,
            servico_sem_inicio,
            self.usuario,
            status='EM_EXECUCAO',
        )
        url = f'/api/v1/ordens-servico/{self.os.pk}/servicos/{item_sem_inicio.pk}/finalizar/'

        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, 400)
        item_sem_inicio.refresh_from_db()
        self.assertEqual(item_sem_inicio.status, 'EM_EXECUCAO')
        self.assertIsNone(item_sem_inicio.data_finalizacao)

    def test_finalizar_servico_bloqueado_se_os_nao_esta_em_execucao(self):
        self._usar_todas_as_pecas()
        OrdemServico.objects.filter(pk=self.os.pk).update(status='RECEBIDA')

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(self.item.status, 'EM_EXECUCAO')
        self.assertEqual(self.os.status, 'RECEBIDA')

    def test_os_sem_itens_pecas_finaliza_normalmente(self):
        os_sem_pecas = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.usuario, status='EXECUCAO'
        )
        item = criar_item_servico_os(
            os_sem_pecas,
            self.servico,
            self.usuario,
            status='EM_EXECUCAO',
            data_inicio=timezone.now(),
        )
        url = f'/api/v1/ordens-servico/{os_sem_pecas.pk}/servicos/{item.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        os_sem_pecas.refresh_from_db()
        self.assertEqual(os_sem_pecas.status, 'FINALIZADA')

    def test_finalizar_em_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro5')
        os_outro = criar_ordem_servico(self.cliente, self.veiculo, usuario=outro)
        servico2 = criar_servico(usuario=outro)
        item_outro = criar_item_servico_os(
            os_outro,
            servico2,
            outro,
            status='EM_EXECUCAO',
            data_inicio=timezone.now(),
        )
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item_outro.pk}/finalizar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action metricas em OrdemServicoViewSet
# ---------------------------------------------------------------------------
