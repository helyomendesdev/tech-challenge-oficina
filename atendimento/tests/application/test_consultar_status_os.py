from atendimento.tests.phase2_helpers import *


class ConsultarStatusOrdemServicoUseCaseFlowTest(Phase2TestBase):

    def test_consulta_status_respeita_dono_outro_usuario_e_staff(self):
        ordem_servico = self.criar_os(usuario=self.usuario)

        response_dono = self.api(self.usuario).get(self.status_url(ordem_servico))
        response_outro = self.api(self.outro_usuario).get(self.status_url(ordem_servico))
        response_staff = self.api(self.staff).get(self.status_url(ordem_servico))

        self.assertEqual(response_dono.status_code, status.HTTP_200_OK)
        self.assertEqual(response_dono.data["status"], StatusOrdemServico.RECEBIDA.value)
        self.assertEqual(response_outro.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response_staff.status_code, status.HTTP_200_OK)
