"""
Signals para auditoria automática LGPD.
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone

from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese
from lgpd.models import AuditoriaAcesso


@receiver(post_save, sender=Cidadao)
def auditar_cidadao_modificado(sender, instance, created, **kwargs):
    """Audita quando um cidadão é criado ou modificado."""
    
    # TODO: Obter usuário atual do request
    # Por enquanto, vamos usar None para modificações automáticas
    
    tipo_acao = 'ACESSO_DADOS' if created else 'MODIFICACAO_DADOS'
    
    try:
        AuditoriaAcesso.objects.create(
            usuario=None,  # Seria obtido do request atual
            cidadao=instance,
            tipo_acao=tipo_acao,
            detalhes={
                'modelo': 'Cidadao',
                'criado': created,
                'timestamp': timezone.now().isoformat()
            },
            ip_address='127.0.0.1',  # Seria obtido do request atual
        )
    except Exception as e:
        # Log error but don't break the save
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar auditoria LGPD: {e}")


@receiver(post_save, sender=DadosSaude)
def auditar_dados_saude_modificados(sender, instance, created, **kwargs):
    """Audita quando dados de saúde são criados ou modificados."""
    
    tipo_acao = 'ACESSO_DADOS' if created else 'MODIFICACAO_DADOS'
    
    try:
        AuditoriaAcesso.objects.create(
            usuario=getattr(instance, 'agente_coleta', None),
            cidadao=instance.cidadao,
            tipo_acao=tipo_acao,
            detalhes={
                'modelo': 'DadosSaude',
                'criado': created,
                'timestamp': timezone.now().isoformat()
            },
            ip_address='127.0.0.1',
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar auditoria LGPD para DadosSaude: {e}")


@receiver(post_save, sender=Anamnese)
def auditar_anamnese_modificada(sender, instance, created, **kwargs):
    """Audita quando anamnese é criada ou modificada."""
    
    tipo_acao = 'ACESSO_DADOS' if created else 'MODIFICACAO_DADOS'
    
    try:
        AuditoriaAcesso.objects.create(
            usuario=getattr(instance, 'revisado_por', None),
            cidadao=instance.cidadao,
            tipo_acao=tipo_acao,
            detalhes={
                'modelo': 'Anamnese',
                'criado': created,
                'status': instance.status,
                'timestamp': timezone.now().isoformat()
            },
            ip_address='127.0.0.1',
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar auditoria LGPD para Anamnese: {e}")


@receiver(post_delete, sender=Cidadao)
def auditar_cidadao_excluido(sender, instance, **kwargs):
    """Audita quando um cidadão é excluído."""
    
    try:
        AuditoriaAcesso.objects.create(
            usuario=None,  # Seria obtido do request atual
            cidadao=instance,
            tipo_acao='EXCLUSAO_DADOS',
            detalhes={
                'modelo': 'Cidadao',
                'nome_anonimizado': instance.nome,
                'timestamp': timezone.now().isoformat()
            },
            ip_address='127.0.0.1',
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar auditoria LGPD para exclusão: {e}")


# Middleware personalizado seria melhor para capturar dados do request
# Essa é uma implementação básica para demonstração