"""
Serviços de integração com OpenAI para análise médica.
"""
import openai
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from anamneses.models import LogAuditoriaIA
from utils.validators import AnonimizadorDados

logger = logging.getLogger('ai_integracao')


class OpenAIService:
    """Serviço principal para integração com OpenAI."""
    
    def __init__(self):
        # Configura chave da API
        openai.api_key = settings.OPENAI_API_KEY
        
        # Configurações padrão
        self.default_model = "gpt-3.5-turbo"
        self.max_tokens = 1500
        self.temperature = 0.3  # Baixa para respostas mais consistentes
    
    def gerar_anamnese(self, dados_paciente: Dict[str, Any], 
                      modelo: str = None, 
                      usuario_id: int = None) -> Dict[str, Any]:
        """
        Gera anamnese automática baseada nos dados do paciente.
        
        Args:
            dados_paciente: Dados anonimizados do paciente
            modelo: Modelo de IA a usar
            usuario_id: ID do usuário solicitante
            
        Returns:
            Dict com resultado da anamnese
        """
        modelo = modelo or self.default_model
        inicio_processamento = timezone.now()
        
        try:
            # Anonimiza dados
            dados_anonimos = AnonimizadorDados.anonimizar_dados_pessoais(dados_paciente)
            
            # Monta prompt estruturado
            prompt = self._construir_prompt_anamnese(dados_anonimos)
            
            # Chama OpenAI
            response = openai.ChatCompletion.create(
                model=modelo,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt_anamnese()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=0.9
            )
            
            # Extrai resposta
            resposta_texto = response.choices[0].message.content
            resposta_estruturada = self._processar_resposta_anamnese(resposta_texto)
            
            # Calcula métricas
            tempo_processamento = timezone.now() - inicio_processamento
            tokens_usados = response.usage.total_tokens
            custo_estimado = self._calcular_custo(tokens_usados, modelo)
            
            # Log de auditoria
            self._criar_log_auditoria(
                tipo_operacao='anamnese',
                modelo=modelo,
                prompt=prompt,
                dados_entrada=dados_anonimos,
                resposta=response.to_dict(),
                tempo_processamento=tempo_processamento,
                tokens_usados=tokens_usados,
                custo_estimado=custo_estimado,
                sucesso=True,
                usuario_id=usuario_id
            )
            
            # Adiciona metadados à resposta
            resposta_estruturada.update({
                'modelo_ia_usado': modelo,
                'tokens_utilizados': tokens_usados,
                'custo_estimado': custo_estimado,
                'tempo_processamento': tempo_processamento.total_seconds(),
                'confianca_ia': self._calcular_confianca(resposta_estruturada),
                'dados_entrada_anonimos': dados_anonimos,
                'resposta_completa': response.to_dict()
            })
            
            logger.info(f"Anamnese gerada com sucesso - Modelo: {modelo}, Tokens: {tokens_usados}")
            
            return resposta_estruturada
            
        except Exception as exc:
            tempo_processamento = timezone.now() - inicio_processamento
            
            # Log de erro
            self._criar_log_auditoria(
                tipo_operacao='anamnese',
                modelo=modelo,
                prompt=prompt if 'prompt' in locals() else '',
                dados_entrada=dados_anonimos if 'dados_anonimos' in locals() else {},
                resposta={},
                tempo_processamento=tempo_processamento,
                sucesso=False,
                erro_detalhes=str(exc),
                usuario_id=usuario_id
            )
            
            logger.error(f"Erro ao gerar anamnese: {exc}")
            raise exc
    
    def classificar_risco(self, dados_paciente: Dict[str, Any], 
                         modelo: str = None) -> Dict[str, Any]:
        """
        Classifica risco do paciente baseado em sintomas e dados.
        
        Args:
            dados_paciente: Dados do paciente
            modelo: Modelo de IA a usar
            
        Returns:
            Dict com classificação de risco
        """
        modelo = modelo or self.default_model
        inicio_processamento = timezone.now()
        
        try:
            # Anonimiza dados
            dados_anonimos = AnonimizadorDados.anonimizar_dados_pessoais(dados_paciente)
            
            # Prompt específico para triagem de risco
            prompt = self._construir_prompt_triagem(dados_anonimos)
            
            response = openai.ChatCompletion.create(
                model=modelo,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt_triagem()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.2  # Ainda mais baixa para triagem
            )
            
            resposta_texto = response.choices[0].message.content
            resultado_triagem = self._processar_resposta_triagem(resposta_texto)
            
            tempo_processamento = timezone.now() - inicio_processamento
            
            # Log
            self._criar_log_auditoria(
                tipo_operacao='triagem',
                modelo=modelo,
                prompt=prompt,
                dados_entrada=dados_anonimos,
                resposta=response.to_dict(),
                tempo_processamento=tempo_processamento,
                sucesso=True
            )
            
            return resultado_triagem
            
        except Exception as exc:
            logger.error(f"Erro na triagem de risco: {exc}")
            raise exc
    
    def extrair_dados_estruturados(self, texto_medico: str) -> Dict[str, Any]:
        """
        Extrai dados estruturados de texto médico livre.
        
        Args:
            texto_medico: Texto médico não estruturado
            
        Returns:
            Dict com dados estruturados
        """
        try:
            prompt = self._construir_prompt_extracao(texto_medico)
            
            response = openai.ChatCompletion.create(
                model=self.default_model,
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt_extracao()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.1
            )
            
            resposta_texto = response.choices[0].message.content
            dados_estruturados = self._processar_resposta_extracao(resposta_texto)
            
            return dados_estruturados
            
        except Exception as exc:
            logger.error(f"Erro na extração de dados: {exc}")
            raise exc
    
    def analisar_tendencias_populacionais(self, dados_agregados: List[Dict]) -> Dict[str, Any]:
        """
        Analisa tendências de saúde populacional.
        
        Args:
            dados_agregados: Lista de dados agregados de múltiplos pacientes
            
        Returns:
            Dict com insights e tendências
        """
        try:
            # Anonimiza todos os dados
            dados_anonimos = [
                AnonimizadorDados.anonimizar_dados_pessoais(dado) 
                for dado in dados_agregados
            ]
            
            prompt = self._construir_prompt_agregacao(dados_anonimos)
            
            response = openai.ChatCompletion.create(
                model="gpt-4",  # Usa modelo mais avançado para análises complexas
                messages=[
                    {
                        "role": "system", 
                        "content": self._get_system_prompt_agregacao()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.4
            )
            
            resposta_texto = response.choices[0].message.content
            analise_tendencias = self._processar_resposta_agregacao(resposta_texto)
            
            return analise_tendencias
            
        except Exception as exc:
            logger.error(f"Erro na análise de tendências: {exc}")
            raise exc
    
    # Métodos privados para construção de prompts
    
    def _get_system_prompt_anamnese(self) -> str:
        """Prompt do sistema para anamnese."""
        return """
        Você é um assistente médico especializado em anamnese. Sua função é analisar dados de saúde 
        de pacientes e gerar anamneses estruturadas, hipóteses diagnósticas e recomendações iniciais.
        
        IMPORTANTE:
        - Sempre mantenha abordagem científica e baseada em evidências
        - Nunca faça diagnósticos definitivos, apenas hipóteses
        - Priorize a segurança do paciente
        - Seja conciso mas completo
        - Use linguagem técnica médica apropriada
        
        Formate sua resposta SEMPRE como JSON válido com as seguintes chaves:
        {
            "resumo_anamnese": "Resumo em até 200 palavras",
            "hipoteses_diagnosticas": [
                {"diagnostico": "Nome", "probabilidade": 0.0-1.0, "justificativa": "Texto"}
            ],
            "triagem_risco": "baixo|medio|alto|critico",
            "recomendacoes": "Lista de recomendações numeradas",
            "exames_sugeridos": ["Lista de exames"],
            "sinais_alerta": ["Lista de sinais que requerem atenção"]
        }
        """
    
    def _get_system_prompt_triagem(self) -> str:
        """Prompt do sistema para triagem de risco."""
        return """
        Você é um especialista em triagem médica. Analise os dados fornecidos e classifique 
        o risco do paciente baseado em protocolos médicos estabelecidos.
        
        CRITÉRIOS DE RISCO:
        - CRÍTICO: Risco iminente de vida, requer atendimento imediato
        - ALTO: Condições graves que requerem atenção médica urgente (< 2h)
        - MÉDIO: Condições que requerem avaliação médica em 24-48h
        - BAIXO: Condições que podem aguardar consulta de rotina
        
        Formate como JSON:
        {
            "risco": "baixo|medio|alto|critico",
            "justificativa": "Explicação detalhada",
            "tempo_recomendado": "Tempo para atendimento",
            "sinais_criticos": ["Lista de sinais críticos identificados"],
            "confianca": 0.0-1.0
        }
        """
    
    def _get_system_prompt_extracao(self) -> str:
        """Prompt para extração de dados estruturados."""
        return """
        Extraia dados estruturados do texto médico fornecido. Identifique e organize 
        informações relevantes em categorias específicas.
        
        Formate como JSON:
        {
            "pressao_arterial": "sistolica/diastolica ou null",
            "sintomas": ["lista de sintomas"],
            "historico_doencas": ["lista de doenças mencionadas"],
            "medicamentos": ["lista de medicamentos"],
            "sinais_vitais": {"fc": null, "temp": null, "peso": null},
            "queixas_principais": "texto resumido",
            "dados_nao_estruturados": "informações que não se encaixam"
        }
        """
    
    def _get_system_prompt_agregacao(self) -> str:
        """Prompt para análise de dados agregados."""
        return """
        Analise os dados de saúde populacionais fornecidos e identifique padrões, 
        tendências e insights relevantes para políticas de saúde pública.
        
        Formate como JSON:
        {
            "tendencias_identificadas": ["lista de tendências"],
            "clusters_doencas": ["agrupamentos de doenças por região/faixa etária"],
            "hotspots_geograficos": ["áreas com concentração de problemas"],
            "recomendacoes_politicas": ["sugestões para políticas públicas"],
            "indicadores_epidemiologicos": {"prevalencia": {}, "incidencia": {}},
            "grupos_risco": ["populações em risco identificadas"],
            "prioridades_intervencao": ["áreas prioritárias para intervenção"]
        }
        """
    
    def _construir_prompt_anamnese(self, dados: Dict[str, Any]) -> str:
        """Constrói prompt para anamnese incluindo informações prévias do cidadão."""
        return f"""
        Analise os seguintes dados de saúde e gere uma anamnese completa:
        
        DADOS DEMOGRÁFICOS:
        - Faixa etária: {dados.get('faixa_etaria', 'N/A')}
        - Sexo: {dados.get('sexo', 'N/A')}
        - Profissão: {dados.get('profissao', 'N/A')}
        - Região: {dados.get('regiao_cep', 'N/A')}
        - Possui plano de saúde: {dados.get('possui_plano_saude', 'N/A')}
        
        CONDIÇÕES CRÔNICAS PREEXISTENTES:
        - Hipertensão: {dados.get('condicoes_cronicas_previas', {}).get('hipertensao', 'Não')}
        - Diabetes: {dados.get('condicoes_cronicas_previas', {}).get('diabetes', 'Não')}
        - Doença cardíaca: {dados.get('condicoes_cronicas_previas', {}).get('doenca_cardiaca', 'Não')}
        - Doença renal: {dados.get('condicoes_cronicas_previas', {}).get('doenca_renal', 'Não')}
        - Asma: {dados.get('condicoes_cronicas_previas', {}).get('asma', 'Não')}
        - Depressão/Ansiedade: {dados.get('condicoes_cronicas_previas', {}).get('depressao_ansiedade', 'Não')}
        
        MEDICAMENTOS E ALERGIAS CONHECIDAS:
        - Medicamentos de uso contínuo: {dados.get('medicamentos_e_alergias', {}).get('medicamentos_continuo', 'Nenhum')}
        - Alergias conhecidas: {dados.get('medicamentos_e_alergias', {}).get('alergias_conhecidas', 'Nenhuma')}
        - Cirurgias anteriores: {dados.get('medicamentos_e_alergias', {}).get('cirurgias_anteriores', 'Nenhuma')}
        
        DADOS VITAIS ATUAIS:
        - Pressão arterial: {dados.get('sinais_vitais', {}).get('pressao_arterial', 'N/A')}
        - Frequência cardíaca: {dados.get('sinais_vitais', {}).get('frequencia_cardiaca', 'N/A')}
        - Temperatura: {dados.get('sinais_vitais', {}).get('temperatura', 'N/A')}
        - IMC: {dados.get('antropometria', {}).get('imc', 'N/A')} ({dados.get('antropometria', {}).get('classificacao_imc', 'N/A')})
        
        SINTOMAS ATUAIS:
        {dados.get('sintomas', {}).get('principais', 'Não informado')}
        - Nível de dor: {dados.get('sintomas', {}).get('nivel_dor', 'N/A')}/10
        - Duração dos sintomas: {dados.get('sintomas', {}).get('duracao', 'N/A')}
        
        HISTÓRICO MÉDICO ATUAL:
        - Doenças/condições relatadas hoje: {dados.get('historico', {}).get('doencas', 'Não informado')}
        - Medicamentos em uso hoje: {dados.get('historico', {}).get('medicamentos', 'Não informado')}
        - Alergias reportadas: {dados.get('historico', {}).get('alergias', 'Não informado')}
        
        HÁBITOS DE VIDA:
        - Fumante: {dados.get('habitos', {}).get('fumante', 'N/A')}
        - Etilista: {dados.get('habitos', {}).get('etilista', 'N/A')}
        - Atividade física: {dados.get('habitos', {}).get('atividade_fisica', 'N/A')}
        - Horas de sono: {dados.get('habitos', {}).get('horas_sono', 'N/A')}
        - Alimentação balanceada: {dados.get('habitos', {}).get('alimentacao_balanceada', 'N/A')}
        - Consumo de água: {dados.get('habitos', {}).get('consumo_agua', 'N/A')} litros/dia
        
        HISTÓRICO DE ANAMNESES ANTERIORES:
        {self._formatar_historico_anamneses(dados.get('historico_anamneses', []))}
        
        INSTRUÇÕES:
        1. Considere as condições crônicas preexistentes na análise
        2. Correlacione sintomas atuais com histórico médico
        3. Identifique possíveis agravamentos de condições crônicas
        4. Avalie interações medicamentosas potenciais
        5. Forneça uma anamnese estruturada em formato JSON com:
           - resumo_anamnese (máximo 200 palavras)
           - hipoteses_diagnosticas (lista ordenada por probabilidade)
           - triagem_risco (baixo/medio/alto/critico)
           - recomendacoes (ações sugeridas)
           - observacoes_especiais (alertas importantes baseados no histórico)
        """
    
    def _formatar_historico_anamneses(self, historico: List[Dict]) -> str:
        """Formata histórico de anamneses anteriores."""
        if not historico:
            return "Nenhuma anamnese anterior registrada."
        
        formatado = "Anamneses anteriores:\n"
        for i, anamnese in enumerate(historico[:3], 1):  # Máximo 3 mais recentes
            formatado += f"{i}. {anamnese.get('data', 'N/A')}: {anamnese.get('resumo', 'N/A')[:50]}...\n"
            formatado += f"   Risco: {anamnese.get('risco', 'N/A')}\n"
        
        return formatado
    
    def _construir_prompt_triagem(self, dados: Dict[str, Any]) -> str:
        """Constrói prompt para triagem de risco."""
        return f"""
        Classifique o risco médico baseado nos seguintes dados:
        
        APRESENTAÇÃO CLÍNICA:
        - Sintomas: {dados.get('sintomas', {}).get('principais', 'N/A')}
        - Dor: {dados.get('sintomas', {}).get('nivel_dor', 'N/A')}/10
        - Sinais vitais: PA {dados.get('sinais_vitais', {}).get('pressao_arterial', 'N/A')}, 
          FC {dados.get('sinais_vitais', {}).get('frequencia_cardiaca', 'N/A')}, 
          T {dados.get('sinais_vitais', {}).get('temperatura', 'N/A')}°C
        
        FATORES DE RISCO:
        - Idade: {dados.get('faixa_etaria', 'N/A')}
        - Comorbidades: {dados.get('historico', {}).get('doencas', 'N/A')}
        - Medicamentos: {dados.get('historico', {}).get('medicamentos', 'N/A')}
        
        Classifique o risco e justifique sua decisão.
        """
    
    def _construir_prompt_extracao(self, texto: str) -> str:
        """Constrói prompt para extração de dados."""
        return f"""
        Extraia dados estruturados do seguinte texto médico:
        
        TEXTO:
        {texto}
        
        Organize as informações em categorias estruturadas.
        """
    
    def _construir_prompt_agregacao(self, dados_lista: List[Dict]) -> str:
        """Constrói prompt para análise agregada."""
        resumo_dados = {
            'total_casos': len(dados_lista),
            'distribuicao_faixa_etaria': {},
            'sintomas_frequentes': {},
            'regioes': set()
        }
        
        # Analisa dados agregados
        for dado in dados_lista:
            faixa = dado.get('faixa_etaria', 'N/A')
            resumo_dados['distribuicao_faixa_etaria'][faixa] = \
                resumo_dados['distribuicao_faixa_etaria'].get(faixa, 0) + 1
            
            if dado.get('regiao_cep'):
                resumo_dados['regioes'].add(dado['regiao_cep'])
        
        return f"""
        Analise os seguintes dados agregados de saúde populacional:
        
        RESUMO ESTATÍSTICO:
        {json.dumps(resumo_dados, indent=2, default=str)}
        
        DADOS DETALHADOS:
        {json.dumps(dados_lista[:50], indent=2, default=str)}  # Limita a 50 registros
        
        Identifique padrões, tendências e forneça insights para políticas de saúde pública.
        """
    
    # Métodos de processamento de respostas
    
    def _processar_resposta_anamnese(self, resposta: str) -> Dict[str, Any]:
        """Processa resposta de anamnese da IA."""
        try:
            # Tenta parsear JSON
            resultado = json.loads(resposta)
            
            # Valida estrutura obrigatória
            campos_obrigatorios = [
                'resumo_anamnese', 'hipoteses_diagnosticas', 
                'triagem_risco', 'recomendacoes'
            ]
            
            for campo in campos_obrigatorios:
                if campo not in resultado:
                    raise ValueError(f"Campo obrigatório ausente: {campo}")
            
            # Valida triagem de risco
            if resultado['triagem_risco'] not in ['baixo', 'medio', 'alto', 'critico']:
                resultado['triagem_risco'] = 'medio'  # Default seguro
            
            return resultado
            
        except json.JSONDecodeError:
            # Fallback se não for JSON válido
            return {
                'resumo_anamnese': resposta[:200] + "..." if len(resposta) > 200 else resposta,
                'hipoteses_diagnosticas': [],
                'triagem_risco': 'medio',
                'recomendacoes': 'Avaliação médica recomendada',
                'exames_sugeridos': [],
                'sinais_alerta': []
            }
    
    def _processar_resposta_triagem(self, resposta: str) -> Dict[str, Any]:
        """Processa resposta de triagem da IA."""
        try:
            resultado = json.loads(resposta)
            
            # Valida risco
            if resultado.get('risco') not in ['baixo', 'medio', 'alto', 'critico']:
                resultado['risco'] = 'medio'
            
            return resultado
            
        except json.JSONDecodeError:
            return {
                'risco': 'medio',
                'justificativa': resposta,
                'tempo_recomendado': '24-48 horas',
                'sinais_criticos': [],
                'confianca': 0.5
            }
    
    def _processar_resposta_extracao(self, resposta: str) -> Dict[str, Any]:
        """Processa resposta de extração de dados."""
        try:
            return json.loads(resposta)
        except json.JSONDecodeError:
            return {
                'dados_nao_estruturados': resposta,
                'erro_parsing': True
            }
    
    def _processar_resposta_agregacao(self, resposta: str) -> Dict[str, Any]:
        """Processa resposta de análise agregada."""
        try:
            return json.loads(resposta)
        except json.JSONDecodeError:
            return {
                'analise_textual': resposta,
                'erro_parsing': True
            }
    
    # Métodos utilitários
    
    def _calcular_custo(self, tokens: int, modelo: str) -> float:
        """Calcula custo estimado da requisição."""
        # Preços aproximados (verificar preços atuais da OpenAI)
        precos = {
            'gpt-3.5-turbo': 0.002 / 1000,  # $0.002 per 1K tokens
            'gpt-4': 0.03 / 1000,           # $0.03 per 1K tokens
            'gpt-4-turbo': 0.01 / 1000      # $0.01 per 1K tokens
        }
        
        preco_por_token = precos.get(modelo, precos['gpt-3.5-turbo'])
        return tokens * preco_por_token
    
    def _calcular_confianca(self, resposta: Dict[str, Any]) -> float:
        """Calcula nível de confiança baseado na resposta."""
        confianca = 0.5  # Base
        
        # Aumenta confiança se há hipóteses bem estruturadas
        if resposta.get('hipoteses_diagnosticas'):
            confianca += 0.2
        
        # Aumenta se há recomendações específicas
        if resposta.get('recomendacoes') and len(resposta['recomendacoes']) > 50:
            confianca += 0.1
        
        # Aumenta se há exames sugeridos
        if resposta.get('exames_sugeridos'):
            confianca += 0.1
        
        return min(confianca, 0.95)  # Máximo 95%
    
    def _criar_log_auditoria(self, **kwargs):
        """Cria log de auditoria da operação de IA."""
        try:
            LogAuditoriaIA.objects.create(
                tipo_operacao=kwargs.get('tipo_operacao'),
                modelo_ia=kwargs.get('modelo'),
                prompt_enviado=kwargs.get('prompt', ''),
                dados_entrada=kwargs.get('dados_entrada', {}),
                resposta_ia=kwargs.get('resposta', {}),
                tempo_processamento=kwargs.get('tempo_processamento', timedelta(0)),
                sucesso=kwargs.get('sucesso', False),
                erro_detalhes=kwargs.get('erro_detalhes', ''),
                tokens_utilizados=kwargs.get('tokens_usados'),
                custo_estimado=kwargs.get('custo_estimado'),
                dados_anonimizados=True,
                usuario_id=kwargs.get('usuario_id')
            )
        except Exception as e:
            logger.error(f"Erro ao criar log de auditoria: {e}")