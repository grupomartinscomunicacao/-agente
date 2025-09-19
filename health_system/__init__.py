# Garante que o Celery seja importado quando Django inicializar
from .celery import app as celery_app

__all__ = ('celery_app',)