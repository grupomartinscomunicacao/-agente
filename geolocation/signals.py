"""
Signals para automatizar processos de geolocalização
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from cidadaos.models import Cidadao
from anamneses.models import Anamnese
from .models import LocalizacaoSaude
from .geocodificacao_service import processar_cidadao_sem_localizacao
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Anamnese)
def criar_localizacao_apos_anamnese(sender, instance, created, **kwargs):
    """
    Cria ou atualiza LocalizacaoSaude APENAS quando uma anamnese é criada,
    herdando o risco diretamente da anamnese.
    """
    if created and instance.triagem_risco:
        cidadao = instance.cidadao
        logger.info(f"Nova anamnese para {cidadao.nome} com risco: {instance.triagem_risco}")
        
        # Verificar se o cidadão tem coordenadas (do cadastro ou CEP)
        if not (cidadao.latitude and cidadao.longitude):
            # Tentar geocodificar pelo CEP
            if cidadao.cep:
                try:
                    resultado_geo = processar_cidadao_sem_localizacao(cidadao)
                    if resultado_geo:
                        cidadao.latitude = resultado_geo.latitude
                        cidadao.longitude = resultado_geo.longitude
                        cidadao.save(update_fields=['latitude', 'longitude'])
                        logger.info(f"✅ {cidadao.nome} geocodificado pelo CEP")
                    else:
                        logger.warning(f"⚠️ Não foi possível geocodificar {cidadao.nome}")
                        return
                except Exception as e:
                    logger.error(f"❌ Erro ao geocodificar {cidadao.nome}: {e}")
                    return
            else:
                logger.warning(f"⚠️ {cidadao.nome} não possui coordenadas nem CEP válido")
                return

        # Criar ou atualizar LocalizacaoSaude com o risco da anamnese
        localizacao, created_loc = LocalizacaoSaude.objects.get_or_create(
            cidadao=cidadao,
            defaults={
                'latitude': cidadao.latitude,
                'longitude': cidadao.longitude,
                'endereco_completo': cidadao.endereco or '',
                'bairro': cidadao.bairro or '',
                'cidade': cidadao.cidade or '',
                'estado': cidadao.estado or '',
                'cep': cidadao.cep or '',
                'anamnese': instance,
                'nivel_risco': instance.triagem_risco,
                'pontuacao_risco': calcular_pontuacao_risco(instance.triagem_risco),
                'fonte_localizacao': 'anamnese'
            }
        )
        
        if not created_loc:
            # Atualizar com dados da nova anamnese
            localizacao.anamnese = instance
            localizacao.nivel_risco = instance.triagem_risco
            localizacao.pontuacao_risco = calcular_pontuacao_risco(instance.triagem_risco)
            localizacao.save(update_fields=['anamnese', 'nivel_risco', 'pontuacao_risco'])
            logger.info(f"✅ LocalizacaoSaude atualizada para {cidadao.nome}: {instance.triagem_risco}")
        else:
            logger.info(f"✅ LocalizacaoSaude criada para {cidadao.nome}: {instance.triagem_risco}")


def calcular_pontuacao_risco(nivel_risco):
    """Converte nível de risco em pontuação numérica."""
    pontuacoes = {
        'baixo': 10,
        'medio': 50,
        'alto': 80,
        'critico': 100
    }
    return pontuacoes.get(nivel_risco, 0)


# Remover o signal antigo que criava localizações automaticamente no cadastro
# @receiver(post_save, sender=Cidadao) - REMOVIDO