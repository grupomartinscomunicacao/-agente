"""
Utilitários para validação e normalização de dados de saúde.
Corrige erros de digitação comuns e valida formatos.
"""
import re
import unicodedata
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple


class ValidadorDados:
    """Classe para validação de dados de saúde."""
    
    @staticmethod
    def validar_cpf(cpf: str) -> Tuple[bool, str]:
        """
        Valida e normaliza CPF.
        
        Args:
            cpf: CPF a ser validado
            
        Returns:
            Tuple[bool, str]: (é_válido, cpf_normalizado)
        """
        # Remove caracteres não numéricos
        cpf_limpo = re.sub(r'[^0-9]', '', cpf)
        
        # Verifica se tem 11 dígitos
        if len(cpf_limpo) != 11:
            return False, cpf
        
        # Verifica se todos os dígitos são iguais
        if cpf_limpo == cpf_limpo[0] * 11:
            return False, cpf
        
        # Validação dos dígitos verificadores
        def calcular_digito(cpf_parcial, peso_inicial):
            soma = sum(int(cpf_parcial[i]) * (peso_inicial - i) for i in range(len(cpf_parcial)))
            resto = soma % 11
            return 0 if resto < 2 else 11 - resto
        
        # Primeiro dígito
        primeiro_digito = calcular_digito(cpf_limpo[:9], 10)
        if int(cpf_limpo[9]) != primeiro_digito:
            return False, cpf
        
        # Segundo dígito
        segundo_digito = calcular_digito(cpf_limpo[:10], 11)
        if int(cpf_limpo[10]) != segundo_digito:
            return False, cpf
        
        # Formata CPF
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        return True, cpf_formatado
    
    @staticmethod
    def validar_telefone(telefone: str) -> Tuple[bool, str]:
        """
        Valida e normaliza número de telefone.
        
        Args:
            telefone: Telefone a ser validado
            
        Returns:
            Tuple[bool, str]: (é_válido, telefone_normalizado)
        """
        # Remove caracteres não numéricos
        tel_limpo = re.sub(r'[^0-9]', '', telefone)
        
        # Verifica se tem 10 ou 11 dígitos
        if len(tel_limpo) not in [10, 11]:
            return False, telefone
        
        # Adiciona 9 se for celular sem o 9
        if len(tel_limpo) == 10 and tel_limpo[2] in '6789':
            tel_limpo = tel_limpo[:2] + '9' + tel_limpo[2:]
        
        # Formata telefone
        if len(tel_limpo) == 11:
            tel_formatado = f"({tel_limpo[:2]}) {tel_limpo[2:7]}-{tel_limpo[7:]}"
        else:
            tel_formatado = f"({tel_limpo[:2]}) {tel_limpo[2:6]}-{tel_limpo[6:]}"
        
        return True, tel_formatado
    
    @staticmethod
    def validar_cep(cep: str) -> Tuple[bool, str]:
        """
        Valida e normaliza CEP.
        
        Args:
            cep: CEP a ser validado
            
        Returns:
            Tuple[bool, str]: (é_válido, cep_normalizado)
        """
        # Remove caracteres não numéricos
        cep_limpo = re.sub(r'[^0-9]', '', cep)
        
        # Verifica se tem 8 dígitos
        if len(cep_limpo) != 8:
            return False, cep
        
        # Formata CEP
        cep_formatado = f"{cep_limpo[:5]}-{cep_limpo[5:]}"
        return True, cep_formatado
    
    @staticmethod
    def validar_pressao_arterial(pressao: str) -> Tuple[bool, Dict[str, int]]:
        """
        Valida pressão arterial no formato sistólica/diastólica.
        
        Args:
            pressao: Pressão arterial (ex: "120/80", "120x80", "120 80")
            
        Returns:
            Tuple[bool, Dict]: (é_válido, {"sistolica": int, "diastolica": int})
        """
        # Padrões aceitos para separadores
        separadores = re.findall(r'(\d+)[/x\s-]+(\d+)', pressao.replace(' ', ''))
        
        if not separadores:
            return False, {}
        
        try:
            sistolica = int(separadores[0][0])
            diastolica = int(separadores[0][1])
            
            # Validação dos valores
            if not (70 <= sistolica <= 250 and 40 <= diastolica <= 150):
                return False, {}
            
            if sistolica <= diastolica:
                return False, {}
            
            return True, {"sistolica": sistolica, "diastolica": diastolica}
            
        except (ValueError, IndexError):
            return False, {}
    
    @staticmethod
    def validar_data_nascimento(data: str) -> Tuple[bool, Optional[date]]:
        """
        Valida e converte data de nascimento.
        
        Args:
            data: Data em string (vários formatos aceitos)
            
        Returns:
            Tuple[bool, Optional[date]]: (é_válido, data_objeto)
        """
        formatos = [
            '%d/%m/%Y',
            '%d-%m-%Y',
            '%d.%m.%Y',
            '%Y-%m-%d',
            '%d/%m/%y',
            '%d-%m-%y'
        ]
        
        for formato in formatos:
            try:
                data_obj = datetime.strptime(data.strip(), formato).date()
                
                # Verifica se a data não é futura
                if data_obj > date.today():
                    return False, None
                
                # Verifica se a pessoa não tem mais de 150 anos
                idade = date.today().year - data_obj.year
                if idade > 150:
                    return False, None
                
                return True, data_obj
                
            except ValueError:
                continue
        
        return False, None


