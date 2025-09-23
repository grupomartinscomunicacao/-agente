from django.apps import AppConfig


class GeolocationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "geolocation"
    
    def ready(self):
        """Importar signals quando a aplicação estiver pronta."""
        import geolocation.signals
