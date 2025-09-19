#!/usr/bin/env python
"""
Script de backup automático para SQLite
Sistema de Saúde Pública
"""

import os
import shutil
import gzip
from datetime import datetime
from pathlib import Path

def backup_sqlite():
    """Criar backup do banco SQLite com timestamp"""
    
    # Caminhos
    db_file = Path('db.sqlite3')
    backup_dir = Path('backups')
    
    if not db_file.exists():
        print("❌ Arquivo db.sqlite3 não encontrado!")
        return False
    
    # Criar diretório de backup
    backup_dir.mkdir(exist_ok=True)
    
    # Nome do backup com timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"db_backup_{timestamp}.sqlite3"
    backup_path = backup_dir / backup_name
    
    try:
        # Copiar arquivo
        shutil.copy2(db_file, backup_path)
        
        # Comprimir para economizar espaço
        compressed_path = backup_dir / f"db_backup_{timestamp}.sqlite3.gz"
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remover arquivo não comprimido
        backup_path.unlink()
        
        file_size = compressed_path.stat().st_size / (1024 * 1024)  # MB
        print(f"✅ Backup criado: {compressed_path}")
        print(f"📊 Tamanho: {file_size:.2f} MB")
        
        # Limpar backups antigos (manter últimos 5)
        cleanup_old_backups(backup_dir)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar backup: {e}")
        return False

def cleanup_old_backups(backup_dir, keep=5):
    """Manter apenas os últimos N backups"""
    backups = sorted(backup_dir.glob('db_backup_*.sqlite3.gz'))
    
    if len(backups) > keep:
        old_backups = backups[:-keep]
        for old_backup in old_backups:
            old_backup.unlink()
            print(f"🗑️ Backup antigo removido: {old_backup.name}")

def restore_backup(backup_file):
    """Restaurar backup do SQLite"""
    backup_path = Path('backups') / backup_file
    
    if not backup_path.exists():
        print(f"❌ Backup não encontrado: {backup_path}")
        return False
    
    try:
        # Descomprimir
        temp_file = Path('temp_restore.sqlite3')
        with gzip.open(backup_path, 'rb') as f_in:
            with open(temp_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Backup do arquivo atual
        if Path('db.sqlite3').exists():
            emergency_backup = f"db_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
            shutil.copy2('db.sqlite3', emergency_backup)
            print(f"🛡️ Backup de emergência: {emergency_backup}")
        
        # Restaurar
        shutil.move(temp_file, 'db.sqlite3')
        print(f"✅ Banco restaurado de: {backup_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao restaurar backup: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False

def list_backups():
    """Listar backups disponíveis"""
    backup_dir = Path('backups')
    
    if not backup_dir.exists():
        print("📁 Nenhum backup encontrado")
        return
    
    backups = sorted(backup_dir.glob('db_backup_*.sqlite3.gz'))
    
    if not backups:
        print("📁 Nenhum backup encontrado")
        return
    
    print("📋 Backups disponíveis:")
    for backup in backups:
        size = backup.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"  📄 {backup.name} - {size:.2f} MB - {mtime.strftime('%d/%m/%Y %H:%M')}")

def main():
    """Menu principal"""
    print("🗄️ Sistema de Backup SQLite")
    print("=" * 40)
    print("1. Criar backup")
    print("2. Listar backups")
    print("3. Restaurar backup")
    print("0. Sair")
    
    choice = input("\nEscolha uma opção: ").strip()
    
    if choice == '1':
        backup_sqlite()
    elif choice == '2':
        list_backups()
    elif choice == '3':
        list_backups()
        backup_file = input("\nNome do arquivo para restaurar: ").strip()
        if backup_file:
            restore_backup(backup_file)
    elif choice == '0':
        print("👋 Até logo!")
    else:
        print("❌ Opção inválida")

if __name__ == "__main__":
    main()