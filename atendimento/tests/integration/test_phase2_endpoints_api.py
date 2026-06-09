from atendimento.tests.phase2_helpers import *


class Phase2EndpointAccessTest(Phase2TestBase):
    def test_endpoints_novos_superuser_acessa_os_de_qualquer_usuario(self):
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

        response_status = self.api(self.superuser).get(self.status_url(os_outro))
        response_fila = self.api(self.superuser).get(self.FILA_URL)

        ids_fila = {item["ordem_servico_id"] for item in response_fila.data}
        self.assertEqual(response_status.status_code, status.HTTP_200_OK)
        self.assertEqual(response_status.data["ordem_servico_id"], os_outro.id)
        self.assertEqual(response_fila.status_code, status.HTTP_200_OK)
        self.assertIn(os_usuario.id, ids_fila)
        self.assertIn(os_outro.id, ids_fila)
