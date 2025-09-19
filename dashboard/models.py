from django.db import models
from django.contrib.auth.models import User
from django.db.models import Count, Avg, Q
from cidadaos.models import Cidadao
from anamneses.models import Anamnese
import json


class RelatorioSaude(models.Model):
    """
    Relatórios agregados para a secretaria de saúde.
    """
    TIPO_RELATORIO_CHOICES = [
        ('mensal', 'Relatório Mensal'),
        ('trimestral', 'Relatório Trimestral'),
        ('anual', 'Relatório Anual'),
        ('especial', 'Relatório Especial'),
    ]
    
    tipo = models.CharField(max_length=20, choices=TIPO_RELATORIO_CHOICES)
    titulo = models.CharField(max_length=200)
    periodo_inicio = models.DateField()
    periodo_fim = models.DateField()
    
    # Dados estatísticos
    total_atendimentos = models.PositiveIntegerField(default=0)
    total_cidadaos = models.PositiveIntegerField(default=0)
    casos_risco_alto = models.PositiveIntegerField(default=0)
    casos_risco_medio = models.PositiveIntegerField(default=0)
    casos_risco_baixo = models.PositiveIntegerField(default=0)
    
    # Insights da IA
    tendencias_saude = models.JSONField(
        null=True, 
        blank=True,
        help_text="Tendências identificadas pela IA"
    )
    clusters_doencas = models.JSONField(
        null=True, 
        blank=True,
        help_text="Clusters de doenças identificados"
    )
    hotspots_geograficos = models.JSONField(
        null=True, 
        blank=True,
        help_text="Hot-spots geográficos de problemas de saúde"
    )
    recomendacoes_ia = models.TextField(
        blank=True,
        help_text="Recomendações da IA para políticas públicas"
    )
    
    # Dados demográficos
    distribuicao_idade = models.JSONField(null=True, blank=True)
    distribuicao_sexo = models.JSONField(null=True, blank=True)
    distribuicao_geografica = models.JSONField(null=True, blank=True)
    
    # Dados clínicos
    sintomas_mais_comuns = models.JSONField(null=True, blank=True)
    diagnosticos_frequentes = models.JSONField(null=True, blank=True)
    medicamentos_mais_usados = models.JSONField(null=True, blank=True)
    
    # Metadados
    gerado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publicado = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Relatório de Saúde"
        verbose_name_plural = "Relatórios de Saúde"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.titulo} ({self.periodo_inicio} - {self.periodo_fim})"


class DashboardConfig(models.Model):
    """
    Configurações do dashboard para diferentes usuários.
    """
    TIPO_USUARIO_CHOICES = [
        ('secretario', 'Secretário de Saúde'),
        ('coordenador', 'Coordenador'),
        ('agente', 'Agente de Saúde'),
        ('medico', 'Médico Revisor'),
    ]
    
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES)
    
    # Widgets habilitados
    widgets_ativos = models.JSONField(
        default=list,
        help_text="Lista de widgets ativos no dashboard"
    )
    
    # Filtros padrão
    filtros_padrao = models.JSONField(
        default=dict,
        help_text="Filtros padrão aplicados no dashboard"
    )
    
    # Configurações de notificações
    notificar_risco_alto = models.BooleanField(default=True)
    notificar_novos_casos = models.BooleanField(default=True)
    notificar_relatorios = models.BooleanField(default=True)
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Configuração do Dashboard"
        verbose_name_plural = "Configurações do Dashboard"
    
    def __str__(self):
        return f"Config de {self.usuario.username} ({self.tipo_usuario})"


class EstatisticaTempoReal(models.Model):
    """
    Estatísticas em tempo real para o dashboard.
    Atualizada automaticamente via signals.
    """
    # Contadores gerais
    total_cidadaos_cadastrados = models.PositiveIntegerField(default=0)
    total_atendimentos_hoje = models.PositiveIntegerField(default=0)
    total_atendimentos_semana = models.PositiveIntegerField(default=0)
    total_anamneses_pendentes = models.PositiveIntegerField(default=0)
    
    # Riscos
    casos_risco_alto_hoje = models.PositiveIntegerField(default=0)
    casos_risco_medio_hoje = models.PositiveIntegerField(default=0)
    alertas_nao_resolvidos = models.PositiveIntegerField(default=0)
    
    # Performance do sistema
    tempo_medio_anamnese = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0,
        help_text="Tempo médio para gerar anamnese (segundos)"
    )
    taxa_sucesso_ia = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=100,
        help_text="Taxa de sucesso da IA (%)"
    )
    
    # Última atualização
    ultima_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Estatística em Tempo Real"
        verbose_name_plural = "Estatísticas em Tempo Real"
    
    def __str__(self):
        return f"Estatísticas - {self.ultima_atualizacao.strftime('%d/%m/%Y %H:%M')}"
    
    @classmethod
    def get_current(cls):
        """Retorna ou cria as estatísticas atuais."""
        obj, created = cls.objects.get_or_create(id=1)
        return obj
    
    def atualizar_contadores(self):
        """Atualiza todos os contadores."""
        from django.utils import timezone
        from datetime import timedelta
        
        hoje = timezone.now().date()
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        
        # Contadores básicos
        self.total_cidadaos_cadastrados = Cidadao.objects.filter(ativo=True).count()
        
        # Atendimentos
        self.total_atendimentos_hoje = Anamnese.objects.filter(
            criado_em__date=hoje
        ).count()
        
        self.total_atendimentos_semana = Anamnese.objects.filter(
            criado_em__date__gte=inicio_semana
        ).count()
        
        # Anamneses pendentes
        self.total_anamneses_pendentes = Anamnese.objects.filter(
            status='pendente'
        ).count()
        
        # Riscos hoje
        self.casos_risco_alto_hoje = Anamnese.objects.filter(
            criado_em__date=hoje,
            triagem_risco='alto'
        ).count()
        
        self.casos_risco_medio_hoje = Anamnese.objects.filter(
            criado_em__date=hoje,
            triagem_risco='medio'
        ).count()
        
        # Alertas não resolvidos
        from anamneses.models import AlertaSaude
        self.alertas_nao_resolvidos = AlertaSaude.objects.filter(
            resolvido=False
        ).count()
        
        self.save()


class ExportacaoDados(models.Model):
    """
    Controle de exportações de dados (CSV, PDF).
    """
    FORMATO_CHOICES = [
        ('csv', 'CSV'),
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
        ('json', 'JSON'),
    ]
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('processando', 'Processando'),
        ('concluido', 'Concluído'),
        ('erro', 'Erro'),
    ]
    
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo_dados = models.CharField(max_length=50, help_text="Tipo de dados exportados")
    formato = models.CharField(max_length=10, choices=FORMATO_CHOICES)
    
    # Filtros aplicados
    filtros_aplicados = models.JSONField(
        help_text="Filtros aplicados na exportação"
    )
    
    # Status e arquivo
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pendente')
    arquivo = models.FileField(upload_to='exports/', null=True, blank=True)
    erro_detalhes = models.TextField(blank=True)
    
    # Contadores
    total_registros = models.PositiveIntegerField(default=0)
    tamanho_arquivo = models.PositiveIntegerField(default=0, help_text="Tamanho em bytes")
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    processado_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Exportação de Dados"
        verbose_name_plural = "Exportações de Dados"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.tipo_dados} ({self.formato}) - {self.status}"
