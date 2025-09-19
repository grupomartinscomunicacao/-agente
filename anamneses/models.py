from django.db import models
from django.contrib.auth.models import User
from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude
import uuid
import json


class Anamnese(models.Model):
    """
    Modelo para armazenar anamnese gerada pela IA e validação humana.
    """
    RISCO_CHOICES = [
        ('baixo', 'Risco Baixo'),
        ('medio', 'Risco Médio'),
        ('alto', 'Risco Alto'),
        ('critico', 'Risco Crítico'),
    ]
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente Revisão'),
        ('aprovada', 'Aprovada'),
        ('rejeitada', 'Rejeitada'),
        ('revisao', 'Em Revisão'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cidadao = models.ForeignKey(Cidadao, on_delete=models.CASCADE, related_name='anamneses')
    dados_saude = models.ForeignKey(DadosSaude, on_delete=models.CASCADE, related_name='anamneses')
    
    # Anamnese gerada pela IA
    resumo_anamnese = models.TextField(
        help_text="Anamnese resumida (máximo 200 palavras)"
    )
    diagnostico_clinico = models.TextField(
        blank=True,
        help_text="Diagnóstico clínico principal gerado pela IA"
    )
    diagnostico_diferencial = models.JSONField(
        default=list,
        help_text="Lista de diagnósticos diferenciais"
    )
    hipoteses_diagnosticas = models.JSONField(
        default=list,
        help_text="Lista de hipóteses diagnósticas ordenadas por probabilidade"
    )
    triagem_risco = models.CharField(
        max_length=10,
        choices=RISCO_CHOICES,
        help_text="Classificação de risco automática"
    )
    recomendacoes = models.TextField(
        help_text="Recomendações iniciais da IA"
    )
    exames_complementares = models.JSONField(
        default=list,
        help_text="Exames recomendados pela IA"
    )
    prognose = models.TextField(
        blank=True,
        help_text="Prognóstico do caso gerado pela IA"
    )
    
    # Dados da IA
    modelo_ia_usado = models.CharField(
        max_length=50,
        default="gpt-3.5-turbo",
        help_text="Modelo de IA utilizado"
    )
    confianca_ia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Nível de confiança da IA (0-100)"
    )
    dados_entrada_ia = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dados enviados para a IA (para auditoria)"
    )
    resposta_completa_ia = models.JSONField(
        default=dict,
        blank=True,
        help_text="Resposta completa da IA"
    )
    
    # Validação humana
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pendente'
    )
    revisado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='anamneses_revisadas'
    )
    data_revisao = models.DateTimeField(null=True, blank=True)
    comentarios_revisao = models.TextField(
        blank=True,
        help_text="Comentários do revisor médico"
    )
    
    # Alterações pós-revisão
    resumo_final = models.TextField(
        blank=True,
        help_text="Resumo final após revisão médica"
    )
    diagnostico_final = models.TextField(
        blank=True,
        help_text="Diagnóstico final após revisão"
    )
    recomendacoes_finais = models.TextField(
        blank=True,
        help_text="Recomendações finais após revisão"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_secretaria = models.BooleanField(default=False)
    data_envio_secretaria = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Anamnese"
        verbose_name_plural = "Anamneses"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"Anamnese de {self.cidadao.nome} - {self.criado_em.strftime('%d/%m/%Y')}"
    
    def get_resumo_json(self):
        """Retorna dados estruturados da anamnese."""
        return {
            'id': str(self.id),
            'cidadao_id': str(self.cidadao.id),
            'data': self.criado_em.isoformat(),
            'resumo': self.resumo_final or self.resumo_anamnese,
            'hipoteses': self.hipoteses_diagnosticas,
            'risco': self.triagem_risco,
            'recomendacoes': self.recomendacoes_finais or self.recomendacoes,
            'status': self.status,
            'revisado': self.status != 'pendente',
            'modelo_ia': self.modelo_ia_usado,
        }
    
    def get_diagnosticos_diferenciais_lista(self):
        """Retorna diagnósticos diferenciais como lista válida."""
        if not self.diagnostico_diferencial:
            return []
        
        if isinstance(self.diagnostico_diferencial, list):
            # Filtra itens vazios ou com apenas 1 caractere
            return [d for d in self.diagnostico_diferencial if isinstance(d, str) and len(d) > 1]
        elif isinstance(self.diagnostico_diferencial, str):
            # Se for string, divide por quebras de linha ou vírgulas
            items = self.diagnostico_diferencial.replace('\n', ',').split(',')
            return [item.strip() for item in items if item.strip() and len(item.strip()) > 1]
        
        return []
    
    def get_exames_complementares_lista(self):
        """Retorna exames complementares como lista válida."""
        if not self.exames_complementares:
            return []
        
        if isinstance(self.exames_complementares, list):
            # Filtra itens vazios ou com apenas 1 caractere
            return [e for e in self.exames_complementares if isinstance(e, str) and len(e) > 1]
        elif isinstance(self.exames_complementares, str):
            # Se for string, divide por quebras de linha ou vírgulas
            items = self.exames_complementares.replace('\n', ',').split(',')
            return [item.strip() for item in items if item.strip() and len(item.strip()) > 1]
        
        return []
    
    def get_hipoteses_diagnosticas_lista(self):
        """Retorna hipóteses diagnósticas como lista válida."""
        if not self.hipoteses_diagnosticas:
            return []
        
        if isinstance(self.hipoteses_diagnosticas, list):
            # Filtra itens vazios ou com apenas 1 caractere
            return [h for h in self.hipoteses_diagnosticas if isinstance(h, str) and len(h) > 1]
        elif isinstance(self.hipoteses_diagnosticas, str):
            # Se for string, divide por quebras de linha ou vírgulas
            items = self.hipoteses_diagnosticas.replace('\n', ',').split(',')
            return [item.strip() for item in items if item.strip() and len(item.strip()) > 1]
        
        return []
    
    def get_contexto_completo_para_ia(self):
        """Retorna contexto completo incluindo informações prévias do cidadão para uso na IA."""
        return {
            'informacoes_demograficas': {
                'idade': self.cidadao.idade,
                'sexo': self.cidadao.get_sexo_display(),
                'profissao': self.cidadao.profissao,
                'possui_plano_saude': self.cidadao.possui_plano_saude,
            },
            'condicoes_cronicas_previas': {
                'hipertensao': self.cidadao.possui_hipertensao,
                'diabetes': self.cidadao.possui_diabetes,
                'doenca_cardiaca': self.cidadao.possui_doenca_cardiaca,
                'doenca_renal': self.cidadao.possui_doenca_renal,
                'asma': self.cidadao.possui_asma,
                'depressao_ansiedade': self.cidadao.possui_depressao,
                'lista_condicoes': self.cidadao.condicoes_saude_cronicas,
            },
            'medicamentos_e_alergias': {
                'medicamentos_continuo': self.cidadao.medicamentos_continuo,
                'alergias_conhecidas': self.cidadao.alergias_conhecidas,
                'cirurgias_anteriores': self.cidadao.cirurgias_anteriores,
            },
            'dados_saude_atuais': self.dados_saude.get_dados_estruturados(),
            'historico_anamneses': [
                anamnese.get_resumo_json() 
                for anamnese in self.cidadao.anamneses.exclude(id=self.id).order_by('-criado_em')[:3]
            ],
        }


class LogAuditoriaIA(models.Model):
    """
    Log de auditoria para todas as interações com IA.
    Essencial para transparência e conformidade LGPD.
    """
    TIPO_OPERACAO_CHOICES = [
        ('anamnese', 'Geração de Anamnese'),
        ('triagem', 'Triagem de Risco'),
        ('extracao', 'Extração de Dados'),
        ('agregacao', 'Agregação de Dados'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identificação da operação
    tipo_operacao = models.CharField(max_length=20, choices=TIPO_OPERACAO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cidadao = models.ForeignKey(Cidadao, on_delete=models.SET_NULL, null=True, blank=True)
    anamnese = models.ForeignKey(Anamnese, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Dados da requisição
    modelo_ia = models.CharField(max_length=50)
    prompt_enviado = models.TextField()
    dados_entrada = models.JSONField()
    
    # Dados da resposta
    resposta_ia = models.JSONField()
    tempo_processamento = models.DurationField()
    sucesso = models.BooleanField()
    erro_detalhes = models.TextField(blank=True)
    
    # Custos e métricas
    tokens_utilizados = models.PositiveIntegerField(null=True, blank=True)
    custo_estimado = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    
    # Dados de conformidade
    dados_anonimizados = models.BooleanField(default=False)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Log de Auditoria IA"
        verbose_name_plural = "Logs de Auditoria IA"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.tipo_operacao} - {self.criado_em.strftime('%d/%m/%Y %H:%M')}"


class AlertaSaude(models.Model):
    """
    Alertas de saúde baseados na triagem de risco.
    """
    PRIORIDADE_CHOICES = [
        ('baixa', 'Baixa'),
        ('media', 'Média'),
        ('alta', 'Alta'),
        ('urgente', 'Urgente'),
    ]
    
    TIPO_CHOICES = [
        ('risco_alto', 'Risco Alto Detectado'),
        ('sintoma_grave', 'Sintoma Grave'),
        ('medicacao', 'Alerta de Medicação'),
        ('acompanhamento', 'Necessita Acompanhamento'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    anamnese = models.ForeignKey(Anamnese, on_delete=models.CASCADE, related_name='alertas')
    
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    prioridade = models.CharField(max_length=10, choices=PRIORIDADE_CHOICES)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    
    # Ação recomendada
    acao_recomendada = models.TextField()
    prazo_acao = models.DateTimeField(null=True, blank=True)
    
    # Status
    visualizado = models.BooleanField(default=False)
    resolvido = models.BooleanField(default=False)
    resolvido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    data_resolucao = models.DateTimeField(null=True, blank=True)
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Alerta de Saúde"
        verbose_name_plural = "Alertas de Saúde"
        ordering = ['-prioridade', '-criado_em']
    
    def __str__(self):
        return f"{self.titulo} - {self.prioridade.title()}"
