"""
Views para o dashboard e frontend do sistema de saúde.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

from cidadaos.models import Cidadao, ContatoEmergencia
from saude_dados.models import DadosSaude
from anamneses.models import Anamnese, AlertaSaude
from dashboard.models import EstatisticaTempoReal, RelatorioSaude, VisitaAgendada, Treinamento
from dashboard.forms import VisitaAgendadaForm, FiltroVisitasForm
from api.serializers import ColetaDadosSerializer, DadosSaudeSerializer
from utils.validators import ValidadorDados, NormalizadorTexto
from utils.tasks import gerar_anamnese_automatica
from ai_integracao.assistant_service import OpenAIAssistantService


class DashboardView(TemplateView):
    """Dashboard principal com estatísticas em tempo real."""
    template_name = 'dashboard/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.now().date()

        # Calcular estatísticas reais do banco de dados
        stats = self._calculate_real_stats()
        
        # Busca dados para os cards e listas
        context.update({
            'stats': stats,
            'alertas_urgentes': self._get_alertas_urgentes(),
            'anamneses_pendentes': self._get_anamneses_pendentes(),
            'alertas_recentes': self._get_alertas_recentes(),
            'treinamentos_recentes': self._get_treinamentos_recentes(),
        })

        # Dados para o minimapa de risco
        context['dados_mapa_risco'] = self._get_dados_mapa_risco()
        
        return context

    def _calculate_real_stats(self):
        """Calcula estatísticas reais do banco de dados."""
        try:
            # Contar dados reais do banco
            total_cidadaos = Cidadao.objects.count()  # Todos os cidadãos cadastrados
            
            # Cidadãos com dados de saúde (que possuem alguma condição médica)
            cidadaos_com_dados_saude = Cidadao.objects.filter(
                Q(possui_hipertensao=True) | 
                Q(possui_diabetes=True) | 
                Q(possui_doenca_cardiaca=True) |
                Q(possui_doenca_renal=True) |
                Q(possui_asma=True) |
                Q(possui_depressao=True) |
                Q(medicamentos_continuo__isnull=False) |
                Q(alergias_conhecidas__isnull=False)
            ).count()
            
            # Visitas pendentes (agendadas)
            visitas_pendentes = VisitaAgendada.objects.filter(
                status='agendada'
            ).count()
            
            # Anamneses completas (concluídas ou qualquer status não pendente)
            anamneses_completas = Anamnese.objects.filter(
                status__in=['concluida', 'aprovada', 'finalizada']
            ).count()
            # Se não houver com esses status, contar todas as não pendentes
            if anamneses_completas == 0:
                anamneses_completas = Anamnese.objects.exclude(status='pendente').count()
            
            # Total de bairros únicos (removendo vazios e duplicatas)
            total_bairros = Cidadao.objects.values_list('bairro', flat=True).exclude(
                Q(bairro__isnull=True) | Q(bairro__exact='')
            ).distinct().count()
            
            # Dados extras para cards adicionais
            visitas_realizadas = VisitaAgendada.objects.filter(status='realizada').count()
            anamneses_pendentes = Anamnese.objects.filter(status='pendente').count()
            total_visitas = VisitaAgendada.objects.count()
            total_anamneses = Anamnese.objects.count()
            
            # Casos de risco alto (tentar do módulo geolocation)
            try:
                from geolocation.models import LocalizacaoSaude
                casos_risco_alto = LocalizacaoSaude.objects.filter(
                    nivel_risco__in=['alto', 'critico']
                ).count()
            except:
                # Fallback: calcular baseado em condições de saúde graves
                casos_risco_alto = Cidadao.objects.filter(
                    Q(possui_doenca_cardiaca=True) | Q(possui_doenca_renal=True)
                ).count()
            
            # Debug: imprimir valores calculados
            logger.info(f"Stats calculadas: cidadãos={total_cidadaos}, com_saude={cidadaos_com_dados_saude}, "
                       f"visitas_pendentes={visitas_pendentes}, anamneses_completas={anamneses_completas}, "
                       f"bairros={total_bairros}")
            
            # Criar objeto de estatísticas
            return type('Stats', (), {
                'total_cidadaos_cadastrados': total_cidadaos,
                'cidadaos_com_dados_saude': cidadaos_com_dados_saude,
                'visitas_pendentes': visitas_pendentes,
                'anamneses_completas': anamneses_completas,
                'total_bairros': total_bairros,
                # Dados extras
                'visitas_realizadas': visitas_realizadas,
                'casos_risco_alto_hoje': casos_risco_alto,
                'total_anamneses_pendentes': anamneses_pendentes,
                'total_visitas': total_visitas,
                'total_anamneses': total_anamneses,
                'ultima_atualizacao': timezone.now()
            })()
            
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            print(f"ERRO nas estatísticas: {e}")  # Debug adicional
            return self._get_fallback_stats()

    def _get_fallback_stats(self):
        """Retorna um objeto de estatísticas vazio em caso de erro."""
        # Contar riscos baseado na localização de saúde (dados atuais) 
        from geolocation.models import LocalizacaoSaude
        alto_risco = LocalizacaoSaude.objects.filter(nivel_risco__in=['alto', 'critico']).count()
        
        return type('Stats', (), {
            'total_cidadaos_cadastrados': Cidadao.objects.count(),
            'total_atendimentos_hoje': 0,  # Será implementado depois
            'total_anamneses_pendentes': Anamnese.objects.filter(status='pendente').count(),
            'casos_risco_alto_hoje': alto_risco,
            'ultima_atualizacao': timezone.now()
        })()

    def _get_alertas_urgentes(self):
        """Retorna os 5 alertas urgentes mais recentes."""
        try:
            return AlertaSaude.objects.filter(resolvido=False).order_by('-prioridade', '-criado_em')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar alertas urgentes: {e}")
            return []

    def _get_anamneses_pendentes(self):
        """Retorna as 10 anamneses pendentes mais recentes."""
        try:
            return Anamnese.objects.filter(status='pendente').order_by('-criado_em')[:10]
        except Exception as e:
            logger.error(f"Erro ao buscar anamneses pendentes: {e}")
            return []

    def _get_alertas_recentes(self):
        """Retorna os 5 últimos registros de cidadãos com risco alto."""
        try:
            # Buscar alertas de saúde recentes com cidadãos de alto risco
            alertas = AlertaSaude.objects.filter(
                nivel_risco__in=['alto', 'critico']
            ).select_related('cidadao').order_by('-data_criacao')[:5]
            
            return alertas
        except Exception as e:
            logger.error(f"Erro ao buscar alertas recentes: {e}")
            return []

    def _get_dados_mapa_risco(self):
        """Retorna dados geográficos para o minimapa de risco."""
        try:
            from geolocation.models import LocalizacaoSaude
            
            # Buscar localizações com dados de risco
            localizacoes = LocalizacaoSaude.objects.select_related('cidadao').filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).exclude(
                latitude=0.0,
                longitude=0.0
            )
            
            dados_mapa = []
            for loc in localizacoes:
                # Definir cor baseada no nível de risco
                if loc.nivel_risco in ['alto', 'critico']:
                    cor = '#dc3545'  # Vermelho
                elif loc.nivel_risco == 'medio':
                    cor = '#ffc107'  # Amarelo
                else:
                    cor = '#28a745'  # Verde
                
                dados_mapa.append({
                    'lat': float(loc.latitude),
                    'lng': float(loc.longitude),
                    'cor': cor,
                    'risco': loc.nivel_risco,
                    'cidadao': loc.cidadao.nome if loc.cidadao else 'Não identificado',
                    'bairro': loc.cidadao.bairro if loc.cidadao and loc.cidadao.bairro else 'Não informado'
                })
            
            return dados_mapa[:50]  # Limitar a 50 pontos para performance
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do mapa de risco: {e}")
            return []

    def _get_treinamentos_recentes(self):
        """Retorna os 3 vídeos mais recentes ativos."""
        try:
            from dashboard.models import Treinamento
            return Treinamento.objects.filter(
                ativo=True
            ).select_related('categoria').order_by('-data_publicacao')[:3]
        except Exception as e:
            logger.error(f"Erro ao buscar treinamentos recentes: {e}")
            return []

    def _get_visitas_hoje(self):
        """Retorna visitas agendadas para hoje."""
        try:
            hoje = timezone.now().date()
            return VisitaAgendada.objects.filter(
                data_visita__date=hoje,
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar visitas de hoje: {e}")
            return []

    def _get_proximas_visitas(self):
        """Retorna próximas 5 visitas dos próximos dias."""
        try:
            amanha = timezone.now().date() + timedelta(days=1)
            uma_semana = timezone.now().date() + timedelta(days=7)
            return VisitaAgendada.objects.filter(
                data_visita__date__range=[amanha, uma_semana],
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar próximas visitas: {e}")
            return []

    def _get_atendimentos_por_dia_data(self):
        """Retorna dados de atendimentos dos últimos 7 dias para o gráfico."""
        try:
            dados = []
            for i in range(7):
                dia = timezone.now().date() - timedelta(days=i)
                count = Anamnese.objects.filter(criado_em__date=dia).count()
                dados.append({
                    'x': dia.strftime('%Y-%m-%d'),
                    'y': count
                })
            return list(reversed(dados))
        except Exception as e:
            logger.error(f"Erro ao buscar dados de atendimentos: {e}")
            return []

    def _get_distribuicao_risco_data(self, hoje):
        """Retorna distribuição de risco para o gráfico."""
        try:
            from geolocation.models import LocalizacaoSaude
            dados = {
                'baixo': LocalizacaoSaude.objects.filter(nivel_risco='baixo').count(),
                'medio': LocalizacaoSaude.objects.filter(nivel_risco='medio').count(),
                'alto': LocalizacaoSaude.objects.filter(nivel_risco='alto').count(),
                'critico': LocalizacaoSaude.objects.filter(nivel_risco='critico').count(),
            }
            return dados
        except Exception as e:
            logger.error(f"Erro ao buscar distribuição de risco: {e}")
            return {'baixo': 0, 'medio': 0, 'alto': 0, 'critico': 0}


class DashboardTesteView(TemplateView):
    """Dashboard de teste para agenda."""
    template_name = 'dashboard/dashboard_teste.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'visitas_hoje': self._get_visitas_hoje(),
            'proximas_visitas': self._get_proximas_visitas(),
        })
        return context
    
    def _get_visitas_hoje(self):
        """Retorna visitas agendadas para hoje."""
        try:
            hoje = timezone.now().date()
            return VisitaAgendada.objects.filter(
                data_visita__date=hoje,
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar visitas de hoje: {e}")
            return []

    def _get_proximas_visitas(self):
        """Retorna próximas 5 visitas dos próximos dias."""
        try:
            amanha = timezone.now().date() + timedelta(days=1)
            uma_semana = timezone.now().date() + timedelta(days=7)
            return VisitaAgendada.objects.filter(
                data_visita__date__range=[amanha, uma_semana],
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar próximas visitas: {e}")
            return []


class DashboardDebugView(TemplateView):
    """Dashboard de debug para agenda."""
    template_name = 'dashboard/debug_simples.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'visitas_hoje': self._get_visitas_hoje(),
            'proximas_visitas': self._get_proximas_visitas(),
            'anamneses_pendentes': self._get_anamneses_pendentes(),
        })
        return context
    
    def _get_visitas_hoje(self):
        """Retorna visitas agendadas para hoje."""
        try:
            hoje = timezone.now().date()
            return VisitaAgendada.objects.filter(
                data_visita__date=hoje,
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar visitas de hoje: {e}")
            return []

    def _get_proximas_visitas(self):
        """Retorna próximas 5 visitas dos próximos dias."""
        try:
            amanha = timezone.now().date() + timedelta(days=1)
            uma_semana = timezone.now().date() + timedelta(days=7)
            return VisitaAgendada.objects.filter(
                data_visita__date__range=[amanha, uma_semana],
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')[:5]
        except Exception as e:
            logger.error(f"Erro ao buscar próximas visitas: {e}")
            return []

    def _get_anamneses_pendentes(self):
        """Retorna as 10 anamneses pendentes mais recentes."""
        try:
            return Anamnese.objects.filter(status='pendente').order_by('-criado_em')[:10]
        except Exception as e:
            logger.error(f"Erro ao buscar anamneses pendentes: {e}")
            return []


class ColetaDadosView(LoginRequiredMixin, TemplateView):
    """Página principal para coleta de dados."""
    template_name = 'dashboard/coleta/coleta_dados.html'


class CadastroCidadaoView(CreateView):
    """Formulário para cadastro de cidadão."""
    model = Cidadao
    template_name = 'dashboard/coleta/cadastro_cidadao.html'
    fields = [
        'nome', 'cpf', 'data_nascimento', 'sexo', 'estado_civil',
        'telefone', 'email', 'endereco', 'cep', 'bairro', 'cidade',
        'estado', 'profissao', 'renda_familiar', 'possui_plano_saude',
        'possui_hipertensao', 'possui_diabetes', 'possui_doenca_cardiaca',
        'possui_doenca_renal', 'possui_asma', 'possui_depressao',
        'medicamentos_continuo', 'alergias_conhecidas', 'cirurgias_anteriores',
        'latitude', 'longitude', 'endereco_capturado_automaticamente'
    ]
    
    def form_valid(self, form):
        """Valida dados antes de salvar."""
        # Validação de CPF
        cpf = form.cleaned_data['cpf']
        valido, cpf_formatado = ValidadorDados.validar_cpf(cpf)
        if not valido:
            form.add_error('cpf', 'CPF inválido')
            return self.form_invalid(form)
        form.instance.cpf = cpf_formatado
        
        # Validação de telefone
        telefone = form.cleaned_data['telefone']
        valido, tel_formatado = ValidadorDados.validar_telefone(telefone)
        if not valido:
            form.add_error('telefone', 'Telefone inválido')
            return self.form_invalid(form)
        form.instance.telefone = tel_formatado
        
        # Debug: Verificar se coordenadas foram capturadas
        lat = form.cleaned_data.get('latitude')
        lng = form.cleaned_data.get('longitude')
        print(f"DEBUG: Coordenadas capturadas - Lat: {lat}, Lng: {lng}")
        
        response = super().form_valid(form)
        messages.success(self.request, f'Cidadão {self.object.nome} cadastrado com sucesso!')
        
        # Se há coordenadas, criar LocalizacaoSaude
        if lat is not None and lng is not None:
            from geolocation.models import LocalizacaoSaude
            try:
                LocalizacaoSaude.objects.create(
                    cidadao=self.object,
                    latitude=lat,
                    longitude=lng,
                    endereco_completo=form.cleaned_data.get('endereco', ''),
                    fonte_localizacao='html5'
                )
                print(f"DEBUG: LocalizacaoSaude criada para {self.object.nome}")
            except Exception as e:
                print(f"DEBUG: Erro ao criar LocalizacaoSaude: {e}")
        
        return response
    
    def get_success_url(self):
        return reverse('dashboard:coleta_saude') + f'?cidadao={self.object.id}'


class ColetaSaudeView(LoginRequiredMixin, CreateView):
    """Formulário para coleta de dados de saúde."""
    model = DadosSaude
    template_name = 'dashboard/coleta/coleta_saude.html'
    fields = [
        'pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca',
        'temperatura', 'peso', 'altura', 'sintomas_principais',
        'nivel_dor', 'duracao_sintomas', 'historico_doencas',
        'medicamentos_uso', 'alergias', 'fumante', 'etilista',
        'nivel_atividade_fisica', 'horas_sono', 'alimentacao_balanceada',
        'consumo_agua_litros'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Se há cidadão selecionado
        cidadao_id = self.request.GET.get('cidadao')
        if cidadao_id:
            try:
                context['cidadao'] = Cidadao.objects.get(id=cidadao_id)
            except Cidadao.DoesNotExist:
                pass
        
        return context
    
    def form_valid(self, form):
        """Processa dados de saúde e inicia anamnese."""
        # Associa agente que coletou
        form.instance.agente_coleta = self.request.user
        
        # Associa cidadão
        cidadao_id = self.request.GET.get('cidadao') or self.request.POST.get('cidadao')
        if cidadao_id:
            form.instance.cidadao = get_object_or_404(Cidadao, id=cidadao_id)
        
        # Normaliza sintomas
        if form.instance.sintomas_principais:
            form.instance.sintomas_principais = NormalizadorTexto.normalizar_texto(
                form.instance.sintomas_principais
            )
        
        print(f"DEBUG: form_valid chamado para dados de saúde")
        print(f"DEBUG: Salvando dados para {form.instance.cidadao.nome}")
        
        response = super().form_valid(form)
        
        print(f"DEBUG: Dados salvos com ID {self.object.id}")
        
        # Processar risco médico e criar LocalizacaoSaude se cidadão tem coordenadas
        cidadao = self.object.cidadao
        if cidadao.latitude is not None and cidadao.longitude is not None:
            from geolocation.models import LocalizacaoSaude
            try:
                # Buscar ou criar LocalizacaoSaude
                loc_saude, created = LocalizacaoSaude.objects.get_or_create(
                    cidadao=cidadao,
                    defaults={
                        'latitude': cidadao.latitude,
                        'longitude': cidadao.longitude,
                        'endereco_completo': cidadao.endereco or '',
                        'fonte_localizacao': 'cadastro_cidadao'
                    }
                )
                
                # Processar dados de saúde
                loc_saude.processar_dados_saude(self.object)
                
                # Calcular risco
                risco = loc_saude.calcular_risco_completo()
                print(f"DEBUG: Risco calculado para {cidadao.nome}: {risco}")
                
                # Gerar relatório médico
                loc_saude.gerar_relatorio_automatico()
                
                messages.success(
                    self.request, 
                    f'Dados coletados! Risco calculado: {risco}. Relatório médico gerado.'
                )
                
            except Exception as e:
                print(f"DEBUG: Erro ao processar localização e risco: {e}")
                messages.warning(
                    self.request,
                    'Dados coletados, mas houve erro no processamento de risco.'
                )
        else:
            print(f"DEBUG: Cidadão {cidadao.nome} não possui coordenadas")
            messages.warning(
                self.request,
                'Dados coletados, mas cidadão não possui localização para mapeamento.'
            )
        
        # Agenda geração de anamnese automática
        gerar_anamnese_automatica.delay(
            str(self.object.id),
            prioridade='normal',
            modelo='gpt-3.5-turbo'
        )
        
        return response
        
        return response
    
    def get_success_url(self):
        return reverse('dashboard:cidadao_detail', kwargs={'pk': self.object.cidadao.id})


class AnamnesesListView(LoginRequiredMixin, ListView):
    """Lista de anamneses com filtros."""
    model = Anamnese
    template_name = 'dashboard/anamneses/anamneses_list.html'
    context_object_name = 'anamneses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Anamnese.objects.select_related('cidadao', 'dados_saude', 'revisado_por')
        
        # Filtros
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        risco = self.request.GET.get('risco')
        if risco:
            queryset = queryset.filter(triagem_risco=risco)
        
        busca = self.request.GET.get('busca')
        if busca:
            queryset = queryset.filter(
                Q(cidadao__nome__icontains=busca) |
                Q(resumo_anamnese__icontains=busca) |
                Q(cidadao__cpf__icontains=busca)
            )
        
        return queryset.order_by('-criado_em')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'filtro_status': self.request.GET.get('status', ''),
            'filtro_risco': self.request.GET.get('risco', ''),
            'busca': self.request.GET.get('busca', ''),
        })
        return context


class AnamneseDetailView(LoginRequiredMixin, DetailView):
    """Detalhes de uma anamnese."""
    model = Anamnese
    template_name = 'dashboard/anamneses/anamnese_detail.html'
    context_object_name = 'anamnese'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Alertas associados
        context['alertas'] = AlertaSaude.objects.filter(
            anamnese=self.object
        ).order_by('-prioridade', '-criado_em')
        
        # Histórico do cidadão
        context['historico_anamneses'] = Anamnese.objects.filter(
            cidadao=self.object.cidadao
        ).exclude(id=self.object.id).order_by('-criado_em')[:5]
        
        return context


class RevisarAnamneseView(LoginRequiredMixin, UpdateView):
    """Revisão de anamnese por médico."""
    model = Anamnese
    template_name = 'dashboard/anamneses/revisar_anamnese.html'
    fields = [
        'comentarios_revisao', 'resumo_final', 
        'diagnostico_final', 'recomendacoes_finais'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dados_saude'] = self.object.dados_saude
        return context
    
    def form_valid(self, form):
        """Processa revisão da anamnese."""
        acao = self.request.POST.get('acao')
        
        if acao == 'aprovar':
            form.instance.status = 'aprovada'
            messages.success(self.request, 'Anamnese aprovada com sucesso!')
        elif acao == 'rejeitar':
            form.instance.status = 'rejeitada'
            messages.warning(self.request, 'Anamnese rejeitada.')
        else:
            form.instance.status = 'revisao'
            messages.info(self.request, 'Anamnese salva em revisão.')
        
        form.instance.revisado_por = self.request.user
        form.instance.data_revisao = timezone.now()
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('dashboard:anamnese_detail', kwargs={'pk': self.object.id})


class AlertasView(LoginRequiredMixin, ListView):
    """Lista de alertas de saúde."""
    model = AlertaSaude
    template_name = 'dashboard/alertas/alertas_list.html'
    context_object_name = 'alertas'
    paginate_by = 30
    
    def get_queryset(self):
        queryset = AlertaSaude.objects.select_related(
            'anamnese__cidadao'
        ).filter(resolvido=False)
        
        prioridade = self.request.GET.get('prioridade')
        if prioridade:
            queryset = queryset.filter(prioridade=prioridade)
        
        return queryset.order_by('-prioridade', '-criado_em')


class ResolverAlertaView(LoginRequiredMixin, TemplateView):
    """Resolve um alerta de saúde."""
    
    def post(self, request, pk):
        alerta = get_object_or_404(AlertaSaude, id=pk)
        
        alerta.resolvido = True
        alerta.resolvido_por = request.user
        alerta.data_resolucao = timezone.now()
        alerta.save()
        
        messages.success(request, f'Alerta "{alerta.titulo}" resolvido.')
        
        return redirect('dashboard:alertas')


class CidadaosListView(LoginRequiredMixin, ListView):
    """Lista de cidadãos cadastrados."""
    model = Cidadao
    template_name = 'dashboard/cidadaos/cidadaos_list.html'
    context_object_name = 'cidadaos'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Cidadao.objects.filter(ativo=True)
        
        busca = self.request.GET.get('busca')
        if busca:
            queryset = queryset.filter(
                Q(nome__icontains=busca) |
                Q(cpf__icontains=busca) |
                Q(email__icontains=busca)
            )
        
        cidade = self.request.GET.get('cidade')
        if cidade:
            queryset = queryset.filter(cidade__icontains=cidade)
            
        faixa_etaria = self.request.GET.get('faixa_etaria')
        if faixa_etaria:
            from datetime import date
            today = date.today()
            if faixa_etaria == '0-17':
                start_date = today.replace(year=today.year - 17)
                queryset = queryset.filter(data_nascimento__gte=start_date)
            elif faixa_etaria == '18-35':
                start_date = today.replace(year=today.year - 35)
                end_date = today.replace(year=today.year - 18)
                queryset = queryset.filter(data_nascimento__lte=end_date, data_nascimento__gte=start_date)
            elif faixa_etaria == '36-60':
                start_date = today.replace(year=today.year - 60)
                end_date = today.replace(year=today.year - 36)
                queryset = queryset.filter(data_nascimento__lte=end_date, data_nascimento__gte=start_date)
            elif faixa_etaria == '60+':
                end_date = today.replace(year=today.year - 60)
                queryset = queryset.filter(data_nascimento__lte=end_date)
        
        return queryset.order_by('nome')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Lista de cidades únicas
        context['cidades'] = Cidadao.objects.filter(ativo=True).values_list('cidade', flat=True).distinct().order_by('cidade')
        
        # Estatísticas simples
        from django.db.models import Count
        total_cidadaos = Cidadao.objects.filter(ativo=True).count()
        com_dados_saude = Cidadao.objects.filter(ativo=True, dados_saude__isnull=False).distinct().count()
        # Calcular alto risco baseado em critérios de pressão e outras métricas
        alto_risco = DadosSaude.objects.filter(
            cidadao__ativo=True,
            pressao_sistolica__gte=140  # Hipertensão grau 1
        ).count()
        anamneses_pendentes = Anamnese.objects.filter(status='pendente').count()
        
        context['stats'] = {
            'total_cidadaos': total_cidadaos,
            'com_dados_saude': com_dados_saude,
            'alto_risco': alto_risco,
            'anamneses_pendentes': anamneses_pendentes,
        }
        
        return context


class CidadaoDetailView(LoginRequiredMixin, DetailView):
    """Detalhes completos do cidadão."""
    model = Cidadao
    template_name = 'dashboard/cidadaos/cidadao_detail.html'
    context_object_name = 'cidadao'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Dados de saúde
        context['dados_saude'] = DadosSaude.objects.filter(
            cidadao=self.object
        ).order_by('-criado_em')
        
        # Anamneses
        context['anamneses'] = Anamnese.objects.filter(
            cidadao=self.object
        ).order_by('-criado_em')
        
        # Alertas ativos
        context['alertas_ativos'] = AlertaSaude.objects.filter(
            anamnese__cidadao=self.object,
            resolvido=False
        ).order_by('-prioridade')
        
        # Contatos de emergência
        context['contatos_emergencia'] = ContatoEmergencia.objects.filter(
            cidadao=self.object
        )
        
        return context


class RelatoriosView(LoginRequiredMixin, ListView):
    """Lista de relatórios disponíveis."""
    model = RelatorioSaude
    template_name = 'dashboard/relatorios/relatorios_list.html'
    context_object_name = 'relatorios'
    paginate_by = 15
    
    def get_queryset(self):
        return RelatorioSaude.objects.filter(
            publicado=True
        ).order_by('-criado_em')


class GerarRelatorioView(LoginRequiredMixin, TemplateView):
    """Formulário para gerar novo relatório."""
    template_name = 'dashboard/relatorios/gerar_relatorio.html'
    
    def post(self, request):
        """Processa solicitação de novo relatório."""
        try:
            data_inicio = datetime.strptime(request.POST['data_inicio'], '%Y-%m-%d').date()
            data_fim = datetime.strptime(request.POST['data_fim'], '%Y-%m-%d').date()
            tipo = request.POST['tipo']
            titulo = request.POST['titulo']
            
            # TODO: Implementar geração real do relatório via Celery
            
            messages.success(request, 'Relatório solicitado! Será processado em breve.')
            return redirect('dashboard:relatorios')
            
        except Exception as e:
            messages.error(request, f'Erro ao gerar relatório: {e}')
            return self.get(request)


class RelatorioDetailView(LoginRequiredMixin, DetailView):
    """Visualização detalhada do relatório."""
    model = RelatorioSaude
    template_name = 'dashboard/relatorios/relatorio_detail.html'
    context_object_name = 'relatorio'


class RelatorioCidadaosView(LoginRequiredMixin, ListView):
    """Relatório de cidadãos com filtros avançados."""
    model = Cidadao
    template_name = 'dashboard/relatorios/relatorio_cidadaos.html'
    context_object_name = 'cidadaos'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Cidadao.objects.select_related().prefetch_related('dados_saude', 'localizacoes_saude').all()
        
        # Filtro por bairro
        bairro = self.request.GET.get('bairro')
        if bairro:
            queryset = queryset.filter(bairro__icontains=bairro)
        
        # Filtro por doença crônica (usando campos booleanos)
        doenca_cronica = self.request.GET.get('doenca_cronica')
        if doenca_cronica:
            if doenca_cronica.lower() == 'hipertensão':
                queryset = queryset.filter(possui_hipertensao=True)
            elif doenca_cronica.lower() == 'diabetes':
                queryset = queryset.filter(possui_diabetes=True)
            elif doenca_cronica.lower() == 'doença cardíaca':
                queryset = queryset.filter(possui_doenca_cardiaca=True)
            elif doenca_cronica.lower() == 'doença renal':
                queryset = queryset.filter(possui_doenca_renal=True)
            elif doenca_cronica.lower() == 'asma':
                queryset = queryset.filter(possui_asma=True)
            elif doenca_cronica.lower() == 'depressão/ansiedade':
                queryset = queryset.filter(possui_depressao=True)
        
        # Filtro por risco
        risco = self.request.GET.get('risco')
        if risco:
            queryset = queryset.filter(localizacoes_saude__nivel_risco=risco)
        
        return queryset.order_by('-criado_em')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Opções para filtros
        context['bairros_disponiveis'] = list(
            Cidadao.objects.exclude(bairro__isnull=True)
            .exclude(bairro__exact='')
            .values_list('bairro', flat=True)
            .distinct()
            .order_by('bairro')
        )
        
        # Doenças crônicas disponíveis baseadas nos campos do modelo
        context['doencas_disponiveis'] = [
            'Hipertensão',
            'Diabetes',
            'Doença Cardíaca',
            'Doença Renal',
            'Asma',
            'Depressão/Ansiedade'
        ]
        
        # Níveis de risco
        context['niveis_risco'] = [
            {'value': 'baixo', 'label': 'Baixo'},
            {'value': 'medio', 'label': 'Médio'},
            {'value': 'alto', 'label': 'Alto'},
            {'value': 'critico', 'label': 'Crítico'},
        ]
        
        # Filtros ativos
        context['filtros_ativos'] = {
            'bairro': self.request.GET.get('bairro', ''),
            'doenca_cronica': self.request.GET.get('doenca_cronica', ''),
            'risco': self.request.GET.get('risco', ''),
        }
        
        # Estatísticas do resultado filtrado
        cidadaos_filtrados = self.get_queryset()
        context['total_cidadaos'] = cidadaos_filtrados.count()
        
        # Distribuição por risco no resultado filtrado
        from django.db.models import Count
        distribuicao_risco = cidadaos_filtrados.filter(
            localizacoes_saude__isnull=False
        ).values('localizacoes_saude__nivel_risco').annotate(
            count=Count('id')
        )
        
        context['distribuicao_risco'] = {}
        for item in distribuicao_risco:
            nivel = item['localizacoes_saude__nivel_risco']
            count = item['count']
            context['distribuicao_risco'][nivel] = count
        
        return context


# Views AJAX

class DashboardStatsAjaxView(LoginRequiredMixin, TemplateView):
    """Atualização de estatísticas via AJAX."""
    
    def get(self, request):
        stats = EstatisticaTempoReal.get_current()
        stats.atualizar_contadores()
        
        return JsonResponse({
            'total_cidadaos': stats.total_cidadaos_cadastrados,
            'atendimentos_hoje': stats.total_atendimentos_hoje,
            'anamneses_pendentes': stats.total_anamneses_pendentes,
            'alertas_nao_resolvidos': stats.alertas_nao_resolvidos,
            'casos_risco_alto_hoje': stats.casos_risco_alto_hoje,
            'ultima_atualizacao': stats.ultima_atualizacao.strftime('%H:%M:%S')
        })


class ValidarCPFAjaxView(LoginRequiredMixin, TemplateView):
    """Validação de CPF via AJAX."""
    
    def post(self, request):
        cpf = request.POST.get('cpf', '')
        valido, cpf_formatado = ValidadorDados.validar_cpf(cpf)
        
        # Verifica se CPF já existe
        cpf_existe = False
        if valido:
            cpf_existe = Cidadao.objects.filter(cpf=cpf_formatado).exists()
        
        return JsonResponse({
            'valido': valido,
            'cpf_formatado': cpf_formatado,
            'cpf_existe': cpf_existe,
            'mensagem': 'CPF válido' if valido else 'CPF inválido'
        })


class AnamneseFormAjaxView(LoginRequiredMixin, TemplateView):
    """Formulário de anamnese via AJAX."""
    
    def post(self, request):
        dados_saude_id = request.POST.get('dados_saude_id')
        
        if dados_saude_id:
            # Agenda geração de anamnese
            task = gerar_anamnese_automatica.delay(
                dados_saude_id,
                prioridade='alta',
                modelo=request.POST.get('modelo', 'gpt-3.5-turbo')
            )
            
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'mensagem': 'Anamnese sendo processada...'
            })
        
        return JsonResponse({
            'success': False,
            'error': 'Dados de saúde não encontrados'
        })


class GerarAnamneseAjaxView(LoginRequiredMixin, View):
    """Gera anamnese via AJAX usando OpenAI Assistant."""
    
    def post(self, request):
        cidadao_id = request.POST.get('cidadao_id')
        dados_saude_id = request.POST.get('dados_saude_id')
        
        try:
            # Valida parâmetros
            if not cidadao_id:
                return JsonResponse({
                    'success': False,
                    'error': 'ID do cidadão é obrigatório'
                })
            
            # Obtém cidadão
            cidadao = get_object_or_404(Cidadao, id=cidadao_id)
            
            # Se tem dados de saúde específicos, usa eles
            if dados_saude_id:
                dados_saude = get_object_or_404(DadosSaude, id=dados_saude_id, cidadao=cidadao)
            else:
                # Pega os dados de saúde mais recentes
                dados_saude = DadosSaude.objects.filter(cidadao=cidadao).order_by('-criado_em').first()
                
                if not dados_saude:
                    return JsonResponse({
                        'success': False,
                        'error': 'Nenhum dado de saúde encontrado para este cidadão'
                    })
            
            # Verifica se já existe anamnese para estes dados
            anamnese_existente = Anamnese.objects.filter(
                cidadao=cidadao, 
                dados_saude=dados_saude
            ).first()
            
            if anamnese_existente:
                return JsonResponse({
                    'success': True,
                    'anamnese_id': str(anamnese_existente.id),
                    'message': 'Anamnese já existe para estes dados',
                    'redirect_url': reverse('dashboard:anamnese_detail', kwargs={'pk': anamnese_existente.id})
                })
            
            # Usa a nova OpenAI Responses API (mais confiável)
            from ai_integracao.modern_service import ModernOpenAIService
            service = ModernOpenAIService()
            resultado = service.salvar_anamnese_moderna(cidadao, dados_saude)
            
            if not resultado['sucesso']:
                return JsonResponse({
                    'success': False,
                    'error': resultado.get('erro', 'Erro desconhecido na IA')
                })
            
            anamnese = resultado['anamnese']
            
            return JsonResponse({
                'success': True,
                'anamnese_id': str(anamnese.id),
                'message': 'Anamnese gerada com sucesso!',
                'redirect_url': reverse('dashboard:anamnese_detail', kwargs={'pk': anamnese.id}),
                'triagem_risco': anamnese.triagem_risco,
                'contexto_usado': True,  # Nova API sempre usa contexto completo
                'tokens_utilizados': resultado.get('tokens_utilizados', 0),
                'modelo_usado': resultado.get('modelo_usado', 'gpt-4o-mini-responses-api')
            })
            
        except Exception as e:
            logger.error(f"Erro na geração de anamnese via AJAX: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            })


class CidadaoCreateView(LoginRequiredMixin, CreateView):
    """Criar novo cidadão."""
    model = Cidadao
    template_name = 'dashboard/cidadaos/cidadao_form.html'
    fields = [
        'nome', 'cpf', 'data_nascimento', 'sexo', 'estado_civil', 
        'telefone', 'email', 'endereco', 'cep', 'bairro', 'cidade', 'estado', 
        'profissao', 'renda_familiar', 'possui_plano_saude',
        'possui_hipertensao', 'possui_diabetes', 'possui_doenca_cardiaca',
        'possui_doenca_renal', 'possui_asma', 'possui_depressao',
        'medicamentos_continuo', 'alergias_conhecidas', 'cirurgias_anteriores'
    ]
    
    def get_success_url(self):
        return reverse('dashboard:cidadaos_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Cidadão {form.cleaned_data["nome"]} cadastrado com sucesso!')
        return super().form_valid(form)


class CidadaoUpdateView(LoginRequiredMixin, UpdateView):
    """Editar cidadão existente."""
    model = Cidadao
    template_name = 'dashboard/cidadaos/cidadao_form.html'
    fields = [
        'nome', 'cpf', 'data_nascimento', 'sexo', 'estado_civil', 
        'telefone', 'email', 'endereco', 'cep', 'bairro', 'cidade', 'estado', 
        'profissao', 'renda_familiar', 'possui_plano_saude',
        'possui_hipertensao', 'possui_diabetes', 'possui_doenca_cardiaca',
        'possui_doenca_renal', 'possui_asma', 'possui_depressao',
        'medicamentos_continuo', 'alergias_conhecidas', 'cirurgias_anteriores'
    ]
    
    def get_success_url(self):
        return reverse('dashboard:cidadaos_list')
    
    def form_valid(self, form):
        messages.success(self.request, f'Cidadão {form.cleaned_data["nome"]} atualizado com sucesso!')
        return super().form_valid(form)


class DadosSaudeCreateView(LoginRequiredMixin, CreateView):
    """Adicionar dados de saúde para um cidadão."""
    model = DadosSaude
    template_name = 'dashboard/cidadaos/dados_saude_form.html'
    fields = [
        'pressao_sistolica', 'pressao_diastolica', 'frequencia_cardiaca',
        'temperatura', 'peso', 'altura', 'sintomas_principais',
        'nivel_dor', 'duracao_sintomas', 'historico_doencas',
        'medicamentos_uso', 'alergias', 'fumante', 'etilista',
        'nivel_atividade_fisica', 'horas_sono', 'alimentacao_balanceada',
        'consumo_agua_litros'
    ]
    
    def get_success_url(self):
        return reverse('dashboard:cidadao_detail', kwargs={'pk': self.object.cidadao.pk})
    
    def form_valid(self, form):
        print(f"DEBUG: form_valid chamado para dados de saúde")
        cidadao = get_object_or_404(Cidadao, pk=self.kwargs['pk'])
        form.instance.cidadao = cidadao
        form.instance.agente_coleta = self.request.user
        print(f"DEBUG: Salvando dados para {cidadao.nome}")
        result = super().form_valid(form)
        print(f"DEBUG: Dados salvos com ID {self.object.id}")
        messages.success(self.request, f'Dados de saúde adicionados para {cidadao.nome}!')
        return result
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cidadao'] = get_object_or_404(Cidadao, pk=self.kwargs['pk'])
        return context


class AlertasListView(LoginRequiredMixin, ListView):
    """Lista de alertas de saúde."""
    model = AlertaSaude
    template_name = 'dashboard/alertas/alertas_list.html'
    context_object_name = 'alertas'
    paginate_by = 25
    
    def get_queryset(self):
        return AlertaSaude.objects.filter(resolvido=False).order_by('-criado_em')


class NovaAnamneseView(LoginRequiredMixin, TemplateView):
    """Criar nova anamnese com seleção de cidadão e integração IA."""
    template_name = 'dashboard/anamneses/nova_anamnese.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Lista de cidadãos com dados de saúde para seleção
        cidadaos_com_dados = Cidadao.objects.filter(
            dados_saude__isnull=False
        ).prefetch_related('dados_saude').distinct().order_by('nome')
        
        context['cidadaos'] = cidadaos_com_dados
        return context
    
    def post(self, request):
        """Processa a criação da anamnese com IA."""
        cidadao_id = request.POST.get('cidadao_id')
        usar_dados_recentes = request.POST.get('usar_dados_recentes', 'true')
        
        try:
            logger.info(f"Iniciando criação de anamnese para cidadão ID: {cidadao_id}")
            
            if not cidadao_id:
                return JsonResponse({
                    'success': False,
                    'error': 'ID do cidadão é obrigatório'
                })
            
            # Obtém o cidadão
            cidadao = get_object_or_404(Cidadao, id=cidadao_id)
            logger.info(f"Cidadão encontrado: {cidadao.nome}")
            
            # Pega os dados de saúde mais recentes
            dados_saude = cidadao.dados_saude.order_by('-criado_em').first()
            if not dados_saude:
                return JsonResponse({
                    'success': False,
                    'error': 'Nenhum dado de saúde encontrado para este cidadão'
                })
            
            logger.info(f"Dados de saúde encontrados: {dados_saude.criado_em}")
            
            # Verifica se já existe anamnese para estes dados
            anamnese_existente = Anamnese.objects.filter(
                cidadao=cidadao,
                dados_saude=dados_saude
            ).first()
            
            if anamnese_existente:
                logger.info(f"Anamnese existente encontrada: {anamnese_existente.id}")
                return JsonResponse({
                    'success': True,
                    'anamnese_id': str(anamnese_existente.id),
                    'message': 'Anamnese já existe para os dados mais recentes deste cidadão',
                    'redirect_url': f'/anamneses/{anamnese_existente.id}/'
                })
            
            # Gera anamnese com OpenAI Assistant
            logger.info("Iniciando geração com OpenAI Assistant...")
            assistant_service = OpenAIAssistantService()
            resultado = assistant_service.gerar_anamnese_com_assistant(cidadao, dados_saude)
            logger.info("OpenAI Assistant concluído com sucesso")
            
            # Processa as recomendações - converte lista para texto formatado
            recomendacoes_raw = resultado.get('recomendacoes', '')
            if isinstance(recomendacoes_raw, list):
                # Converte lista para texto formatado com numeração
                recomendacoes_formatadas = '\n'.join([f"{i+1}. {rec}" for i, rec in enumerate(recomendacoes_raw)])
            else:
                recomendacoes_formatadas = str(recomendacoes_raw)
            
            # Processa exames complementares
            exames_raw = resultado.get('exames_complementares', [])
            if isinstance(exames_raw, list):
                exames_formatados = '\n'.join([f"• {exame}" for exame in exames_raw])
            else:
                exames_formatados = str(exames_raw) if exames_raw else ''
            
            # Cria a anamnese no banco
            logger.info("Criando anamnese no banco de dados...")
            anamnese = Anamnese.objects.create(
                cidadao=cidadao,
                dados_saude=dados_saude,
                resumo_anamnese=resultado.get('resumo_anamnese', ''),
                diagnostico_clinico=resultado.get('diagnostico_clinico', ''),
                diagnostico_diferencial=resultado.get('diagnostico_diferencial', []),
                hipoteses_diagnosticas=resultado.get('hipoteses_diagnosticas', []),
                triagem_risco=resultado.get('triagem_risco', 'medio'),
                recomendacoes=recomendacoes_formatadas,
                exames_complementares=exames_raw if isinstance(exames_raw, list) else [],
                prognose=resultado.get('prognose', ''),
                modelo_ia_usado=resultado.get('modelo_ia_usado', 'openai-assistant'),
                confianca_ia=0.95,
                dados_entrada_ia=resultado.get('dados_entrada_anonimos', {}),
                resposta_completa_ia=resultado,
                status='concluida'  # Marca como concluída
            )
            
            logger.info(f"Anamnese criada com sucesso: {anamnese.id}")
            
            return JsonResponse({
                'success': True,
                'anamnese_id': str(anamnese.id),
                'message': 'Nova anamnese gerada com sucesso!',
                'redirect_url': f'/anamneses/{anamnese.id}/',
                'triagem_risco': anamnese.triagem_risco,
                'contexto_usado': resultado.get('contexto_historico_usado', False)
            })
            
        except Exception as e:
            logger.error(f"Erro na criação de nova anamnese: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            })


class ProcessarTodasAnamnesessAjaxView(LoginRequiredMixin, View):
    """Processa todas as anamneses pendentes usando IA em lote."""
    
    def post(self, request):
        """Processa todas as anamneses pendentes automaticamente."""
        try:
            # Buscar todos os cidadãos que têm dados de saúde mas não têm anamnese correspondente
            from django.db.models import Q
            from ai_integracao.assistant_service import OpenAIAssistantService
            
            # Encontrar cidadãos com dados de saúde recentes sem anamnese
            cidadaos_sem_anamnese = []
            for cidadao in Cidadao.objects.filter(dados_saude__isnull=False).distinct():
                dados_recentes = cidadao.dados_saude.order_by('-criado_em').first()
                if dados_recentes:
                    # Verificar se já existe anamnese para estes dados
                    anamnese_existente = Anamnese.objects.filter(
                        cidadao=cidadao,
                        dados_saude=dados_recentes
                    ).exists()
                    
                    if not anamnese_existente:
                        cidadaos_sem_anamnese.append((cidadao, dados_recentes))
            
            if not cidadaos_sem_anamnese:
                return JsonResponse({
                    'success': False,
                    'message': 'Não há anamneses pendentes para processar. Todos os cidadãos já possuem anamneses para seus dados mais recentes.'
                })
            
            logger.info(f"Processando {len(cidadaos_sem_anamnese)} anamneses em lote")
            
            assistant_service = OpenAIAssistantService()
            anamneses_criadas = 0
            erros = 0
            
            for cidadao, dados_saude in cidadaos_sem_anamnese:
                try:
                    logger.info(f"Processando anamnese para {cidadao.nome}")
                    
                    # Gerar anamnese com IA
                    resultado = assistant_service.gerar_anamnese_com_assistant(cidadao, dados_saude)
                    
                    # Processar as recomendações
                    recomendacoes_raw = resultado.get('recomendacoes', '')
                    if isinstance(recomendacoes_raw, list):
                        recomendacoes_formatadas = '\n'.join([f"{i+1}. {rec}" for i, rec in enumerate(recomendacoes_raw)])
                    else:
                        recomendacoes_formatadas = str(recomendacoes_raw)
                    
                    # Processar exames complementares
                    exames_raw = resultado.get('exames_complementares', [])
                    
                    # Criar a anamnese
                    anamnese = Anamnese.objects.create(
                        cidadao=cidadao,
                        dados_saude=dados_saude,
                        resumo_anamnese=resultado.get('resumo_anamnese', ''),
                        diagnostico_clinico=resultado.get('diagnostico_clinico', ''),
                        diagnostico_diferencial=resultado.get('diagnostico_diferencial', []),
                        hipoteses_diagnosticas=resultado.get('hipoteses_diagnosticas', []),
                        triagem_risco=resultado.get('triagem_risco', 'medio'),
                        recomendacoes=recomendacoes_formatadas,
                        exames_complementares=exames_raw if isinstance(exames_raw, list) else [],
                        prognose=resultado.get('prognose', ''),
                        modelo_ia_usado=resultado.get('modelo_ia_usado', 'openai-assistant'),
                        confianca_ia=0.95,
                        dados_entrada_ia=resultado.get('dados_entrada_anonimos', {}),
                        resposta_completa_ia=resultado,
                        status='concluida'
                    )
                    
                    anamneses_criadas += 1
                    logger.info(f"Anamnese criada para {cidadao.nome}: {anamnese.id}")
                    
                except Exception as e:
                    erros += 1
                    logger.error(f"Erro ao processar anamnese para {cidadao.nome}: {e}")
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f'Processamento concluído! {anamneses_criadas} anamneses criadas com sucesso.',
                'anamneses_criadas': anamneses_criadas,
                'erros': erros,
                'total_candidatos': len(cidadaos_sem_anamnese)
            })
            
        except Exception as e:
            logger.error(f"Erro no processamento em lote de anamneses: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno no processamento: {str(e)}'
            })


class TestNovaAnamneseView(TemplateView):
    """
    View simples para testar a funcionalidade de nova anamnese.
    """
    template_name = 'test_nova_anamnese.html'


# ====================================================================
# VIEWS PARA AGENDA DE VISITAS
# ====================================================================

from datetime import date, datetime, timedelta


class AgendaEventosAPIView(View):
    """
    API para eventos do calendário (formato FullCalendar.js).
    """
    def get(self, request):
        """Retorna eventos para o calendário."""
        try:
            # Parâmetros de filtro
            start = request.GET.get('start')
            end = request.GET.get('end')
            
            # Filtrar visitas
            visitas = VisitaAgendada.objects.all()
            
            if start:
                visitas = visitas.filter(data_visita__gte=start)
            if end:
                visitas = visitas.filter(data_visita__lte=end)
            
            # Converter para formato FullCalendar
            eventos = []
            for visita in visitas:
                eventos.append({
                    'id': str(visita.id),
                    'title': f"{visita.cidadao.nome} - {visita.get_motivo_display()}",
                    'start': visita.data_visita.isoformat(),
                    'backgroundColor': visita.cor_status,
                    'borderColor': visita.cor_status,
                    'textColor': '#fff' if visita.status != 'agendada' else '#000',
                    'extendedProps': {
                        'cidadao_id': str(visita.cidadao.id),
                        'cidadao_nome': visita.cidadao.nome,
                        'motivo': visita.get_motivo_display(),
                        'motivo_codigo': visita.motivo,
                        'status': visita.get_status_display(),
                        'status_codigo': visita.status,
                        'observacoes': visita.observacoes or '',
                        'pode_editar': visita.pode_ser_editada(),
                        'pode_cancelar': visita.pode_ser_cancelada(),
                        'eh_hoje': visita.eh_hoje,
                        'eh_atrasada': visita.eh_atrasada,
                    }
                })
            
            return JsonResponse(eventos, safe=False)
            
        except Exception as e:
            logger.error(f"Erro na API de eventos: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class CriarVisitaView(View):
    """
    View para criar nova visita agendada.
    """
    def post(self, request):
        """Cria nova visita."""
        try:
            data = json.loads(request.body)
            
            # Validar campos obrigatórios
            campos_obrigatorios = ['cidadao_id', 'data_visita', 'motivo']
            for campo in campos_obrigatorios:
                if not data.get(campo):
                    return JsonResponse({
                        'success': False,
                        'error': f'Campo {campo} é obrigatório'
                    }, status=400)
            
            # Buscar cidadão
            try:
                cidadao = Cidadao.objects.get(id=data['cidadao_id'])
            except Cidadao.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Cidadão não encontrado'
                }, status=404)
            
            # Converter data
            try:
                data_visita = datetime.fromisoformat(data['data_visita'].replace('Z', '+00:00'))
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de data inválido'
                }, status=400)
            
            # Verificar se não é no passado
            if data_visita < timezone.now():
                return JsonResponse({
                    'success': False,
                    'error': 'Não é possível agendar visitas no passado'
                }, status=400)
            
            # Verificar conflitos de horário
            conflitos = VisitaAgendada.objects.filter(
                agente=request.user,
                data_visita__date=data_visita.date(),
                data_visita__hour=data_visita.hour,
                status__in=['agendada', 'confirmada']
            ).exists()
            
            if conflitos:
                return JsonResponse({
                    'success': False,
                    'error': 'Já existe uma visita agendada para este horário'
                }, status=409)
            
            # Criar visita
            visita = VisitaAgendada.objects.create(
                cidadao=cidadao,
                agente=request.user,
                data_visita=data_visita,
                motivo=data.get('motivo'),
                observacoes=data.get('observacoes', ''),
                criado_por=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Visita agendada com sucesso!',
                'visita_id': str(visita.id),
                'evento': {
                    'id': str(visita.id),
                    'title': f"{visita.cidadao.nome} - {visita.get_motivo_display()}",
                    'start': visita.data_visita.isoformat(),
                    'backgroundColor': visita.cor_status,
                    'borderColor': visita.cor_status,
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Dados JSON inválidos'
            }, status=400)
        except Exception as e:
            logger.error(f"Erro ao criar visita: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }, status=500)


class EditarVisitaView(View):
    """
    View para editar visita existente.
    """
    def put(self, request, visita_id):
        """Edita visita existente."""
        try:
            visita = get_object_or_404(VisitaAgendada, id=visita_id)
            
            # Verificar permissão
            if not visita.pode_ser_editada():
                return JsonResponse({
                    'success': False,
                    'error': 'Esta visita não pode mais ser editada'
                }, status=403)
            
            data = json.loads(request.body)
            
            # Atualizar campos
            if 'data_visita' in data:
                try:
                    nova_data = datetime.fromisoformat(data['data_visita'].replace('Z', '+00:00'))
                    if nova_data < timezone.now():
                        return JsonResponse({
                            'success': False,
                            'error': 'Não é possível agendar visitas no passado'
                        }, status=400)
                    visita.data_visita = nova_data
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'error': 'Formato de data inválido'
                    }, status=400)
            
            if 'motivo' in data:
                visita.motivo = data['motivo']
            
            if 'observacoes' in data:
                visita.observacoes = data['observacoes']
            
            if 'status' in data:
                visita.status = data['status']
            
            visita.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Visita atualizada com sucesso!'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Dados JSON inválidos'
            }, status=400)
        except Exception as e:
            logger.error(f"Erro ao editar visita: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }, status=500)


class ConfirmarVisitaView(LoginRequiredMixin, View):
    """
    View para confirmar visita como realizada.
    """
    def post(self, request, visita_id):
        """Confirma visita como realizada."""
        try:
            visita = get_object_or_404(VisitaAgendada, id=visita_id)
            
            # Atualizar status
            visita.status = 'realizada'
            visita.data_confirmacao = timezone.now()
            visita.confirmado_por = request.user
            visita.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Visita confirmada como realizada!',
                'novo_status': visita.get_status_display()
            })
            
        except Exception as e:
            logger.error(f"Erro ao confirmar visita: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }, status=500)


class ExcluirVisitaView(View):
    """
    View para excluir visita.
    """
    def delete(self, request, visita_id):
        """Exclui visita."""
        try:
            visita = get_object_or_404(VisitaAgendada, id=visita_id)
            
            # Verificar se pode ser cancelada
            if not visita.pode_ser_cancelada():
                return JsonResponse({
                    'success': False,
                    'error': 'Esta visita não pode mais ser cancelada'
                }, status=403)
            
            visita.status = 'cancelada'
            visita.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Visita cancelada com sucesso!'
            })
            
        except Exception as e:
            logger.error(f"Erro ao cancelar visita: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }, status=500)


class VisitasHojeView(View):
    """
    API para visitas agendadas para hoje.
    """
    def get(self, request):
        """Retorna visitas de hoje."""
        try:
            hoje = timezone.now().date()
            
            visitas_hoje = VisitaAgendada.objects.filter(
                data_visita__date=hoje,
                status__in=['agendada', 'confirmada']
            ).select_related('cidadao').order_by('data_visita')
            
            visitas_data = []
            for visita in visitas_hoje:
                visitas_data.append({
                    'id': str(visita.id),
                    'cidadao_nome': visita.cidadao.nome,
                    'hora': visita.data_visita.strftime('%H:%M'),
                    'motivo': visita.get_motivo_display(),
                    'status': visita.get_status_display(),
                    'endereco': visita.cidadao.endereco,
                    'telefone': visita.cidadao.telefone,
                    'eh_atrasada': visita.eh_atrasada,
                })
            
            return JsonResponse({
                'visitas': visitas_data,
                'total': len(visitas_data)
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar visitas de hoje: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class CidadaosParaAgendamentoView(View):
    """
    API para buscar cidadãos disponíveis para agendamento.
    """
    def get(self, request):
        """Retorna cidadãos para agendamento."""
        try:
            termo = request.GET.get('q', '').strip()
            
            cidadaos = Cidadao.objects.all()
            
            if termo:
                cidadaos = cidadaos.filter(
                    Q(nome__icontains=termo) |
                    Q(cpf__icontains=termo) |
                    Q(telefone__icontains=termo)
                )
            
            cidadaos = cidadaos[:20]  # Limitar resultados
            
            resultados = []
            for cidadao in cidadaos:
                resultados.append({
                    'id': str(cidadao.id),
                    'nome': cidadao.nome,
                    'cpf': cidadao.cpf,
                    'idade': cidadao.idade,
                    'telefone': cidadao.telefone,
                    'endereco': cidadao.endereco,
                })
            
            return JsonResponse({
                'cidadaos': resultados
            })
            
        except Exception as e:
            logger.error(f"Erro ao buscar cidadãos: {e}")
            return JsonResponse({'error': str(e)}, status=500)


class AgendaView(LoginRequiredMixin, TemplateView):
    """Página específica da agenda de visitas."""
    template_name = 'dashboard/agenda.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoje = timezone.now().date()
        
        try:
            # Visitas de hoje
            visitas_hoje = VisitaAgendada.objects.filter(
                data_visita__date=hoje
            ).select_related('cidadao').order_by('data_visita')
            
            # Próximas visitas (próximos 7 dias)
            amanha = hoje + timedelta(days=1)
            uma_semana = hoje + timedelta(days=7)
            proximas_visitas = VisitaAgendada.objects.filter(
                data_visita__date__range=[amanha, uma_semana]
            ).select_related('cidadao').order_by('data_visita')
            
            # Visitas por status
            visitas_confirmadas = VisitaAgendada.objects.filter(
                status='confirmada',
                data_visita__date__gte=hoje
            ).select_related('cidadao')
            
            visitas_pendentes = VisitaAgendada.objects.filter(
                status='agendada',
                data_visita__date__gte=hoje
            ).select_related('cidadao')
            
            # Formulário para nova visita
            form_nova_visita = VisitaAgendadaForm()
            
            # Formulário de filtros
            form_filtros = FiltroVisitasForm(self.request.GET)
            
            context.update({
                'visitas_hoje': visitas_hoje,
                'proximas_visitas': proximas_visitas,
                'visitas_confirmadas': visitas_confirmadas,
                'visitas_pendentes': visitas_pendentes,
                'form_nova_visita': form_nova_visita,
                'form_filtros': form_filtros,
                'cidadaos': Cidadao.objects.filter(ativo=True).order_by('nome'),
            })
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados da agenda: {e}")
            context.update({
                'visitas_hoje': [],
                'proximas_visitas': [],
                'visitas_confirmadas': [],
                'visitas_pendentes': [],
                'form_nova_visita': VisitaAgendadaForm(),
                'form_filtros': FiltroVisitasForm(),
                'cidadaos': [],
            })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Processa criação de nova visita via formulário."""
        try:
            form = VisitaAgendadaForm(request.POST)
            
            if form.is_valid():
                # Criar nova visita
                visita = form.save(commit=False)
                visita.agente = request.user
                visita.criado_por = request.user
                visita.save()
                
                if request.headers.get('Content-Type') == 'application/json':
                    # Resposta AJAX
                    return JsonResponse({
                        'success': True,
                        'message': 'Visita agendada com sucesso!',
                        'visita_id': str(visita.id),
                        'evento': {
                            'id': str(visita.id),
                            'title': f"{visita.cidadao.nome} - {visita.get_motivo_display()}",
                            'start': visita.data_visita.isoformat(),
                            'backgroundColor': visita.cor_status,
                            'borderColor': visita.cor_status,
                        }
                    })
                else:
                    # Redirecionamento normal
                    messages.success(request, 'Visita agendada com sucesso!')
                    return redirect('dashboard:agenda')
            else:
                # Formulário com erros
                if request.headers.get('Content-Type') == 'application/json':
                    return JsonResponse({
                        'success': False,
                        'errors': form.errors
                    }, status=400)
                else:
                    messages.error(request, 'Erro ao agendar visita. Verifique os dados.')
                    
        except Exception as e:
            logger.error(f"Erro ao criar visita: {e}")
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                }, status=500)
            else:
                messages.error(request, f'Erro interno: {str(e)}')
        
        # Em caso de erro, retorna página com formulário preenchido
        return self.get(request, *args, **kwargs)


