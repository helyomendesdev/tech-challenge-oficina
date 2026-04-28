from django.apps import AppConfig


class AtendimentoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'atendimento'

    def ready(self):
        import atendimento.signals  # noqa: F401  # Isso ativa o gatilho!
