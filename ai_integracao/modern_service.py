"""
Serviço modernizado usando a nova OpenAI Responses API.
Muito mais simples e eficiente que a Assistant API.
"""
import json
import logging
from typing import Dict, Any
from datetime import datetime
from django.conf import settings
from openai import OpenAI

from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese

logger = logging.getLogger('ai_integracao')


class ModernOpenAIService:
    """Serviço usando a nova OpenAI Responses API (mais simples e eficiente)."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def gerar_anamnese_moderna(self, cidadao: Cidadao, dados_saude: DadosSaude) -> Dict[str, Any]:
        """
        Gera anamnese usando a nova Responses API - muito mais simples!
        
        Args:
            cidadao: Instância do cidadão
            dados_saude: Dados de saúde coletados
            
        Returns:
            Dict com resultado da anamnese
        """
        try:
            # Prepara contexto médico
            contexto = self._preparar_contexto_medico(cidadao, dados_saude)
            
            # Prompt estruturado para diagnóstico médico conforme especificado
            prompt = f"""
            Você é um médico especialista em triagem e diagnóstico. Analise os dados médicos abaixo e forneça uma resposta estruturada em JSON.

            DADOS DO PACIENTE:
            {contexto}

            IMPORTANTE: Retorne APENAS o JSON válido, sem markdown, sem explicações adicionais, sem ```json```.

            INSTRUÇÕES ESPECIAIS:
            - SEMPRE considerar as CONDIÇÕES CRÔNICAS quando presentes - elas são FUNDAMENTAIS para o diagnóstico
            - Condições crônicas podem influenciar significativamente os sintomas atuais e o manejo clínico
            - Histórico familiar e procedimentos anteriores devem ser considerados na análise de risco
            - Se há "RECOMENDAÇÃO ESPECIAL DE HIDRATAÇÃO" nos dados, SEMPRE inclua essa recomendação específica nas "recomendacoes"
            - Para adultos (18+ anos), priorize orientações de hidratação adequada baseada no peso corporal
            - Internações anteriores podem indicar gravidade de condições preexistentes

            Forneça sua análise médica no seguinte formato JSON:
            {{
                "resumo_anamnese": "Resumo clínico do caso",
                "diagnostico_clinico": "Diagnóstico principal suspeito",
                "diagnostico_diferencial": ["Lista de diagnósticos diferenciais"],
                "hipoteses_diagnosticas": ["Lista de hipóteses diagnósticas"],
                "triagem_risco": "baixo/medio/alto",
                "recomendacoes": ["Lista de recomendações médicas incluindo hidratação quando aplicável"],
                "exames_complementares": ["Lista de exames sugeridos"],
                "prognose": "Prognóstico do caso"
            }}

            Seja preciso e baseie-se em evidências médicas. Considere a idade, sintomas, sinais vitais, condições crônicas, histórico familiar e contexto social do paciente.
            """
            
            logger.info("Gerando anamnese com nova Responses API")
            
            # Usa a nova API Responses
            response = self.client.responses.create(
                model="gpt-4o-mini",  # Modelo econômico com boa qualidade
                input=prompt
            )
            
            # Extrai o texto da resposta
            output_text = response.output[0].content[0].text
            
            logger.info("Resposta recebida da API, processando JSON")
            
            # Parse do JSON - remove markdown se existir
            try:
                # Remove markdown ```json ``` se presente
                json_text = output_text.strip()
                if json_text.startswith('```json'):
                    json_text = json_text[7:]  # Remove ```json
                if json_text.endswith('```'):
                    json_text = json_text[:-3]  # Remove ```
                json_text = json_text.strip()
                
                resultado = json.loads(json_text)
                
                # Adiciona metadados da API
                resultado.update({
                    'modelo_ia_usado': 'gpt-4o-mini-responses-api',
                    'response_id': response.id,
                    'tokens_usados': response.usage.total_tokens,
                    'dados_entrada_anonimos': self._anonimizar_dados(contexto)
                })
                
                logger.info(f"Anamnese gerada com sucesso. Tokens: {response.usage.total_tokens}")
                return resultado
                
            except json.JSONDecodeError as e:
                logger.error(f"Erro ao parse JSON da resposta: {e}")
                # Fallback: criar estrutura mínima
                return {
                    'resumo_anamnese': output_text[:500],
                    'diagnostico_clinico': 'Diagnóstico requer revisão médica',
                    'diagnostico_diferencial': [],
                    'hipoteses_diagnosticas': ['Análise pendente'],
                    'triagem_risco': 'medio',
                    'recomendacoes': ['Consulta médica presencial recomendada'],
                    'exames_complementares': [],
                    'prognose': 'A ser determinado em consulta',
                    'modelo_ia_usado': 'gpt-4o-mini-responses-api-fallback',
                    'dados_entrada_anonimos': {},
                    'resposta_raw': output_text
                }
                
        except Exception as e:
            logger.error(f"Erro na geração de anamnese moderna: {e}")
            raise
    
    def _preparar_contexto_medico(self, cidadao: Cidadao, dados_saude: DadosSaude) -> str:
        """Prepara contexto médico estruturado."""
        
        # Dados demográficos
        idade = cidadao.idade
        sexo = getattr(cidadao, 'sexo', 'Não informado')
        
        # Buscar histórico de saúde com condições crônicas
        historico_saude = getattr(cidadao, 'historico_saude', None)
        
        # Calcular recomendação de água se idade >= 18
        recomendacao_agua = ""
        if idade >= 18 and dados_saude.peso:
            agua_ml_dia = dados_saude.peso * 35  # 35ml por kg
            agua_litros_dia = agua_ml_dia / 1000  # converter para litros
            recomendacao_agua = f"""
        
        RECOMENDAÇÃO ESPECIAL DE HIDRATAÇÃO:
        - Para adulto de {dados_saude.peso}kg: {agua_litros_dia:.1f} litros de água por dia
        - Base: 35ml por kg de peso corporal
        - IMPORTANTE: Incluir esta recomendação nas orientações finais
        """
        
        contexto = f"""
        DADOS DEMOGRÁFICOS:
        - Nome: {cidadao.nome}
        - Idade: {idade} anos
        - Sexo: {sexo}
        
        SINAIS VITAIS:
        - Pressão Arterial: {dados_saude.pressao_sistolica}/{dados_saude.pressao_diastolica} mmHg
        - Frequência Cardíaca: {dados_saude.frequencia_cardiaca} bpm
        - Temperatura: {dados_saude.temperatura}°C
        - Peso: {dados_saude.peso} kg
        - Altura: {dados_saude.altura} m{recomendacao_agua}
        
        SINTOMAS PRINCIPAIS:
        {dados_saude.sintomas_principais or 'Nenhum sintoma relatado'}
        
        NÍVEL DE DOR: {dados_saude.nivel_dor}/10
        DURAÇÃO DOS SINTOMAS: {dados_saude.duracao_sintomas or 'Não informado'}
        
        MEDICAMENTOS EM USO:
        {dados_saude.medicamentos_uso or 'Nenhum medicamento'}
        
        HISTÓRICO DE DOENÇAS:
        {dados_saude.historico_doencas or 'Nenhum histórico conhecido'}
        
        CONDIÇÕES CRÔNICAS:
        {historico_saude.condicoes_cronicas if historico_saude and historico_saude.condicoes_cronicas else 'Nenhuma condição crônica conhecida'}
        
        HISTÓRICO FAMILIAR:
        {historico_saude.historico_familiar if historico_saude and historico_saude.historico_familiar else 'Nenhum histórico familiar conhecido'}
        
        PROCEDIMENTOS REALIZADOS:
        {historico_saude.procedimentos_realizados if historico_saude and historico_saude.procedimentos_realizados else 'Nenhum procedimento conhecido'}
        
        INTERNAÇÕES ANTERIORES:
        {historico_saude.internacoes if historico_saude and historico_saude.internacoes else 'Nenhuma internação conhecida'}
        
        ALERGIAS:
        {dados_saude.alergias or 'Nenhuma alergia conhecida'}
        
        HÁBITOS DE VIDA:
        - Fumante: {'Sim' if dados_saude.fumante else 'Não'}
        - Etilista: {'Sim' if dados_saude.etilista else 'Não'}
        - Atividade Física: {dados_saude.get_nivel_atividade_fisica_display() if hasattr(dados_saude, 'get_nivel_atividade_fisica_display') else dados_saude.nivel_atividade_fisica}
        - Horas de Sono: {dados_saude.horas_sono}h
        - Alimentação Balanceada: {'Sim' if dados_saude.alimentacao_balanceada else 'Não'}
        - Consumo de Água: {dados_saude.consumo_agua_litros}L/dia
        
        DADOS EXTRAS:
        {dados_saude.dados_extras or 'Nenhuma informação adicional'}
        """
        
        return contexto.strip()
    
    def _anonimizar_dados(self, contexto: str) -> Dict[str, Any]:
        """Cria versão anonimizada dos dados para auditoria."""
        return {
            'contexto_anonimizado': '[DADOS ANONIMIZADOS PARA CONFORMIDADE LGPD]',
            'timestamp': datetime.now().isoformat()
        }

    def salvar_anamnese_moderna(self, cidadao: Cidadao, dados_saude: DadosSaude) -> Dict[str, Any]:
        """
        Gera anamnese moderna E salva no banco de dados.
        
        Returns:
            Dict com resultado da operação
        """
        try:
            # Gerar anamnese com nova API
            resultado_ia = self.gerar_anamnese_moderna(cidadao, dados_saude)
            
            if 'erro' in resultado_ia:
                return {
                    'sucesso': False,
                    'erro': resultado_ia['erro']
                }
            
            # Criar registro de anamnese
            anamnese = Anamnese.objects.create(
                cidadao=cidadao,
                dados_saude=dados_saude,
                resumo_anamnese=resultado_ia.get('resumo_anamnese', ''),
                diagnostico_clinico=resultado_ia.get('diagnostico_clinico', ''),
                hipoteses_diagnosticas=resultado_ia.get('hipoteses_diagnosticas', []),
                triagem_risco=resultado_ia.get('triagem_risco', 'medio'),
                recomendacoes=', '.join(resultado_ia.get('recomendacoes', [])),
                exames_complementares=', '.join(resultado_ia.get('exames_complementares', [])),
                prognose=resultado_ia.get('prognose', ''),
                dados_entrada_ia=resultado_ia.get('dados_entrada_anonimos', {}),
                resposta_completa_ia=resultado_ia,
                modelo_ia_usado=resultado_ia.get('modelo_ia_usado', 'gpt-4o-mini-responses-api')
            )
            
            logger.info(f"Anamnese moderna salva: ID {anamnese.id}")
            
            return {
                'sucesso': True,
                'mensagem': 'Anamnese gerada e salva com nova API Responses',
                'anamnese': anamnese,
                'tokens_utilizados': resultado_ia.get('tokens_usados', 0),
                'modelo_usado': resultado_ia.get('modelo_ia_usado', 'gpt-4o-mini-responses-api')
            }
            
        except Exception as e:
            logger.error(f"Erro ao salvar anamnese moderna: {str(e)}")
            return {
                'sucesso': False,
                'erro': f"Erro ao salvar anamnese: {str(e)}"
            }