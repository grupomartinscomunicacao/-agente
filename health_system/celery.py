"""
Configuração do Celery para processamento assíncrono.
"""
import os
from celery import Celery
from django.conf import settings

# Configuração do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')

# Instância do Celery
app = Celery('health_system')

# Configuração usando settings do Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscovery de tasks
app.autodiscover_tasks()

# Configurações adicionais
app.conf.update(
    # Formato de serialização
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Timezone
    timezone=settings.TIME_ZONE,
    enable_utc=True,
    
    # Configurações de retry
    task_soft_time_limit=300,  # 5 minutos
    task_time_limit=600,       # 10 minutos
    
    # Configurações de roteamento
    task_routes={
        'ai_integracao.tasks.gerar_anamnese': {'queue': 'anamnese'},
        'ai_integracao.tasks.processar_triagem': {'queue': 'triagem'},
        'dashboard.tasks.gerar_relatorio': {'queue': 'relatorios'},
    },
    
    # Configurações de worker
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # Configurações de resultado
    result_expires=3600,  # 1 hora
)