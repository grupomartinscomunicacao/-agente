"""
Views para conformidade LGPD.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import secrets

from cidadaos.models import Cidadao
from lgpd.models import ConsentimentoLGPD, AuditoriaAcesso, ViolacaoDados, PoliticaPrivacidade
from utils.lgpd import AnonimizadorLGPD, RelatorioLGPD, ConsentimentoLGPD as ConsentimentoUtil


@login_required
def dashboard_lgpd(request):
    """Dashboard principal de conformidade LGPD."""
    
    # Estatísticas gerais
    total_cidadaos = Cidadao.objects.count()
    consentimentos_ativos = ConsentimentoLGPD.objects.filter(
        consentido=True,
        data_revogacao__isnull=True,
        valido_ate__gt=timezone.now()
    ).count()
    
    violacoes_pendentes = ViolacaoDados.objects.filter(resolvida=False).count()
    acessos_hoje = AuditoriaAcesso.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Violações recentes
    violacoes_recentes = ViolacaoDados.objects.filter(
        resolvida=False
    ).order_by('-data_deteccao')[:5]
    
    # Política ativa
    politica_ativa = PoliticaPrivacidade.objects.filter(ativa=True).first()
    
    context = {
        'total_cidadaos': total_cidadaos,
        'consentimentos_ativos': consentimentos_ativos,
        'violacoes_pendentes': violacoes_pendentes,
        'acessos_hoje': acessos_hoje,
        'violacoes_recentes': violacoes_recentes,
        'politica_ativa': politica_ativa,
        'taxa_consentimento': (consentimentos_ativos / total_cidadaos * 100) if total_cidadaos > 0 else 0,
    }
    
    return render(request, 'lgpd/dashboard.html', context)


def termo_consentimento(request, cidadao_id=None):
    """Página de termo de consentimento."""
    
    cidadao = None
    if cidadao_id:
        cidadao = get_object_or_404(Cidadao, id=cidadao_id)
    
    politica_ativa = PoliticaPrivacidade.objects.filter(ativa=True).first()
    
    if request.method == 'POST':
        finalidades = request.POST.getlist('finalidades')
        
        if not finalidades:
            messages.error(request, 'Selecione pelo menos uma finalidade para continuar.')
            return render(request, 'lgpd/termo_consentimento.html', {
                'cidadao': cidadao,
                'politica': politica_ativa,
                'finalidades': ConsentimentoLGPD.FINALIDADES_CHOICES
            })
        
        # Registrar consentimento
        ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        for finalidade_code in finalidades:
            ConsentimentoLGPD.objects.update_or_create(
                cidadao=cidadao,
                finalidade=finalidade_code,
                defaults={
                    'consentido': True,
                    'token_consentimento': secrets.token_urlsafe(32),
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'valido_ate': timezone.now() + timezone.timedelta(days=365),
                    'data_revogacao': None,
                }
            )
        
        # Registrar auditoria
        AuditoriaAcesso.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            cidadao=cidadao,
            tipo_acao='CONSENTIMENTO_DADO',
            detalhes={'finalidades': finalidades},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        messages.success(request, 'Consentimento registrado com sucesso!')
        
        if request.user.is_authenticated:
            return redirect('dashboard:cidadao_detail', pk=cidadao.id)
        else:
            return render(request, 'lgpd/consentimento_sucesso.html', {'cidadao': cidadao})
    
    context = {
        'cidadao': cidadao,
        'politica': politica_ativa,
        'finalidades': ConsentimentoLGPD.FINALIDADES_CHOICES
    }
    
    return render(request, 'lgpd/termo_consentimento.html', context)


@login_required
def gerenciar_consentimentos(request, cidadao_id):
    """Página para gerenciar consentimentos de um cidadão."""
    
    cidadao = get_object_or_404(Cidadao, id=cidadao_id)
    
    consentimentos = ConsentimentoLGPD.objects.filter(
        cidadao=cidadao
    ).order_by('-data_consentimento')
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        consentimento_id = request.POST.get('consentimento_id')
        
        if acao == 'revogar' and consentimento_id:
            consentimento = get_object_or_404(
                ConsentimentoLGPD, 
                id=consentimento_id, 
                cidadao=cidadao
            )
            consentimento.revogar()
            
            # Registrar auditoria
            AuditoriaAcesso.objects.create(
                usuario=request.user,
                cidadao=cidadao,
                tipo_acao='CONSENTIMENTO_REVOGADO',
                detalhes={'finalidade': consentimento.finalidade},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            
            messages.success(request, f'Consentimento para "{consentimento.get_finalidade_display()}" foi revogado.')
            return redirect('lgpd:gerenciar_consentimentos', cidadao_id=cidadao_id)
    
    context = {
        'cidadao': cidadao,
        'consentimentos': consentimentos,
    }
    
    return render(request, 'lgpd/gerenciar_consentimentos.html', context)


@login_required
def relatorio_dados_cidadao(request, cidadao_id):
    """Gera relatório completo dos dados de um cidadão (Art. 9 LGPD)."""
    
    cidadao = get_object_or_404(Cidadao, id=cidadao_id)
    
    # Registrar acesso
    AuditoriaAcesso.objects.create(
        usuario=request.user,
        cidadao=cidadao,
        tipo_acao='EXPORTACAO_DADOS',
        detalhes={'tipo': 'relatorio_completo'},
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    
    relatorio = RelatorioLGPD.gerar_relatorio_dados_cidadao(str(cidadao.id))
    
    if request.GET.get('format') == 'json':
        response = HttpResponse(
            json.dumps(relatorio, indent=2, ensure_ascii=False),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="dados_cidadao_{cidadao.id}.json"'
        return response
    
    context = {
        'cidadao': cidadao,
        'relatorio': relatorio,
    }
    
    return render(request, 'lgpd/relatorio_dados_cidadao.html', context)


@login_required
def anonimizar_cidadao(request, cidadao_id):
    """Anonimiza dados de um cidadão."""
    
    cidadao = get_object_or_404(Cidadao, id=cidadao_id)
    
    if request.method == 'POST':
        # Anonimizar dados
        dados_originais = {
            'nome': cidadao.nome,
            'cpf': cidadao.cpf,
            'email': cidadao.email,
            'telefone': cidadao.telefone,
        }
        
        cidadao.nome = AnonimizadorLGPD.anonimizar_nome(cidadao.nome)
        cidadao.cpf = AnonimizadorLGPD.anonimizar_cpf(cidadao.cpf)
        cidadao.email = AnonimizadorLGPD.anonimizar_email(cidadao.email) if cidadao.email else ''
        cidadao.telefone = AnonimizadorLGPD.anonimizar_telefone(cidadao.telefone)
        cidadao.endereco = AnonimizadorLGPD.anonimizar_endereco(cidadao.endereco) if cidadao.endereco else ''
        cidadao.save()
        
        # Registrar auditoria
        AuditoriaAcesso.objects.create(
            usuario=request.user,
            cidadao=cidadao,
            tipo_acao='ANONIMIZACAO_DADOS',
            detalhes={'dados_anonimizados': list(dados_originais.keys())},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        messages.success(request, f'Dados do cidadão {dados_originais["nome"]} foram anonimizados.')
        return redirect('lgpd:dashboard')
    
    context = {
        'cidadao': cidadao,
    }
    
    return render(request, 'lgpd/confirmar_anonimizacao.html', context)


@login_required
def historico_acessos(request, cidadao_id):
    """Histórico de acessos aos dados de um cidadão."""
    
    cidadao = get_object_or_404(Cidadao, id=cidadao_id)
    
    acessos = AuditoriaAcesso.objects.filter(
        cidadao=cidadao
    ).order_by('-timestamp')[:50]
    
    context = {
        'cidadao': cidadao,
        'acessos': acessos,
    }
    
    return render(request, 'lgpd/historico_acessos.html', context)


@login_required
def violacoes_dados(request):
    """Lista de violações de dados."""
    
    violacoes = ViolacaoDados.objects.all().order_by('-data_deteccao')
    
    context = {
        'violacoes': violacoes,
    }
    
    return render(request, 'lgpd/violacoes_dados.html', context)


@login_required
def registrar_violacao(request):
    """Registra uma nova violação de dados."""
    
    if request.method == 'POST':
        violacao = ViolacaoDados.objects.create(
            tipo_violacao=request.POST['tipo_violacao'],
            severidade=request.POST['severidade'],
            descricao=request.POST['descricao'],
            data_ocorrencia_estimada=request.POST.get('data_ocorrencia') or None,
            detectado_por=request.user,
        )
        
        # TODO: Implementar notificação automática se necessário
        
        messages.success(request, 'Violação registrada com sucesso!')
        return redirect('lgpd:violacoes_dados')
    
    context = {
        'tipos_violacao': ViolacaoDados.TIPOS_VIOLACAO,
        'severidades': ViolacaoDados.SEVERIDADES,
    }
    
    return render(request, 'lgpd/registrar_violacao.html', context)


def politica_privacidade(request):
    """Exibe a política de privacidade ativa."""
    
    politica = PoliticaPrivacidade.objects.filter(ativa=True).first()
    
    context = {
        'politica': politica,
    }
    
    return render(request, 'lgpd/politica_privacidade.html', context)


# API Views

@csrf_exempt
@require_http_methods(["POST"])
def api_verificar_consentimento(request):
    """API para verificar consentimento de um cidadão."""
    
    try:
        data = json.loads(request.body)
        cidadao_id = data.get('cidadao_id')
        finalidade = data.get('finalidade')
        
        if not cidadao_id or not finalidade:
            return JsonResponse({'error': 'cidadao_id e finalidade são obrigatórios'}, status=400)
        
        consentimento = ConsentimentoLGPD.objects.filter(
            cidadao_id=cidadao_id,
            finalidade=finalidade,
            consentido=True,
            data_revogacao__isnull=True,
            valido_ate__gt=timezone.now()
        ).exists()
        
        return JsonResponse({
            'consentimento_valido': consentimento,
            'verificado_em': timezone.now().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_relatorio_conformidade(request):
    """API para obter relatório de conformidade LGPD."""
    
    relatorio = RelatorioLGPD.gerar_relatorio_conformidade()
    
    return JsonResponse(relatorio)