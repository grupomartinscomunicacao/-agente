"""
Utilidades para conformidade com LGPD (Lei Geral de Proteção de Dados).
"""
import hashlib
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class AnonimizadorLGPD:
    """Classe para anonimização de dados pessoais conforme LGPD."""
    
    @staticmethod
    def anonimizar_cpf(cpf: str) -> str:
        """
        Anonimiza CPF mantendo apenas os últimos 4 dígitos.
        Ex: 123.456.789-10 -> ***.***.***-10
        """
        if not cpf:
            return ""
        
        cpf_limpo = re.sub(r'[^\d]', '', cpf)
        if len(cpf_limpo) != 11:
            return "***.***.***-**"
        
        return f"***.***.***-{cpf_limpo[-2:]}"
    
    @staticmethod
    def anonimizar_nome(nome: str) -> str:
        """
        Anonimiza nome mantendo apenas as iniciais.
        Ex: João Silva Santos -> J. S. S.
        """
        if not nome:
            return ""
        
        palavras = nome.strip().split()
        iniciais = []
        
        for palavra in palavras:
            if len(palavra) > 0:
                iniciais.append(f"{palavra[0].upper()}.")
        
        return " ".join(iniciais)
    
    @staticmethod
    def anonimizar_email(email: str) -> str:
        """
        Anonimiza email mantendo apenas a primeira letra e domínio.
        Ex: joao@email.com -> j***@email.com
        """
        if not email or '@' not in email:
            return "***@***.***"
        
        usuario, dominio = email.split('@', 1)
        if len(usuario) > 0:
            return f"{usuario[0]}***@{dominio}"
        return f"***@{dominio}"
    
    @staticmethod
    def anonimizar_telefone(telefone: str) -> str:
        """
        Anonimiza telefone mantendo apenas os últimos 4 dígitos.
        Ex: (11) 99999-9999 -> (11) ****-9999
        """
        if not telefone:
            return ""
        
        # Extrai apenas números
        numeros = re.sub(r'[^\d]', '', telefone)
        
        if len(numeros) >= 10:
            # Mantém DDD e últimos 4 dígitos
            ddd = numeros[:2]
            final = numeros[-4:]
            return f"({ddd}) ****-{final}"
        
        return "(**) ****-****"
    
    @staticmethod
    def anonimizar_endereco(endereco: str) -> str:
        """
        Anonimiza endereço mantendo apenas o bairro/cidade.
        """
        if not endereco:
            return ""
        
        # Remove números e mantém apenas palavras importantes
        endereco_limpo = re.sub(r'\d+', '***', endereco)
        return endereco_limpo
    
    @staticmethod
    def gerar_hash_anonimo(valor: str, salt: Optional[str] = None) -> str:
        """
        Gera hash SHA-256 para anonimização irreversível.
        """
        if not valor:
            return ""
        
        if not salt:
            salt = getattr(settings, 'LGPD_SALT', 'default_salt_key')
        
        combined = f"{valor}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]


class GeradorPseudonimoLGPD:
    """Gerador de pseudônimos para substituir dados pessoais."""
    
    NOMES_MASCULINOS = [
        "Alberto", "Bruno", "Carlos", "Daniel", "Eduardo", "Fernando", 
        "Gabriel", "Henrique", "Igor", "João", "Lucas", "Marcos",
        "Nicolas", "Pedro", "Rafael", "Sérgio", "Thiago", "Vinícius"
    ]
    
    NOMES_FEMININOS = [
        "Ana", "Beatriz", "Carla", "Daniela", "Elena", "Fernanda",
        "Gabriela", "Helena", "Isabela", "Juliana", "Larissa", "Mariana",
        "Natália", "Paula", "Rafaela", "Sofia", "Tatiana", "Vanessa"
    ]
    
    SOBRENOMES = [
        "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira",
        "Alves", "Pereira", "Lima", "Gomes", "Costa", "Ribeiro",
        "Martins", "Carvalho", "Barbosa", "Rocha", "Dias", "Monteiro"
    ]
    
    @classmethod
    def gerar_nome_pseudonimo(cls, sexo: str = 'M') -> str:
        """Gera um nome pseudônimo baseado no sexo."""
        if sexo.upper() == 'F':
            nome = secrets.choice(cls.NOMES_FEMININOS)
        else:
            nome = secrets.choice(cls.NOMES_MASCULINOS)
        
        sobrenome = secrets.choice(cls.SOBRENOMES)
        return f"{nome} {sobrenome}"
    
    @classmethod
    def gerar_cpf_pseudonimo(cls) -> str:
        """Gera um CPF fictício para pseudonimização."""
        # Gera números aleatórios mas mantém formato válido
        base = ''.join([str(secrets.randbelow(10)) for _ in range(9)])
        
        # Calcula dígitos verificadores fictícios
        d1 = secrets.randbelow(10)
        d2 = secrets.randbelow(10)
        
        cpf = f"{base}{d1}{d2}"
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    
    @classmethod
    def gerar_telefone_pseudonimo(cls) -> str:
        """Gera um telefone fictício."""
        ddd = secrets.choice(['11', '21', '31', '41', '51', '61', '71', '81', '85'])
        numero = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
        return f"({ddd}) 9{numero[:4]}-{numero[4:]}"


