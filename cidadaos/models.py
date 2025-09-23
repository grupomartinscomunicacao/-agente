from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from datetime import date
import uuid


class Cidadao(models.Model):
    """
    Modelo para representar um cidadão no sistema de saúde pública.
    Inclui validações e campos estruturados para coleta de dados.
    """
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
    ]
    
    ESTADO_CIVIL_CHOICES = [
        ('S', 'Solteiro(a)'),
        ('C', 'Casado(a)'),
        ('D', 'Divorciado(a)'),
        ('V', 'Viúvo(a)'),
        ('U', 'União Estável'),
    ]
    
    # ID único para garantir anonimização
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Dados pessoais básicos
    nome = models.CharField(max_length=200, help_text="Nome completo do cidadão")
    cpf = models.CharField(
        max_length=14, 
        unique=True,
        validators=[RegexValidator(
            regex=r'^\d{3}\.\d{3}\.\d{3}-\d{2}$',
            message='CPF deve estar no formato 000.000.000-00'
        )],
        help_text="CPF no formato 000.000.000-00"
    )
    data_nascimento = models.DateField(help_text="Data de nascimento")
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    estado_civil = models.CharField(max_length=1, choices=ESTADO_CIVIL_CHOICES)
    
    # Contato
    telefone = models.CharField(
        max_length=15,
        validators=[RegexValidator(
            regex=r'^\(\d{2}\)\s\d{4,5}-\d{4}$',
            message='Telefone deve estar no formato (00) 00000-0000'
        )],
        help_text="Telefone no formato (00) 00000-0000"
    )
    email = models.EmailField(blank=True, null=True)
    
    # Endereço
    endereco = models.CharField(max_length=200, help_text="Endereço completo")
    cep = models.CharField(
        max_length=9,
        validators=[RegexValidator(
            regex=r'^\d{5}-\d{3}$',
            message='CEP deve estar no formato 00000-000'
        )]
    )
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    
    # Geolocalização
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=8, 
        null=True, 
        blank=True,
        help_text="Latitude da localização do cidadão"
    )
    longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=8, 
        null=True, 
        blank=True,
        help_text="Longitude da localização do cidadão"
    )
    endereco_capturado_automaticamente = models.BooleanField(
        default=False,
        help_text="Indica se o endereço foi obtido via geolocalização automática"
    )
    
    # Dados complementares
    profissao = models.CharField(max_length=100, blank=True)
    renda_familiar = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Renda familiar em reais"
    )
    possui_plano_saude = models.BooleanField(default=False)
    
    # Informações básicas de saúde
    possui_hipertensao = models.BooleanField(
        default=False,
        help_text="Possui hipertensão arterial"
    )
    possui_diabetes = models.BooleanField(
        default=False,
        help_text="Possui diabetes mellitus"
    )
    possui_doenca_cardiaca = models.BooleanField(
        default=False,
        help_text="Possui doença cardíaca"
    )
    possui_doenca_renal = models.BooleanField(
        default=False,
        help_text="Possui doença renal"
    )
    possui_asma = models.BooleanField(
        default=False,
        help_text="Possui asma"
    )
    possui_depressao = models.BooleanField(
        default=False,
        help_text="Possui depressão ou ansiedade"
    )
    medicamentos_continuo = models.TextField(
        blank=True,
        help_text="Medicamentos de uso contínuo"
    )
    alergias_conhecidas = models.TextField(
        blank=True,
        help_text="Alergias conhecidas"
    )
    cirurgias_anteriores = models.TextField(
        blank=True,
        help_text="Cirurgias realizadas anteriormente"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Cidadão"
        verbose_name_plural = "Cidadãos"
        ordering = ['-criado_em']
        
    def __str__(self):
        return self.nome
    
    @property
    def idade(self):
        """Calcula a idade do cidadão."""
        today = date.today()
        return today.year - self.data_nascimento.year - (
            (today.month, today.day) < 
            (self.data_nascimento.month, self.data_nascimento.day)
        )
    
    @property
    def dados_saude_recentes(self):
        """Retorna os dados de saúde mais recentes do cidadão."""
        return self.dados_saude.order_by('-criado_em').first()
    
    @property
    def condicoes_saude_cronicas(self):
        """Retorna lista das condições crônicas do cidadão."""
        condicoes = []
        if self.possui_hipertensao:
            condicoes.append("Hipertensão")
        if self.possui_diabetes:
            condicoes.append("Diabetes")
        if self.possui_doenca_cardiaca:
            condicoes.append("Doença Cardíaca")
        if self.possui_doenca_renal:
            condicoes.append("Doença Renal")
        if self.possui_asma:
            condicoes.append("Asma")
        if self.possui_depressao:
            condicoes.append("Depressão/Ansiedade")
        return condicoes
    
    def get_perfil_saude_completo(self):
        """Retorna perfil completo de saúde para uso em anamneses."""
        return {
            'dados_demograficos': {
                'idade': self.idade,
                'sexo': self.get_sexo_display(),
                'profissao': self.profissao,
            },
            'condicoes_cronicas': {
                'hipertensao': self.possui_hipertensao,
                'diabetes': self.possui_diabetes,
                'doenca_cardiaca': self.possui_doenca_cardiaca,
                'doenca_renal': self.possui_doenca_renal,
                'asma': self.possui_asma,
                'depressao': self.possui_depressao,
            },
            'medicamentos_continuo': self.medicamentos_continuo,
            'alergias_conhecidas': self.alergias_conhecidas,
            'cirurgias_anteriores': self.cirurgias_anteriores,
            'plano_saude': self.possui_plano_saude,
        }
    
    def get_dados_anonimos(self):
        """Retorna dados anonimizados para envio à IA."""
        return {
            'idade': self.idade,
            'sexo': self.sexo,
            'estado_civil': self.estado_civil,
            'profissao': self.profissao,
            'possui_plano_saude': self.possui_plano_saude,
            'cidade': self.cidade,
            'estado': self.estado,
        }
    
    @property
    def tem_localizacao(self):
        """Verifica se o cidadão possui dados de geolocalização."""
        return self.latitude is not None and self.longitude is not None
    
    @property
    def coordenadas(self):
        """Retorna as coordenadas em formato de tupla."""
        if self.tem_localizacao:
            return (float(self.latitude), float(self.longitude))
        return None
    
    def get_coordenadas_json(self):
        """Retorna coordenadas em formato JSON para uso em mapas."""
        if self.tem_localizacao:
            return {
                'lat': float(self.latitude),
                'lng': float(self.longitude),
                'nome': self.nome,
                'endereco': f"{self.endereco}, {self.bairro}, {self.cidade}"
            }
        return None
    
    def calcular_risco_saude_basico(self):
        """
        Calcula nível de risco básico baseado em comorbidades e idade.
        Retorna: 'baixo', 'medio', 'alto'
        """
        pontos_risco = 0
        
        # Pontuação por idade
        if self.idade >= 60:
            pontos_risco += 3
        elif self.idade >= 40:
            pontos_risco += 1
            
        # Pontuação por comorbidades
        comorbidades = [
            self.possui_hipertensao,
            self.possui_diabetes,
            self.possui_doenca_cardiaca,
            self.possui_doenca_renal,
            self.possui_asma,
            self.possui_depressao
        ]
        pontos_risco += sum(comorbidades) * 2
        
        # Classificação final
        if pontos_risco >= 6:
            return 'alto'
        elif pontos_risco >= 3:
            return 'medio'
        else:
            return 'baixo'


class ContatoEmergencia(models.Model):
    """Contato de emergência do cidadão."""
    cidadao = models.ForeignKey(
        Cidadao, 
        on_delete=models.CASCADE, 
        related_name='contatos_emergencia'
    )
    nome = models.CharField(max_length=200)
    parentesco = models.CharField(max_length=50)
    telefone = models.CharField(max_length=15)
    
    class Meta:
        verbose_name = "Contato de Emergência"
        verbose_name_plural = "Contatos de Emergência"
    
    def __str__(self):
        return f"{self.nome} ({self.parentesco})"
