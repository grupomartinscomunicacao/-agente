"""
Modelos para conformidade LGPD.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from utils.lgpd import AnonimizadorLGPD


class ConsentimentoLGPD(models.Model):
    """Registro de consentimento do cidadão para tratamento de dados."""
    
    FINALIDADES_CHOICES = [
        ('ATENDIMENTO_MEDICO', 'Atendimento médico e cuidados de saúde'),
        ('PESQUISA_CIENTIFICA', 'Pesquisa científica em saúde pública'),
        ('ESTATISTICAS_PUBLICAS', 'Estatísticas e análises de saúde pública'),
        ('INTELIGENCIA_ARTIFICIAL', 'Processamento por IA para diagnóstico'),
        ('COMUNICACAO_EMERGENCIA', 'Comunicação em casos de emergência'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cidadao = models.ForeignKey(
        'cidadaos.Cidadao',
        on_delete=models.CASCADE,
        related_name='consentimentos'
    )
    
    # Finalidades do tratamento
    finalidade = models.CharField(max_length=50, choices=FINALIDADES_CHOICES)
    consentido = models.BooleanField(default=True)
    
    # Dados do consentimento
    token_consentimento = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Temporalidade
    data_consentimento = models.DateTimeField(default=timezone.now)
    valido_ate = models.DateTimeField()
    data_revogacao = models.DateTimeField(null=True, blank=True)
    
    # Auditoria
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Consentimento LGPD'
        verbose_name_plural = 'Consentimentos LGPD'
        unique_together = ['cidadao', 'finalidade']
        indexes = [
            models.Index(fields=['cidadao', 'finalidade']),
            models.Index(fields=['valido_ate']),
        ]
    
    def __str__(self):
        return f"{self.cidadao.nome} - {self.get_finalidade_display()}"
    
    @property
    def ativo(self):
        """Verifica se o consentimento está ativo."""
        agora = timezone.now()
        return (
            self.consentido and 
            not self.data_revogacao and 
            self.valido_ate > agora
        )
    
    def revogar(self):
        """Revoga o consentimento."""
        self.consentido = False
        self.data_revogacao = timezone.now()
        self.save()


class AuditoriaAcesso(models.Model):
    """Registro de auditoria para acessos a dados pessoais."""
    
    TIPOS_ACAO = [
        ('ACESSO_DADOS', 'Acesso aos dados'),
        ('MODIFICACAO_DADOS', 'Modificação de dados'),
        ('EXCLUSAO_DADOS', 'Exclusão de dados'),
        ('ANONIMIZACAO_DADOS', 'Anonimização de dados'),
        ('EXPORTACAO_DADOS', 'Exportação de dados'),
        ('CONSENTIMENTO_DADO', 'Consentimento concedido'),
        ('CONSENTIMENTO_REVOGADO', 'Consentimento revogado'),
        ('VIOLACAO_DADOS', 'Violação de dados detectada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dados do acesso
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acessos_auditoria'
    )
    cidadao = models.ForeignKey(
        'cidadaos.Cidadao',
        on_delete=models.CASCADE,
        related_name='acessos_auditoria'
    )
    
    # Ação realizada
    tipo_acao = models.CharField(max_length=30, choices=TIPOS_ACAO)
    detalhes = models.JSONField(default=dict, blank=True)
    
    # Contexto técnico
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    session_id = models.CharField(max_length=64, blank=True)
    url_acessada = models.URLField(blank=True)
    
    # Temporal
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = 'Auditoria de Acesso'
        verbose_name_plural = 'Auditorias de Acesso'
        indexes = [
            models.Index(fields=['cidadao', 'timestamp']),
            models.Index(fields=['usuario', 'timestamp']),
            models.Index(fields=['tipo_acao', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.get_tipo_acao_display()} - {self.cidadao.nome} - {self.timestamp}"


class DadosAnonimizados(models.Model):
    """Registro de dados anonimizados para fins estatísticos."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Identificador original (hash)
    hash_cidadao = models.CharField(max_length=64, db_index=True)
    
    # Dados demográficos anonimizados
    faixa_etaria = models.CharField(max_length=20)  # "18-25", "26-35", etc.
    sexo = models.CharField(max_length=1)
    regiao_residencia = models.CharField(max_length=50)  # Apenas cidade/estado
    
    # Dados de saúde agregados
    tem_doenca_cronica = models.BooleanField(null=True)
    categoria_imc = models.CharField(max_length=20, blank=True)  # "normal", "sobrepeso", etc.
    nivel_risco_geral = models.CharField(max_length=20, blank=True)
    
    # Metadados
    data_anonimizacao = models.DateTimeField(default=timezone.now)
    finalidade = models.CharField(max_length=100)  # Para que foi anonimizado
    
    class Meta:
        verbose_name = 'Dados Anonimizados'
        verbose_name_plural = 'Dados Anonimizados'
        indexes = [
            models.Index(fields=['faixa_etaria', 'sexo']),
            models.Index(fields=['data_anonimizacao']),
        ]
    
    def __str__(self):
        return f"Dados Anônimos - {self.faixa_etaria} - {self.data_anonimizacao.date()}"