class AuditoriaLGPD:
    """Sistema de auditoria para conformidade LGPD."""
    
    TIPOS_ACAO = [
        'ACESSO_DADOS',
        'MODIFICACAO_DADOS', 
        'EXCLUSAO_DADOS',
        'ANONIMIZACAO_DADOS',
        'EXPORTACAO_DADOS',
        'CONSENTIMENTO_DADO',
        'CONSENTIMENTO_REVOGADO',
        'VIOLACAO_DADOS'
    ]
    
    @staticmethod
    def registrar_acesso(
        usuario_id: int,
        cidadao_id: str,
        tipo_acao: str,
        detalhes: Dict[str, Any] = None,
        ip_address: str = None
    ) -> None:
        """Registra um acesso aos dados para auditoria."""
        try:
            log_entry = {
                'timestamp': timezone.now().isoformat(),
                'usuario_id': usuario_id,
                'cidadao_id': cidadao_id,
                'tipo_acao': tipo_acao,
                'detalhes': detalhes or {},
                'ip_address': ip_address,
                'session_id': None  # Pode ser preenchido conforme necessário
            }
            
            # Log para arquivo
            logger.info(f"LGPD_AUDIT: {log_entry}")
            
            # Cache para análise rápida
            cache_key = f"lgpd_audit_{cidadao_id}_{tipo_acao}"
            cache.set(cache_key, log_entry, timeout=86400)  # 24 horas
            
        except Exception as e:
            logger.error(f"Erro ao registrar auditoria LGPD: {e}")
    
    @staticmethod
    def obter_historico_acesso(cidadao_id: str, dias: int = 30) -> List[Dict]:
        """Obtém histórico de acessos aos dados de um cidadão."""
        # Em produção, isso viria de um banco de dados de auditoria
        # Por agora, retorna estrutura de exemplo
        return [
            {
                'timestamp': timezone.now().isoformat(),
                'usuario': 'Sistema',
                'acao': 'ACESSO_DADOS',
                'detalhes': 'Consulta para geração de anamnese'
            }
        ]
    
    @staticmethod
    def detectar_acessos_suspeitos(cidadao_id: str) -> List[Dict]:
        """Detecta padrões de acesso suspeitos."""
        suspeitos = []
        
        # Implementar lógica de detecção
        # Ex: muitos acessos em pouco tempo, acessos fora do horário, etc.
        
        return suspeitos


class ConsentimentoLGPD:
    """Gerenciamento de consentimento para tratamento de dados."""
    
    FINALIDADES = {
        'ATENDIMENTO_MEDICO': 'Atendimento médico e cuidados de saúde',
        'PESQUISA_CIENTIFICA': 'Pesquisa científica em saúde pública',
        'ESTATISTICAS_PUBLICAS': 'Estatísticas e análises de saúde pública',
        'INTELIGENCIA_ARTIFICIAL': 'Processamento por IA para diagnóstico',
        'COMUNICACAO_EMERGENCIA': 'Comunicação em casos de emergência'
    }
    
    @staticmethod
    def registrar_consentimento(
        cidadao_id: str,
        finalidades: List[str],
        ip_address: str = None,
        user_agent: str = None
    ) -> Dict[str, Any]:
        """Registra consentimento do cidadão."""
        consentimento = {
            'cidadao_id': cidadao_id,
            'finalidades_consentidas': finalidades,
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'user_agent': user_agent,
            'token_consentimento': secrets.token_urlsafe(32),
            'valido_ate': (timezone.now() + timedelta(days=365)).isoformat()
        }
        
        # Salvar em cache/banco
        cache_key = f"consentimento_{cidadao_id}"
        cache.set(cache_key, consentimento, timeout=31536000)  # 1 ano
        
        # Auditoria
        AuditoriaLGPD.registrar_acesso(
            usuario_id=0,
            cidadao_id=cidadao_id,
            tipo_acao='CONSENTIMENTO_DADO',
            detalhes={'finalidades': finalidades},
            ip_address=ip_address
        )
        
        return consentimento
    
    @staticmethod
    def verificar_consentimento(cidadao_id: str, finalidade: str) -> bool:
        """Verifica se há consentimento válido para uma finalidade."""
        cache_key = f"consentimento_{cidadao_id}"
        consentimento = cache.get(cache_key)
        
        if not consentimento:
            return False
        
        # Verifica se não expirou
        valido_ate = datetime.fromisoformat(consentimento['valido_ate'].replace('Z', '+00:00'))
        if timezone.now() > valido_ate:
            return False
        
        # Verifica se a finalidade foi consentida
        return finalidade in consentimento.get('finalidades_consentidas', [])
    
    @staticmethod
    def revogar_consentimento(cidadao_id: str, finalidades: List[str] = None) -> None:
        """Revoga consentimento (total ou parcial)."""
        cache_key = f"consentimento_{cidadao_id}"
        consentimento = cache.get(cache_key)
        
        if consentimento:
            if finalidades:
                # Revogação parcial
                for finalidade in finalidades:
                    if finalidade in consentimento['finalidades_consentidas']:
                        consentimento['finalidades_consentidas'].remove(finalidade)
                
                cache.set(cache_key, consentimento, timeout=31536000)
            else:
                # Revogação total
                cache.delete(cache_key)
            
            # Auditoria
            AuditoriaLGPD.registrar_acesso(
                usuario_id=0,
                cidadao_id=cidadao_id,
                tipo_acao='CONSENTIMENTO_REVOGADO',
                detalhes={'finalidades_revogadas': finalidades or 'TODAS'}
            )


