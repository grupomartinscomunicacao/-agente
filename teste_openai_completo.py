#!/usr/bin/env python
"""
Teste com carregamento manual do .env
"""
import os
import sys
from pathlib import Path

# Adiciona o projeto ao path
project_root = Path('C:\\Users\\teste\\OneDrive\\Desktop\\+agente')
sys.path.append(str(project_root))

# Carrega manualmente o .env
from decouple import config

print("=== TESTE COM CARREGAMENTO MANUAL DO .env ===")
print(f"OPENAI_API_KEY do .env: {'✅' if config('OPENAI_API_KEY', default='') else '❌'}")
print(f"ASSISTANT_ID do .env: {'✅' if config('ASSISTANT_ID', default='') else '❌'}")

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')

import django
django.setup()

from django.conf import settings

print("\n=== CONFIGURAÇÕES DJANGO ===")
print(f"OPENAI_API_KEY django: {'✅' if settings.OPENAI_API_KEY else '❌'}")
print(f"ASSISTANT_ID django: {'✅' if getattr(settings, 'ASSISTANT_ID', None) else '❌'}")

# Teste o serviço
try:
    print("\n=== TESTE DO SERVIÇO ===")
    from ai_integracao.assistant_service import OpenAIAssistantService
    service = OpenAIAssistantService()
    print(f"Cliente OpenAI inicializado: {'✅' if service.client else '❌'}")
    print(f"Assistant ID: {service.assistant_id}")
    
    # Vamos fazer um teste real com dados fictícios
    from cidadaos.models import Cidadao
    from saude_dados.models import DadosSaude
    
    # Busca um cidadão de teste
    cidadao = Cidadao.objects.first()
    if cidadao:
        print(f"Cidadão teste encontrado: {cidadao.nome}")
        
        # Busca dados de saúde
        dados_saude = DadosSaude.objects.filter(cidadao=cidadao).first()
        if dados_saude:
            print(f"Dados de saúde encontrados: ID {dados_saude.id}")
            
            # TESTE REAL DA ANAMNESE
            print("\n--- TESTANDO GERAÇÃO DE ANAMNESE ---")
            resultado = service.gerar_anamnese_com_assistant(cidadao, dados_saude)
            
            if resultado.get('sucesso', False):
                print("✅ Anamnese gerada com sucesso!")
                print(f"Triagem: {resultado.get('triagem_risco', 'N/A')}")
                print(f"Resumo: {resultado.get('resumo_anamnese', 'N/A')[:100]}...")
            else:
                print("❌ Erro na geração da anamnese:")
                print(f"Erro: {resultado.get('erro', 'Erro desconhecido')}")
        else:
            print("❌ Nenhum dado de saúde encontrado")
    else:
        print("❌ Nenhum cidadão encontrado para teste")
        
except Exception as e:
    print(f"❌ Erro no teste: {e}")
    print(f"Tipo: {type(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIM DO TESTE ===")