class NormalizadorTexto:
    """Classe para normalização de texto médico."""
    
    # Dicionário de correções comuns
    CORRECOES_COMUNS = {
        # Sintomas de dor
        'mta dor': 'muita dor',
        'mt dor': 'muita dor',
        'pouca dor': 'pouca dor',
        'nenhuma dor': 'sem dor',
        'sem dr': 'sem dor',
        'dor d cabeça': 'dor de cabeça',
        'dor d barriga': 'dor de barriga',
        'dor nas costa': 'dor nas costas',
        'dor no peito': 'dor no peito',
        
        # Sintomas gerais
        'febre alta': 'febre alta',
        'febr': 'febre',
        'tosse seca': 'tosse seca',
        'tosse c catarro': 'tosse com catarro',
        'falta d ar': 'falta de ar',
        'cansaço': 'cansaço',
        'cansaso': 'cansaço',
        'tontura': 'tontura',
        'tontera': 'tontura',
        'nausea': 'náusea',
        'vomito': 'vômito',
        'vomitos': 'vômitos',
        
        # Medicamentos
        'dipirona': 'dipirona',
        'paracetamol': 'paracetamol',
        'ibuprofeno': 'ibuprofeno',
        'aspirina': 'aspirina',
        'captopril': 'captopril',
        'losartana': 'losartana',
        'metformina': 'metformina',
        'insulina': 'insulina',
        
        # Doenças
        'diabetes': 'diabetes',
        'diabete': 'diabetes',
        'hipertensao': 'hipertensão',
        'pressao alta': 'pressão alta',
        'colesterol alto': 'colesterol alto',
        'asma': 'asma',
        'bronquite': 'bronquite',
        'pneumonia': 'pneumonia',
        
        # Negações e quantificadores
        'nao': 'não',
        'naum': 'não',
        'nunca': 'nunca',
        'sempre': 'sempre',
        'as vezes': 'às vezes',
        'de vez em quando': 'de vez em quando',
        'raramente': 'raramente',
        'frequentemente': 'frequentemente',
        
        # Intensificadores
        'muito': 'muito',
        'mto': 'muito',
        'mt': 'muito',
        'pouco': 'pouco',
        'bastante': 'bastante',
        'extremamente': 'extremamente',
        'levemente': 'levemente',
        'moderadamente': 'moderadamente',
    }
    
    @classmethod
    def normalizar_texto(cls, texto: str) -> str:
        """
        Normaliza texto corrigindo erros comuns.
        
        Args:
            texto: Texto a ser normalizado
            
        Returns:
            str: Texto normalizado
        """
        if not texto:
            return ""
        
        # Remove acentos e converte para minúsculas
        texto_normalizado = unicodedata.normalize('NFD', texto.lower())
        texto_normalizado = ''.join(c for c in texto_normalizado if unicodedata.category(c) != 'Mn')
        
        # Aplica correções comuns
        for erro, correcao in cls.CORRECOES_COMUNS.items():
            # Normaliza a correção também
            correcao_norm = unicodedata.normalize('NFD', correcao.lower())
            correcao_norm = ''.join(c for c in correcao_norm if unicodedata.category(c) != 'Mn')
            texto_normalizado = texto_normalizado.replace(erro, correcao_norm)
        
        # Remove espaços extras
        texto_normalizado = re.sub(r'\s+', ' ', texto_normalizado).strip()
        
        return texto_normalizado
    
    @classmethod
    def extrair_sintomas(cls, texto: str) -> list:
        """
        Extrai sintomas do texto normalizado.
        
        Args:
            texto: Texto contendo sintomas
            
        Returns:
            list: Lista de sintomas identificados
        """
        sintomas_conhecidos = [
            'dor de cabeça', 'dor no peito', 'dor nas costas', 'dor de barriga',
            'febre', 'tosse', 'falta de ar', 'cansaço', 'tontura', 'náusea',
            'vômito', 'diarreia', 'constipação', 'insônia', 'mal estar'
        ]
        
        texto_norm = cls.normalizar_texto(texto)
        sintomas_encontrados = []
        
        for sintoma in sintomas_conhecidos:
            sintoma_norm = cls.normalizar_texto(sintoma)
            if sintoma_norm in texto_norm:
                sintomas_encontrados.append(sintoma)
        
        return sintomas_encontrados


