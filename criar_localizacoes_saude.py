#!/usr/bin/env python3
"""
Script para criar LocalizacaoSaude para cidadãos geocodificados com anamnese.
"""

import os
import sys
import django
import sqlite3
import uuid

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.development')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

def main():
    print("=== CRIANDO LOCALIZACAOSAUDE ===")
    print()
    
    # Conectar ao banco SQLite
    db_path = 'db.sqlite3'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Buscar cidadãos com anamnese e coordenadas que não têm LocalizacaoSaude
        cursor.execute('''
            SELECT 
                c.id, c.nome, c.latitude, c.longitude, c.endereco, 
                c.bairro, c.cidade, c.estado, c.cep,
                a.id as anamnese_id, a.triagem_risco
            FROM cidadaos_cidadao c
            INNER JOIN anamneses_anamnese a ON c.id = a.cidadao_id
            LEFT JOIN geolocation_localizacaosaude l ON c.id = l.cidadao_id
            WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
                AND c.latitude != 0 AND c.longitude != 0
                AND l.id IS NULL
            ORDER BY c.id, a.criado_em DESC
        ''')
        
        cidadaos_para_mapa = cursor.fetchall()
        
        # Agrupar por cidadão para pegar apenas a anamnese mais recente
        cidadaos_unicos = {}
        for row in cidadaos_para_mapa:
            cidadao_id = row[0]
            if cidadao_id not in cidadaos_unicos:
                cidadaos_unicos[cidadao_id] = row
        
        print(f"📍 Criando {len(cidadaos_unicos)} LocalizacaoSaude...")
        
        for cidadao_id, dados in cidadaos_unicos.items():
            (cidadao_id, nome, latitude, longitude, endereco, 
             bairro, cidade, estado, cep, anamnese_id, triagem_risco) = dados
            
            # Determinar pontuação baseada no risco
            pontuacao_map = {
                'baixo': 25,
                'medio': 50, 
                'médio': 50,
                'alto': 75,
                'critico': 100
            }
            pontuacao = pontuacao_map.get(triagem_risco.lower(), 25)
            
            # Inserir LocalizacaoSaude
            cursor.execute('''
                INSERT INTO geolocation_localizacaosaude 
                (id, cidadao_id, anamnese_id, latitude, longitude, 
                 endereco_completo, bairro, cidade, estado, cep,
                 nivel_risco, pontuacao_risco, ativo, criado_em, atualizado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                        datetime('now'), datetime('now'))
            ''', [
                str(uuid.uuid4()),  # ID único UUID válido
                cidadao_id,
                anamnese_id, 
                latitude,
                longitude,
                endereco or '',
                bairro or '',
                cidade or '',
                estado or '',
                cep or '',
                triagem_risco.lower(),
                pontuacao,
                1  # ativo = True
            ])
            
            print(f"   📍 {nome}: {triagem_risco}")
        
        conn.commit()
        
        # Estatísticas finais
        cursor.execute('SELECT COUNT(*) FROM geolocation_localizacaosaude')
        total_final = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT nivel_risco, COUNT(*) 
            FROM geolocation_localizacaosaude 
            GROUP BY nivel_risco
            ORDER BY COUNT(*) DESC
        ''')
        riscos = cursor.fetchall()
        
        print()
        print("✅ PROCESSO CONCLUÍDO!")
        print(f"📍 Total de localizações no mapa: {total_final}")
        print("📊 Distribuição por risco:")
        for risco, count in riscos:
            print(f"   - {risco.title()}: {count}")
            
    except Exception as e:
        print(f"❌ Erro durante processo: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    main()