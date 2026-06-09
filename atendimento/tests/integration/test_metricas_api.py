from atendimento.tests.helpers import *
class MetricasServicoTest(TestCase):
    def setUp(self):
        from django.utils import timezone
        import datetime
        self.usuario = criar_usuario(username='tecnico6')
        self.cliente = criar_cliente(usuario=self.usuario, documento='01.339.513/0001-08')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E31')
        self.servico1 = criar_servico(usuario=self.usuario, descricao='Troca de Óleo')
        self.servico2 = criar_servico(usuario=self.usuario, descricao='Alinhamento')
        self.os = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.usuario, status='EXECUCAO'
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
        self.client = api_client_for_user(self.usuario)
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
        os_outro = criar_ordem_servico(self.cliente, self.veiculo, usuario=outro)
        url = f'/api/v1/ordens-servico/{os_outro.pk}/metricas/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_metricas_inclui_pecas_consumidas(self):
        peca = criar_peca(usuario=self.usuario, estoque_atual=5)
        item_peca = criar_item_peca_os(self.os, peca, usuario=self.usuario, quantidade=3)
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
