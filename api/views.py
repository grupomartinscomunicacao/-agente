"""
Views da API REST para o sistema de saúde pública.
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
# from django_filters.rest_framework import DjangoFilterBackend  # Comentado temporariamente
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404

from cidadaos.models import Cidadao, ContatoEmergencia
from saude_dados.models import DadosSaude, HistoricoSaude
from anamneses.models import Anamnese, LogAuditoriaIA, AlertaSaude
from dashboard.models import RelatorioSaude, EstatisticaTempoReal

from .serializers import (
    CidadaoSerializer, ContatoEmergenciaSerializer, DadosSaudeSerializer,
    AnamneseSerializer, AlertaSaudeSerializer, LogAuditoriaIASerializer,
    RelatorioSaudeSerializer, EstatisticaTempoRealSerializer,
    ColetaDadosSerializer, SolicitacaoAnamneseSerializer, FiltroRelatorioSerializer
)

from utils.processors import ProcessadorDadosMedicos, GeradorRelatorios


class CidadaoViewSet(viewsets.ModelViewSet):
    """ViewSet para gerenciamento de cidadãos."""
    
    queryset = Cidadao.objects.filter(ativo=True)
    serializer_class = CidadaoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]  # DjangoFilterBackend comentado
    filterset_fields = ['sexo', 'estado_civil', 'cidade', 'estado', 'possui_plano_saude']
    search_fields = ['nome', 'cpf', 'email']
    ordering_fields = ['nome', 'criado_em', 'data_nascimento']
    ordering = ['-criado_em']
    
    @action(detail=True, methods=['get'])
    def dados_saude(self, request, pk=None):
        """Retorna dados de saúde do cidadão."""
        cidadao = self.get_object()
        dados_saude = DadosSaude.objects.filter(cidadao=cidadao).order_by('-criado_em')
        serializer = DadosSaudeSerializer(dados_saude, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def anamneses(self, request, pk=None):
        """Retorna anamneses do cidadão."""
        cidadao = self.get_object()
        anamneses = Anamnese.objects.filter(cidadao=cidadao).order_by('-criado_em')
        serializer = AnamneseSerializer(anamneses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def historico_completo(self, request, pk=None):
        """Retorna histórico completo do cidadão."""
        cidadao = self.get_object()
        
        # Dados básicos
        dados_cidadao = CidadaoSerializer(cidadao).data
        
        # Dados de saúde
        dados_saude = DadosSaude.objects.filter(cidadao=cidadao).order_by('-criado_em')
        dados_saude_serialized = DadosSaudeSerializer(dados_saude, many=True).data
        
        # Anamneses
        anamneses = Anamnese.objects.filter(cidadao=cidadao).order_by('-criado_em')
        anamneses_serialized = AnamneseSerializer(anamneses, many=True).data
        
        # Alertas ativos
        alertas = AlertaSaude.objects.filter(
            anamnese__cidadao=cidadao,
            resolvido=False
        ).order_by('-prioridade', '-criado_em')
        alertas_serialized = AlertaSaudeSerializer(alertas, many=True).data
        
        return Response({
            'cidadao': dados_cidadao,
            'dados_saude': dados_saude_serialized,
            'anamneses': anamneses_serialized,
            'alertas_ativos': alertas_serialized,
            'total_atendimentos': len(anamneses_serialized),
            'ultimo_atendimento': anamneses_serialized[0]['criado_em'] if anamneses_serialized else None
        })


class DadosSaudeViewSet(viewsets.ModelViewSet):
    """ViewSet para dados de saúde."""
    
    queryset = DadosSaude.objects.all()
    serializer_class = DadosSaudeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]  # DjangoFilterBackend comentado
    # filterset_fields = ['cidadao', 'agente_coleta', 'nivel_dor', 'fumante', 'etilista']  # Comentado
    ordering_fields = ['criado_em', 'pressao_sistolica', 'temperatura']
    ordering = ['-criado_em']
    
    def perform_create(self, serializer):
        """Adiciona agente que coletou os dados."""
        serializer.save(agente_coleta=self.request.user)
    
    @action(detail=True, methods=['get'])
    def dados_processados(self, request, pk=None):
        """Retorna dados processados para análise."""
        dados_saude = self.get_object()
        
        # Obtém dados do cidadão
        cidadao_data = {
            'data_nascimento': dados_saude.cidadao.data_nascimento,
            'sexo': dados_saude.cidadao.sexo,
            'estado_civil': dados_saude.cidadao.estado_civil,
            'profissao': dados_saude.cidadao.profissao,
            'cidade': dados_saude.cidadao.cidade,
            'estado': dados_saude.cidadao.estado,
            'possui_plano_saude': dados_saude.cidadao.possui_plano_saude,
        }
        
        # Processa dados
        processador = ProcessadorDadosMedicos()
        dados_estruturados = processador.processar_dados_completos(
            cidadao_data, 
            dados_saude.get_dados_estruturados()
        )
        
        # Gera resumo
        resumo = GeradorRelatorios.gerar_resumo_anamnese(dados_estruturados)
        
        return Response(resumo)


class AnamneseViewSet(viewsets.ModelViewSet):
    """ViewSet para anamneses."""
    
    queryset = Anamnese.objects.all()
    serializer_class = AnamneseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]  # DjangoFilterBackend comentado
    # filterset_fields = ['cidadao', 'triagem_risco', 'status', 'revisado_por']  # Comentado
    ordering_fields = ['criado_em', 'triagem_risco']
    ordering = ['-criado_em']
    
    @action(detail=False, methods=['get'])
    def pendentes_revisao(self, request):
        """Retorna anamneses pendentes de revisão."""
        anamneses = self.get_queryset().filter(status='pendente')
        serializer = self.get_serializer(anamneses, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def aprovar(self, request, pk=None):
        """Aprova uma anamnese."""
        anamnese = self.get_object()
        
        comentarios = request.data.get('comentarios_revisao', '')
        resumo_final = request.data.get('resumo_final', anamnese.resumo_anamnese)
        diagnostico_final = request.data.get('diagnostico_final', '')
        recomendacoes_finais = request.data.get('recomendacoes_finais', anamnese.recomendacoes)
        
        anamnese.status = 'aprovada'
        anamnese.revisado_por = request.user
        anamnese.data_revisao = timezone.now()
        anamnese.comentarios_revisao = comentarios
        anamnese.resumo_final = resumo_final
        anamnese.diagnostico_final = diagnostico_final
        anamnese.recomendacoes_finais = recomendacoes_finais
        anamnese.save()
        
        serializer = self.get_serializer(anamnese)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def rejeitar(self, request, pk=None):
        """Rejeita uma anamnese."""
        anamnese = self.get_object()
        
        motivo = request.data.get('motivo', '')
        if not motivo:
            return Response(
                {'error': 'Motivo da rejeição é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        anamnese.status = 'rejeitada'
        anamnese.revisado_por = request.user
        anamnese.data_revisao = timezone.now()
        anamnese.comentarios_revisao = motivo
        anamnese.save()
        
        serializer = self.get_serializer(anamnese)
        return Response(serializer.data)


class AlertaSaudeViewSet(viewsets.ModelViewSet):
    """ViewSet para alertas de saúde."""
    
    queryset = AlertaSaude.objects.all()
    serializer_class = AlertaSaudeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]  # DjangoFilterBackend comentado
    # filterset_fields = ['tipo', 'prioridade', 'visualizado', 'resolvido']  # Comentado
    ordering_fields = ['criado_em', 'prioridade', 'prazo_acao']
    ordering = ['-prioridade', '-criado_em']
    
    @action(detail=False, methods=['get'])
    def ativos(self, request):
        """Retorna alertas ativos (não resolvidos)."""
        alertas = self.get_queryset().filter(resolvido=False)
        serializer = self.get_serializer(alertas, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def marcar_visualizado(self, request, pk=None):
        """Marca alerta como visualizado."""
        alerta = self.get_object()
        alerta.visualizado = True
        alerta.save()
        
        serializer = self.get_serializer(alerta)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resolver(self, request, pk=None):
        """Resolve um alerta."""
        alerta = self.get_object()
        
        alerta.resolvido = True
        alerta.resolvido_por = request.user
        alerta.data_resolucao = timezone.now()
        alerta.save()
        
        serializer = self.get_serializer(alerta)
        return Response(serializer.data)


class RelatorioSaudeViewSet(viewsets.ModelViewSet):
    """ViewSet para relatórios de saúde."""
    
    queryset = RelatorioSaude.objects.all()
    serializer_class = RelatorioSaudeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]  # DjangoFilterBackend comentado
    # filterset_fields = ['tipo', 'publicado', 'gerado_por']  # Comentado
    ordering_fields = ['criado_em', 'periodo_inicio']
    ordering = ['-criado_em']
    
    @action(detail=False, methods=['post'])
    def gerar_relatorio(self, request):
        """Gera um novo relatório baseado em filtros."""
        serializer = FiltroRelatorioSerializer(data=request.data)
        if serializer.is_valid():
            # Aqui seria chamado o serviço de geração de relatórios
            # Por enquanto, retorna estrutura básica
            filtros = serializer.validated_data
            
            # TODO: Implementar geração real do relatório
            relatorio_data = {
                'tipo': 'especial',
                'titulo': f"Relatório {filtros['data_inicio']} a {filtros['data_fim']}",
                'periodo_inicio': filtros['data_inicio'],
                'periodo_fim': filtros['data_fim'],
                'total_atendimentos': 0,
                'total_cidadaos': 0,
                'gerado_por': request.user.id
            }
            
            relatorio_serializer = RelatorioSaudeSerializer(data=relatorio_data)
            if relatorio_serializer.is_valid():
                relatorio = relatorio_serializer.save()
                return Response(RelatorioSaudeSerializer(relatorio).data, 
                              status=status.HTTP_201_CREATED)
            
            return Response(relatorio_serializer.errors, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Views de funcionalidade específica

from rest_framework.views import APIView
from django.utils import timezone

class ColetaDadosAPIView(APIView):
    """
    Endpoint para coleta completa de dados (cidadão + saúde).
    Usado pelos agentes de saúde em campo.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Coleta dados completos de cidadão e saúde."""
        serializer = ColetaDadosSerializer(data=request.data)
        
        if serializer.is_valid():
            resultado = serializer.save()
            
            return Response({
                'success': True,
                'cidadao_id': str(resultado['cidadao'].id),
                'dados_saude_id': str(resultado['dados_saude'].id),
                'message': 'Dados coletados com sucesso'
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SolicitarAnamneseAPIView(APIView):
    """
    Endpoint para solicitar anamnese automática via IA.
    Processa de forma assíncrona usando Celery.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Solicita geração de anamnese."""
        serializer = SolicitacaoAnamneseSerializer(data=request.data)
        
        if serializer.is_valid():
            dados_saude_id = serializer.validated_data['dados_saude_id']
            prioridade = serializer.validated_data['prioridade']
            modelo_ia = serializer.validated_data['modelo_ia']
            
            # TODO: Aqui seria enviado para fila Celery
            # Por enquanto, cria anamnese básica
            try:
                dados_saude = DadosSaude.objects.get(id=dados_saude_id)
                
                anamnese = Anamnese.objects.create(
                    cidadao=dados_saude.cidadao,
                    dados_saude=dados_saude,
                    resumo_anamnese="Anamnese em processamento...",
                    hipoteses_diagnosticas=[],
                    triagem_risco='baixo',
                    recomendacoes="Aguardando processamento da IA",
                    modelo_ia_usado=modelo_ia,
                    dados_entrada_ia={},
                    resposta_completa_ia={}
                )
                
                return Response({
                    'success': True,
                    'anamnese_id': str(anamnese.id),
                    'status': 'processando',
                    'message': 'Anamnese solicitada com sucesso'
                }, status=status.HTTP_202_ACCEPTED)
                
            except DadosSaude.DoesNotExist:
                return Response(
                    {'error': 'Dados de saúde não encontrados'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DashboardAPIView(APIView):
    """
    Endpoint para dados do dashboard em tempo real.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Retorna estatísticas do dashboard."""
        # Atualiza estatísticas
        stats = EstatisticaTempoReal.get_current()
        stats.atualizar_contadores()
        
        # Serializa dados
        serializer = EstatisticaTempoRealSerializer(stats)
        
        # Adiciona dados extras
        dados_dashboard = serializer.data.copy()
        
        # Alertas urgentes
        alertas_urgentes = AlertaSaude.objects.filter(
            prioridade='urgente',
            resolvido=False
        ).count()
        
        # Anamneses por risco hoje
        hoje = timezone.now().date()
        anamneses_hoje = Anamnese.objects.filter(criado_em__date=hoje)
        
        distribuicao_risco = anamneses_hoje.values('triagem_risco').annotate(
            count=Count('id')
        )
        
        dados_dashboard.update({
            'alertas_urgentes': alertas_urgentes,
            'distribuicao_risco_hoje': {item['triagem_risco']: item['count'] 
                                      for item in distribuicao_risco},
            'anamneses_por_status': {
                'pendente': anamneses_hoje.filter(status='pendente').count(),
                'aprovada': anamneses_hoje.filter(status='aprovada').count(),
                'rejeitada': anamneses_hoje.filter(status='rejeitada').count(),
            }
        })
        
        return Response(dados_dashboard)


class SincronizacaoOfflineAPIView(APIView):
    """
    Endpoint para sincronização de dados offline.
    Usado pelos agentes em campo com conectividade intermitente.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Sincroniza dados coletados offline."""
        dados_lote = request.data.get('dados', [])
        resultados = []
        
        for item in dados_lote:
            try:
                # Verifica se é dados de cidadão ou dados de saúde
                if 'cidadao' in item:
                    serializer = ColetaDadosSerializer(data=item)
                else:
                    serializer = DadosSaudeSerializer(data=item)
                
                if serializer.is_valid():
                    resultado = serializer.save()
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': True,
                        'id_servidor': str(resultado.id) if hasattr(resultado, 'id') else str(resultado['cidadao'].id)
                    })
                else:
                    resultados.append({
                        'id_local': item.get('id_local'),
                        'success': False,
                        'errors': serializer.errors
                    })
                    
            except Exception as e:
                resultados.append({
                    'id_local': item.get('id_local'),
                    'success': False,
                    'errors': str(e)
                })
        
        return Response({
            'total_processados': len(dados_lote),
            'sucessos': len([r for r in resultados if r['success']]),
            'erros': len([r for r in resultados if not r['success']]),
            'resultados': resultados
        })
