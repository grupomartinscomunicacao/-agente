from django.contrib import admin
from django.utils.html import format_html
from .models import Treinamento, CategoriaTreinamento


@admin.register(CategoriaTreinamento)
class CategoriaTreinamentoAdmin(admin.ModelAdmin):
    """
    Configuração da interface administrativa para o modelo CategoriaTreinamento.
    
    Permite gerenciar as categorias de treinamento com facilidade,
    incluindo ordenação e visualização de estatísticas.
    """
    
    # Organização da listagem
    list_display = [
        'nome',
        'descricao_resumida',
        'ordem',
        'total_treinamentos_display',
        'criado_em'
    ]
    list_filter = [
        'criado_em',
    ]
    search_fields = [
        'nome',
        'descricao'
    ]
    list_editable = ['ordem']  # Permite editar ordem diretamente na lista
    
    # Organização dos campos no formulário
    fieldsets = (
        ('Informações da Categoria', {
            'fields': ('nome', 'descricao')
        }),
        ('Configurações de Exibição', {
            'fields': ('ordem',),
            'description': 'Ordem de exibição (menor número aparece primeiro)'
        }),
    )
    
    # Campos somente leitura
    readonly_fields = ['criado_em', 'atualizado_em']
    
    # Ordenação padrão
    ordering = ['ordem', 'nome']
    
    # Paginação
    list_per_page = 30
    
    def descricao_resumida(self, obj):
        """Exibe uma versão resumida da descrição."""
        if obj.descricao:
            return obj.descricao[:100] + "..." if len(obj.descricao) > 100 else obj.descricao
        return "Sem descrição"
    
    descricao_resumida.short_description = "Descrição"
    
    def total_treinamentos_display(self, obj):
        """Exibe o total de treinamentos ativos na categoria."""
        total = obj.total_treinamentos
        if total > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{} vídeo{}</span>',
                total,
                's' if total != 1 else ''
            )
        return format_html('<span style="color: #999;">0 vídeos</span>')
    
    total_treinamentos_display.short_description = "Treinamentos"


@admin.register(Treinamento)
class TreinamentoAdmin(admin.ModelAdmin):
    """
    Configuração da interface administrativa para o modelo Treinamento.
    
    Organiza os campos em seções lógicas, adiciona filtros úteis e
    melhora a experiência de uso do Django Admin.
    """
    
    # Organização da listagem
    list_display = [
        'titulo',
        'categoria',
        'preview_video', 
        'data_publicacao', 
        'ativo', 
        'criado_em'
    ]
    list_filter = [
        'categoria',  # Filtro por categoria
        'ativo',
        'data_publicacao',
        'criado_em'
    ]
    search_fields = [
        'titulo',
        'descricao',
        'categoria__nome'  # Pesquisar também pelo nome da categoria
    ]
    list_editable = ['ativo']  # Permite editar status diretamente na lista
    
    # Organização dos campos no formulário
    fieldsets = (
        ('Informações do Vídeo', {
            'fields': ('titulo', 'descricao', 'categoria')
        }),
        ('Configurações do YouTube', {
            'fields': ('url_video',)
        }),
        ('Publicação', {
            'fields': ('data_publicacao', 'ativo'),
            'description': 'Controle quando e se o treinamento será visível para os agentes'
        }),
    )
    
    # Campos somente leitura
    readonly_fields = ['criado_em', 'atualizado_em']
    
    # Ordenação padrão (mais recentes primeiro)
    ordering = ['-data_publicacao']
    
    # Paginação
    list_per_page = 20
    
    # Ações personalizadas
    actions = ['ativar_treinamentos', 'desativar_treinamentos']
    
    def preview_video(self, obj):
        """
        Exibe uma prévia do vídeo na listagem do admin.
        """
        video_id = obj.get_youtube_video_id()
        if video_id:
            thumbnail_url = obj.get_thumbnail_url()
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="120" height="68" '
                'style="border-radius: 4px;" title="Ver vídeo no YouTube"/>'
                '</a>',
                obj.url_video,
                thumbnail_url
            )
        return "Vídeo inválido"
    
    preview_video.short_description = "Preview"
    preview_video.admin_order_field = 'url_video'
    
    def ativar_treinamentos(self, request, queryset):
        """Ativa os treinamentos selecionados."""
        count = queryset.update(ativo=True)
        self.message_user(
            request,
            f'{count} treinamento(s) ativado(s) com sucesso.'
        )
    
    ativar_treinamentos.short_description = "Ativar treinamentos selecionados"
    
    def desativar_treinamentos(self, request, queryset):
        """Desativa os treinamentos selecionados."""
        count = queryset.update(ativo=False)
        self.message_user(
            request,
            f'{count} treinamento(s) desativado(s) com sucesso.'
        )
    
    desativar_treinamentos.short_description = "Desativar treinamentos selecionados"
