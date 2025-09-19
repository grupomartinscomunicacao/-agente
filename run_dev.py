#!/usr/bin/env python
"""
Script para inicialização em desenvolvimento local
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    """Configurar e executar o servidor de desenvolvimento."""
    
    print("🚀 Sistema de Saúde Pública - Desenvolvimento Local")
    print("=" * 50)
    
    # Definir settings de desenvolvimento
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.development')
    
    # Verificar se .env existe
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ Arquivo .env não encontrado!")
        print("📋 Copie .env.example para .env e configure suas variáveis:")
        print("   cp .env.example .env")
        return
    
    try:
        import django
        from django.core.management import execute_from_command_line
        
        # Setup Django
        django.setup()
        
        print("✅ Django configurado com sucesso")
        print("🔧 Executando migrações...")
        
        # Executar migrações automaticamente
        execute_from_command_line(['manage.py', 'migrate'])
        
        print("✅ Migrações executadas")
        print("👤 Verificando superuser...")
        
        # Verificar se existe superuser
        from django.contrib.auth.models import User
        if not User.objects.filter(is_superuser=True).exists():
            print("❌ Nenhum superuser encontrado")
            print("🔧 Execute: python manage.py createsuperuser")
        else:
            print("✅ Superuser existe")
        
        print("🌐 Iniciando servidor de desenvolvimento...")
        print("📱 Acesse: http://127.0.0.1:8000/")
        print("🔑 Admin: http://127.0.0.1:8000/admin/")
        print("📊 Dashboard: http://127.0.0.1:8000/dashboard/")
        print("")
        print("Para parar o servidor: Ctrl+C")
        print("=" * 50)
        
        # Iniciar servidor
        execute_from_command_line(['manage.py', 'runserver', '0.0.0.0:8000'])
        
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    except KeyboardInterrupt:
        print("\n🛑 Servidor parado pelo usuário")
        print("👋 Até logo!")

if __name__ == '__main__':
    main()