from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class TestClienteAtivoMigration(TransactionTestCase):
    migrate_from = [("atendimento", "0007_add_data_ultima_transicao")]
    migrate_to = [("atendimento", "0008_cliente_ativo")]

    def setUp(self):
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)

        old_apps = self.executor.loader.project_state(self.migrate_from).apps
        Cliente = old_apps.get_model("atendimento", "Cliente")
        Cliente.objects.create(
            nome="Cliente Legado",
            documento="11222333000181",
            email="legado@teste.com",
            telefone="11999999999",
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)
        self.apps = self.executor.loader.project_state(self.migrate_to).apps

    def test_registros_existentes_recebem_ativo_true(self):
        Cliente = self.apps.get_model("atendimento", "Cliente")

        cliente = Cliente.objects.get(documento="11222333000181")

        self.assertIs(cliente.ativo, True)
