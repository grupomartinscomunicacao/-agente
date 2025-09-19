"""
URLs da API REST para o sistema de saúde pública.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    CidadaoViewSet, DadosSaudeViewSet, AnamneseViewSet,
    AlertaSaudeViewSet, RelatorioSaudeViewSet,
    ColetaDadosAPIView, SolicitarAnamneseAPIView,
    DashboardAPIView, SincronizacaoOfflineAPIView
)

# Router para ViewSets
router = DefaultRouter()
router.register(r'cidadaos', CidadaoViewSet)
router.register(r'dados-saude', DadosSaudeViewSet)
router.register(r'anamneses', AnamneseViewSet)
router.register(r'alertas', AlertaSaudeViewSet)
router.register(r'relatorios', RelatorioSaudeViewSet)

app_name = 'api'

urlpatterns = [
    # Endpoints dos ViewSets
    path('', include(router.urls)),
    
    # Autenticação
    path('auth/token/', obtain_auth_token, name='auth_token'),
    
    # Endpoints específicos
    path('coleta-dados/', ColetaDadosAPIView.as_view(), name='coleta_dados'),
    path('solicitar-anamnese/', SolicitarAnamneseAPIView.as_view(), name='solicitar_anamnese'),
    path('dashboard/', DashboardAPIView.as_view(), name='dashboard'),
    path('sincronizacao/', SincronizacaoOfflineAPIView.as_view(), name='sincronizacao_offline'),
]