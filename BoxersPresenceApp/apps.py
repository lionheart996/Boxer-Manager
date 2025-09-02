from django.apps import AppConfig

class BoxersPresenceAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "BoxersPresenceApp"

    def ready(self):
        from . import signals  # noqa
