from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # O monitor/scheduler não é mais iniciado implicitamente.
        # Cada serviço roda em seu próprio processo/container, via
        # `manage.py run_collector`, `run_experiments` etc.
        from core import signals  # noqa: F401
