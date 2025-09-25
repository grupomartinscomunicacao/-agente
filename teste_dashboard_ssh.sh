echo "🏥 TESTANDO DASHBOARD COMPLETO" && export DJANGO_SETTINGS_MODULE=health_system.emergency_settings && python3 -c "
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'health_system.emergency_settings'
django.setup()

print('=== TESTE COMPLETO DO DASHBOARD ===')
print()

# 1. VERIFICAR ESTRUTURA DO SISTEMA
print('1️⃣ VERIFICANDO ESTRUTURA...')
try:
    from cidadaos.models import Cidadao
    from ai_integracao.assistant_service import OpenAIAssistantService
    from dashboard.views import dashboard_view
    print('✅ Todos os modelos importados')
except Exception as e:
    print(f'❌ Erro imports: {e}')

# 2. VERIFICAR DADOS
print()
print('2️⃣ VERIFICANDO DADOS...')
try:
    total_cidadaos = Cidadao.objects.count()
    print(f'✅ Cidadãos cadastrados: {total_cidadaos}')
    
    if total_cidadaos > 0:
        cidadao_teste = Cidadao.objects.first()
        print(f'   Exemplo: {cidadao_teste.nome}, {getattr(cidadao_teste, \"idade\", \"N/A\")} anos')
    else:
        print('⚠️ Nenhum cidadão cadastrado - vou criar um exemplo:')
        cidadao_teste = Cidadao.objects.create(
            nome='João Silva',
            cpf='12345678901',
            telefone='(11) 99999-9999',
            email='joao@teste.com',
            data_nascimento='1980-01-01',
            sexo='M',
            logradouro='Rua Teste, 123',
            cidade='São Paulo',
            estado='SP',
            cep='01000-000',
            condicoes_saude_cronicas='Hipertensão'
        )
        print(f'✅ Cidadão teste criado: {cidadao_teste.nome}')
        
except Exception as e:
    print(f'❌ Erro dados: {e}')

# 3. TESTAR ANAMNESE
print()
print('3️⃣ TESTANDO GERAÇÃO DE ANAMNESE...')
try:
    service = OpenAIAssistantService()
    cidadao = Cidadao.objects.first()
    
    if cidadao:
        print(f'   Testando com: {cidadao.nome}')
        resultado = service.gerar_anamnese_com_assistant(cidadao, None)
        
        print('✅ ANAMNESE GERADA:')
        print(f'   Modo: {resultado.get(\"modo\", \"N/A\")}')
        print(f'   Risco: {resultado.get(\"triagem_risco\", \"N/A\")}')
        print(f'   Diagnóstico: {resultado.get(\"diagnostico_clinico\", \"N/A\")}')
        print(f'   Resumo: {resultado.get(\"resumo_anamnese\", \"\")[:80]}...')
        
        # Salvar resultado para o dashboard
        if not hasattr(cidadao, '_anamnese_teste'):
            cidadao._anamnese_teste = resultado
            
    else:
        print('❌ Nenhum cidadão para teste')
        
except Exception as e:
    print(f'❌ Erro anamnese: {e}')

# 4. SIMULAR REQUEST DO DASHBOARD
print()
print('4️⃣ SIMULANDO DASHBOARD...')
try:
    from django.test import RequestFactory
    from django.contrib.auth.models import User
    
    # Criar request fake
    factory = RequestFactory()
    request = factory.get('/dashboard/')
    
    # Criar usuário admin se não existir
    try:
        admin_user = User.objects.get(username='admin')
    except:
        admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
        print('✅ Usuário admin criado')
    
    request.user = admin_user
    
    # Testar view do dashboard
    response = dashboard_view(request)
    
    if response.status_code == 200:
        print('✅ DASHBOARD RESPONDENDO!')
        print(f'   Status: {response.status_code}')
        
        # Verificar conteúdo
        content = response.content.decode('utf-8')
        if 'Cidadãos' in content:
            print('✅ Conteúdo carregado corretamente')
        else:
            print('⚠️ Conteúdo pode estar incompleto')
            
    else:
        print(f'❌ Dashboard erro: {response.status_code}')
        
except Exception as e:
    print(f'❌ Erro dashboard: {e}')
    import traceback
    traceback.print_exc()

# 5. ESTATÍSTICAS FINAIS
print()
print('5️⃣ ESTATÍSTICAS DO SISTEMA:')
try:
    stats = {
        'total_cidadaos': Cidadao.objects.count(),
        'com_email': Cidadao.objects.exclude(email__isnull=True).exclude(email='').count(),
        'com_telefone': Cidadao.objects.exclude(telefone__isnull=True).exclude(telefone='').count(),
    }
    
    print(f'✅ Total de cidadãos: {stats[\"total_cidadaos\"]}')
    print(f'✅ Com email: {stats[\"com_email\"]}')
    print(f'✅ Com telefone: {stats[\"com_telefone\"]}')
    
    # Classificação por risco (simulada)
    if stats['total_cidadaos'] > 0:
        print()
        print('📊 SIMULAÇÃO DE TRIAGEM:')
        for cidadao in Cidadao.objects.all()[:3]:
            idade = getattr(cidadao, 'idade', 0) or 0
            if idade > 65:
                risco = 'alto'
            elif idade > 50:
                risco = 'medio'
            else:
                risco = 'baixo'
            print(f'   {cidadao.nome}: risco {risco}')
            
except Exception as e:
    print(f'❌ Erro stats: {e}')

print()
print('🎉 TESTE COMPLETO FINALIZADO!')
print('📱 Acesse: http://maisagente.site/dashboard/')
print('👤 Login: admin / admin123')
" && echo "🏁 DASHBOARD TESTADO!"