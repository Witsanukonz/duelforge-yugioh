from django.apps import AppConfig


class BanlistsConfig(AppConfig):
    name = 'banlists'

    def ready(self):
        from . import signals  # noqa: F401
