"""
URLs para o módulo de geolocalização.
"""
from django.urls import path
from . import views

app_name = 'geolocation'

urlpatterns = [
    # Mapa principal
    path('mapa/', views.MapaRiscoView.as_view(), name='mapa_risco'),
    
    # API para dados do mapa
    path('api/mapa-dados/', views.MapaDadosAPIView.as_view(), name='mapa_dados_api'),
    
    # Captura de localização
    path('api/capturar-localizacao/', views.CapturaLocalizacaoView.as_view(), name='capturar_localizacao'),
    
    # Processamento de risco
    path('api/processar-risco/', views.ProcessarRiscoView.as_view(), name='processar_risco'),
    
    # Relatórios médicos
    path('relatorios/', views.ListaRelatoriosView.as_view(), name='lista_relatorios'),
    path('relatorio/<uuid:pk>/', views.RelatorioMedicoDetailView.as_view(), name='relatorio_detail'),
    
    # Estatísticas
    path('estatisticas/', views.EstatisticasRiscoView.as_view(), name='estatisticas_risco'),
    
    # Geocodificação
    path('api/geocodificar/', views.geocodificar_endereco, name='geocodificar_endereco'),
    
    # Teste de mapa (DEBUG)
    path('teste-mapa/', views.teste_mapa_simples, name='teste_mapa'),
    path('debug-mapa/', views.debug_mapa, name='debug_mapa'),
]