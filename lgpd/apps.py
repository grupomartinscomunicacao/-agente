"""
Configuração da app LGPD.
"""
from django.apps import AppConfig


class LgpdConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lgpd'
    verbose_name = 'Conformidade LGPD'
    
    def ready(self):
        """Configurações quando a app estiver pronta."""
        import lgpd.signals