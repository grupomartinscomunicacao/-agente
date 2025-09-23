"""
Views para o módulo de geolocalização e mapas de risco.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone

import json
import logging
import requests
from decimal import Decimal

from .models import LocalizacaoSaude, RelatorioMedico, HistoricoLocalizacao
from cidadaos.models import Cidadao
from saude_dados.models import DadosSaude

logger = logging.getLogger(__name__)


class MapaRiscoView(TemplateView):
    """
    View principal para exibir o mapa de calor com os riscos de saúde.
    """
    template_name = 'geolocation/mapa_risco_simples.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas para o mapa - apenas cidadãos com anamneses
        total_localizacoes = LocalizacaoSaude.objects.filter(
            ativo=True, 
            anamnese__isnull=False
        ).count()
        
        stats_risco = LocalizacaoSaude.objects.filter(
            ativo=True,
            anamnese__isnull=False
        ).values('nivel_risco').annotate(count=Count('id'))
        
        # Organizar estatísticas
        stats = {
            'total': total_localizacoes,
            'baixo': 0,
            'medio': 0,
            'alto': 0,
            'critico': 0
        }
        
        for stat in stats_risco:
            stats[stat['nivel_risco']] = stat['count']
        
        # Coordenadas do centro (Brasília como padrão)
        centro_mapa = {
            'lat': -15.7939,
            'lng': -47.8828,
            'zoom': 10
        }
        
        context.update({
            'stats': stats,
            'centro_mapa': centro_mapa,
        })
        
        return context


class MapaDadosAPIView(TemplateView):
    """
    API que retorna dados das localizações para o mapa.
    Apenas cidadãos com anamneses aparecem no mapa.
    """
    
    def get(self, request, *args, **kwargs):
        """Retorna dados JSON das localizações para o mapa."""
        try:
            # Filtros opcionais
            nivel_risco = request.GET.get('risco')
            cidade = request.GET.get('cidade')
            data_inicio = request.GET.get('data_inicio')
            data_fim = request.GET.get('data_fim')
            
            # Query base - APENAS localizações que têm anamneses associadas
            query = LocalizacaoSaude.objects.filter(
                ativo=True,
                anamnese__isnull=False  # Só aparecem no mapa se tiverem anamnese
            ).select_related('cidadao', 'anamnese')
            
            # Aplicar filtros
            if nivel_risco and nivel_risco != 'todos':
                query = query.filter(nivel_risco=nivel_risco)
            
            if cidade:
                query = query.filter(cidade__icontains=cidade)
            
            if data_inicio:
                query = query.filter(anamnese__criado_em__date__gte=data_inicio)
            
            if data_fim:
                query = query.filter(anamnese__criado_em__date__lte=data_fim)
            
            # Limitar resultados para performance
            query = query[:1000]
            
            # Converter para formato do mapa
            marcadores = []
            for localizacao in query:
                marcadores.append(localizacao.dados_mapa)
            
            return JsonResponse({
                'success': True,
                'marcadores': marcadores,
                'total': len(marcadores)
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do mapa: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class CapturaLocalizacaoView(LoginRequiredMixin, TemplateView):
    """
    View para capturar localização durante o cadastro de cidadão.
    """
    
    def post(self, request, *args, **kwargs):
        """Processa dados de localização enviados via JavaScript."""
        try:
            data = json.loads(request.body)
            cidadao_id = data.get('cidadao_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            endereco = data.get('endereco', '')
            
            # Validações básicas
            if not all([cidadao_id, latitude, longitude]):
                return JsonResponse({
                    'success': False,
                    'error': 'Dados incompletos'
                }, status=400)
            
            # Buscar cidadão
            try:
                cidadao = Cidadao.objects.get(id=cidadao_id)
            except Cidadao.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Cidadão não encontrado'
                }, status=404)
            
            # Salvar localização no cidadão
            if cidadao.latitude and cidadao.longitude:
                # Registrar histórico se houve mudança
                HistoricoLocalizacao.objects.create(
                    cidadao=cidadao,
                    latitude_anterior=cidadao.latitude,
                    longitude_anterior=cidadao.longitude,
                    latitude_nova=Decimal(str(latitude)),
                    longitude_nova=Decimal(str(longitude)),
                    motivo_mudanca="Atualização via geolocalização",
                    usuario_responsavel=request.user
                )
            
            cidadao.latitude = Decimal(str(latitude))
            cidadao.longitude = Decimal(str(longitude))
            cidadao.endereco_capturado_automaticamente = True
            
            # Se o endereço foi obtido via reverse geocoding
            if endereco:
                cidadao.endereco = endereco
            
            cidadao.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Localização capturada com sucesso!',
                'dados': {
                    'latitude': float(cidadao.latitude),
                    'longitude': float(cidadao.longitude),
                    'endereco': cidadao.endereco
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato de dados inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"Erro ao capturar localização: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            }, status=500)


class ProcessarRiscoView(LoginRequiredMixin, TemplateView):
    """
    View para processar classificação de risco após coleta de dados de saúde.
    """
    
    def post(self, request, *args, **kwargs):
        """Processa classificação de risco após coleta de dados."""
        try:
            dados_saude_id = request.POST.get('dados_saude_id')
            
            if not dados_saude_id:
                return JsonResponse({
                    'success': False,
                    'error': 'ID dos dados de saúde não fornecido'
                }, status=400)
            
            # Buscar dados de saúde
            try:
                dados_saude = DadosSaude.objects.get(id=dados_saude_id)
            except DadosSaude.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Dados de saúde não encontrados'
                }, status=404)
            
            cidadao = dados_saude.cidadao
            
            # Verificar se o cidadão tem localização
            if not cidadao.tem_localizacao:
                return JsonResponse({
                    'success': False,
                    'error': 'Cidadão não possui dados de localização'
                }, status=400)
            
            # Criar ou atualizar LocalizacaoSaude
            localizacao_saude, created = LocalizacaoSaude.objects.get_or_create(
                cidadao=cidadao,
                latitude=cidadao.latitude,
                longitude=cidadao.longitude,
                defaults={
                    'dados_saude': dados_saude,
                    'endereco_completo': cidadao.endereco,
                    'bairro': cidadao.bairro,
                    'cidade': cidadao.cidade,
                    'estado': cidadao.estado,
                    'cep': cidadao.cep,
                }
            )
            
            # Se já existe, atualizar com novos dados
            if not created:
                localizacao_saude.dados_saude = dados_saude
                localizacao_saude.save()
            
            # Calcular risco
            nivel_risco = localizacao_saude.calcular_risco_completo()
            
            # Gerar relatório médico
            relatorio = RelatorioMedico.objects.create(
                cidadao=cidadao,
                localizacao_saude=localizacao_saude,
                tipo_relatorio='triagem',
                titulo=f"Relatório de Triagem - {cidadao.nome}"
            )
            relatorio.gerar_relatorio_automatico()
            
            return JsonResponse({
                'success': True,
                'message': f'Risco classificado como: {nivel_risco.upper()}',
                'dados': {
                    'nivel_risco': nivel_risco,
                    'pontuacao_risco': localizacao_saude.pontuacao_risco,
                    'relatorio_id': str(relatorio.id),
                    'cor_marcador': localizacao_saude.get_cor_marcador(),
                }
            })
            
        except Exception as e:
            logger.error(f"Erro ao processar risco: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Erro interno do servidor'
            }, status=500)


class RelatorioMedicoDetailView(LoginRequiredMixin, DetailView):
    """
    View para exibir detalhes de um relatório médico.
    """
    model = RelatorioMedico
    template_name = 'geolocation/relatorio_medico.html'
    context_object_name = 'relatorio'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        relatorio = self.object
        context.update({
            'cidadao': relatorio.cidadao,
            'localizacao': relatorio.localizacao_saude,
            'nivel_risco_cor': relatorio.localizacao_saude.get_cor_marcador(),
        })
        
        return context


class ListaRelatoriosView(LoginRequiredMixin, ListView):
    """
    Lista de relatórios médicos gerados.
    """
    model = RelatorioMedico
    template_name = 'geolocation/lista_relatorios.html'
    context_object_name = 'relatorios'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = RelatorioMedico.objects.select_related(
            'cidadao', 'localizacao_saude'
        ).order_by('-criado_em')
        
        # Filtros
        tipo = self.request.GET.get('tipo')
        risco = self.request.GET.get('risco')
        status = self.request.GET.get('status')
        
        if tipo:
            queryset = queryset.filter(tipo_relatorio=tipo)
        
        if risco:
            queryset = queryset.filter(localizacao_saude__nivel_risco=risco)
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Opções para filtros
        context.update({
            'tipos_relatorio': RelatorioMedico.TIPO_RELATORIO_CHOICES,
            'niveis_risco': LocalizacaoSaude.NIVEL_RISCO_CHOICES,
            'status_choices': RelatorioMedico.STATUS_CHOICES,
        })
        
        return context


class EstatisticasRiscoView(LoginRequiredMixin, TemplateView):
    """
    View para exibir estatísticas detalhadas de risco geográfico.
    """
    template_name = 'geolocation/estatisticas_risco.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas por nível de risco
        stats_risco = LocalizacaoSaude.objects.filter(ativo=True).values(
            'nivel_risco'
        ).annotate(count=Count('id')).order_by('nivel_risco')
        
        # Estatísticas por cidade
        stats_cidade = LocalizacaoSaude.objects.filter(ativo=True).values(
            'cidade', 'nivel_risco'
        ).annotate(count=Count('id')).order_by('cidade', 'nivel_risco')
        
        # Estatísticas temporais (últimos 30 dias)
        data_limite = timezone.now() - timezone.timedelta(days=30)
        stats_temporais = LocalizacaoSaude.objects.filter(
            ativo=True,
            criado_em__gte=data_limite
        ).extra(
            select={'dia': 'date(criado_em)'}
        ).values('dia', 'nivel_risco').annotate(
            count=Count('id')
        ).order_by('dia')
        
        context.update({
            'stats_risco': stats_risco,
            'stats_cidade': stats_cidade,
            'stats_temporais': stats_temporais,
        })
        
        return context


def geocodificar_endereco(request):
    """
    Função auxiliar para geocodificação de endereços usando Google Maps API.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            endereco = data.get('endereco')
            
            if not endereco:
                return JsonResponse({
                    'success': False,
                    'error': 'Endereço não fornecido'
                }, status=400)
            
            # Aqui você integraria com a API do Google Maps
            # Para desenvolvimento, retornando coordenadas fictícias de Brasília
            coordenadas_ficticias = {
                'lat': -15.7939 + (hash(endereco) % 1000) / 10000,  # Variação fictícia
                'lng': -47.8828 + (hash(endereco) % 1000) / 10000,
                'endereco_formatado': endereco,
                'cidade': 'Brasília',
                'estado': 'DF',
                'cep': '70000-000'
            }
            
            return JsonResponse({
                'success': True,
                'dados': coordenadas_ficticias
            })
            
        except Exception as e:
            logger.error(f"Erro na geocodificação: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Erro na geocodificação'
            }, status=500)
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'}, status=405)


