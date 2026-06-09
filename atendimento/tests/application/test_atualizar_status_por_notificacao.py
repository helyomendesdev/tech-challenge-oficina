from atendimento.tests.phase2_helpers import *


class AtualizarStatusPorNotificacaoUseCaseFlowTest(Phase2TestBase):

    def test_status_notificacao_transicao_valida_funciona(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.RECEBIDA.value)

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "DIAGNOSTICO",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.DIAGNOSTICO.value)

    def test_status_notificacao_transicao_invalida_falha(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.RECEBIDA.value)

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "EXECUCAO",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.RECEBIDA.value)

    def test_status_notificacao_nao_sai_de_estado_final(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.ENTREGUE.value)

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "DIAGNOSTICO",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.ENTREGUE.value)

    def test_status_notificacao_nao_finaliza_com_servico_pendente(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.EXECUCAO.value)
        servico = self.criar_servico(self.usuario)
        create_item_servico_os(
            ordem_servico,
            servico,
            usuario=self.usuario,
            status=StatusItemServico.PENDENTE.value,
        )

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "FINALIZADA",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.EXECUCAO.value)

    def test_status_notificacao_nao_finaliza_com_peca_nao_utilizada(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.EXECUCAO.value)
        servico = self.criar_servico(self.usuario)
        peca = self.criar_peca(self.usuario, estoque=3)
        create_item_servico_os(
            ordem_servico,
            servico,
            usuario=self.usuario,
            status=StatusItemServico.CONCLUIDO.value,
        )
        create_item_peca_os(
            ordem_servico,
            peca,
            usuario=self.usuario,
            quantidade=1,
            quantidade_utilizada=0,
        )

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "FINALIZADA",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.EXECUCAO.value)

    def test_status_notificacao_finaliza_quando_gates_estao_ok(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.EXECUCAO.value)
        servico = self.criar_servico(self.usuario)
        create_item_servico_os(
            ordem_servico,
            servico,
            usuario=self.usuario,
            status=StatusItemServico.CONCLUIDO.value,
        )

        response = self.api(self.usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "FINALIZADA",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.FINALIZADA.value)
        self.assertIsNotNone(ordem_servico.data_finalizacao)

    def test_status_notificacao_outro_usuario_nao_altera(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.RECEBIDA.value)

        response = self.api(self.outro_usuario).post(
            self.STATUS_NOTIFICACOES_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "novo_status": "DIAGNOSTICO",
                "origem": "painel-externo",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.RECEBIDA.value)
