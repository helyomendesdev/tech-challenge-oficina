from atendimento.tests.phase2_helpers import *


class ListarFilaOrdensServicoUseCaseFlowTest(Phase2TestBase):

    def test_fila_operacional_ordena_por_status_data_e_exclui_finais(self):
        base = timezone.now() - timedelta(days=1)
        recebida_antiga = self.criar_os(
            self.usuario,
            StatusOrdemServico.RECEBIDA.value,
            documento="52998224725",
            placa="AAA1A11",
        )
        recebida_nova = self.criar_os(
            self.usuario,
            StatusOrdemServico.RECEBIDA.value,
            documento="11144477735",
            placa="BBB1B11",
        )
        diagnostico = self.criar_os(
            self.usuario,
            StatusOrdemServico.DIAGNOSTICO.value,
            documento="93541134780",
            placa="CCC1C11",
        )
        aguardando = self.criar_os(
            self.usuario,
            StatusOrdemServico.AGUARDANDO.value,
            documento="06325152706",
            placa="DDD1D11",
        )
        execucao = self.criar_os(
            self.usuario,
            StatusOrdemServico.EXECUCAO.value,
            documento="98765432100",
            placa="EEE1E11",
        )
        for index, status_os in enumerate(
            [
                StatusOrdemServico.FINALIZADA.value,
                StatusOrdemServico.ENTREGUE.value,
                StatusOrdemServico.CANCELADA.value,
            ]
        ):
            self.criar_os(
                self.usuario,
                status_os,
                documento=f"0000000000{index}",
                placa=f"ZZZ1Z1{index}",
            )

        self.definir_data_abertura(execucao, base + timedelta(minutes=50))
        self.definir_data_abertura(aguardando, base + timedelta(minutes=40))
        self.definir_data_abertura(diagnostico, base + timedelta(minutes=30))
        self.definir_data_abertura(recebida_antiga, base + timedelta(minutes=10))
        self.definir_data_abertura(recebida_nova, base + timedelta(minutes=20))

        response = self.api(self.usuario).get(self.FILA_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["ordem_servico_id"] for item in response.data],
            [
                execucao.id,
                aguardando.id,
                diagnostico.id,
                recebida_antiga.id,
                recebida_nova.id,
            ],
        )

    def test_fila_operacional_usuario_comum_ve_suas_os_e_staff_ve_todas(self):
        os_usuario = self.criar_os(
            self.usuario,
            StatusOrdemServico.EXECUCAO.value,
            documento="52998224725",
            placa="AAA1A11",
        )
        os_outro = self.criar_os(
            self.outro_usuario,
            StatusOrdemServico.EXECUCAO.value,
            documento="11144477735",
            placa="BBB1B11",
        )

        response_usuario = self.api(self.usuario).get(self.FILA_URL)
        response_staff = self.api(self.staff).get(self.FILA_URL)

        ids_usuario = {item["ordem_servico_id"] for item in response_usuario.data}
        ids_staff = {item["ordem_servico_id"] for item in response_staff.data}
        self.assertEqual(response_usuario.status_code, status.HTTP_200_OK)
        self.assertEqual(ids_usuario, {os_usuario.id})
        self.assertEqual(response_staff.status_code, status.HTTP_200_OK)
        self.assertIn(os_usuario.id, ids_staff)
        self.assertIn(os_outro.id, ids_staff)
