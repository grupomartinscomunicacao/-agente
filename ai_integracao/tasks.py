"""
Tasks assíncronas para integração com IA.
"""
from celery import shared_task
from django.utils import timezone
import logging

from .services import OpenAIService
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese
from utils.processors import ProcessadorDadosMedicos

logger = logging.getLogger('ai_integracao')


@shared_task(bind=True, max_retries=3)
def gerar_anamnese_openai(self, dados_saude_id, modelo='gpt-3.5-turbo', usuario_id=None):
    """
    Gera anamnese usando OpenAI de forma assíncrona.
    
    Args:
        dados_saude_id: ID dos dados de saúde
        modelo: Modelo de IA a usar
        usuario_id: ID do usuário que solicitou
    """
    try:
        # Obtém dados de saúde
        dados_saude = DadosSaude.objects.get(id=dados_saude_id)
        
        # Prepara dados para IA
        cidadao_data = {
            'data_nascimento': dados_saude.cidadao.data_nascimento,
            'sexo': dados_saude.cidadao.sexo,
            'estado_civil': dados_saude.cidadao.estado_civil,
            'profissao': dados_saude.cidadao.profissao,
            'cidade': dados_saude.cidadao.cidade,
            'estado': dados_saude.cidadao.estado,
            'possui_plano_saude': dados_saude.cidadao.possui_plano_saude,
        }
        
        # Processa dados
        processador = ProcessadorDadosMedicos()
        dados_estruturados = processador.processar_dados_completos(
            cidadao_data, 
            dados_saude.get_dados_estruturados()
        )
        
        # Converte para formato adequado para IA
        dados_para_ia = {
            'faixa_etaria': dados_estruturados.dados_demograficos.get('faixa_etaria'),
            'sexo': dados_estruturados.dados_demograficos.get('sexo'),
            'profissao': dados_saude.cidadao.profissao,
            'possui_plano_saude': dados_saude.cidadao.possui_plano_saude,
            'sinais_vitais': dados_estruturados.sinais_vitais,
            'sintomas': dados_estruturados.sintomas,
            'historico': dados_estruturados.historico_medico,
            'habitos': dados_estruturados.habitos_vida,
            'regiao_cep': dados_saude.cidadao.cep[:3] + "00-000" if dados_saude.cidadao.cep else None,
            'antropometria': dados_estruturados.antropometria if hasattr(dados_estruturados, 'antropometria') else {},
        }
        
        # Adiciona contexto completo do cidadão se existe anamnese
        try:
            # Tenta criar uma anamnese temporária para obter o contexto completo
            anamnese_temp = Anamnese(dados_saude=dados_saude, cidadao=dados_saude.cidadao)
            contexto_completo = anamnese_temp.get_contexto_completo_para_ia()
            
            # Adiciona condições crônicas prévias e medicamentos/alergias
            dados_para_ia.update({
                'condicoes_cronicas_previas': contexto_completo.get('condicoes_cronicas_previas', {}),
                'medicamentos_e_alergias': contexto_completo.get('medicamentos_e_alergias', {}),
                'historico_anamneses': contexto_completo.get('historico_anamneses_anteriores', [])
            })
        except Exception as e:
            # Se houver erro, continua sem o contexto extra
            logger.warning(f"Erro ao obter contexto completo: {e}")
            dados_para_ia.update({
                'condicoes_cronicas_previas': {},
                'medicamentos_e_alergias': {},
                'historico_anamneses': []
            })
        
        # Chama serviço OpenAI
        openai_service = OpenAIService()
        resultado = openai_service.gerar_anamnese(
            dados_para_ia, 
            modelo=modelo, 
            usuario_id=usuario_id
        )
        
        # Cria ou atualiza anamnese
        anamnese, created = Anamnese.objects.get_or_create(
            dados_saude=dados_saude,
            cidadao=dados_saude.cidadao,
            defaults={
                'resumo_anamnese': resultado['resumo_anamnese'],
                'hipoteses_diagnosticas': resultado['hipoteses_diagnosticas'],
                'triagem_risco': resultado['triagem_risco'],
                'recomendacoes': resultado['recomendacoes'],
                'modelo_ia_usado': resultado['modelo_ia_usado'],
                'confianca_ia': resultado['confianca_ia'],
                'dados_entrada_ia': resultado['dados_entrada_anonimos'],
                'resposta_completa_ia': resultado['resposta_completa']
            }
        )
        
        if not created:
            # Atualiza anamnese existente
            anamnese.resumo_anamnese = resultado['resumo_anamnese']
            anamnese.hipoteses_diagnosticas = resultado['hipoteses_diagnosticas']
            anamnese.triagem_risco = resultado['triagem_risco']
            anamnese.recomendacoes = resultado['recomendacoes']
            anamnese.modelo_ia_usado = resultado['modelo_ia_usado']
            anamnese.confianca_ia = resultado['confianca_ia']
            anamnese.dados_entrada_ia = resultado['dados_entrada_anonimos']
            anamnese.resposta_completa_ia = resultado['resposta_completa']
            anamnese.save()
        
        logger.info(f"Anamnese OpenAI gerada para dados {dados_saude_id}")
        
        return {
            'success': True,
            'anamnese_id': str(anamnese.id),
            'triagem_risco': resultado['triagem_risco'],
            'confianca': resultado['confianca_ia'],
            'tokens_utilizados': resultado['tokens_utilizados']
        }
        
    except DadosSaude.DoesNotExist:
        logger.error(f"Dados de saúde {dados_saude_id} não encontrados")
        return {'success': False, 'error': 'Dados não encontrados'}
        
    except Exception as exc:
        logger.error(f"Erro ao gerar anamnese OpenAI para {dados_saude_id}: {exc}")
        
        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=exc
            )
        
        return {'success': False, 'error': str(exc)}


