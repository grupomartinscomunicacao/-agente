"""
Utilitários para processamento de dados médicos e formatação.
"""
import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class DadosEstruturados:
    """Estrutura para dados médicos processados."""
    dados_demograficos: Dict[str, Any]
    sinais_vitais: Dict[str, Any]
    sintomas: List[str]
    historico_medico: Dict[str, Any]
    habitos_vida: Dict[str, Any]
    alertas: List[str]
    risco_calculado: str


class ProcessadorDadosMedicos:
    """Processa e estrutura dados médicos para análise."""
    
    def __init__(self):
        self.sintomas_graves = {
            'dor no peito': 'alto',
            'falta de ar severa': 'alto',
            'perda de consciencia': 'alto',
            'sangramento intenso': 'alto',
            'dor abdominal intensa': 'alto',
            'febre muito alta': 'medio',
            'vomitos persistentes': 'medio',
            'dor de cabeça severa': 'medio',
        }
        
        self.medicamentos_controlados = [
            'warfarina', 'insulina', 'digoxina', 'lítio',
            'fenitoína', 'carbamazepina', 'amiodarona'
        ]
    
    def processar_dados_completos(self, dados_cidadao: Dict, dados_saude: Dict) -> DadosEstruturados:
        """
        Processa dados completos do cidadão e saúde.
        
        Args:
            dados_cidadao: Dados demográficos do cidadão
            dados_saude: Dados de saúde coletados
            
        Returns:
            DadosEstruturados: Dados processados e estruturados
        """
        # Processa dados demográficos
        demograficos = self._processar_demograficos(dados_cidadao)
        
        # Processa sinais vitais
        sinais_vitais = self._processar_sinais_vitais(dados_saude)
        
        # Extrai e processa sintomas
        sintomas = self._processar_sintomas(dados_saude.get('sintomas_principais', ''))
        
        # Processa histórico médico
        historico = self._processar_historico_medico(dados_saude)
        
        # Processa hábitos de vida
        habitos = self._processar_habitos_vida(dados_saude)
        
        # Gera alertas baseados nos dados
        alertas = self._gerar_alertas(sinais_vitais, sintomas, historico, habitos)
        
        # Calcula risco geral
        risco = self._calcular_risco_geral(sinais_vitais, sintomas, historico, alertas)
        
        return DadosEstruturados(
            dados_demograficos=demograficos,
            sinais_vitais=sinais_vitais,
            sintomas=sintomas,
            historico_medico=historico,
            habitos_vida=habitos,
            alertas=alertas,
            risco_calculado=risco
        )
    
    def _processar_demograficos(self, dados: Dict) -> Dict[str, Any]:
        """Processa dados demográficos."""
        from datetime import date
        
        demograficos = {}
        
        if 'data_nascimento' in dados:
            nascimento = dados['data_nascimento']
            if isinstance(nascimento, str):
                nascimento = datetime.strptime(nascimento, '%Y-%m-%d').date()
            
            idade = date.today().year - nascimento.year
            demograficos['idade'] = idade
            demograficos['faixa_etaria'] = self._classificar_faixa_etaria(idade)
        
        demograficos.update({
            'sexo': dados.get('sexo'),
            'estado_civil': dados.get('estado_civil'),
            'profissao': dados.get('profissao'),
            'cidade': dados.get('cidade'),
            'estado': dados.get('estado'),
            'possui_plano_saude': dados.get('possui_plano_saude', False)
        })
        
        return demograficos
    
    def _processar_sinais_vitais(self, dados: Dict) -> Dict[str, Any]:
        """Processa sinais vitais com validações."""
        sinais = {}
        
        # Pressão arterial
        if 'pressao_sistolica' in dados and 'pressao_diastolica' in dados:
            sistolica = dados['pressao_sistolica']
            diastolica = dados['pressao_diastolica']
            
            sinais['pressao_arterial'] = {
                'sistolica': sistolica,
                'diastolica': diastolica,
                'formatada': f"{sistolica}/{diastolica}",
                'classificacao': self._classificar_pressao(sistolica, diastolica)
            }
        
        # Frequência cardíaca
        if 'frequencia_cardiaca' in dados:
            fc = dados['frequencia_cardiaca']
            sinais['frequencia_cardiaca'] = {
                'valor': fc,
                'classificacao': self._classificar_frequencia_cardiaca(fc)
            }
        
        # Temperatura
        if 'temperatura' in dados:
            temp = float(dados['temperatura'])
            sinais['temperatura'] = {
                'valor': temp,
                'classificacao': self._classificar_temperatura(temp)
            }
        
        # IMC
        if 'peso' in dados and 'altura' in dados:
            peso = float(dados['peso'])
            altura = float(dados['altura'])
            imc = peso / (altura ** 2)
            
            sinais['antropometria'] = {
                'peso': peso,
                'altura': altura,
                'imc': round(imc, 2),
                'classificacao_imc': self._classificar_imc(imc)
            }
        
        return sinais
    
    def _processar_sintomas(self, texto_sintomas: str) -> List[str]:
        """Extrai e processa sintomas do texto."""
        from utils.validators import NormalizadorTexto
        
        if not texto_sintomas:
            return []
        
        # Normaliza texto
        texto_normalizado = NormalizadorTexto.normalizar_texto(texto_sintomas)
        
        # Extrai sintomas conhecidos
        sintomas = NormalizadorTexto.extrair_sintomas(texto_sintomas)
        
        # Adiciona sintomas do texto livre
        palavras_sintomas = [
            'dor', 'febre', 'tosse', 'cansaco', 'tontura', 
            'nausea', 'vomito', 'falta de ar', 'palpitacao'
        ]
        
        for palavra in palavras_sintomas:
            if palavra in texto_normalizado and palavra not in sintomas:
                sintomas.append(palavra)
        
        return sintomas
    
    def _processar_historico_medico(self, dados: Dict) -> Dict[str, Any]:
        """Processa histórico médico."""
        historico = {}
        
        # Doenças crônicas
        if 'historico_doencas' in dados:
            doencas_texto = dados['historico_doencas'].lower()
            doencas_conhecidas = [
                'diabetes', 'hipertensao', 'cardiopatia', 'asma',
                'bronquite', 'artrite', 'osteoporose', 'cancer'
            ]
            
            doencas_identificadas = []
            for doenca in doencas_conhecidas:
                if doenca in doencas_texto:
                    doencas_identificadas.append(doenca)
            
            historico['doencas_cronicas'] = doencas_identificadas
        
        # Medicamentos
        if 'medicamentos_uso' in dados:
            medicamentos_texto = dados['medicamentos_uso'].lower()
            medicamentos_controlados_encontrados = []
            
            for med in self.medicamentos_controlados:
                if med in medicamentos_texto:
                    medicamentos_controlados_encontrados.append(med)
            
            historico['medicamentos_controlados'] = medicamentos_controlados_encontrados
            historico['medicamentos_texto'] = dados['medicamentos_uso']
        
        # Alergias
        historico['alergias'] = dados.get('alergias', '')
        
        return historico
    
    def _processar_habitos_vida(self, dados: Dict) -> Dict[str, Any]:
        """Processa hábitos de vida."""
        habitos = {
            'fumante': dados.get('fumante', False),
            'etilista': dados.get('etilista', False),
            'atividade_fisica': dados.get('nivel_atividade_fisica', 'sedentario'),
            'horas_sono': dados.get('horas_sono', 8),
            'alimentacao_balanceada': dados.get('alimentacao_balanceada', False),
            'consumo_agua': float(dados.get('consumo_agua_litros', 2.0))
        }
        
        # Calcula score de hábitos saudáveis
        score = 0
        if not habitos['fumante']:
            score += 2
        if not habitos['etilista']:
            score += 1
        if habitos['atividade_fisica'] in ['moderada', 'intensa']:
            score += 2
        if 7 <= habitos['horas_sono'] <= 9:
            score += 1
        if habitos['alimentacao_balanceada']:
            score += 2
        if habitos['consumo_agua'] >= 1.5:
            score += 1
        
        habitos['score_habitos_saudaveis'] = score
        habitos['classificacao_habitos'] = self._classificar_habitos(score)
        
        return habitos
    
    def _gerar_alertas(self, sinais_vitais: Dict, sintomas: List[str], 
                      historico: Dict, habitos: Dict) -> List[str]:
        """Gera alertas baseados nos dados processados."""
        alertas = []
        
        # Alertas de sinais vitais
        if 'pressao_arterial' in sinais_vitais:
            pa = sinais_vitais['pressao_arterial']
            if pa['classificacao'] in ['hipertensao_estagio_2', 'crise_hipertensiva']:
                alertas.append(f"Pressão arterial elevada: {pa['formatada']} mmHg")
        
        if 'temperatura' in sinais_vitais:
            temp = sinais_vitais['temperatura']
            if temp['classificacao'] == 'febre_alta':
                alertas.append(f"Febre alta detectada: {temp['valor']}°C")
        
        # Alertas de sintomas
        for sintoma in sintomas:
            if sintoma in self.sintomas_graves:
                nivel_risco = self.sintomas_graves[sintoma]
                alertas.append(f"Sintoma de risco {nivel_risco}: {sintoma}")
        
        # Alertas de medicamentos controlados
        if historico.get('medicamentos_controlados'):
            alertas.append("Paciente usa medicamentos controlados - monitoramento necessário")
        
        # Alertas de hábitos
        if habitos.get('score_habitos_saudaveis', 0) < 3:
            alertas.append("Hábitos de vida não saudáveis detectados")
        
        return alertas
    
    def _calcular_risco_geral(self, sinais_vitais: Dict, sintomas: List[str],
                             historico: Dict, alertas: List[str]) -> str:
        """Calcula risco geral do paciente."""
        pontuacao_risco = 0
        
        # Pontuação por sinais vitais alterados
        if 'pressao_arterial' in sinais_vitais:
            classificacao_pa = sinais_vitais['pressao_arterial']['classificacao']
            if classificacao_pa == 'crise_hipertensiva':
                pontuacao_risco += 5
            elif classificacao_pa in ['hipertensao_estagio_2']:
                pontuacao_risco += 3
            elif classificacao_pa == 'hipertensao_estagio_1':
                pontuacao_risco += 2
        
        # Pontuação por sintomas
        for sintoma in sintomas:
            if sintoma in self.sintomas_graves:
                if self.sintomas_graves[sintoma] == 'alto':
                    pontuacao_risco += 4
                elif self.sintomas_graves[sintoma] == 'medio':
                    pontuacao_risco += 2
        
        # Pontuação por histórico
        doencas_cronicas = historico.get('doencas_cronicas', [])
        pontuacao_risco += len(doencas_cronicas)
        
        # Pontuação por medicamentos controlados
        if historico.get('medicamentos_controlados'):
            pontuacao_risco += 2
        
        # Classificação final
        if pontuacao_risco >= 8:
            return 'critico'
        elif pontuacao_risco >= 5:
            return 'alto'
        elif pontuacao_risco >= 2:
            return 'medio'
        else:
            return 'baixo'
    
    # Métodos auxiliares de classificação
    def _classificar_faixa_etaria(self, idade: int) -> str:
        """Classifica faixa etária."""
        if idade < 18:
            return "menor_18"
        elif idade < 30:
            return "18_29"
        elif idade < 50:
            return "30_49"
        elif idade < 65:
            return "50_64"
        else:
            return "65_mais"
    
    def _classificar_pressao(self, sistolica: int, diastolica: int) -> str:
        """Classifica pressão arterial."""
        if sistolica >= 180 or diastolica >= 120:
            return "crise_hipertensiva"
        elif sistolica >= 160 or diastolica >= 100:
            return "hipertensao_estagio_2"
        elif sistolica >= 140 or diastolica >= 90:
            return "hipertensao_estagio_1"
        elif sistolica >= 120 or diastolica >= 80:
            return "pre_hipertensao"
        else:
            return "normal"
    
    def _classificar_frequencia_cardiaca(self, fc: int) -> str:
        """Classifica frequência cardíaca."""
        if fc > 100:
            return "taquicardia"
        elif fc < 60:
            return "bradicardia"
        else:
            return "normal"
    
    def _classificar_temperatura(self, temp: float) -> str:
        """Classifica temperatura corporal."""
        if temp >= 39.0:
            return "febre_alta"
        elif temp >= 37.5:
            return "febre"
        elif temp < 35.0:
            return "hipotermia"
        else:
            return "normal"
    
    def _classificar_imc(self, imc: float) -> str:
        """Classifica IMC."""
        if imc < 18.5:
            return "abaixo_peso"
        elif imc < 25:
            return "normal"
        elif imc < 30:
            return "sobrepeso"
        else:
            return "obesidade"
    
    def _classificar_habitos(self, score: int) -> str:
        """Classifica hábitos de vida."""
        if score >= 7:
            return "muito_saudavel"
        elif score >= 5:
            return "saudavel"
        elif score >= 3:
            return "moderado"
        else:
            return "nao_saudavel"


