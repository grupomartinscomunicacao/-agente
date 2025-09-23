"""
Sistema de Cálculo de Risco de Saúde
Avalia múltiplos fatores para determinar nível de risco do cidadão
"""

import logging
from typing import Dict, Optional
from datetime import date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)


class CalculadorRisco:
    """Sistema inteligente de cálculo de risco de saúde."""
    
    def __init__(self):
        # Pesos para diferentes fatores de risco
        self.pesos = {
            'idade': 0.25,
            'condicoes_cronicas': 0.30,
            'sinais_vitais': 0.20,
            'sintomas': 0.15,
            'habitos': 0.10
        }
    
    def calcular_risco_cidadao(self, cidadao) -> Dict:
        """
        Calcula risco geral do cidadão baseado em todos os dados disponíveis.
        Prioriza o resultado da anamnese se disponível.
        
        Args:
            cidadao: Instância do modelo Cidadao
            
        Returns:
            Dict com nível de risco e pontuação detalhada
        """
        try:
            logger.info(f"Calculando risco para: {cidadao.nome}")
            
            # 1. PRIMEIRO: Verificar se existe anamnese com triagem de risco
            anamnese_mais_recente = cidadao.anamneses.filter(
                triagem_risco__isnull=False
            ).order_by('-criado_em').first()
            
            if anamnese_mais_recente and anamnese_mais_recente.triagem_risco:
                # Usar o risco da anamnese (mais confiável)
                nivel_anamnese = anamnese_mais_recente.triagem_risco.lower()
                
                # Converter para pontuação equivalente para manter consistência
                pontuacao_anamnese = {
                    'baixo': 20.0,
                    'medio': 50.0, 
                    'alto': 80.0,
                    'critico': 95.0
                }.get(nivel_anamnese, 20.0)
                
                resultado = {
                    'nivel': nivel_anamnese,
                    'pontuacao': pontuacao_anamnese,
                    'detalhes': {
                        'fonte_anamnese': True,
                        'anamnese_id': str(anamnese_mais_recente.id),
                        'data_anamnese': anamnese_mais_recente.criado_em.isoformat()
                    },
                    'fonte': 'anamnese_ia'
                }
                
                logger.info(f"Risco da anamnese para {cidadao.nome}: {nivel_anamnese.upper()} ({pontuacao_anamnese})")
                return resultado
            
            # 2. FALLBACK: Usar cálculo automático se não há anamnese
            logger.info(f"Nenhuma anamnese encontrada para {cidadao.nome}, usando cálculo automático")
            
            pontuacao_total = 0
            detalhes = {}
            
            # Fator idade
            pontuacao_idade = self._calcular_risco_idade(cidadao)
            pontuacao_total += pontuacao_idade * self.pesos['idade']
            detalhes['idade'] = pontuacao_idade
            
            # Condições crônicas (do modelo Cidadao)
            pontuacao_cronicas = self._calcular_risco_condicoes_cronicas(cidadao)
            pontuacao_total += pontuacao_cronicas * self.pesos['condicoes_cronicas']
            detalhes['condicoes_cronicas'] = pontuacao_cronicas
            
            # Últimos dados de saúde
            ultimo_dados_saude = cidadao.dados_saude.order_by('-criado_em').first()
            if ultimo_dados_saude:
                pontuacao_vitais = self._calcular_risco_sinais_vitais(ultimo_dados_saude)
                pontuacao_sintomas = self._calcular_risco_sintomas(ultimo_dados_saude)
                pontuacao_habitos = self._calcular_risco_habitos(ultimo_dados_saude)
                
                pontuacao_total += pontuacao_vitais * self.pesos['sinais_vitais']
                pontuacao_total += pontuacao_sintomas * self.pesos['sintomas']
                pontuacao_total += pontuacao_habitos * self.pesos['habitos']
                
                detalhes['sinais_vitais'] = pontuacao_vitais
                detalhes['sintomas'] = pontuacao_sintomas
                detalhes['habitos'] = pontuacao_habitos
            else:
                logger.info(f"Nenhum dado de saúde encontrado para {cidadao.nome}")
                detalhes['sinais_vitais'] = 0
                detalhes['sintomas'] = 0
                detalhes['habitos'] = 0
            
            # Normalizar pontuação (0-100)
            pontuacao_final = min(100, max(0, pontuacao_total))
            nivel = self._determinar_nivel_risco(pontuacao_final)
            
            resultado = {
                'nivel': nivel,
                'pontuacao': round(pontuacao_final, 1),
                'detalhes': detalhes,
                'fonte': 'calculo_automatico'
            }
            
            logger.info(f"Risco calculado para {cidadao.nome}: {nivel} ({pontuacao_final:.1f})")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular risco para {cidadao.nome}: {e}")
            return {
                'nivel': 'baixo',
                'pontuacao': 0,
                'detalhes': {},
                'fonte': 'erro_calculo'
            }
    
    def _calcular_risco_idade(self, cidadao) -> float:
        """Calcula risco baseado na idade (0-100)."""
        try:
            if not cidadao.data_nascimento:
                return 10  # Risco baixo por falta de dados
            
            hoje = date.today()
            idade = hoje.year - cidadao.data_nascimento.year
            
            if hoje.month < cidadao.data_nascimento.month or \
               (hoje.month == cidadao.data_nascimento.month and hoje.day < cidadao.data_nascimento.day):
                idade -= 1
            
            # Escala de risco por idade
            if idade < 18:
                return 5
            elif idade < 30:
                return 10
            elif idade < 45:
                return 20
            elif idade < 60:
                return 35
            elif idade < 75:
                return 55
            else:
                return 75
                
        except Exception as e:
            logger.error(f"Erro ao calcular risco idade: {e}")
            return 10
    
    def _calcular_risco_condicoes_cronicas(self, cidadao) -> float:
        """Calcula risco baseado em condições crônicas (0-100)."""
        try:
            pontuacao = 0
            
            # Condições de alto risco
            if getattr(cidadao, 'possui_diabetes', False):
                pontuacao += 25
            if getattr(cidadao, 'possui_hipertensao', False):
                pontuacao += 20
            if getattr(cidadao, 'possui_doenca_cardiaca', False):
                pontuacao += 30
            if getattr(cidadao, 'possui_doenca_renal', False):
                pontuacao += 25
            
            # Condições de médio risco
            if getattr(cidadao, 'possui_asma', False):
                pontuacao += 15
            if getattr(cidadao, 'possui_depressao', False):
                pontuacao += 10
            
            return min(100, pontuacao)
            
        except Exception as e:
            logger.error(f"Erro ao calcular risco condições crônicas: {e}")
            return 0
    
    def _calcular_risco_sinais_vitais(self, dados_saude) -> float:
        """Calcula risco baseado em sinais vitais (0-100)."""
        try:
            pontuacao = 0
            
            # Pressão arterial
            sistolica = dados_saude.pressao_sistolica
            diastolica = dados_saude.pressao_diastolica
            
            if sistolica >= 180 or diastolica >= 110:
                pontuacao += 40  # Hipertensão grave
            elif sistolica >= 140 or diastolica >= 90:
                pontuacao += 25  # Hipertensão
            elif sistolica >= 130 or diastolica >= 80:
                pontuacao += 10  # Pré-hipertensão
            
            # Frequência cardíaca
            fc = dados_saude.frequencia_cardiaca
            if fc > 100 or fc < 50:
                pontuacao += 20
            elif fc > 90 or fc < 60:
                pontuacao += 10
            
            # Temperatura
            temp = float(dados_saude.temperatura)
            if temp >= 39.0:
                pontuacao += 25  # Febre alta
            elif temp >= 37.5:
                pontuacao += 15  # Febre
            elif temp <= 35.0:
                pontuacao += 20  # Hipotermia
            
            # IMC
            peso = float(dados_saude.peso)
            altura = float(dados_saude.altura)
            imc = peso / (altura ** 2)
            
            if imc >= 35:
                pontuacao += 20  # Obesidade severa
            elif imc >= 30:
                pontuacao += 15  # Obesidade
            elif imc >= 25:
                pontuacao += 5   # Sobrepeso
            elif imc < 18.5:
                pontuacao += 10  # Baixo peso
            
            return min(100, pontuacao)
            
        except Exception as e:
            logger.error(f"Erro ao calcular risco sinais vitais: {e}")
            return 0
    
    def _calcular_risco_sintomas(self, dados_saude) -> float:
        """Calcula risco baseado em sintomas (0-100)."""
        try:
            pontuacao = 0
            
            # Nível de dor
            nivel_dor = dados_saude.nivel_dor
            if nivel_dor >= 8:
                pontuacao += 30
            elif nivel_dor >= 6:
                pontuacao += 20
            elif nivel_dor >= 4:
                pontuacao += 10
            
            # Sintomas críticos (busca por palavras-chave)
            sintomas = dados_saude.sintomas_principais.lower()
            sintomas_criticos = [
                'dor no peito', 'falta de ar', 'tontura severa', 
                'desmaio', 'convulsao', 'sangramento', 'vomito',
                'dor abdominal intensa'
            ]
            
            for sintoma in sintomas_criticos:
                if sintoma in sintomas:
                    pontuacao += 15
            
            return min(100, pontuacao)
            
        except Exception as e:
            logger.error(f"Erro ao calcular risco sintomas: {e}")
            return 0
    
    def _calcular_risco_habitos(self, dados_saude) -> float:
        """Calcula risco baseado em hábitos (0-100)."""
        try:
            pontuacao = 0
            
            # Fumo
            if dados_saude.fumante:
                pontuacao += 25
            
            # Consumo de álcool (se campo existir)
            if hasattr(dados_saude, 'consumo_alcool'):
                consumo = getattr(dados_saude, 'consumo_alcool', 'nao_informado')
                if consumo in ['diario', 'frequente']:
                    pontuacao += 20
                elif consumo in ['eventual', 'social']:
                    pontuacao += 5
            
            # Atividade física
            if hasattr(dados_saude, 'nivel_atividade'):
                atividade = getattr(dados_saude, 'nivel_atividade', 'sedentario')
                if atividade == 'sedentario':
                    pontuacao += 15
                elif atividade == 'leve':
                    pontuacao += 5
            
            return min(100, pontuacao)
            
        except Exception as e:
            logger.error(f"Erro ao calcular risco hábitos: {e}")
            return 0
    
    def _determinar_nivel_risco(self, pontuacao: float) -> str:
        """Determina nível de risco baseado na pontuação."""
        if pontuacao >= 70:
            return 'critico'
        elif pontuacao >= 50:
            return 'alto'
        elif pontuacao >= 25:
            return 'medio'
        else:
            return 'baixo'


# Instância global do calculador
calculador_risco = CalculadorRisco()


def calcular_risco_cidadao(cidadao) -> Dict:
    """
    Função de conveniência para calcular risco de um cidadão.
    
    Args:
        cidadao: Instância do modelo Cidadao
        
    Returns:
        Dict com nível de risco e detalhes
    """
    return calculador_risco.calcular_risco_cidadao(cidadao)