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
from dashboard.models import EstatisticaTempoReal, RelatorioSaude
from api.serializers import ColetaDadosSerializer, DadosSaudeSerializer
from utils.validators import ValidadorDados, NormalizadorTexto
from utils.tasks import gerar_anamnese_automatica
from ai_integracao.assistant_service import OpenAIAssistantService


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard principal com estatísticas em tempo real."""
    template_name = 'dashboard/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Estatísticas gerais
            stats = EstatisticaTempoReal.get_current()
            stats.atualizar_contadores()
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            # Criar stats vazias como fallback
            stats = type('Stats', (), {
                'total_cidadaos_cadastrados': 0,
                'total_atendimentos_hoje': 0,
                'total_anamneses_pendentes': 0,
                'alertas_nao_resolvidos': 0,
                'casos_risco_alto_hoje': 0,
                'ultima_atualizacao': timezone.now()
            })()
        
        try:
            alertas_urgentes = AlertaSaude.objects.filter(
                prioridade='urgente', 
                resolvido=False
            )[:5]
        except:
            alertas_urgentes = []
            
        try:
            anamneses_pendentes = Anamnese.objects.filter(
                status='pendente'
            )[:10]
        except:
            anamneses_pendentes = []
            
        try:
            casos_alto_risco_hoje = Anamnese.objects.filter(
                criado_em__date=timezone.now().date(),
                triagem_risco__in=['alto', 'critico']
            )
        except:
            casos_alto_risco_hoje = []
        
        context.update({
            'stats': stats,
            'alertas_urgentes': alertas_urgentes,
            'anamneses_pendentes': anamneses_pendentes,
            'casos_alto_risco_hoje': casos_alto_risco_hoje,
        })
        
        return context
        
        # Distribuição de risco
        distribuicao_risco = Anamnese.objects.filter(
            criado_em__date=hoje
        ).values('triagem_risco').annotate(count=Count('id'))
        
        context.update({
            'atendimentos_por_dia': json.dumps(atendimentos_por_dia),
            'distribuicao_risco': json.dumps(list(distribuicao_risco)),
        })
        
        return context


class ColetaDadosView(LoginRequiredMixin, TemplateView):
    """Página principal para coleta de dados."""
    template_name = 'dashboard/coleta/coleta_dados.html'


class CadastroCidadaoView(LoginRequiredMixin, CreateView):
    """Formulário para cadastro de cidadão."""
    model = Cidadao
    template_name = 'dashboard/coleta/cadastro_cidadao.html'
    fields = [
        'nome', 'cpf', 'data_nascimento', 'sexo', 'estado_civil',
        'telefone', 'email', 'endereco', 'cep', 'bairro', 'cidade',
        'estado', 'profissao', 'renda_familiar', 'possui_plano_saude',
        'possui_hipertensao', 'possui_diabetes', 'possui_doenca_cardiaca',
        'possui_doenca_renal', 'possui_asma', 'possui_depressao',
        'medicamentos_continuo', 'alergias_conhecidas', 'cirurgias_anteriores'
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
        
        response = super().form_valid(form)
        messages.success(self.request, f'Cidadão {self.object.nome} cadastrado com sucesso!')
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
        
        response = super().form_valid(form)
        
        # Agenda geração de anamnese automática
        gerar_anamnese_automatica.delay(
            str(self.object.id),
            prioridade='normal',
            modelo='gpt-3.5-turbo'
        )
        
        messages.success(
            self.request, 
            'Dados coletados com sucesso! Anamnese será gerada automaticamente.'
        )
        
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
