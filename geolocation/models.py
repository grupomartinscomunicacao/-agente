"""
Modelos para geolocalização e análise de risco geográfico.
"""
from django.db import models
from django.contrib.auth.models import User
from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese
from django.utils import timezone
import uuid
import json


class LocalizacaoSaude(models.Model):
    """
    Modelo para armazenar dados de localização associados a dados de saúde.
    """
    NIVEL_RISCO_CHOICES = [
        ('baixo', 'Baixo Risco'),
        ('medio', 'Médio Risco'),
        ('alto', 'Alto Risco'),
        ('critico', 'Crítico'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cidadao = models.ForeignKey(Cidadao, on_delete=models.CASCADE, related_name='localizacoes_saude')
    dados_saude = models.ForeignKey(DadosSaude, on_delete=models.CASCADE, null=True, blank=True)
    anamnese = models.ForeignKey(Anamnese, on_delete=models.CASCADE, null=True, blank=True)
    
    # Dados de localização
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    endereco_completo = models.CharField(max_length=500, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    
    # Classificação de risco
    nivel_risco = models.CharField(
        max_length=10, 
        choices=NIVEL_RISCO_CHOICES,
        default='baixo'
    )
    pontuacao_risco = models.IntegerField(default=0, help_text="Pontuação numérica do risco")
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Localização de Saúde"
        verbose_name_plural = "Localizações de Saúde"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.cidadao.nome} - {self.nivel_risco.title()} - {self.cidade}"
    
    @property
    def coordenadas_geojson(self):
        """Retorna coordenadas em formato GeoJSON."""
        return {
            "type": "Point",
            "coordinates": [float(self.longitude), float(self.latitude)]
        }
    
    @property
    def dados_mapa(self):
        """Retorna dados formatados para exibição no mapa."""
        return {
            'lat': float(self.latitude),
            'lng': float(self.longitude),
            'nome': self.cidadao.nome,
            'idade': self.cidadao.idade,
            'endereco': self.endereco_completo,
            'nivel_risco': self.nivel_risco,
            'pontuacao_risco': self.pontuacao_risco,
            'data_coleta': self.criado_em.strftime('%d/%m/%Y %H:%M'),
            'cor_marcador': self.get_cor_marcador(),
        }
    
    def get_cor_marcador(self):
        """Retorna cor do marcador baseada no nível de risco."""
        cores = {
            'baixo': '#28a745',     # Verde
            'medio': '#ffc107',     # Amarelo  
            'alto': '#dc3545',      # Vermelho
            'critico': '#a71d2a',   # Vermelho escuro
        }
        return cores.get(self.nivel_risco, '#6c757d')  # Cinza como padrão
    
    def calcular_risco_completo(self):
        """
        Calcula o nível de risco baseado em múltiplos fatores.
        """
        pontos = 0
        
        # Fatores do cidadão
        cidadao = self.cidadao
        
        # Idade
        if cidadao.idade >= 65:
            pontos += 4
        elif cidadao.idade >= 60:
            pontos += 3
        elif cidadao.idade >= 45:
            pontos += 2
        elif cidadao.idade >= 30:
            pontos += 1
            
        # Comorbidades
        comorbidades_graves = [
            cidadao.possui_doenca_cardiaca,
            cidadao.possui_doenca_renal,
        ]
        comorbidades_moderadas = [
            cidadao.possui_hipertensao,
            cidadao.possui_diabetes,
        ]
        comorbidades_leves = [
            cidadao.possui_asma,
            cidadao.possui_depressao,
        ]
        
        pontos += sum(comorbidades_graves) * 3
        pontos += sum(comorbidades_moderadas) * 2
        pontos += sum(comorbidades_leves) * 1
        
        # Dados de saúde se disponíveis
        if self.dados_saude:
            dados = self.dados_saude
            
            # Sinais vitais
            if dados.pressao_sistolica >= 140 or dados.pressao_diastolica >= 90:
                pontos += 2
            if dados.frequencia_cardiaca > 100 or dados.frequencia_cardiaca < 60:
                pontos += 1
            if dados.temperatura >= 38.0:
                pontos += 2
            
            # IMC
            imc = dados.imc
            if imc >= 35:  # Obesidade mórbida
                pontos += 3
            elif imc >= 30:  # Obesidade
                pontos += 2
            elif imc < 18.5:  # Baixo peso
                pontos += 1
            
            # Nível de dor
            if dados.nivel_dor >= 8:
                pontos += 3
            elif dados.nivel_dor >= 6:
                pontos += 2
            elif dados.nivel_dor >= 4:
                pontos += 1
            
            # Hábitos de vida
            if dados.fumante:
                pontos += 2
            if dados.etilista:
                pontos += 1
            if dados.nivel_atividade_fisica == 'sedentario':
                pontos += 1
            if dados.horas_sono < 6 or dados.horas_sono > 9:
                pontos += 1
        
        # Classificação final
        self.pontuacao_risco = pontos
        
        if pontos >= 12:
            self.nivel_risco = 'critico'
        elif pontos >= 8:
            self.nivel_risco = 'alto'
        elif pontos >= 4:
            self.nivel_risco = 'medio'
        else:
            self.nivel_risco = 'baixo'
        
        self.save()
        return self.nivel_risco


class RelatorioMedico(models.Model):
    """
    Modelo para relatórios médicos gerados automaticamente.
    """
    TIPO_RELATORIO_CHOICES = [
        ('triagem', 'Triagem Inicial'),
        ('acompanhamento', 'Acompanhamento'),
        ('emergencia', 'Emergência'),
        ('preventivo', 'Preventivo'),
    ]
    
    STATUS_CHOICES = [
        ('gerado', 'Gerado'),
        ('revisado', 'Revisado'),
        ('aprovado', 'Aprovado'),
        ('arquivado', 'Arquivado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cidadao = models.ForeignKey(Cidadao, on_delete=models.CASCADE, related_name='relatorios_medicos')
    localizacao_saude = models.ForeignKey(
        LocalizacaoSaude, 
        on_delete=models.CASCADE, 
        related_name='relatorios'
    )
    
    # Metadados do relatório
    tipo_relatorio = models.CharField(max_length=20, choices=TIPO_RELATORIO_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='gerado')
    medico_responsavel = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Conteúdo do relatório
    titulo = models.CharField(max_length=200)
    resumo_clinico = models.TextField()
    recomendacoes = models.TextField()
    medicamentos_sugeridos = models.TextField(blank=True)
    exames_solicitados = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    
    # Dados estruturados (JSON)
    dados_completos = models.JSONField(default=dict)
    
    # Metadados
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Relatório Médico"
        verbose_name_plural = "Relatórios Médicos"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"Relatório {self.tipo_relatorio} - {self.cidadao.nome} - {self.criado_em.strftime('%d/%m/%Y')}"
    
    def gerar_relatorio_automatico(self):
        """
        Gera relatório médico automático baseado nos dados disponíveis.
        """
        cidadao = self.cidadao
        localizacao = self.localizacao_saude
        dados_saude = localizacao.dados_saude
        
        # Título do relatório
        self.titulo = f"Relatório de Triagem - {cidadao.nome}"
        
        # Resumo clínico
        resumo_parts = []
        resumo_parts.append(f"Paciente: {cidadao.get_sexo_display()}, {cidadao.idade} anos")
        resumo_parts.append(f"Profissão: {cidadao.profissao or 'Não informado'}")
        
        # Comorbidades
        comorbidades = cidadao.condicoes_saude_cronicas
        if comorbidades:
            resumo_parts.append(f"Comorbidades: {', '.join(comorbidades)}")
        else:
            resumo_parts.append("Sem comorbidades conhecidas")
        
        # Dados de saúde
        if dados_saude:
            resumo_parts.append(f"Sinais vitais: PA {dados_saude.pressao_sistolica}x{dados_saude.pressao_diastolica}mmHg, FC {dados_saude.frequencia_cardiaca}bpm, T {dados_saude.temperatura}°C")
            resumo_parts.append(f"IMC: {dados_saude.imc} ({dados_saude.classificacao_imc})")
            resumo_parts.append(f"Sintomas: {dados_saude.sintomas_principais}")
            resumo_parts.append(f"Nível de dor: {dados_saude.nivel_dor}/10")
        
        self.resumo_clinico = "\n".join(resumo_parts)
        
        # Recomendações baseadas no risco
        recomendacoes = []
        
        if localizacao.nivel_risco == 'critico':
            recomendacoes.append("🚨 ATENDIMENTO IMEDIATO NECESSÁRIO")
            recomendacoes.append("- Encaminhamento urgente para unidade de emergência")
            recomendacoes.append("- Monitoramento contínuo dos sinais vitais")
        elif localizacao.nivel_risco == 'alto':
            recomendacoes.append("⚠️ ACOMPANHAMENTO PRIORITÁRIO")
            recomendacoes.append("- Consulta médica em até 24h")
            recomendacoes.append("- Reavaliação em 48h")
        elif localizacao.nivel_risco == 'medio':
            recomendacoes.append("📋 ACOMPANHAMENTO REGULAR")
            recomendacoes.append("- Consulta médica em até 7 dias")
            recomendacoes.append("- Acompanhamento mensal")
        else:
            recomendacoes.append("✅ ACOMPANHAMENTO PREVENTIVO")
            recomendacoes.append("- Consulta médica de rotina")
            recomendacoes.append("- Reavaliação semestral")
        
        # Recomendações específicas baseadas nos dados
        if dados_saude:
            if dados_saude.fumante:
                recomendacoes.append("- Orientação para cessação do tabagismo")
            if dados_saude.etilista:
                recomendacoes.append("- Orientação sobre consumo de álcool")
            if dados_saude.nivel_atividade_fisica == 'sedentario':
                recomendacoes.append("- Incentivo à prática de atividade física")
            if not dados_saude.alimentacao_balanceada:
                recomendacoes.append("- Orientação nutricional")
            if dados_saude.consumo_agua_litros < 2:
                recomendacoes.append("- Aumentar consumo de água para pelo menos 2L/dia")
        
        self.recomendacoes = "\n".join(recomendacoes)
        
        # Dados completos em JSON
        self.dados_completos = {
            'nivel_risco': localizacao.nivel_risco,
            'pontuacao_risco': localizacao.pontuacao_risco,
            'coordenadas': {
                'lat': float(localizacao.latitude),
                'lng': float(localizacao.longitude)
            },
            'dados_demograficos': cidadao.get_perfil_saude_completo()['dados_demograficos'],
            'comorbidades': cidadao.get_perfil_saude_completo()['condicoes_cronicas'],
            'dados_vitais': {
                'imc': float(dados_saude.imc) if dados_saude else None,
                'classificacao_imc': dados_saude.classificacao_imc if dados_saude else None,
            } if dados_saude else {},
            'timestamp': timezone.now().isoformat()
        }
        
        self.save()
        return self


class HistoricoLocalizacao(models.Model):
    """
    Histórico de mudanças de localização do cidadão.
    """
    cidadao = models.ForeignKey(Cidadao, on_delete=models.CASCADE, related_name='historico_localizacao')
    latitude_anterior = models.DecimalField(max_digits=10, decimal_places=8, null=True)
    longitude_anterior = models.DecimalField(max_digits=11, decimal_places=8, null=True)
    latitude_nova = models.DecimalField(max_digits=10, decimal_places=8)
    longitude_nova = models.DecimalField(max_digits=11, decimal_places=8)
    
    motivo_mudanca = models.CharField(
        max_length=200,
        help_text="Motivo da alteração da localização"
    )
    usuario_responsavel = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Histórico de Localização"
        verbose_name_plural = "Histórico de Localizações"
        ordering = ['-criado_em']
    
    def __str__(self):
        return f"{self.cidadao.nome} - {self.criado_em.strftime('%d/%m/%Y %H:%M')}"