@shared_task
def classificar_risco_lote(lista_dados_saude_ids, modelo='gpt-3.5-turbo'):
    """
    Classifica risco para múltiplos pacientes em lote.
    
    Args:
        lista_dados_saude_ids: Lista de IDs de dados de saúde
        modelo: Modelo de IA a usar
    """
    resultados = []
    openai_service = OpenAIService()
    
    for dados_id in lista_dados_saude_ids:
        try:
            dados_saude = DadosSaude.objects.get(id=dados_id)
            
            # Prepara dados
            dados_para_ia = {
                'sintomas': {'principais': dados_saude.sintomas_principais},
                'sinais_vitais': {
                    'pressao_arterial': f"{dados_saude.pressao_sistolica}/{dados_saude.pressao_diastolica}",
                    'frequencia_cardiaca': dados_saude.frequencia_cardiaca,
                    'temperatura': float(dados_saude.temperatura)
                },
                'historico': {
                    'doencas': dados_saude.historico_doencas,
                    'medicamentos': dados_saude.medicamentos_uso
                },
                'faixa_etaria': dados_saude.cidadao.idade // 10 * 10  # Faixa de 10 anos
            }
            
            # Classifica risco
            resultado_risco = openai_service.classificar_risco(dados_para_ia, modelo)
            
            # Atualiza anamnese se existir
            try:
                anamnese = Anamnese.objects.get(dados_saude=dados_saude)
                if resultado_risco['risco'] != anamnese.triagem_risco:
                    anamnese.triagem_risco = resultado_risco['risco']
                    anamnese.save()
            except Anamnese.DoesNotExist:
                pass
            
            resultados.append({
                'dados_saude_id': str(dados_id),
                'success': True,
                'risco_atual': resultado_risco['risco'],
                'confianca': resultado_risco.get('confianca', 0.5)
            })
            
        except Exception as exc:
            resultados.append({
                'dados_saude_id': str(dados_id),
                'success': False,
                'error': str(exc)
            })
    
    logger.info(f"Classificação de risco em lote concluída: {len(resultados)} itens")
    
    return {
        'total_processados': len(lista_dados_saude_ids),
        'sucessos': len([r for r in resultados if r.get('success')]),
        'resultados': resultados
    }


