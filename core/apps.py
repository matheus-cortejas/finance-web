from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from core import signals  # noqa: F401
        from core.startup import start_background_monitor, start_background_scheduler

        start_background_monitor()
        start_background_scheduler()
