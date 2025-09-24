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
        
        # Riscos baseados apenas em cidadãos que têm anamneses (aparecem no mapa)
        from geolocation.models import LocalizacaoSaude
        self.casos_risco_alto_hoje = LocalizacaoSaude.objects.filter(
            nivel_risco__in=['alto', 'critico'],
            anamnese__isnull=False  # Apenas com anamnese
        ).count()
        
        self.casos_risco_medio_hoje = LocalizacaoSaude.objects.filter(
            nivel_risco='medio',
            anamnese__isnull=False  # Apenas com anamnese
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


class VisitaAgendada(models.Model):
    """
    Agendamentos de visitas dos agentes de saúde aos cidadãos.
    """
    MOTIVO_CHOICES = [
        ('retorno_exame', 'Retorno de Exame'),
        ('avaliacao_sintomas', 'Avaliação de Sintomas'),
        ('acompanhamento_comorbidades', 'Acompanhamento de Comorbidades'),
        ('primeira_visita', 'Primeira Visita'),
        ('revisao_anamnese', 'Revisão de Anamnese'),
        ('medicacao', 'Controle de Medicação'),
        ('preventiva', 'Consulta Preventiva'),
        ('emergencia', 'Situação de Emergência'),
        ('outros', 'Outros'),
    ]

    STATUS_CHOICES = [
        ('agendada', 'Agendada'),
        ('confirmada', 'Confirmada'),
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
        ('reagendada', 'Reagendada'),
    ]

    # Relacionamentos
    cidadao = models.ForeignKey(
        Cidadao, 
        on_delete=models.CASCADE, 
        related_name='visitas_agendadas',
        help_text="Cidadão que receberá a visita"
    )
    agente = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='visitas_agendadas',
        help_text="Agente de saúde responsável pela visita"
    )

    # Dados da visita
    data_visita = models.DateTimeField(
        help_text="Data e hora agendada para a visita"
    )
    motivo = models.CharField(
        max_length=30,
        choices=MOTIVO_CHOICES,
        help_text="Motivo principal da visita"
    )
    observacoes = models.TextField(
        blank=True,
        help_text="Observações adicionais sobre a visita"
    )
    
    # Status da visita
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='agendada',
        help_text="Status atual da visita"
    )
    
    # Dados da realização (quando aplicável)
    data_realizacao = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data e hora real da visita (quando realizada)"
    )
    duracao_minutos = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duração da visita em minutos"
    )
    relatorio_visita = models.TextField(
        blank=True,
        help_text="Relatório da visita realizada"
    )
    
    # Controle de notificações
    notificacao_enviada = models.BooleanField(
        default=False,
        help_text="Se já foi enviada notificação para o cidadão"
    )
    lembrete_agente = models.BooleanField(
        default=True,
        help_text="Se deve enviar lembrete para o agente"
    )

    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visitas_criadas',
        help_text="Usuário que criou o agendamento"
    )

    class Meta:
        verbose_name = "Visita Agendada"
        verbose_name_plural = "Visitas Agendadas"
        ordering = ['data_visita']
        indexes = [
            models.Index(fields=['data_visita', 'status']),
            models.Index(fields=['cidadao', 'status']),
            models.Index(fields=['agente', 'data_visita']),
        ]

    def __str__(self):
        return f"{self.cidadao.nome} - {self.data_visita.strftime('%d/%m/%Y %H:%M')} - {self.get_motivo_display()}"

    @property
    def eh_hoje(self):
        """Verifica se a visita é para hoje."""
        from django.utils import timezone
        hoje = timezone.now().date()
        return self.data_visita.date() == hoje

    @property
    def eh_atrasada(self):
        """Verifica se a visita está atrasada."""
        from django.utils import timezone
        return (
            self.data_visita < timezone.now() and 
            self.status in ['agendada', 'confirmada']
        )

    @property
    def cor_status(self):
        """Retorna cor para exibição no calendário."""
        cores = {
            'agendada': '#ffc107',      # Amarelo
            'confirmada': '#28a745',    # Verde
            'realizada': '#6c757d',     # Cinza
            'cancelada': '#dc3545',     # Vermelho
            'reagendada': '#fd7e14',    # Laranja
        }
        return cores.get(self.status, '#6c757d')

    def pode_ser_editada(self):
        """Verifica se a visita pode ser editada."""
        return self.status in ['agendada', 'confirmada']

    def pode_ser_cancelada(self):
        """Verifica se a visita pode ser cancelada."""
        from django.utils import timezone
        return (
            self.status in ['agendada', 'confirmada'] and
            self.data_visita > timezone.now()
        )


class CategoriaTreinamento(models.Model):
    """
    Modelo para categorizar os treinamentos dos agentes de saúde.
    
    Permite criar categorias personalizadas para organizar melhor
    os vídeos de treinamento por tipo de conteúdo.
    """
    
    # Informações da categoria
    nome = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nome da categoria (ex: Procedimentos de Saúde)"
    )
    descricao = models.TextField(
        blank=True,
        null=True,
        help_text="Descrição opcional da categoria"
    )
    
    # Controle de ordem
    ordem = models.PositiveIntegerField(
        default=0,
        help_text="Ordem de exibição da categoria (menor número aparece primeiro)"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Categoria de Treinamento"
        verbose_name_plural = "Categorias de Treinamento"
        ordering = ['ordem', 'nome']  # Ordenar por ordem, depois por nome
    
    def __str__(self):
        return self.nome
    
    @property
    def total_treinamentos(self):
        """Retorna o total de treinamentos ativos nesta categoria."""
        return self.treinamentos.filter(ativo=True).count()


class Treinamento(models.Model):
    """
    Modelo para gerenciar vídeos de treinamento dos agentes de saúde.
    
    Permite o cadastro de vídeos do YouTube com informações complementares
    e controle de visibilidade no aplicativo.
    """
    
    # Informações básicas do vídeo
    titulo = models.CharField(
        max_length=200,
        help_text="Título do vídeo de treinamento"
    )
    descricao = models.TextField(
        help_text="Descrição do conteúdo do treinamento"
    )
    
    # Relacionamento com categoria
    categoria = models.ForeignKey(
        CategoriaTreinamento,
        on_delete=models.CASCADE,
        related_name='treinamentos',
        help_text="Categoria do treinamento"
    )
    
    # URL do YouTube
    url_video = models.URLField(
        help_text="Link do vídeo no YouTube (ex: https://www.youtube.com/watch?v=VIDEO_ID)"
    )
    
    # Controle de publicação
    data_publicacao = models.DateTimeField(
        help_text="Data em que o treinamento foi disponibilizado"
    )
    ativo = models.BooleanField(
        default=True,
        help_text="Define se o vídeo está visível para os agentes"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Treinamento"
        verbose_name_plural = "Treinamentos"
        ordering = ['-data_publicacao']  # Mais recentes primeiro
    
    def __str__(self):
        return f"{self.titulo} ({'Ativo' if self.ativo else 'Inativo'})"
    
    def get_youtube_video_id(self):
        """
        Extrai o ID do vídeo do YouTube a partir da URL.
        
        Suporta formatos:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        """
        import re
        
        # Padrões para diferentes formatos de URL do YouTube
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com\/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.url_video)
            if match:
                return match.group(1)
        
        return None
    
    def get_embed_url(self):
        """
        Retorna a URL de embed do YouTube para usar em iframes.
        """
        video_id = self.get_youtube_video_id()
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"
        return None
    
    def get_thumbnail_url(self):
        """
        Retorna a URL da thumbnail do vídeo.
        """
        video_id = self.get_youtube_video_id()
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        return None
