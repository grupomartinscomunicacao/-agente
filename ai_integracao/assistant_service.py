"""
Serviço para integração com OpenAI Assistant API para anamnese médica.
"""
import openai
import json
import time
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone

from anamneses.models import Anamnese
from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude

logger = logging.getLogger('ai_integracao')


class OpenAIAssistantService:
    """Serviço para usar OpenAI Assistant API."""
    
    def __init__(self):
        # Configura cliente OpenAI
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.assistant_id = settings.ASSISTANT_ID
        
    def gerar_anamnese_com_assistant(self, cidadao: Cidadao, dados_saude: DadosSaude) -> Dict[str, Any]:
        """
        Gera anamnese usando o Assistant API com contexto completo.
        
        Args:
            cidadao: Instância do cidadão
            dados_saude: Dados de saúde coletados
            
        Returns:
            Dict com resultado da anamnese
        """
        try:
            # Prepara contexto completo
            contexto = self._preparar_contexto_completo(cidadao, dados_saude)
            
            # Cria thread
            thread = self.client.beta.threads.create()
            
            # Envia mensagem com contexto
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=f"""
                Analise os seguintes dados médicos e gere uma anamnese completa com diagnóstico clínico:
                
                {json.dumps(contexto, indent=2, ensure_ascii=False, default=str)}
                
                INSTRUÇÕES ESPECÍFICAS:
                - Analise cuidadosamente o resumo da anamnese e dados coletados
                - Correlacione sintomas atuais com histórico médico
                - Considere condições pré-existentes e medicamentos em uso
                - Identifique padrões clínicos significativos
                - Avalie gravidade e urgência do caso
                
                Gere uma resposta em formato JSON com:
                1. resumo_anamnese (máximo 300 palavras - síntese clínica do caso)
                2. diagnostico_clinico (diagnóstico médico provável baseado na análise)
                3. diagnostico_diferencial (lista de diagnósticos alternativos a considerar)
                4. hipoteses_diagnosticas (lista ordenada por probabilidade clínica)
                5. triagem_risco (baixo/medio/alto/critico com justificativa)
                6. recomendacoes (ações médicas específicas e urgentes)
                7. exames_complementares (exames recomendados para confirmar diagnóstico)
                8. observacoes_especiais (alertas críticos e contraindicações)
                9. prognose (expectativa de evolução do caso)
                10. contexto_utilizado (como o histórico médico influenciou o diagnóstico)
                
                FOQUE NO DIAGNÓSTICO MÉDICO baseado nos sintomas apresentados e histórico clínico.
                """
            )
            
            # Executa o assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # Aguarda conclusão
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
            
            if run.status == 'completed':
                # Recupera mensagens
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                
                # Pega última resposta do assistant
                assistant_message = messages.data[0]
                resposta_texto = assistant_message.content[0].text.value
                
                # Processa resposta
                resultado = self._processar_resposta_assistant(resposta_texto)
                
                # Adiciona metadados (serialização segura para JSON)
                from datetime import datetime, date
                
                def serialize_json_safe(obj):
                    """Converte objetos não-serializáveis para JSON."""
                    if isinstance(obj, (datetime, date)):
                        return obj.isoformat()
                    elif hasattr(obj, '__dict__'):
                        return str(obj)
                    return obj
                
                # Limpa contexto para ser JSON-safe
                contexto_safe = json.loads(
                    json.dumps(contexto, default=serialize_json_safe)
                )
                
                resultado.update({
                    'modelo_ia_usado': 'openai-assistant',
                    'assistant_id': self.assistant_id,
                    'thread_id': thread.id,
                    'run_id': run.id,
                    'contexto_historico_usado': True,
                    'dados_entrada_anonimos': contexto_safe
                })
                
                return resultado
                
            else:
                raise Exception(f"Assistant execution failed: {run.status}")
                
        except Exception as e:
            logger.error(f"Erro na geração de anamnese com Assistant: {e}")
            return {
                'erro': str(e),
                'resumo_anamnese': 'Erro na geração automática da anamnese.',
                'hipoteses_diagnosticas': [],
                'triagem_risco': 'medio',
                'recomendacoes': 'Consulta médica recomendada.',
                'observacoes_especiais': 'Anamnese gerada manualmente devido a erro no sistema.',
                'sucesso': False
            }
    
    def _preparar_contexto_completo(self, cidadao: Cidadao, dados_saude: DadosSaude) -> Dict[str, Any]:
        """Prepara contexto completo para o Assistant."""
        
        # Dados estruturados de saúde
        dados_estruturados = dados_saude.get_dados_estruturados()
        
        # Contexto completo
        contexto = {
            'informacoes_demograficas': {
                'idade': cidadao.idade,
                'sexo': cidadao.sexo,
                'profissao': cidadao.profissao,
                'possui_plano_saude': cidadao.possui_plano_saude,
                'cidade': cidadao.cidade,
                'estado': cidadao.estado
            },
            
            'historico_medico_previo': {
                'condicoes_cronicas': {
                    'hipertensao': cidadao.possui_hipertensao,
                    'diabetes': cidadao.possui_diabetes,
                    'doenca_cardiaca': cidadao.possui_doenca_cardiaca,
                    'doenca_renal': cidadao.possui_doenca_renal,
                    'asma': cidadao.possui_asma,
                    'depressao_ansiedade': cidadao.possui_depressao,
                    'lista_condicoes_ativas': cidadao.condicoes_saude_cronicas
                },
                'medicamentos_continuos': cidadao.medicamentos_continuo,
                'alergias_conhecidas': cidadao.alergias_conhecidas,
                'cirurgias_anteriores': cidadao.cirurgias_anteriores
            },
            
            'dados_consulta_atual': {
                'data_coleta': dados_saude.criado_em,
                'sinais_vitais': dados_estruturados.get('sinais_vitais', {}),
                'antropometria': dados_estruturados.get('antropometria', {}),
                'sintomas_atuais': dados_estruturados.get('sintomas', {}),
                'historico_consulta': dados_estruturados.get('historico_medico', {}),
                'habitos_vida': dados_estruturados.get('habitos_vida', {}),
                'medicamentos_hoje': dados_estruturados.get('historico_medico', {}).get('medicamentos', ''),
                'agente_coleta': dados_saude.agente_coleta.get_full_name() if dados_saude.agente_coleta else 'N/A'
            },
            
            'instrucoes_especiais': {
                'considerar_historico': True,
                'alertar_para_alergias': bool(cidadao.alergias_conhecidas),
                'monitorar_condicoes_cronicas': bool(cidadao.condicoes_saude_cronicas),
                'avaliar_interacoes_medicamentosas': bool(cidadao.medicamentos_continuo),
                'priorizar_seguranca': True
            }
        }
        
        # Adiciona histórico de anamneses anteriores
        anamneses_anteriores = Anamnese.objects.filter(
            cidadao=cidadao
        ).exclude(dados_saude=dados_saude).order_by('-criado_em')[:3]
        
        if anamneses_anteriores:
            contexto['historico_anamneses_anteriores'] = []
            for anamnese in anamneses_anteriores:
                contexto['historico_anamneses_anteriores'].append({
                    'data': anamnese.criado_em,
                    'risco': anamnese.triagem_risco,
                    'resumo': anamnese.resumo_anamnese[:100] + '...',
                    'principais_hipoteses': anamnese.hipoteses_diagnosticas[:2] if anamnese.hipoteses_diagnosticas else []
                })
        
        return contexto
    
    def _processar_resposta_assistant(self, resposta_texto: str) -> Dict[str, Any]:
        """Processa resposta do Assistant."""
        try:
            # Tenta extrair JSON da resposta
            inicio_json = resposta_texto.find('{')
            fim_json = resposta_texto.rfind('}') + 1
            
            if inicio_json >= 0 and fim_json > inicio_json:
                json_texto = resposta_texto[inicio_json:fim_json]
                resultado = json.loads(json_texto)
            else:
                # Fallback: cria estrutura baseada no texto
                resultado = {
                    'resumo_anamnese': resposta_texto[:500],
                    'hipoteses_diagnosticas': [],
                    'triagem_risco': 'medio',
                    'recomendacoes': 'Consulta médica recomendada.',
                    'observacoes_especiais': 'Resposta processada como texto livre.'
                }
            
            # Valida campos obrigatórios
            campos_obrigatorios = ['resumo_anamnese', 'hipoteses_diagnosticas', 'triagem_risco', 'recomendacoes']
            for campo in campos_obrigatorios:
                if campo not in resultado:
                    resultado[campo] = 'Não informado'
            
            # Valida triagem de risco
            if resultado['triagem_risco'] not in ['baixo', 'medio', 'alto', 'critico']:
                resultado['triagem_risco'] = 'medio'
            
            resultado['sucesso'] = True
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao processar resposta do Assistant: {e}")
            return {
                'resumo_anamnese': resposta_texto[:500] if resposta_texto else 'Erro no processamento',
                'hipoteses_diagnosticas': [],
                'triagem_risco': 'medio',
                'recomendacoes': 'Consulta médica recomendada devido a erro no processamento.',
                'observacoes_especiais': f'Erro no processamento: {str(e)}',
                'sucesso': False
            }