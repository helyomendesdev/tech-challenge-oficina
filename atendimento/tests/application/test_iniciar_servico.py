from atendimento.tests.helpers import *
class IniciarServicoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(username='tecnico4')
        self.cliente = criar_cliente(usuario=self.usuario, documento='67.501.780/0001-96')
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario, placa='GTI2E29')
        self.servico = criar_servico(usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario, estoque_atual=10)
        self.os = criar_ordem_servico(
            self.cliente, self.veiculo, usuario=self.usuario, status='EXECUCAO'
        )
        self.item_peca = criar_item_peca_os(
            self.os, self.peca, usuario=self.usuario, quantidade=5
        )
        self.item = criar_item_servico_os(self.os, self.servico, self.usuario)
        self.client = api_client_for_user(self.usuario)
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

    def test_iniciar_servico_bloqueado_se_os_nao_esta_em_execucao(self):
        OrdemServico.objects.filter(pk=self.os.pk).update(status='RECEBIDA')

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'PENDENTE')

    def test_iniciar_com_pecas_registra_consumo(self):
        self.peca.refresh_from_db()
        estoque_apos_reserva = self.peca.estoque_atual
        payload = {'pecas': [{'item_peca_os_id': self.item_peca.pk, 'quantidade': 3}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.item_peca.refresh_from_db()
        self.peca.refresh_from_db()
        self.assertEqual(self.item_peca.quantidade_utilizada, 3)
        self.assertEqual(self.peca.estoque_atual, estoque_apos_reserva)
        self.assertEqual(ConsumoItemServico.objects.filter(item_servico_os=self.item).count(), 1)

    def test_iniciar_com_peca_repetida_agrupa_consumo_sem_baixar_estoque(self):
        self.peca.refresh_from_db()
        estoque_apos_reserva = self.peca.estoque_atual
        payload = {
            'pecas': [
                {'item_peca_os_id': self.item_peca.pk, 'quantidade': 2},
                {'item_peca_os_id': self.item_peca.pk, 'quantidade': 3},
            ]
        }

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.item_peca.refresh_from_db()
        self.peca.refresh_from_db()
        consumo = ConsumoItemServico.objects.get(item_servico_os=self.item)
        self.assertEqual(consumo.quantidade, 5)
        self.assertEqual(self.item_peca.quantidade_utilizada, 5)
        self.assertEqual(self.peca.estoque_atual, estoque_apos_reserva)

    def test_iniciar_com_quantidade_acima_do_disponivel_retorna_400(self):
        # Partially consume so disponivel=2, then request 3 (>2 but <=5)
        ItemPecaOS.objects.filter(pk=self.item_peca.pk).update(quantidade_utilizada=3)
        self.item_peca.refresh_from_db()
        payload = {'pecas': [{'item_peca_os_id': self.item_peca.pk, 'quantidade': 3}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Quantidade indispon', response.data['mensagem'])

    def test_iniciar_com_quantidade_acima_do_disponivel_nao_cria_consumo(self):
        ItemPecaOS.objects.filter(pk=self.item_peca.pk).update(quantidade_utilizada=3)
        payload = {'pecas': [{'item_peca_os_id': self.item_peca.pk, 'quantidade': 3}]}

        response = self.client.post(self.url, payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.item_peca.refresh_from_db()
        self.assertEqual(self.item_peca.quantidade_utilizada, 3)
        self.assertEqual(ConsumoItemServico.objects.filter(item_servico_os=self.item).count(), 0)

    def test_repository_nao_deixa_quantidade_utilizada_ultrapassar_reserva(self):
        from atendimento.domain.exceptions import QuantidadeIndisponivelError
        from atendimento.infrastructure.repositories.django_ordem_servico_repository import (
            DjangoOrdemServicoRepository,
        )

        ItemPecaOS.objects.filter(pk=self.item_peca.pk).update(quantidade_utilizada=4)
        self.item_peca.refresh_from_db()

        with self.assertRaises(QuantidadeIndisponivelError):
            DjangoOrdemServicoRepository().atualizar_quantidade_utilizada_item_peca(
                self.item_peca,
                2,
            )

        self.item_peca.refresh_from_db()
        self.assertEqual(self.item_peca.quantidade_utilizada, 4)

    def test_iniciar_peca_de_outra_os_retorna_400(self):
        outra_os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.usuario)
        peca_outra = criar_peca(usuario=self.usuario, estoque_atual=5)
        item_outra = criar_item_peca_os(
            outra_os, peca_outra, usuario=self.usuario, quantidade=3
        )
        payload = {'pecas': [{'item_peca_os_id': item_outra.pk, 'quantidade': 1}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('pertence', response.data['mensagem'])

    def test_iniciar_servico_ja_iniciado_retorna_400(self):
        self.item.status = 'EM_EXECUCAO'
        self.item.data_inicio = timezone.now()
        self.item.save()
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_iniciar_servico_ja_concluido_retorna_400(self):
        self.item.status = 'CONCLUIDO'
        self.item.data_inicio = timezone.now()
        self.item.data_finalizacao = timezone.now()
        self.item.save()

        response = self.client.post(self.url, {}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_iniciar_em_os_de_outro_usuario_retorna_404(self):
        outro = criar_usuario(username='outro4')
        os_outro = criar_ordem_servico(self.cliente, self.veiculo, usuario=outro)
        item_outro = criar_item_servico_os(os_outro, self.servico, outro)
        url = f'/api/v1/ordens-servico/{os_outro.pk}/servicos/{item_outro.pk}/iniciar/'
        response = self.client.post(url, {}, format='json')
        self.assertEqual(response.status_code, 404)


# ---------------------------------------------------------------------------
# Testes da action finalizar em ItemServicoOS
# ---------------------------------------------------------------------------
