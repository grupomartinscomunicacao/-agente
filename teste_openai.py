#!/usr/bin/env python
"""
Teste de inicialização do OpenAI para identificar o problema
"""
import os
import sys
sys.path.append('C:\\Users\\teste\\OneDrive\\Desktop\\+agente')

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')

import django
django.setup()

from django.conf import settings

print("=== TESTE DE INICIALIZAÇÃO OPENAI ===")
print(f"OPENAI_API_KEY configurada: {'✅' if settings.OPENAI_API_KEY else '❌'}")
print(f"ASSISTANT_ID configurado: {'✅' if getattr(settings, 'ASSISTANT_ID', None) else '❌'}")

try:
    import openai
    print(f"Versão OpenAI: {openai.__version__}")
    
    # Teste 1: Inicialização básica
    print("\n--- Teste 1: Inicialização básica ---")
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    print("✅ Cliente OpenAI inicializado com sucesso!")
    
    # Teste 2: Teste da assistant service
    print("\n--- Teste 2: Assistant Service ---")
    from ai_integracao.assistant_service import OpenAIAssistantService
    service = OpenAIAssistantService()
    print("✅ OpenAIAssistantService inicializado com sucesso!")
    
except Exception as e:
    print(f"❌ Erro: {e}")
    print(f"Tipo do erro: {type(e)}")
    
    # Vamos tentar uma inicialização mais específica
    print("\n--- Tentando inicialização com timeout ---")
    try:
        client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0
        )
        print("✅ Cliente com timeout inicializado!")
    except Exception as e2:
        print(f"❌ Ainda com erro: {e2}")
        
print("\n=== FIM DO TESTE ===")