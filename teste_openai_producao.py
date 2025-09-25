#!/usr/bin/env python3
"""
Teste específico de OpenAI no ambiente de produção
"""
import os
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')

print("🧪 TESTE OPENAI - AMBIENTE DE PRODUÇÃO")
print("======================================")

try:
    # 1. Teste de importação básica
    print("\n1️⃣ Teste de importação:")
    import openai
    print(f"✅ OpenAI importado - versão: {openai.__version__}")
    
    # 2. Configurar Django
    print("\n2️⃣ Inicializando Django:")
    import django
    django.setup()
    from django.conf import settings
    print("✅ Django inicializado")
    
    # 3. Verificar configurações
    print("\n3️⃣ Verificando configurações:")
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    assistant_id = getattr(settings, 'ASSISTANT_ID', '')
    
    print(f"OPENAI_API_KEY: {'✅ Configurado' if api_key else '❌ Vazio'}")
    print(f"ASSISTANT_ID: {'✅ Configurado' if assistant_id else '❌ Vazio'}")
    
    if api_key:
        print(f"API Key (primeiros 20 chars): {api_key[:20]}...")
    
    # 4. Teste de inicialização do cliente OpenAI
    print("\n4️⃣ Teste de inicialização:")
    try:
        # TESTE 1: Inicialização básica (pode dar erro de proxies)
        try:
            client = openai.OpenAI(api_key=api_key)
            print("✅ Cliente OpenAI básico inicializado")
        except Exception as e:
            print(f"❌ Erro cliente básico: {e}")
            
            # TESTE 2: Inicialização com timeout
            try:
                client = openai.OpenAI(
                    api_key=api_key,
                    timeout=30.0
                )
                print("✅ Cliente OpenAI com timeout inicializado")
            except Exception as e2:
                print(f"❌ Erro com timeout: {e2}")
                
                # TESTE 3: Inicialização minimalista 
                try:
                    import httpx
                    client = openai.OpenAI(
                        api_key=api_key,
                        http_client=httpx.Client(timeout=30.0)
                    )
                    print("✅ Cliente OpenAI com httpx customizado inicializado")
                except Exception as e3:
                    print(f"❌ Erro com httpx: {e3}")
                    client = None
    
    except Exception as e:
        print(f"❌ Erro geral na inicialização: {e}")
        client = None
    
    # 5. Teste do serviço Assistant
    print("\n5️⃣ Teste do serviço Assistant:")
    try:
        from ai_integracao.assistant_service import OpenAIAssistantService
        service = OpenAIAssistantService()
        print(f"✅ AssistantService inicializado")
        print(f"Cliente existe: {'✅ SIM' if service.client else '❌ NÃO'}")
        print(f"Assistant ID: {service.assistant_id or 'Vazio'}")
        
    except Exception as e:
        print(f"❌ Erro no AssistantService: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. Teste com dados reais (se existirem)
    print("\n6️⃣ Teste com dados do banco:")
    try:
        from cidadaos.models import Cidadao
        from saude_dados.models import DadosSaude
        
        cidadao_count = Cidadao.objects.count()
        dados_count = DadosSaude.objects.count()
        
        print(f"Cidadãos no banco: {cidadao_count}")
        print(f"Dados de saúde no banco: {dados_count}")
        
        if cidadao_count > 0 and dados_count > 0:
            cidadao = Cidadao.objects.first()
            dados_saude = DadosSaude.objects.filter(cidadao=cidadao).first()
            
            if dados_saude:
                print(f"Testando com: {cidadao.nome}")
                print("⚠️ Para testar geração real, execute: python3 teste_anamnese_producao.py")
        
    except Exception as e:
        print(f"❌ Erro ao acessar banco: {e}")

except Exception as e:
    print(f"❌ Erro crítico: {e}")
    import traceback
    traceback.print_exc()

print("\n🏁 Teste concluído!")
print("💡 Se houver erro de 'proxies', execute: python3 corrigir_openai_producao.py")