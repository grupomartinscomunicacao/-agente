"""
URLs para app LGPD.
"""
from django.urls import path
from . import views

app_name = 'lgpd'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_lgpd, name='dashboard'),
    
    # Consentimento
    path('consentimento/', views.termo_consentimento, name='termo_consentimento'),
    path('consentimento/<uuid:cidadao_id>/', views.termo_consentimento, name='termo_consentimento_cidadao'),
    path('consentimentos/<uuid:cidadao_id>/', views.gerenciar_consentimentos, name='gerenciar_consentimentos'),
    
    # Dados do cidadão
    path('relatorio/<uuid:cidadao_id>/', views.relatorio_dados_cidadao, name='relatorio_dados_cidadao'),
    path('anonimizar/<uuid:cidadao_id>/', views.anonimizar_cidadao, name='anonimizar_cidadao'),
    path('historico/<uuid:cidadao_id>/', views.historico_acessos, name='historico_acessos'),
    
    # Violações
    path('violacoes/', views.violacoes_dados, name='violacoes_dados'),
    path('violacoes/registrar/', views.registrar_violacao, name='registrar_violacao'),
    
    # Política de privacidade
    path('politica/', views.politica_privacidade, name='politica_privacidade'),
    
    # API
    path('api/verificar-consentimento/', views.api_verificar_consentimento, name='api_verificar_consentimento'),
    path('api/relatorio-conformidade/', views.api_relatorio_conformidade, name='api_relatorio_conformidade'),
]