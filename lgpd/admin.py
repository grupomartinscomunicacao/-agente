"""
Django admin para app LGPD.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse

from .models import (
    ConsentimentoLGPD, AuditoriaAcesso, DadosAnonimizados, 
    ViolacaoDados, PoliticaPrivacidade
)


@admin.register(ConsentimentoLGPD)
class ConsentimentoLGPDAdmin(admin.ModelAdmin):
    list_display = [
        'cidadao', 'finalidade', 'consentido', 'ativo_status', 
        'data_consentimento', 'valido_ate'
    ]
    list_filter = [
        'finalidade', 'consentido', 'data_consentimento', 'valido_ate'
    ]
    search_fields = ['cidadao__nome', 'cidadao__cpf']
    readonly_fields = ['token_consentimento', 'criado_em', 'atualizado_em']
    
    def ativo_status(self, obj):
        if obj.ativo:
            return format_html('<span style="color: green;">✓ Ativo</span>')
        else:
            return format_html('<span style="color: red;">✗ Inativo</span>')
    ativo_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('cidadao')


@admin.register(AuditoriaAcesso)
class AuditoriaAcessoAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'usuario', 'cidadao', 'tipo_acao', 'ip_address'
    ]
    list_filter = ['tipo_acao', 'timestamp']
    search_fields = ['cidadao__nome', 'usuario__username', 'ip_address']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario', 'cidadao')


@admin.register(DadosAnonimizados)
class DadosAnonimizadosAdmin(admin.ModelAdmin):
    list_display = [
        'hash_cidadao', 'faixa_etaria', 'sexo', 'regiao_residencia',
        'nivel_risco_geral', 'data_anonimizacao'
    ]
    list_filter = [
        'faixa_etaria', 'sexo', 'nivel_risco_geral', 'data_anonimizacao'
    ]
    search_fields = ['hash_cidadao', 'regiao_residencia']
    readonly_fields = ['data_anonimizacao']
    date_hierarchy = 'data_anonimizacao'


@admin.register(ViolacaoDados)
class ViolacaoDadosAdmin(admin.ModelAdmin):
    list_display = [
        'tipo_violacao', 'severidade', 'data_deteccao', 
        'resolvida', 'anpd_notificada', 'cidadaos_notificados'
    ]
    list_filter = [
        'tipo_violacao', 'severidade', 'resolvida', 
        'anpd_notificada', 'data_deteccao'
    ]
    search_fields = ['descricao']
    readonly_fields = ['data_deteccao']
    date_hierarchy = 'data_deteccao'
    
    fieldsets = (
        ('Informações da Violação', {
            'fields': ('tipo_violacao', 'severidade', 'descricao', 'data_deteccao', 'data_ocorrencia_estimada')
        }),
        ('Dados Afetados', {
            'fields': ('cidadaos_afetados', 'tipos_dados_afetados')
        }),
        ('Resposta e Notificações', {
            'fields': (
                'acoes_corretivas', 'anpd_notificada', 'data_notificacao_anpd',
                'cidadaos_notificados', 'data_notificacao_cidadaos'
            )
        }),
        ('Status', {
            'fields': ('resolvida', 'data_resolucao')
        })
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Novo objeto
            obj.detectado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(PoliticaPrivacidade)
class PoliticaPrivacidadeAdmin(admin.ModelAdmin):
    list_display = ['versao', 'titulo', 'ativa', 'data_vigencia', 'criada_em']
    list_filter = ['ativa', 'data_vigencia', 'criada_em']
    search_fields = ['titulo', 'versao']
    readonly_fields = ['criada_em']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Novo objeto
            obj.criada_por = request.user
        super().save_model(request, obj, form, change)


# Configurações globais do admin
admin.site.site_header = 'Sistema de Saúde - Administração LGPD'
admin.site.site_title = 'Admin LGPD'
admin.site.index_title = 'Conformidade LGPD'