@shared_task
def extrair_dados_texto_medico(texto_medico, anamnese_id=None):
    """
    Extrai dados estruturados de texto médico livre.
    
    Args:
        texto_medico: Texto médico não estruturado
        anamnese_id: ID da anamnese associada (opcional)
    """
    try:
        openai_service = OpenAIService()
        dados_extraidos = openai_service.extrair_dados_estruturados(texto_medico)
        
        # Se há anamnese associada, atualiza com dados extraídos
        if anamnese_id:
            try:
                anamnese = Anamnese.objects.get(id=anamnese_id)
                
                # Atualiza campos se dados foram extraídos
                if dados_extraidos.get('sintomas'):
                    sintomas_atuais = anamnese.resumo_anamnese
                    sintomas_extraidos = ', '.join(dados_extraidos['sintomas'])
                    anamnese.resumo_anamnese = f"{sintomas_atuais}\n\nSintomas extraídos: {sintomas_extraidos}"
                
                if dados_extraidos.get('medicamentos'):
                    # Adiciona aos dados de entrada da IA
                    dados_entrada = anamnese.dados_entrada_ia or {}
                    dados_entrada['medicamentos_extraidos'] = dados_extraidos['medicamentos']
                    anamnese.dados_entrada_ia = dados_entrada
                
                anamnese.save()
                
            except Anamnese.DoesNotExist:
                pass
        
        logger.info(f"Dados extraídos do texto médico com sucesso")
        
        return {
            'success': True,
            'dados_extraidos': dados_extraidos,
            'anamnese_atualizada': anamnese_id is not None
        }
        
    except Exception as exc:
        logger.error(f"Erro ao extrair dados do texto: {exc}")
        return {'success': False, 'error': str(exc)}


@shared_task
def gerar_insights_populacionais(periodo_dias=30):
    """
    Gera insights sobre tendências de saúde populacional.
    
    Args:
        periodo_dias: Período em dias para análise
    """
    try:
        from datetime import timedelta
        
        # Obtém dados do período
        data_limite = timezone.now() - timedelta(days=periodo_dias)
        
        anamneses = Anamnese.objects.filter(
            criado_em__gte=data_limite,
            status='aprovada'
        ).select_related('cidadao', 'dados_saude')
        
        # Prepara dados agregados (anonimizados)
        dados_agregados = []
        for anamnese in anamneses:
            dados_agregados.append({
                'faixa_etaria': anamnese.cidadao.idade // 10 * 10,
                'sexo': anamnese.cidadao.sexo,
                'regiao': anamnese.cidadao.cep[:3] if anamnese.cidadao.cep else None,
                'triagem_risco': anamnese.triagem_risco,
                'hipoteses': [h.get('diagnostico', '') for h in anamnese.hipoteses_diagnosticas],
                'sintomas': anamnese.dados_saude.sintomas_principais[:100],  # Trunca
                'mes_ano': anamnese.criado_em.strftime('%Y-%m')
            })
        
        if len(dados_agregados) < 10:
            return {
                'success': False, 
                'error': 'Dados insuficientes para análise'
            }
        
        # Chama IA para análise
        openai_service = OpenAIService()
        insights = openai_service.analisar_tendencias_populacionais(dados_agregados)
        
        # Salva insights no banco (poderia ser um modelo específico)
        logger.info(f"Insights populacionais gerados para {len(dados_agregados)} casos")
        
        return {
            'success': True,
            'periodo_analisado': periodo_dias,
            'casos_analisados': len(dados_agregados),
            'insights': insights
        }
        
    except Exception as exc:
        logger.error(f"Erro ao gerar insights populacionais: {exc}")
        return {'success': False, 'error': str(exc)}