class GeradorRelatorios:
    """Gera relatórios estruturados dos dados médicos."""
    
    @staticmethod
    def gerar_resumo_anamnese(dados_estruturados: DadosEstruturados) -> Dict[str, Any]:
        """
        Gera resumo estruturado para anamnese.
        
        Args:
            dados_estruturados: Dados processados
            
        Returns:
            Dict: Resumo estruturado
        """
        resumo = {
            'paciente': {
                'idade': dados_estruturados.dados_demograficos.get('idade'),
                'sexo': dados_estruturados.dados_demograficos.get('sexo'),
                'faixa_etaria': dados_estruturados.dados_demograficos.get('faixa_etaria')
            },
            'sinais_vitais': dados_estruturados.sinais_vitais,
            'sintomas_principais': dados_estruturados.sintomas,
            'historico_relevante': dados_estruturados.historico_medico,
            'habitos_vida': dados_estruturados.habitos_vida,
            'alertas_detectados': dados_estruturados.alertas,
            'classificacao_risco': dados_estruturados.risco_calculado,
            'recomendacoes_preliminares': GeradorRelatorios._gerar_recomendacoes(dados_estruturados)
        }
        
        return resumo
    
    @staticmethod
    def _gerar_recomendacoes(dados: DadosEstruturados) -> List[str]:
        """Gera recomendações baseadas nos dados."""
        recomendacoes = []
        
        # Recomendações por risco
        if dados.risco_calculado == 'critico':
            recomendacoes.append("Encaminhamento imediato para atendimento médico especializado")
        elif dados.risco_calculado == 'alto':
            recomendacoes.append("Consulta médica prioritária nas próximas 24h")
        elif dados.risco_calculado == 'medio':
            recomendacoes.append("Agendamento de consulta médica em até 7 dias")
        
        # Recomendações por sinais vitais
        if 'pressao_arterial' in dados.sinais_vitais:
            classificacao = dados.sinais_vitais['pressao_arterial']['classificacao']
            if classificacao in ['hipertensao_estagio_1', 'hipertensao_estagio_2']:
                recomendacoes.append("Monitoramento regular da pressão arterial")
                recomendacoes.append("Redução do consumo de sal e atividade física regular")
        
        # Recomendações por hábitos
        habitos = dados.habitos_vida
        if habitos.get('fumante'):
            recomendacoes.append("Cessação do tabagismo com suporte médico")
        
        if habitos.get('atividade_fisica') == 'sedentario':
            recomendacoes.append("Iniciar programa de atividade física gradual")
        
        if not habitos.get('alimentacao_balanceada'):
            recomendacoes.append("Orientação nutricional para dieta balanceada")
        
        return recomendacoes