def teste_mapa_simples(request):
    """View para testar mapa Leaflet básico."""
    html = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <title>Teste Mapa Leaflet</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        #map { height: 400px; width: 100%; }
        body { font-family: Arial, sans-serif; padding: 20px; }
    </style>
</head>
<body>
    <h2>🗺️ Teste de Mapa Leaflet</h2>
    <div id="map"></div>
    <div id="status" style="margin-top: 10px;"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const statusDiv = document.getElementById('status');
        
        try {
            statusDiv.innerHTML = '⏳ Iniciando mapa...';
            console.log('Iniciando mapa...');
            
            const map = L.map('map').setView([-23.5505, -46.6333], 13);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);

            // Adicionar marcador de teste
            L.marker([-23.5505, -46.6333])
                .addTo(map)
                .bindPopup('🏥 Teste São Paulo - Sistema de Saúde')
                .openPopup();
            
            statusDiv.innerHTML = '✅ Mapa criado com sucesso!';
            console.log('Mapa criado com sucesso!');
        } catch (error) {
            statusDiv.innerHTML = '❌ Erro ao criar mapa: ' + error.message;
            console.error('Erro ao criar mapa:', error);
        }
    </script>
</body>
</html>
    """
    return HttpResponse(html)


def debug_mapa(request):
    """View para debug completo do mapa com dados da API."""
    html = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debug Mapa</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" 
          crossorigin=""/>
    <style>
        #mapa { height: 400px; border: 2px solid #ccc; }
        body { font-family: Arial, sans-serif; margin: 20px; }
        .debug { margin: 10px 0; padding: 10px; background: #f5f5f5; border-radius: 5px; }
        .error { background: #ffebee; color: #c62828; }
        .success { background: #e8f5e8; color: #2e7d32; }
    </style>
</head>
<body>
    <h1>🗺️ Debug do Mapa de Risco</h1>
    
    <div class="debug">
        <strong>Status:</strong>
        <div id="console"></div>
    </div>
    
    <div id="mapa"></div>
    
    <div class="debug">
        <h3>Dados da API:</h3>
        <pre id="api-data">Carregando...</pre>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" 
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" 
            crossorigin=""></script>
    
    <script>
        const consoleDiv = document.getElementById('console');
        const apiDataDiv = document.getElementById('api-data');
        
        function log(message, type = 'info') {
            console.log(message);
            const div = document.createElement('div');
            div.textContent = new Date().toLocaleTimeString() + ' - ' + message;
            div.className = type;
            consoleDiv.appendChild(div);
        }
        
        log('Iniciando debug...');
        
        // Teste se Leaflet carregou
        if (typeof L !== 'undefined') {
            log('✅ Leaflet carregou', 'success');
        } else {
            log('❌ Leaflet não carregou', 'error');
            apiDataDiv.textContent = 'Erro: Leaflet não carregou';
        }
        
        // Criar mapa
        try {
            log('Criando mapa...');
            const map = L.map('mapa').setView([-15.7939, -47.8828], 10);
            log('✅ Mapa criado', 'success');
            
            // Adicionar tiles
            const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            });
            tiles.addTo(map);
            log('✅ Tiles adicionados', 'success');
            
            // Testar API
            log('Testando API...');
            fetch('/geolocation/api/mapa-dados/')
                .then(response => {
                    log('Resposta da API: ' + response.status);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    apiDataDiv.textContent = JSON.stringify(data, null, 2);
                    log('✅ Dados recebidos: ' + JSON.stringify(data), 'success');
                    
                    if (data.success && data.marcadores && data.marcadores.length > 0) {
                        log('Adicionando ' + data.marcadores.length + ' marcadores...', 'success');
                        
                        data.marcadores.forEach((item, index) => {
                            try {
                                const marker = L.circleMarker([item.lat, item.lng], {
                                    color: item.cor_marcador || '#FF0000',
                                    fillColor: item.cor_marcador || '#FF0000',
                                    fillOpacity: 0.7,
                                    radius: 8
                                }).addTo(map);
                                
                                marker.bindPopup(
                                    '<strong>' + (item.nome || 'Sem nome') + '</strong><br>' +
                                    'Risco: ' + (item.nivel_risco || 'N/A') + '<br>' +
                                    'Coords: ' + item.lat + ', ' + item.lng
                                );
                                
                                log('✅ Marcador ' + index + ': ' + (item.nome || 'Sem nome'), 'success');
                            } catch (e) {
                                log('❌ Erro no marcador ' + index + ': ' + e.message, 'error');
                            }
                        });
                        
                        // Ajustar visualização
                        try {
                            const group = L.featureGroup(Object.values(map._layers).filter(layer => layer instanceof L.CircleMarker));
                            if (group.getLayers().length > 0) {
                                map.fitBounds(group.getBounds().pad(0.1));
                                log('✅ Mapa ajustado aos marcadores', 'success');
                            }
                        } catch (e) {
                            log('⚠️ Não foi possível ajustar o zoom: ' + e.message);
                        }
                    } else {
                        log('⚠️ Nenhum marcador encontrado ou dados inválidos');
                    }
                })
                .catch(error => {
                    log('❌ Erro na API: ' + error.message, 'error');
                    apiDataDiv.textContent = 'Erro: ' + error.message;
                });
                
        } catch (error) {
            log('❌ Erro ao criar mapa: ' + error.message, 'error');
        }
    </script>
</body>
</html>
    """
    return HttpResponse(html)