class TreinamentosView(LoginRequiredMixin, TemplateView):
    """
    View para exibir os vídeos de treinamento disponíveis para os agentes.
    
    Organiza os treinamentos por categoria e permite filtrar por categoria específica.
    Suporta filtro via parâmetro GET 'categoria'.
    """
    template_name = 'dashboard/treinamentos.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtro por categoria (via GET parameter)
        categoria_filtro = self.request.GET.get('categoria')
        
        # Buscar apenas treinamentos ativos
        treinamentos = Treinamento.objects.filter(ativo=True).select_related('categoria')
        
        # Aplicar filtro de categoria se especificado
        if categoria_filtro and categoria_filtro.isdigit():
            treinamentos = treinamentos.filter(categoria_id=categoria_filtro)
        
        # Buscar todas as categorias que têm treinamentos ativos
        from .models import CategoriaTreinamento
        categorias_com_treinamentos = CategoriaTreinamento.objects.filter(
            treinamentos__ativo=True
        ).distinct().order_by('ordem', 'nome')
        
        # Agrupar treinamentos por categoria
        treinamentos_por_categoria = {}
        for categoria in categorias_com_treinamentos:
            categoria_treinamentos = treinamentos.filter(categoria=categoria).order_by('-data_publicacao')
            if categoria_treinamentos.exists():
                treinamentos_por_categoria[categoria.id] = {
                    'categoria': categoria,
                    'treinamentos': categoria_treinamentos,
                    'total': categoria_treinamentos.count()
                }
        
        # Categoria selecionada para o filtro
        categoria_selecionada = None
        if categoria_filtro and categoria_filtro.isdigit():
            try:
                categoria_selecionada = CategoriaTreinamento.objects.get(id=categoria_filtro)
            except CategoriaTreinamento.DoesNotExist:
                pass
        
        # Adicionar contexto
        context.update({
            'treinamentos_por_categoria': treinamentos_por_categoria,
            'todas_categorias': categorias_com_treinamentos,
            'categoria_selecionada': categoria_selecionada,
            'total_treinamentos': treinamentos.count(),
            'total_categorias': len(treinamentos_por_categoria),
            'page_title': 'Treinamentos para Agentes de Saúde'
        })
        
        return context
