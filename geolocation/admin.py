"""
Administração do módulo de geolocalização.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import LocalizacaoSaude, RelatorioMedico, HistoricoLocalizacao


@admin.register(LocalizacaoSaude)
class LocalizacaoSaudeAdmin(admin.ModelAdmin):
    list_display = [
        'cidadao', 'nivel_risco_badge', 'pontuacao_risco', 
        'cidade', 'estado', 'criado_em', 'ativo'
    ]
    list_filter = [
        'nivel_risco', 'cidade', 'estado', 'ativo', 'criado_em'
    ]
    search_fields = [
        'cidadao__nome', 'cidadao__cpf', 'endereco_completo', 
        'cidade', 'bairro'
    ]
    readonly_fields = [
        'id', 'coordenadas_geojson', 'dados_mapa', 'criado_em', 'atualizado_em'
    ]
    fieldsets = [
        ('Cidadão', {
            'fields': ('cidadao', 'dados_saude', 'anamnese')
        }),
        ('Localização', {
            'fields': (
                'latitude', 'longitude', 'endereco_completo', 
                'bairro', 'cidade', 'estado', 'cep'
            )
        }),
        ('Classificação de Risco', {
            'fields': ('nivel_risco', 'pontuacao_risco')
        }),
        ('Dados Técnicos', {
            'fields': ('id', 'coordenadas_geojson', 'dados_mapa'),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('ativo', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    ]
    
    def nivel_risco_badge(self, obj):
        """Exibe o nível de risco com badge colorido."""
        cores = {
            'baixo': 'success',
            'medio': 'warning', 
            'alto': 'danger',
            'critico': 'dark'
        }
        cor = cores.get(obj.nivel_risco, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            cor, obj.get_nivel_risco_display()
        )
    nivel_risco_badge.short_description = 'Nível de Risco'
    
    def coordenadas_geojson(self, obj):
        """Exibe coordenadas em formato JSON."""
        return format_html('<pre>{}</pre>', obj.coordenadas_geojson)
    coordenadas_geojson.short_description = 'Coordenadas GeoJSON'
    
    actions = ['recalcular_risco', 'ativar_localizacoes', 'desativar_localizacoes']
    
    def recalcular_risco(self, request, queryset):
        """Recalcula o risco para as localizações selecionadas."""
        count = 0
        for localizacao in queryset:
            localizacao.calcular_risco_completo()
            count += 1
        self.message_user(request, f'{count} localizações tiveram o risco recalculado.')
    recalcular_risco.short_description = 'Recalcular risco das localizações selecionadas'
    
    def ativar_localizacoes(self, request, queryset):
        """Ativa as localizações selecionadas."""
        count = queryset.update(ativo=True)
        self.message_user(request, f'{count} localizações foram ativadas.')
    ativar_localizacoes.short_description = 'Ativar localizações selecionadas'
    
    def desativar_localizacoes(self, request, queryset):
        """Desativa as localizações selecionadas."""
        count = queryset.update(ativo=False)
        self.message_user(request, f'{count} localizações foram desativadas.')
    desativar_localizacoes.short_description = 'Desativar localizações selecionadas'


@admin.register(RelatorioMedico)
class RelatorioMedicoAdmin(admin.ModelAdmin):
    list_display = [
        'cidadao', 'tipo_relatorio', 'status_badge', 'nivel_risco_localizacao',
        'medico_responsavel', 'criado_em'
    ]
    list_filter = [
        'tipo_relatorio', 'status', 'localizacao_saude__nivel_risco', 'criado_em'
    ]
    search_fields = [
        'cidadao__nome', 'cidadao__cpf', 'titulo', 'resumo_clinico'
    ]
    readonly_fields = [
        'id', 'criado_em', 'atualizado_em'
    ]
    fieldsets = [
        ('Informações Básicas', {
            'fields': (
                'cidadao', 'localizacao_saude', 'tipo_relatorio', 
                'status', 'medico_responsavel'
            )
        }),
        ('Conteúdo do Relatório', {
            'fields': (
                'titulo', 'resumo_clinico', 'recomendacoes',
                'medicamentos_sugeridos', 'exames_solicitados', 'observacoes'
            )
        }),
        ('Dados Estruturados', {
            'fields': ('dados_completos',),
            'classes': ('collapse',)
        }),
        ('Metadados', {
            'fields': ('id', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    ]
    
    def status_badge(self, obj):
        """Exibe o status com badge colorido."""
        cores = {
            'gerado': 'info',
            'revisado': 'warning',
            'aprovado': 'success',
            'arquivado': 'secondary'
        }
        cor = cores.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            cor, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def nivel_risco_localizacao(self, obj):
        """Exibe o nível de risco da localização."""
        return obj.localizacao_saude.get_nivel_risco_display()
    nivel_risco_localizacao.short_description = 'Nível de Risco'
    
    actions = ['gerar_relatorios_automaticos', 'marcar_como_revisado']
    
    def gerar_relatorios_automaticos(self, request, queryset):
        """Gera conteúdo automático para os relatórios selecionados."""
        count = 0
        for relatorio in queryset:
            relatorio.gerar_relatorio_automatico()
            count += 1
        self.message_user(request, f'{count} relatórios foram regenerados automaticamente.')
    gerar_relatorios_automaticos.short_description = 'Regenerar conteúdo automático'
    
    def marcar_como_revisado(self, request, queryset):
        """Marca relatórios como revisados."""
        count = queryset.update(status='revisado')
        self.message_user(request, f'{count} relatórios foram marcados como revisados.')
    marcar_como_revisado.short_description = 'Marcar como revisado'


@admin.register(HistoricoLocalizacao)
class HistoricoLocalizacaoAdmin(admin.ModelAdmin):
    list_display = [
        'cidadao', 'coordenadas_antigas', 'coordenadas_novas', 
        'motivo_mudanca', 'usuario_responsavel', 'criado_em'
    ]
    list_filter = [
        'motivo_mudanca', 'usuario_responsavel', 'criado_em'
    ]
    search_fields = [
        'cidadao__nome', 'cidadao__cpf', 'motivo_mudanca'
    ]
    readonly_fields = ['criado_em']
    
    def coordenadas_antigas(self, obj):
        """Exibe coordenadas anteriores."""
        if obj.latitude_anterior and obj.longitude_anterior:
            return f"{obj.latitude_anterior}, {obj.longitude_anterior}"
        return "N/A"
    coordenadas_antigas.short_description = 'Coordenadas Anteriores'
    
    def coordenadas_novas(self, obj):
        """Exibe coordenadas novas."""
        return f"{obj.latitude_nova}, {obj.longitude_nova}"
    coordenadas_novas.short_description = 'Coordenadas Novas'