class ViolacaoDados(models.Model):
    """Registro de violações ou incidentes de segurança de dados."""
    
    TIPOS_VIOLACAO = [
        ('ACESSO_NAO_AUTORIZADO', 'Acesso não autorizado'),
        ('VAZAMENTO_DADOS', 'Vazamento de dados'),
        ('PERDA_DADOS', 'Perda de dados'),
        ('ALTERACAO_NAO_AUTORIZADA', 'Alteração não autorizada'),
        ('TENTATIVA_INVASAO', 'Tentativa de invasão'),
        ('USO_INDEVIDO', 'Uso indevido de dados'),
    ]
    
    SEVERIDADES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dados da violação
    tipo_violacao = models.CharField(max_length=30, choices=TIPOS_VIOLACAO)
    severidade = models.CharField(max_length=10, choices=SEVERIDADES)
    descricao = models.TextField()
    
    # Dados afetados
    cidadaos_afetados = models.ManyToManyField(
        'cidadaos.Cidadao',
        related_name='violacoes',
        blank=True
    )
    tipos_dados_afetados = models.JSONField(default=list)  # ['cpf', 'email', etc.]
    
    # Detecção e resposta
    data_deteccao = models.DateTimeField(default=timezone.now)
    data_ocorrencia_estimada = models.DateTimeField(null=True, blank=True)
    detectado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='violacoes_detectadas'
    )
    
    # Ações tomadas
    acoes_corretivas = models.TextField(blank=True)
    anpd_notificada = models.BooleanField(default=False)
    data_notificacao_anpd = models.DateTimeField(null=True, blank=True)
    cidadaos_notificados = models.BooleanField(default=False)
    data_notificacao_cidadaos = models.DateTimeField(null=True, blank=True)
    
    # Status
    resolvida = models.BooleanField(default=False)
    data_resolucao = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Violação de Dados'
        verbose_name_plural = 'Violações de Dados'
        ordering = ['-data_deteccao']
    
    def __str__(self):
        return f"{self.get_tipo_violacao_display()} - {self.data_deteccao.date()}"
    
    @property
    def deve_notificar_anpd(self):
        """Verifica se deve notificar a ANPD (72h para alto risco)."""
        if self.severidade in ['ALTA', 'CRITICA'] and not self.anpd_notificada:
            limite = self.data_deteccao + timezone.timedelta(hours=72)
            return timezone.now() < limite
        return False


class PoliticaPrivacidade(models.Model):
    """Versões das políticas de privacidade."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dados da política
    versao = models.CharField(max_length=20)  # "1.0", "1.1", etc.
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    
    # Vigência
    data_vigencia = models.DateTimeField()
    ativa = models.BooleanField(default=False)
    
    # Auditoria
    criada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Política de Privacidade'
        verbose_name_plural = 'Políticas de Privacidade'
        ordering = ['-data_vigencia']
    
    def __str__(self):
        return f"Política v{self.versao} - {self.titulo}"
    
    def save(self, *args, **kwargs):
        """Ao ativar uma política, desativa as outras."""
        if self.ativa:
            PoliticaPrivacidade.objects.filter(ativa=True).update(ativa=False)
        super().save(*args, **kwargs)