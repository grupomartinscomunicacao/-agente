#!/usr/bin/env python3
import os
import sys
import django
import sqlite3

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from geolocation.geocodificacao_service import GeocodificacaoService

def main():
    print("=== VERIFICAÇÃO DA ANA DE FREITAS ===")
    print()
    
    # Conectar ao banco SQLite
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()
    
    # Verificar dados da Ana
    cursor.execute('''
        SELECT c.id, c.nome, c.cep, c.cidade, c.estado, c.endereco,
               c.latitude, c.longitude,
               l.latitude as loc_lat, l.longitude as loc_lng
        FROM cidadaos_cidadao c 
        LEFT JOIN geolocation_localizacaosaude l ON c.id = l.cidadao_id 
        WHERE c.nome LIKE '%Ana%'
    ''')
    
    ana_dados = cursor.fetchone()
    if ana_dados:
        (id, nome, cep, cidade, estado, endereco, 
         c_lat, c_lng, l_lat, l_lng) = ana_dados
        
        print(f"👤 {nome}")
        print(f"📮 CEP: {cep}")
        print(f"🏙️ Cidade cadastrada: {cidade}")
        print(f"🗺️ Estado: {estado}")
        print(f"📍 Coordenadas do cidadão: {c_lat}, {c_lng}")
        print(f"📍 Coordenadas no mapa: {l_lat}, {l_lng}")
        print()
        
        # Verificar se as coordenadas correspondem a São Paulo ou Carinhanha
        if c_lat and c_lng:
            lat = float(c_lat)
            lng = float(c_lng)
            
            # São Paulo: aproximadamente -23.5489, -46.6388
            # Carinhanha: aproximadamente -14.3049, -43.7817
            
            if lat < -20:  # Região de São Paulo
                print("🔍 COORDENADAS INDICAM: São Paulo (SP)")
                localizacao_real = "São Paulo"
            else:  # Região de Carinhanha
                print("🔍 COORDENADAS INDICAM: Carinhanha (BA)")
                localizacao_real = "Carinhanha"
            
            print(f"❌ PROBLEMA: Cidade cadastrada ({cidade}) não confere com coordenadas ({localizacao_real})")
            
            # Vamos corrigir usando o CEP
            if cep:
                print(f"🔧 Tentando geocodificar novamente pelo CEP: {cep}")
                geo_service = GeocodificacaoService()
                resultado = geo_service.geocodificar_por_cep(cep)
                
                if resultado:
                    print(f"✅ Resultado da geocodificação:")
                    print(f"   Cidade: {resultado.get('cidade', 'N/A')}")
                    print(f"   Estado: {resultado.get('estado', 'N/A')}")
                    print(f"   Coordenadas: {resultado.get('latitude', 'N/A')}, {resultado.get('longitude', 'N/A')}")
                    
                    # Atualizar dados do cidadão
                    cursor.execute('''
                        UPDATE cidadaos_cidadao 
                        SET cidade = ?, estado = ?, latitude = ?, longitude = ?
                        WHERE id = ?
                    ''', [
                        resultado.get('cidade', cidade),
                        resultado.get('estado', estado),
                        resultado.get('latitude', lat),
                        resultado.get('longitude', lng),
                        id
                    ])
                    
                    # Atualizar LocalizacaoSaude
                    cursor.execute('''
                        UPDATE geolocation_localizacaosaude
                        SET cidade = ?, estado = ?, latitude = ?, longitude = ?
                        WHERE cidadao_id = ?
                    ''', [
                        resultado.get('cidade', cidade),
                        resultado.get('estado', estado),
                        resultado.get('latitude', lat),
                        resultado.get('longitude', lng),
                        id
                    ])
                    
                    conn.commit()
                    print("✅ Dados atualizados!")
                else:
                    print("❌ Não foi possível geocodificar o CEP")
    
    conn.close()

if __name__ == "__main__":
    main()