class RelatorioLGPD:
    """Geração de relatórios para conformidade LGPD."""
    
    @staticmethod
    def gerar_relatorio_dados_cidadao(cidadao_id: str) -> Dict[str, Any]:
        """Gera relatório completo dos dados de um cidadão."""
        from cidadaos.models import Cidadao
        from saude_dados.models import DadosSaude
        from anamneses.models import Anamnese
        
        try:
            cidadao = Cidadao.objects.get(id=cidadao_id)
            
            relatorio = {
                'cidadao': {
                    'nome': cidadao.nome,
                    'cpf': AnonimizadorLGPD.anonimizar_cpf(cidadao.cpf),
                    'email': AnonimizadorLGPD.anonimizar_email(cidadao.email),
                    'telefone': AnonimizadorLGPD.anonimizar_telefone(cidadao.telefone),
                    'data_cadastro': cidadao.criado_em.isoformat()
                },
                'dados_saude': [],
                'anamneses': [],
                'historico_acessos': AuditoriaLGPD.obter_historico_acesso(cidadao_id),
                'consentimentos': ConsentimentoLGPD.verificar_consentimento(cidadao_id, 'ATENDIMENTO_MEDICO'),
                'gerado_em': timezone.now().isoformat()
            }
            
            # Dados de saúde
            for dados in DadosSaude.objects.filter(cidadao=cidadao):
                relatorio['dados_saude'].append({
                    'data_coleta': dados.criado_em.isoformat(),
                    'sintomas': dados.sintomas_principais[:100] + '...' if dados.sintomas_principais else '',
                    'pressao': f"{dados.pressao_sistolica}/{dados.pressao_diastolica}" if dados.pressao_sistolica else '',
                    'peso': dados.peso,
                    'altura': dados.altura
                })
            
            # Anamneses
            for anamnese in Anamnese.objects.filter(cidadao=cidadao):
                relatorio['anamneses'].append({
                    'data': anamnese.criado_em.isoformat(),
                    'status': anamnese.status,
                    'triagem_risco': anamnese.triagem_risco,
                    'resumo': anamnese.resumo_anamnese[:200] + '...' if anamnese.resumo_anamnese else ''
                })
            
            return relatorio
            
        except Exception as e:
            logger.error(f"Erro ao gerar relatório LGPD: {e}")
            return {'erro': str(e)}
    
    @staticmethod
    def gerar_relatorio_conformidade() -> Dict[str, Any]:
        """Gera relatório geral de conformidade LGPD."""
        from cidadaos.models import Cidadao
        from anamneses.models import Anamnese
        
        total_cidadaos = Cidadao.objects.count()
        total_anamneses = Anamnese.objects.count()
        
        return {
            'total_cidadaos_cadastrados': total_cidadaos,
            'total_anamneses_processadas': total_anamneses,
            'cidadaos_com_consentimento': 0,  # Implementar contagem real
            'acessos_suspeitos_detectados': 0,  # Implementar detecção
            'violacoes_reportadas': 0,  # Implementar sistema de violações
            'ultima_auditoria': timezone.now().isoformat(),
            'politicas_vigentes': [
                'Política de Privacidade v1.0',
                'Termo de Consentimento v1.0',
                'Procedimento de Anonimização v1.0'
            ]
        }