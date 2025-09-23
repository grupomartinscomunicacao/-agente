"""
URLs para o dashboard e frontend.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard principal
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard_alt'),  # URL alternativa
    
    # Coleta de dados
    path('coleta/', views.ColetaDadosView.as_view(), name='coleta_dados'),
    path('coleta/cidadao/', views.CadastroCidadaoView.as_view(), name='cadastro_cidadao'),
    path('coleta/saude/', views.ColetaSaudeView.as_view(), name='coleta_saude'),
    
    # Gestão de anamneses
    path('anamneses/', views.AnamnesesListView.as_view(), name='anamneses_list'),
    path('anamneses/<uuid:pk>/', views.AnamneseDetailView.as_view(), name='anamnese_detail'),
    path('anamneses/<uuid:pk>/revisar/', views.RevisarAnamneseView.as_view(), name='revisar_anamnese'),
    path('nova-anamnese/', views.NovaAnamneseView.as_view(), name='nova_anamnese'),
    
    # Relatórios
    path('relatorios/', views.RelatoriosView.as_view(), name='relatorios'),
    path('relatorios/cidadaos/', views.RelatorioCidadaosView.as_view(), name='relatorio_cidadaos'),
    path('relatorios/gerar/', views.GerarRelatorioView.as_view(), name='gerar_relatorio'),
    path('relatorios/<int:pk>/', views.RelatorioDetailView.as_view(), name='relatorio_detail'),
    
    # Alertas
    path('alertas/', views.AlertasView.as_view(), name='alertas'),
    path('alertas/<uuid:pk>/resolver/', views.ResolverAlertaView.as_view(), name='resolver_alerta'),
    
    # Cidadãos
    path('cidadaos/', views.CidadaosListView.as_view(), name='cidadaos_list'),
    path('cidadaos/<uuid:pk>/', views.CidadaoDetailView.as_view(), name='cidadao_detail'),
    path('cidadaos/novo/', views.CidadaoCreateView.as_view(), name='cidadao_create'),
    path('cidadaos/<uuid:pk>/editar/', views.CidadaoUpdateView.as_view(), name='cidadao_update'),
    path('cidadaos/<uuid:pk>/dados-saude/', views.DadosSaudeCreateView.as_view(), name='dados_saude_create'),
    
    # Alertas  
    path('alertas/', views.AlertasListView.as_view(), name='alertas_list'),
    
    # AJAX endpoints
    path('ajax/dashboard-stats/', views.DashboardStatsAjaxView.as_view(), name='dashboard_stats_ajax'),
    path('ajax/anamnese-form/', views.AnamneseFormAjaxView.as_view(), name='anamnese_form_ajax'),
    path('ajax/validar-cpf/', views.ValidarCPFAjaxView.as_view(), name='validar_cpf_ajax'),
    path('ajax/gerar-anamnese/', views.GerarAnamneseAjaxView.as_view(), name='gerar_anamnese_ajax'),
    path('ajax/processar-todas-anamneses/', views.ProcessarTodasAnamnesessAjaxView.as_view(), name='processar_todas_anamneses_ajax'),
    
    # Teste (desenvolvimento)
    path('test-nova-anamnese/', views.TestNovaAnamneseView.as_view(), name='test_nova_anamnese'),
]