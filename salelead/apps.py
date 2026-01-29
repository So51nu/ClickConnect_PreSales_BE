# salelead/apps.py
from django.apps import AppConfig

class SaleleadConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "salelead"

    def ready(self):
        import salelead.signals  # noqa
