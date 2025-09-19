"""
Serializers para a API REST do sistema de saúde.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from cidadaos.models import Cidadao, ContatoEmergencia
from saude_dados.models import DadosSaude, HistoricoSaude
from anamneses.models import Anamnese, LogAuditoriaIA, AlertaSaude
from dashboard.models import RelatorioSaude, EstatisticaTempoReal
from utils.validators import ValidadorDados, NormalizadorTexto, ValidadorMedico


class CidadaoSerializer(serializers.ModelSerializer):
    """Serializer para dados do cidadão."""
    idade = serializers.ReadOnlyField()
    
    class Meta:
        model = Cidadao
        fields = [
            'id', 'nome', 'cpf', 'data_nascimento', 'idade', 'sexo', 
            'estado_civil', 'telefone', 'email', 'endereco', 'cep', 
            'bairro', 'cidade', 'estado', 'profissao', 'renda_familiar',
            'possui_plano_saude', 'criado_em', 'ativo'
        ]
        read_only_fields = ['id', 'criado_em', 'idade']
    
    def validate_cpf(self, value):
        """Valida CPF."""
        valido, cpf_formatado = ValidadorDados.validar_cpf(value)
        if not valido:
            raise serializers.ValidationError("CPF inválido.")
        return cpf_formatado
    
    def validate_telefone(self, value):
        """Valida telefone."""
        valido, tel_formatado = ValidadorDados.validar_telefone(value)
        if not valido:
            raise serializers.ValidationError("Telefone inválido.")
        return tel_formatado
    
    def validate_cep(self, value):
        """Valida CEP."""
        valido, cep_formatado = ValidadorDados.validar_cep(value)
        if not valido:
            raise serializers.ValidationError("CEP inválido.")
        return cep_formatado


class ContatoEmergenciaSerializer(serializers.ModelSerializer):
    """Serializer para contatos de emergência."""
    
    class Meta:
        model = ContatoEmergencia
        fields = ['id', 'nome', 'parentesco', 'telefone']
        
    def validate_telefone(self, value):
        """Valida telefone do contato."""
        valido, tel_formatado = ValidadorDados.validar_telefone(value)
        if not valido:
            raise serializers.ValidationError("Telefone inválido.")
        return tel_formatado


class DadosSaudeSerializer(serializers.ModelSerializer):
    """Serializer para dados de saúde."""
    imc = serializers.ReadOnlyField()
    classificacao_imc = serializers.ReadOnlyField()
    dados_estruturados = serializers.ReadOnlyField(source='get_dados_estruturados')
    
    class Meta:
        model = DadosSaude
        fields = [
            'id', 'cidadao', 'agente_coleta', 'pressao_sistolica', 
            'pressao_diastolica', 'frequencia_cardiaca', 'temperatura',
            'peso', 'altura', 'imc', 'classificacao_imc', 'sintomas_principais',
            'nivel_dor', 'duracao_sintomas', 'historico_doencas',
            'medicamentos_uso', 'alergias', 'fumante', 'etilista',
            'nivel_atividade_fisica', 'horas_sono', 'alimentacao_balanceada',
            'consumo_agua_litros', 'dados_extras', 'criado_em', 
            'sincronizado', 'dados_estruturados'
        ]
        read_only_fields = ['id', 'criado_em', 'imc', 'classificacao_imc']
    
    def validate(self, data):
        """Validações customizadas."""
        # Valida pressão arterial
        if 'pressao_sistolica' in data and 'pressao_diastolica' in data:
            sistolica = data['pressao_sistolica']
            diastolica = data['pressao_diastolica']
            
            if sistolica <= diastolica:
                raise serializers.ValidationError(
                    "Pressão sistólica deve ser maior que a diastólica."
                )
        
        # Valida IMC
        if 'peso' in data and 'altura' in data:
            peso = data['peso']
            altura = data['altura']
            valido, imc, classificacao = ValidadorMedico.validar_imc(float(peso), float(altura))
            
            if not valido:
                raise serializers.ValidationError("Valores de peso e altura inválidos.")
        
        return data
    
    def create(self, validated_data):
        """Criação com normalização de sintomas."""
        if 'sintomas_principais' in validated_data:
            sintomas = validated_data['sintomas_principais']
            validated_data['sintomas_principais'] = NormalizadorTexto.normalizar_texto(sintomas)
        
        return super().create(validated_data)


class AnamneseSerializer(serializers.ModelSerializer):
    """Serializer para anamnese."""
    resumo_json = serializers.ReadOnlyField(source='get_resumo_json')
    cidadao_nome = serializers.CharField(source='cidadao.nome', read_only=True)
    revisor_nome = serializers.CharField(source='revisado_por.username', read_only=True)
    
    class Meta:
        model = Anamnese
        fields = [
            'id', 'cidadao', 'cidadao_nome', 'dados_saude', 'resumo_anamnese',
            'hipoteses_diagnosticas', 'triagem_risco', 'recomendacoes',
            'modelo_ia_usado', 'confianca_ia', 'status', 'revisado_por',
            'revisor_nome', 'data_revisao', 'comentarios_revisao',
            'resumo_final', 'diagnostico_final', 'recomendacoes_finais',
            'criado_em', 'enviado_secretaria', 'resumo_json'
        ]
        read_only_fields = [
            'id', 'criado_em', 'modelo_ia_usado', 'confianca_ia',
            'dados_entrada_ia', 'resposta_completa_ia', 'resumo_json'
        ]


class AlertaSaudeSerializer(serializers.ModelSerializer):
    """Serializer para alertas de saúde."""
    paciente_nome = serializers.CharField(source='anamnese.cidadao.nome', read_only=True)
    
    class Meta:
        model = AlertaSaude
        fields = [
            'id', 'anamnese', 'paciente_nome', 'tipo', 'prioridade',
            'titulo', 'descricao', 'acao_recomendada', 'prazo_acao',
            'visualizado', 'resolvido', 'resolvido_por', 'data_resolucao',
            'criado_em'
        ]
        read_only_fields = ['id', 'criado_em']


class LogAuditoriaIASerializer(serializers.ModelSerializer):
    """Serializer para logs de auditoria da IA."""
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)
    
    class Meta:
        model = LogAuditoriaIA
        fields = [
            'id', 'tipo_operacao', 'usuario', 'usuario_nome', 'cidadao',
            'anamnese', 'modelo_ia', 'prompt_enviado', 'dados_entrada',
            'resposta_ia', 'tempo_processamento', 'sucesso', 'erro_detalhes',
            'tokens_utilizados', 'custo_estimado', 'dados_anonimizados',
            'ip_origem', 'criado_em'
        ]
        read_only_fields = ['id', 'criado_em']


class RelatorioSaudeSerializer(serializers.ModelSerializer):
    """Serializer para relatórios de saúde."""
    gerado_por_nome = serializers.CharField(source='gerado_por.username', read_only=True)
    
    class Meta:
        model = RelatorioSaude
        fields = [
            'id', 'tipo', 'titulo', 'periodo_inicio', 'periodo_fim',
            'total_atendimentos', 'total_cidadaos', 'casos_risco_alto',
            'casos_risco_medio', 'casos_risco_baixo', 'tendencias_saude',
            'clusters_doencas', 'hotspots_geograficos', 'recomendacoes_ia',
            'distribuicao_idade', 'distribuicao_sexo', 'distribuicao_geografica',
            'sintomas_mais_comuns', 'diagnosticos_frequentes', 
            'medicamentos_mais_usados', 'gerado_por', 'gerado_por_nome',
            'criado_em', 'publicado'
        ]
        read_only_fields = ['id', 'criado_em']


class EstatisticaTempoRealSerializer(serializers.ModelSerializer):
    """Serializer para estatísticas em tempo real."""
    
    class Meta:
        model = EstatisticaTempoReal
        fields = [
            'total_cidadaos_cadastrados', 'total_atendimentos_hoje',
            'total_atendimentos_semana', 'total_anamneses_pendentes',
            'casos_risco_alto_hoje', 'casos_risco_medio_hoje',
            'alertas_nao_resolvidos', 'tempo_medio_anamnese',
            'taxa_sucesso_ia', 'ultima_atualizacao'
        ]
        read_only_fields = ['ultima_atualizacao']


# Serializers para operações específicas

class ColetaDadosSerializer(serializers.Serializer):
    """Serializer para coleta completa de dados (cidadão + saúde)."""
    
    # Dados do cidadão
    cidadao = CidadaoSerializer()
    contatos_emergencia = ContatoEmergenciaSerializer(many=True, required=False)
    
    # Dados de saúde
    dados_saude = DadosSaudeSerializer()
    
    def create(self, validated_data):
        """Cria cidadão e dados de saúde em uma transação."""
        from django.db import transaction
        
        with transaction.atomic():
            # Cria cidadão
            dados_cidadao = validated_data.pop('cidadao')
            contatos_data = validated_data.pop('contatos_emergencia', [])
            
            cidadao = Cidadao.objects.create(**dados_cidadao)
            
            # Cria contatos de emergência
            for contato_data in contatos_data:
                ContatoEmergencia.objects.create(cidadao=cidadao, **contato_data)
            
            # Cria dados de saúde
            dados_saude_data = validated_data.pop('dados_saude')
            dados_saude_data['cidadao'] = cidadao
            dados_saude = DadosSaude.objects.create(**dados_saude_data)
            
            return {
                'cidadao': cidadao,
                'dados_saude': dados_saude
            }


class SolicitacaoAnamneseSerializer(serializers.Serializer):
    """Serializer para solicitação de anamnese automática."""
    
    dados_saude_id = serializers.UUIDField()
    prioridade = serializers.ChoiceField(
        choices=['normal', 'alta', 'urgente'],
        default='normal'
    )
    modelo_ia = serializers.ChoiceField(
        choices=['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo'],
        default='gpt-3.5-turbo'
    )
    incluir_historico = serializers.BooleanField(default=True)
    
    def validate_dados_saude_id(self, value):
        """Valida se os dados de saúde existem."""
        try:
            dados_saude = DadosSaude.objects.get(id=value)
            # Verifica se já não existe anamnese para estes dados
            if Anamnese.objects.filter(dados_saude=dados_saude).exists():
                raise serializers.ValidationError(
                    "Já existe anamnese para estes dados de saúde."
                )
            return value
        except DadosSaude.DoesNotExist:
            raise serializers.ValidationError("Dados de saúde não encontrados.")


class FiltroRelatorioSerializer(serializers.Serializer):
    """Serializer para filtros de relatórios."""
    
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    risco = serializers.MultipleChoiceField(
        choices=[('baixo', 'Baixo'), ('medio', 'Médio'), ('alto', 'Alto'), ('critico', 'Crítico')],
        required=False
    )
    cidade = serializers.CharField(required=False)
    faixa_etaria = serializers.MultipleChoiceField(
        choices=[('menor_18', 'Menor de 18'), ('18_29', '18-29'), 
                ('30_49', '30-49'), ('50_64', '50-64'), ('65_mais', '65+')],
        required=False
    )
    sexo = serializers.MultipleChoiceField(
        choices=[('M', 'Masculino'), ('F', 'Feminino'), ('O', 'Outro')],
        required=False
    )
    
    def validate(self, data):
        """Valida período do relatório."""
        if data['data_inicio'] > data['data_fim']:
            raise serializers.ValidationError(
                "Data de início deve ser anterior à data de fim."
            )
        return data