from atendimento.tests.helpers import *
class OrdemServicoModelTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.cliente = criar_cliente(usuario=self.usuario)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.usuario)
        self.peca = criar_peca(usuario=self.usuario)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.usuario)

    def test_calculo_total_com_peca(self):
        criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=1)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 90.00)

    def test_calculo_total_com_multiplas_pecas(self):
        criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=2)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 180.00)

    def test_calculo_total_com_servico(self):
        servico = criar_servico(usuario=self.usuario)
        criar_item_servico_os(self.os, servico, self.usuario)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 150.00)

    def test_calculo_total_peca_e_servico(self):
        servico = criar_servico(usuario=self.usuario)
        criar_item_servico_os(self.os, servico, self.usuario)
        criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=1)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 240.00)

    def test_baixa_estoque_automatica(self):
        criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=3)
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 7)

    def test_devolucao_estoque_ao_remover_peca(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=3)
        item.delete()
        self.peca.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 10)

    def test_aumentar_quantidade_baixa_apenas_diferenca(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=3)

        item.quantidade = 5
        item.save()

        self.peca.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 5)
        self.assertEqual(float(self.os.valor_total), 450.00)

    def test_diminuir_quantidade_devolve_apenas_diferenca(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=5)

        item.quantidade = 2
        item.save()

        self.peca.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 8)
        self.assertEqual(float(self.os.valor_total), 180.00)

    def test_quantidade_utilizada_nao_pode_superar_quantidade_reservada(self):
        from django.core.exceptions import ValidationError

        item = criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=2)
        item.quantidade_utilizada = 3

        with self.assertRaises(ValidationError):
            item.save()

    def test_trocar_peca_devolve_antiga_e_baixa_nova(self):
        peca_nova = criar_peca(
            usuario=self.usuario,
            nome='Filtro de Oleo',
            valor_unitario=50.00,
            estoque_atual=4,
        )
        item = criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=3)

        item.peca = peca_nova
        item.quantidade = 2
        item.save()

        self.peca.refresh_from_db()
        peca_nova.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 10)
        self.assertEqual(peca_nova.estoque_atual, 2)
        self.assertEqual(float(self.os.valor_total), 100.00)

    def test_estoque_insuficiente_levanta_erro(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            criar_item_peca_os(self.os, self.peca, usuario=self.usuario, quantidade=999)

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

class ItemPecaOSAPITest(TestCase):
    def setUp(self):
        self.user = criar_usuario('tecnico_item')
        self.client = api_client_for_user(self.user)
        self.cliente = criar_cliente(usuario=self.user)
        self.veiculo = criar_veiculo(self.cliente, usuario=self.user)
        self.os = criar_ordem_servico(self.cliente, self.veiculo, usuario=self.user)
        self.peca = criar_peca(usuario=self.user, estoque_atual=10)

    def test_adicionar_peca_estoque_insuficiente(self):
        payload = {'os': self.os.id, 'peca': self.peca.id, 'quantidade': 11}
        response = self.client.post('/api/v1/itens-pecas/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_adicionar_peca_recalcula_total_os(self):
        payload = {'os': self.os.id, 'peca': self.peca.id, 'quantidade': 2}

        response = self.client.post('/api/v1/itens-pecas/', payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 180.00)

    def test_remover_peca_recalcula_total_os(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.user, quantidade=2)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 180.00)

        response = self.client.delete(f'/api/v1/itens-pecas/{item.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.os.refresh_from_db()
        self.assertEqual(float(self.os.valor_total), 0.00)

    def test_atualizar_peca_estoque_insuficiente(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.user, quantidade=5)
        self.peca.refresh_from_db()
        payload = {'quantidade': 15}
        response = self.client.patch(f'/api/v1/itens-pecas/{item.id}/', payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_quantidade_menor_que_utilizada_retorna_400(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.user, quantidade=5)
        ItemPecaOS.objects.filter(pk=item.pk).update(quantidade_utilizada=3)

        response = self.client.patch(
            f'/api/v1/itens-pecas/{item.id}/',
            {'quantidade': 2},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_atualizar_quantidade_devolve_estoque_e_recalcula_total(self):
        item = criar_item_peca_os(self.os, self.peca, usuario=self.user, quantidade=5)

        response = self.client.patch(
            f'/api/v1/itens-pecas/{item.id}/',
            {'quantidade': 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.peca.refresh_from_db()
        self.os.refresh_from_db()
        self.assertEqual(self.peca.estoque_atual, 8)
        self.assertEqual(float(self.os.valor_total), 180.00)