class ValidadorMedico:
    """Validações específicas para dados médicos."""
    
    @staticmethod
    def validar_imc(peso: float, altura: float) -> Tuple[bool, Optional[float], str]:
        """
        Calcula e valida IMC.
        
        Args:
            peso: Peso em kg
            altura: Altura em metros
            
        Returns:
            Tuple[bool, Optional[float], str]: (é_válido, imc, classificação)
        """
        if peso <= 0 or altura <= 0:
            return False, None, ""
        
        imc = peso / (altura ** 2)
        
        if imc < 16:
            classificacao = "Muito abaixo do peso"
        elif imc < 18.5:
            classificacao = "Abaixo do peso"
        elif imc < 25:
            classificacao = "Peso normal"
        elif imc < 30:
            classificacao = "Sobrepeso"
        elif imc < 35:
            classificacao = "Obesidade grau I"
        elif imc < 40:
            classificacao = "Obesidade grau II"
        else:
            classificacao = "Obesidade grau III"
        
        return True, round(imc, 2), classificacao
    
    @staticmethod
    def validar_sinais_vitais(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida sinais vitais e identifica valores de alerta.
        
        Args:
            dados: Dicionário com sinais vitais
            
        Returns:
            Dict: Dados validados com alertas
        """
        alertas = []
        
        # Pressão arterial
        if 'pressao_sistolica' in dados and 'pressao_diastolica' in dados:
            sistolica = dados['pressao_sistolica']
            diastolica = dados['pressao_diastolica']
            
            if sistolica >= 180 or diastolica >= 120:
                alertas.append("Crise hipertensiva - procurar atendimento imediato")
            elif sistolica >= 140 or diastolica >= 90:
                alertas.append("Hipertensão detectada")
            elif sistolica < 90 or diastolica < 60:
                alertas.append("Hipotensão detectada")
        
        # Frequência cardíaca
        if 'frequencia_cardiaca' in dados:
            fc = dados['frequencia_cardiaca']
            if fc > 100:
                alertas.append("Taquicardia detectada")
            elif fc < 60:
                alertas.append("Bradicardia detectada")
        
        # Temperatura
        if 'temperatura' in dados:
            temp = float(dados['temperatura'])
            if temp >= 38.0:
                alertas.append("Febre detectada")
            elif temp >= 39.0:
                alertas.append("Febre alta - atenção necessária")
            elif temp < 35.0:
                alertas.append("Hipotermia detectada")
        
        return {
            'dados_validados': dados,
            'alertas': alertas,
            'risco_detectado': len(alertas) > 0
        }


class AnonimizadorDados:
    """Classe para anonimização de dados conforme LGPD."""
    
    @staticmethod
    def anonimizar_dados_pessoais(dados: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove ou substitui dados pessoais identificáveis.
        
        Args:
            dados: Dados originais
            
        Returns:
            Dict: Dados anonimizados
        """
        campos_remover = ['nome', 'cpf', 'email', 'telefone', 'endereco']
        campos_generalizar = ['data_nascimento', 'cep']
        
        dados_anonimos = dados.copy()
        
        # Remove campos identificáveis
        for campo in campos_remover:
            if campo in dados_anonimos:
                del dados_anonimos[campo]
        
        # Generaliza dados sensíveis
        if 'data_nascimento' in dados_anonimos:
            # Substitui por faixa etária
            nascimento = dados_anonimos['data_nascimento']
            if isinstance(nascimento, str):
                nascimento = datetime.strptime(nascimento, '%Y-%m-%d').date()
            
            idade = date.today().year - nascimento.year
            
            if idade < 18:
                faixa_etaria = "menor_18"
            elif idade < 30:
                faixa_etaria = "18_29"
            elif idade < 50:
                faixa_etaria = "30_49"
            elif idade < 65:
                faixa_etaria = "50_64"
            else:
                faixa_etaria = "65_mais"
            
            dados_anonimos['faixa_etaria'] = faixa_etaria
            del dados_anonimos['data_nascimento']
        
        if 'cep' in dados_anonimos:
            # Mantém apenas os 3 primeiros dígitos
            cep = dados_anonimos['cep'].replace('-', '')
            dados_anonimos['regiao_cep'] = cep[:3] + "00-000"
            del dados_anonimos['cep']
        
        return dados_anonimos
    
    @staticmethod
    def hash_identificador(valor: str) -> str:
        """
        Cria hash irreversível para identificadores.
        
        Args:
            valor: Valor a ser hasheado
            
        Returns:
            str: Hash do valor
        """
        import hashlib
        return hashlib.sha256(valor.encode()).hexdigest()[:12]