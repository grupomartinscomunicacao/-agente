#!/usr/bin/env python
"""
Script para recalcular os riscos de todos os cidadãos com base nos seus dados de saúde
"""
import os
import django

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings')
django.setup()

from geolocation.models import LocalizacaoSaude
from geolocation.calculador_risco import CalculadorRisco
from geolocation.geocodificacao_service import GeocodificacaoService
from cidadaos.models import Cidadao
import random
import math

def recalcular_riscos():
    """Recalcula os riscos de todos os cidadãos"""
    calculador = CalculadorRisco()
    geocod_service = GeocodificacaoService()
    
    localizacoes = LocalizacaoSaude.objects.all()
    print(f"🎯 Recalculando riscos para {localizacoes.count()} cidadãos...")
    
    atualizados = 0
    
    for loc in localizacoes:
        try:
            # Calcular risco baseado nos dados de saúde
            nivel_risco, pontuacao_risco = calculador.calcular_risco_cidadao(loc.cidadao)
            
            # Aplicar dispersão nas coordenadas se necessário
            if loc.cidade and loc.estado:
                # Verificar se há outros cidadãos na mesma cidade
                mesma_cidade = LocalizacaoSaude.objects.filter(
                    cidade=loc.cidade,
                    estado=loc.estado
                ).exclude(id=loc.id)
                
                if mesma_cidade.exists():
                    # Aplicar jitter para evitar sobreposição
                    novas_coords = geocod_service.adicionar_jitter_coordenadas(
                        loc.latitude, 
                        loc.longitude,
                        raio_metros=1500  # Raio maior para cidades
                    )
                    loc.latitude = novas_coords[0]
                    loc.longitude = novas_coords[1]
            
            # Atualizar os dados
            loc.nivel_risco = nivel_risco
            loc.pontuacao_risco = pontuacao_risco
            loc.save()
            
            print(f"✅ {loc.cidadao.nome}: {nivel_risco.upper()} (pontuação: {pontuacao_risco:.1f})")
            atualizados += 1
            
        except Exception as e:
            print(f"❌ Erro ao processar {loc.cidadao.nome}: {e}")
    
    print(f"\n🎉 Processamento concluído: {atualizados}/{localizacoes.count()} cidadãos atualizados")

if __name__ == "__main__":
    recalcular_riscos()