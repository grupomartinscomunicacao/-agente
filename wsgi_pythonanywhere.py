"""
WSGI config for health_system project - PythonAnywhere Production.

Configuração específica para deploy no PythonAnywhere.
"""

import os
import sys
from pathlib import Path

# Adicionar o diretório do projeto ao Python path
path = '/home/seunome/health_system'  # MUDAR para seu nome de usuário
if path not in sys.path:
    sys.path.append(path)

# Adicionar o diretório pai também
parent_path = '/home/seunome'  # MUDAR para seu nome de usuário  
if parent_path not in sys.path:
    sys.path.append(parent_path)

# Definir settings de produção
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.production')

try:
    from django.core.wsgi import get_wsgi_application
    application = get_wsgi_application()
    
    print("✅ WSGI para PythonAnywhere configurado com sucesso")
    
except Exception as e:
    print(f"❌ Erro ao configurar WSGI: {e}")
    # Log the error for debugging
    import traceback
    with open('/home/seunome/logs/wsgi_error.log', 'w') as f:  # MUDAR para seu nome de usuário
        f.write(f"WSGI Error: {e}\n")
        f.write(traceback.format_exc())
    raise