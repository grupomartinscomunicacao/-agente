#!/usr/bin/env python
"""
Script para padronizar os níveis de risco no banco (remover acentos)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')
django.setup()

from geolocation.models import LocalizacaoSaude

def padronizar_riscos():
    """Padroniza os níveis de risco removendo acentos"""
    
    # Mapeamento de correções
    correcoes = {
        'médio': 'medio',
        'MÉDIO': 'medio', 
        'Médio': 'medio',
        'MEDIO': 'medio',
        'Medio': 'medio',
        'baixo': 'baixo',
        'BAIXO': 'baixo',
        'Baixo': 'baixo',
        'alto': 'alto',
        'ALTO': 'alto',
        'Alto': 'alto',
        'critico': 'critico',
        'CRITICO': 'critico',
        'Critico': 'critico'
    }
    
    localizacoes = LocalizacaoSaude.objects.all()
    corrigidos = 0
    
    print("🎯 Padronizando níveis de risco...")
    print(f"Total de registros: {localizacoes.count()}")
    
    for loc in localizacoes:
        risco_original = loc.nivel_risco
        risco_corrigido = correcoes.get(risco_original, risco_original.lower())
        
        if risco_original != risco_corrigido:
            loc.nivel_risco = risco_corrigido
            loc.save()
            print(f"✅ {loc.cidadao.nome}: '{risco_original}' → '{risco_corrigido}'")
            corrigidos += 1
        else:
            print(f"🔹 {loc.cidadao.nome}: '{risco_original}' (já correto)")
    
    print(f"\n🎉 Processamento concluído: {corrigidos} registros corrigidos")
    
    # Mostrar distribuição final
    from collections import Counter
    riscos_finais = [loc.nivel_risco for loc in LocalizacaoSaude.objects.all()]
    distribuicao = Counter(riscos_finais)
    
    print("\n📊 Distribuição final:")
    for risco, qtd in sorted(distribuicao.items()):
        print(f"   {risco}: {qtd} cidadãos")

if __name__ == "__main__":
    padronizar_riscos()