from atendimento.tests.phase2_helpers import *


class ProcessarRespostaOrcamentoUseCaseFlowTest(Phase2TestBase):

    def test_orcamento_aprovado_altera_aguardando_para_execucao(self):
        ordem_servico = self.criar_os(
            self.usuario,
            StatusOrdemServico.AGUARDANDO.value,
        )

        response = self.api(self.usuario).post(
            self.ORCAMENTO_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "decisao": "APROVADO",
                "origem": "email",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.EXECUCAO.value)
        self.assertIsNotNone(ordem_servico.data_inicio_execucao)

    def test_orcamento_recusado_altera_aguardando_para_diagnostico(self):
        ordem_servico = self.criar_os(
            self.usuario,
            StatusOrdemServico.AGUARDANDO.value,
        )

        response = self.api(self.usuario).post(
            self.ORCAMENTO_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "decisao": "RECUSADO",
                "origem": "email",
                "motivo": "Cliente solicitou novo diagnostico.",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.DIAGNOSTICO.value)

    def test_orcamento_falha_se_status_nao_for_aguardando(self):
        ordem_servico = self.criar_os(self.usuario, StatusOrdemServico.RECEBIDA.value)

        response = self.api(self.usuario).post(
            self.ORCAMENTO_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "decisao": "APROVADO",
                "origem": "email",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.RECEBIDA.value)

    def test_orcamento_outro_usuario_nao_altera(self):
        ordem_servico = self.criar_os(
            self.usuario,
            StatusOrdemServico.AGUARDANDO.value,
        )

        response = self.api(self.outro_usuario).post(
            self.ORCAMENTO_URL,
            {
                "ordem_servico_id": ordem_servico.id,
                "decisao": "APROVADO",
                "origem": "email",
            },
            format="json",
        )

        ordem_servico.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ordem_servico.status, StatusOrdemServico.AGUARDANDO.value)
