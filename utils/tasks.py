"""
Tasks assíncronas para processamento de dados de saúde.
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth.models import User
import logging
import json
import time
from datetime import timedelta

from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese, LogAuditoriaIA, AlertaSaude
from utils.processors import ProcessadorDadosMedicos, GeradorRelatorios

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def processar_dados_saude(self, dados_saude_id):
    """
    Processa dados de saúde coletados e identifica alertas.
    
    Args:
        dados_saude_id: ID dos dados de saúde a processar
    """
    try:
        dados_saude = DadosSaude.objects.get(id=dados_saude_id)
        
        # Obtém dados do cidadão
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
        
        # Verifica se há alertas de alto risco
        if dados_estruturados.risco_calculado in ['alto', 'critico']:
            # Agenda geração de anamnese prioritária
            gerar_anamnese_automatica.apply_async(
                args=[dados_saude_id],
                kwargs={'prioridade': 'alta'},
                countdown=10  # Processa em 10 segundos
            )
        
        # Cria alertas se necessário
        for alerta_desc in dados_estruturados.alertas:
            # Determina tipo e prioridade do alerta
            if 'crise hipertensiva' in alerta_desc.lower():
                tipo = 'risco_alto'
                prioridade = 'urgente'
            elif 'febre alta' in alerta_desc.lower():
                tipo = 'sintoma_grave'
                prioridade = 'alta'
            elif 'medicamentos controlados' in alerta_desc.lower():
                tipo = 'medicacao'
                prioridade = 'media'
            else:
                tipo = 'acompanhamento'
                prioridade = 'baixa'
            
            # Cria uma anamnese temporária para associar o alerta
            anamnese_temp, created = Anamnese.objects.get_or_create(
                dados_saude=dados_saude,
                cidadao=dados_saude.cidadao,
                defaults={
                    'resumo_anamnese': 'Processando...',
                    'hipoteses_diagnosticas': [],
                    'triagem_risco': dados_estruturados.risco_calculado,
                    'recomendacoes': 'Aguardando processamento',
                    'dados_entrada_ia': {},
                    'resposta_completa_ia': {}
                }
            )
            
            # Cria alerta
            AlertaSaude.objects.create(
                anamnese=anamnese_temp,
                tipo=tipo,
                prioridade=prioridade,
                titulo=f"Alerta: {alerta_desc[:50]}...",
                descricao=alerta_desc,
                acao_recomendada="Avaliar paciente e tomar ação apropriada",
                prazo_acao=timezone.now() + timedelta(hours=24)
            )
        
        # Marca dados como processados
        dados_saude.sincronizado = True
        dados_saude.save()
        
        logger.info(f"Dados de saúde {dados_saude_id} processados com sucesso")
        
        return {
            'success': True,
            'dados_saude_id': str(dados_saude_id),
            'risco_detectado': dados_estruturados.risco_calculado,
            'alertas_criados': len(dados_estruturados.alertas)
        }
        
    except DadosSaude.DoesNotExist:
        logger.error(f"Dados de saúde {dados_saude_id} não encontrados")
        return {'success': False, 'error': 'Dados não encontrados'}
        
    except Exception as exc:
        logger.error(f"Erro ao processar dados {dados_saude_id}: {exc}")
        
        # Retry com backoff exponencial
        if self.request.retries < self.max_retries:
            raise self.retry(
                countdown=60 * (2 ** self.request.retries),
                exc=exc
            )
        
        return {'success': False, 'error': str(exc)}


@shared_task(bind=True, max_retries=2)
def gerar_anamnese_automatica(self, dados_saude_id, prioridade='normal', modelo_ia='gpt-3.5-turbo'):
    """
    Gera anamnese automática usando IA.
    
    Args:
        dados_saude_id: ID dos dados de saúde
        prioridade: Prioridade do processamento
        modelo_ia: Modelo de IA a usar
    """
    try:
        dados_saude = DadosSaude.objects.get(id=dados_saude_id)
        
        # Obtém dados do cidadão (anonimizados)
        dados_anonimos = dados_saude.cidadao.get_dados_anonimos()
        dados_estruturados = dados_saude.get_dados_estruturados()
        
        # Chama serviço de IA (será implementado no próximo todo)
        # Por enquanto, simula processamento
        time.sleep(2)  # Simula tempo de processamento
        
        # Dados simulados da resposta da IA
        resposta_ia = {
            'resumo_anamnese': f"""
            Paciente de {dados_anonimos.get('idade', 'N/A')} anos, sexo {dados_anonimos.get('sexo', 'N/A')}, 
            apresenta sintomas de {dados_estruturados['sintomas'].get('principais', 'não informado')}. 
            Sinais vitais mostram pressão arterial de {dados_estruturados['sinais_vitais'].get('pressao_arterial', 'N/A')} mmHg.
            Requer avaliação médica para investigação diagnóstica adequada.
            """.strip(),
            
            'hipoteses_diagnosticas': [
                {'diagnostico': 'Hipertensão arterial', 'probabilidade': 0.8},
                {'diagnostico': 'Síndrome gripal', 'probabilidade': 0.6},
                {'diagnostico': 'Ansiedade', 'probabilidade': 0.4}
            ],
            
            'triagem_risco': 'medio',
            
            'recomendacoes': """
            1. Consulta médica em até 48 horas
            2. Monitoramento da pressão arterial
            3. Exames complementares se necessário
            4. Retorno em 7 dias para reavaliação
            """
        }
        
        # Cria ou atualiza anamnese
        anamnese, created = Anamnese.objects.get_or_create(
            dados_saude=dados_saude,
            cidadao=dados_saude.cidadao,
            defaults={
                'resumo_anamnese': resposta_ia['resumo_anamnese'],
                'hipoteses_diagnosticas': resposta_ia['hipoteses_diagnosticas'],
                'triagem_risco': resposta_ia['triagem_risco'],
                'recomendacoes': resposta_ia['recomendacoes'],
                'modelo_ia_usado': modelo_ia,
                'confianca_ia': 85.5,
                'dados_entrada_ia': {
                    'dados_anonimos': dados_anonimos,
                    'dados_estruturados': dados_estruturados
                },
                'resposta_completa_ia': resposta_ia
            }
        )
        
        if not created:
            # Atualiza anamnese existente
            anamnese.resumo_anamnese = resposta_ia['resumo_anamnese']
            anamnese.hipoteses_diagnosticas = resposta_ia['hipoteses_diagnosticas']
            anamnese.triagem_risco = resposta_ia['triagem_risco']
            anamnese.recomendacoes = resposta_ia['recomendacoes']
            anamnese.save()
        
        # Log de auditoria
        LogAuditoriaIA.objects.create(
            tipo_operacao='anamnese',
            modelo_ia=modelo_ia,
            prompt_enviado="Prompt simulado para anamnese",
            dados_entrada=dados_anonimos,
            resposta_ia=resposta_ia,
            tempo_processamento=timedelta(seconds=2),
            sucesso=True,
            dados_anonimizados=True,
            cidadao=dados_saude.cidadao,
            anamnese=anamnese
        )
        
        # Notifica se for caso de alto risco
        if resposta_ia['triagem_risco'] in ['alto', 'critico']:
            notificar_caso_alto_risco.delay(str(anamnese.id))
        
        logger.info(f"Anamnese gerada para dados {dados_saude_id}")
        
        return {
            'success': True,
            'anamnese_id': str(anamnese.id),
            'triagem_risco': resposta_ia['triagem_risco'],
            'created': created
        }
        
    except DadosSaude.DoesNotExist:
        logger.error(f"Dados de saúde {dados_saude_id} não encontrados")
        return {'success': False, 'error': 'Dados não encontrados'}
        
    except Exception as exc:
        logger.error(f"Erro ao gerar anamnese para {dados_saude_id}: {exc}")
        
        # Log de erro na auditoria
        try:
            dados_saude = DadosSaude.objects.get(id=dados_saude_id)
            LogAuditoriaIA.objects.create(
                tipo_operacao='anamnese',
                modelo_ia=modelo_ia,
                prompt_enviado="Erro durante processamento",
                dados_entrada={},
                resposta_ia={},
                tempo_processamento=timedelta(seconds=0),
                sucesso=False,
                erro_detalhes=str(exc),
                cidadao=dados_saude.cidadao
            )
        except:
            pass
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120, exc=exc)
        
        return {'success': False, 'error': str(exc)}


@shared_task
def notificar_caso_alto_risco(anamnese_id):
    """
    Notifica equipe sobre casos de alto risco.
    
    Args:
        anamnese_id: ID da anamnese de alto risco
    """
    try:
        anamnese = Anamnese.objects.get(id=anamnese_id)
        
        # Lista de usuários para notificar (médicos, coordenadores)
        usuarios_notificar = User.objects.filter(
            groups__name__in=['Médicos', 'Coordenadores', 'Supervisores']
        )
        
        if usuarios_notificar.exists():
            emails = [user.email for user in usuarios_notificar if user.email]
            
            if emails:
                assunto = f"URGENTE: Caso de Alto Risco - {anamnese.cidadao.nome}"
                mensagem = f"""
                Um caso de alto risco foi identificado:
                
                Paciente: {anamnese.cidadao.nome}
                Triagem de Risco: {anamnese.triagem_risco.upper()}
                Data: {anamnese.criado_em.strftime('%d/%m/%Y %H:%M')}
                
                Resumo: {anamnese.resumo_anamnese[:200]}...
                
                Acesse o sistema para mais detalhes e ações necessárias.
                """
                
                send_mail(
                    assunto,
                    mensagem,
                    'sistema@saude.gov.br',
                    emails,
                    fail_silently=False
                )
                
                logger.info(f"Notificação enviada para {len(emails)} usuários sobre caso {anamnese_id}")
        
        return {'success': True, 'notificados': len(emails) if 'emails' in locals() else 0}
        
    except Anamnese.DoesNotExist:
        logger.error(f"Anamnese {anamnese_id} não encontrada")
        return {'success': False, 'error': 'Anamnese não encontrada'}
        
    except Exception as exc:
        logger.error(f"Erro ao notificar caso {anamnese_id}: {exc}")
        return {'success': False, 'error': str(exc)}


@shared_task
def sincronizar_dados_offline(dados_lote):
    """
    Sincroniza dados coletados offline pelos agentes.
    
    Args:
        dados_lote: Lista de dados coletados offline
    """
    resultados = []
    
    for item in dados_lote:
        try:
            # Processa cada item do lote
            if 'cidadao' in item:
                # É uma coleta completa
                from api.serializers import ColetaDadosSerializer
                serializer = ColetaDadosSerializer(data=item)
                
                if serializer.is_valid():
                    resultado = serializer.save()
                    
                    # Agenda processamento automático
                    processar_dados_saude.delay(str(resultado['dados_saude'].id))
                    
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': True,
                        'cidadao_id': str(resultado['cidadao'].id),
                        'dados_saude_id': str(resultado['dados_saude'].id)
                    })
                else:
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': False,
                        'errors': serializer.errors
                    })
            else:
                # São apenas dados de saúde
                from api.serializers import DadosSaudeSerializer
                serializer = DadosSaudeSerializer(data=item)
                
                if serializer.is_valid():
                    dados_saude = serializer.save()
                    
                    # Agenda processamento
                    processar_dados_saude.delay(str(dados_saude.id))
                    
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': True,
                        'dados_saude_id': str(dados_saude.id)
                    })
                else:
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': False,
                        'errors': serializer.errors
                    })
                    
        except Exception as exc:
            resultados.append({
                'id_local': item.get('id_local'),
                'success': False,
                'error': str(exc)
            })
    
    logger.info(f"Sincronização offline concluída: {len(resultados)} itens processados")
    
    return {
        'total_processados': len(dados_lote),
        'sucessos': len([r for r in resultados if r.get('success')]),
        'erros': len([r for r in resultados if not r.get('success')]),
        'resultados': resultados
    }


@shared_task
def atualizar_estatisticas_dashboard():
    """
    Atualiza estatísticas do dashboard periodicamente.
    Executada a cada 5 minutos via cron.
    """
    try:
        from dashboard.models import EstatisticaTempoReal
        
        stats = EstatisticaTempoReal.get_current()
        stats.atualizar_contadores()
        
        logger.info("Estatísticas do dashboard atualizadas")
        
        return {'success': True, 'timestamp': timezone.now().isoformat()}
        
    except Exception as exc:
        logger.error(f"Erro ao atualizar estatísticas: {exc}")
        return {'success': False, 'error': str(exc)}


@shared_task
def limpar_logs_antigos():
    """
    Remove logs de auditoria antigos (> 1 ano) para otimizar banco.
    Executada diariamente.
    """
    try:
        limite_data = timezone.now() - timedelta(days=365)
        
        logs_removidos = LogAuditoriaIA.objects.filter(
            criado_em__lt=limite_data
        ).delete()
        
        logger.info(f"Logs antigos removidos: {logs_removidos[0]} registros")
        
        return {
            'success': True,
            'logs_removidos': logs_removidos[0],
            'data_limite': limite_data.isoformat()
        }
        
    except Exception as exc:
        logger.error(f"Erro ao limpar logs: {exc}")
        return {'success': False, 'error': str(exc)}