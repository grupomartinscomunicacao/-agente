from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from cidadaos.models import Cidadao
import uuid
import json


class DadosSaude(models.Model):
    """
    Modelo para armazenar dados de saúde coletados do cidadão.
    Estruturado para fácil integração com APIs externas.
    """
    NIVEL_DOR_CHOICES = [
        (0, 'Sem dor'),
        (1, 'Dor muito leve'),
        (2, 'Dor leve'),
        (3, 'Dor moderada'),
        (4, 'Dor forte'),
        (5, 'Dor muito forte'),
        (6, 'Dor severa'),
        (7, 'Dor muito severa'),
        (8, 'Dor intensa'),
        (9, 'Dor insuportável'),
        (10, 'Dor máxima'),
    ]
    
    NIVEL_ATIVIDADE_CHOICES = [
        ('sedentario', 'Sedentário'),
        ('leve', 'Atividade Leve'),
        ('moderada', 'Atividade Moderada'),
        ('intensa', 'Atividade Intensa'),
        ('muito_intensa', 'Atividade Muito Intensa'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cidadao = models.ForeignKey(Cidadao, on_delete=models.CASCADE, related_name='dados_saude')
    agente_coleta = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Sinais vitais
    pressao_sistolica = models.PositiveIntegerField(
        validators=[MinValueValidator(70), MaxValueValidator(250)],
        help_text="Pressão arterial sistólica (mmHg)"
    )
    pressao_diastolica = models.PositiveIntegerField(
        validators=[MinValueValidator(40), MaxValueValidator(150)],
        help_text="Pressão arterial diastólica (mmHg)"
    )
    frequencia_cardiaca = models.PositiveIntegerField(
        validators=[MinValueValidator(30), MaxValueValidator(220)],
        help_text="Frequência cardíaca (bpm)"
    )
    temperatura = models.DecimalField(
        max_digits=4, 
        decimal_places=1,
        validators=[MinValueValidator(30.0), MaxValueValidator(45.0)],
        help_text="Temperatura corporal (°C)"
    )
    peso = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(1.0), MaxValueValidator(300.0)],
        help_text="Peso em kg"
    )
    altura = models.DecimalField(
        max_digits=4, 
        decimal_places=2,
        validators=[MinValueValidator(0.3), MaxValueValidator(2.5)],
        help_text="Altura em metros"
    )
    
    # Sintomas
    sintomas_principais = models.TextField(
        help_text="Descrição dos sintomas principais"
    )
    nivel_dor = models.IntegerField(
        choices=NIVEL_DOR_CHOICES,
        help_text="Escala de dor de 0 a 10"
    )
    duracao_sintomas = models.CharField(
        max_length=100,
        help_text="Há quanto tempo os sintomas iniciaram"
    )
    
    # Histórico médico
    historico_doencas = models.TextField(
        blank=True,
        help_text="Histórico de doenças crônicas e anteriores"
    )
    medicamentos_uso = models.TextField(
        blank=True,
        help_text="Medicamentos em uso atual"
    )
    alergias = models.TextField(
        blank=True,
        help_text="Alergias conhecidas"
    )
    
    # Hábitos de vida
    fumante = models.BooleanField(default=False)
    etilista = models.BooleanField(default=False)
    nivel_atividade_fisica = models.CharField(
        max_length=20,
        choices=NIVEL_ATIVIDADE_CHOICES,
        default='sedentario'
    )
    horas_sono = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(24)],
        help_text="Horas de sono por noite"
    )
    
    # Alimentação
    alimentacao_balanceada = models.BooleanField(
        default=False,
        help_text="Possui alimentação balanceada"
    )
    consumo_agua_litros = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0.1), MaxValueValidator(10.0)],
        help_text="Consumo de água em litros por dia"
    )
    
    # Dados adicionais (JSON para flexibilidade)
    dados_extras = models.JSONField(
        blank=True,
        null=True,
        help_text="Dados adicionais em formato JSON"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    sincronizado = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Dados de Saúde"
        verbose_name_plural = "Dados de Saúde"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"Dados de {self.cidadao.nome} - {self.criado_em.strftime('%d/%m/%Y')}"
    
    @property
    def imc(self):
        """Calcula o IMC."""
        return round(float(self.peso) / (float(self.altura) ** 2), 2)
    
    @property
    def classificacao_imc(self):
        """Classifica o IMC."""
        imc = self.imc
        if imc < 18.5:
            return "Abaixo do peso"
        elif imc < 25:
            return "Peso normal"
        elif imc < 30:
            return "Sobrepeso"
        else:
            return "Obesidade"
    
    def get_dados_estruturados(self):
        """Retorna dados estruturados para análise de IA."""
        return {
            'sinais_vitais': {
                'pressao_arterial': f"{self.pressao_sistolica}/{self.pressao_diastolica}",
                'frequencia_cardiaca': self.frequencia_cardiaca,
                'temperatura': float(self.temperatura),
            },
            'antropometria': {
                'peso': float(self.peso),
                'altura': float(self.altura),
                'imc': self.imc,
                'classificacao_imc': self.classificacao_imc,
            },
            'sintomas': {
                'principais': self.sintomas_principais,
                'nivel_dor': self.nivel_dor,
                'duracao': self.duracao_sintomas,
            },
            'historico': {
                'doencas': self.historico_doencas,
                'medicamentos': self.medicamentos_uso,
                'alergias': self.alergias,
            },
            'habitos': {
                'fumante': self.fumante,
                'etilista': self.etilista,
                'atividade_fisica': self.nivel_atividade_fisica,
                'horas_sono': self.horas_sono,
                'alimentacao_balanceada': self.alimentacao_balanceada,
                'consumo_agua': float(self.consumo_agua_litros),
            },
            'dados_extras': self.dados_extras or {},
        }


class HistoricoSaude(models.Model):
    """Histórico consolidado de saúde do cidadão."""
    cidadao = models.OneToOneField(
        Cidadao, 
        on_delete=models.CASCADE, 
        related_name='historico_saude'
    )
    
    # Resumo médico
    condicoes_cronicas = models.TextField(blank=True)
    procedimentos_realizados = models.TextField(blank=True)
    internacoes = models.TextField(blank=True)
    
    # Família
    historico_familiar = models.TextField(
        blank=True,
        help_text="Histórico de doenças na família"
    )
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Histórico de Saúde"
        verbose_name_plural = "Históricos de Saúde"
    
    def __str__(self):
        return f"Histórico de {self.cidadao.nome}"
