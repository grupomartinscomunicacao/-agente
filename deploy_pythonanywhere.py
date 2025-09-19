"""
Script de deploy automático para PythonAnywhere
Utiliza a API do PythonAnywhere para automatizar o processo de deploy
"""

import requests
import os
import sys
import json
from pathlib import Path

# Configurações
PYTHONANYWHERE_TOKEN = "587142a8e95f7065f0e043599b711316408637c9"
PYTHONANYWHERE_USERNAME = "maisagente"  # ALTERE para seu username
DOMAIN_NAME = f"{PYTHONANYWHERE_USERNAME}.pythonanywhere.com"
PROJECT_PATH = f"/home/{PYTHONANYWHERE_USERNAME}/health_system"

class PythonAnywhereDeployer:
    def __init__(self):
        self.api_base = "https://www.pythonanywhere.com/api/v0/user"
        self.headers = {
            'Authorization': f'Token {PYTHONANYWHERE_TOKEN}',
            'Content-Type': 'application/json'
        }
    
    def log(self, message, level="INFO"):
        """Log com formatação colorida"""
        colors = {
            "INFO": "\033[92m",  # Verde
            "WARN": "\033[93m",  # Amarelo  
            "ERROR": "\033[91m", # Vermelho
            "RESET": "\033[0m"   # Reset
        }
        print(f"{colors.get(level, '')}{level}: {message}{colors['RESET']}")
    
    def check_token(self):
        """Verificar se o token está válido"""
        self.log("🔑 Verificando token da API...")
        response = requests.get(
            f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/",
            headers=self.headers
        )
        
        if response.status_code == 200:
            self.log("✅ Token válido!")
            return True
        else:
            self.log(f"❌ Token inválido! Status: {response.status_code}", "ERROR")
            return False
    
    def create_webapp(self):
        """Criar web app no PythonAnywhere"""
        self.log("🌐 Criando/verificando web app...")
        
        # Verificar se já existe
        response = requests.get(
            f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/webapps/{DOMAIN_NAME}/",
            headers=self.headers
        )
        
        if response.status_code == 200:
            self.log("✅ Web app já existe")
            return True
        
        # Criar novo web app
        data = {
            'domain_name': DOMAIN_NAME,
            'python_version': 'python310'  # Python 3.10
        }
        
        response = requests.post(
            f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/webapps/",
            headers=self.headers,
            json=data
        )
        
        if response.status_code == 201:
            self.log("✅ Web app criado com sucesso!")
            return True
        else:
            self.log(f"❌ Erro ao criar web app: {response.text}", "ERROR")
            return False
    
    def update_wsgi(self):
        """Atualizar arquivo WSGI"""
        self.log("📝 Atualizando arquivo WSGI...")
        
        wsgi_content = f"""
import os
import sys

# Adicionar projeto ao path  
project_home = '{PROJECT_PATH}'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Ativar virtual environment
venv_path = '{PROJECT_PATH}/venv/bin/activate_this.py'
exec(open(venv_path).read(), dict(__file__=venv_path))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.production')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
"""
        
        data = {
            'content': wsgi_content
        }
        
        response = requests.put(
            f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/webapps/{DOMAIN_NAME}/wsgi_file/",
            headers=self.headers,
            json=data
        )
        
        if response.status_code == 200:
            self.log("✅ Arquivo WSGI atualizado!")
            return True
        else:
            self.log(f"❌ Erro ao atualizar WSGI: {response.text}", "ERROR")
            return False
    
    def configure_static_files(self):
        """Configurar arquivos estáticos"""
        self.log("📁 Configurando arquivos estáticos...")
        
        static_mappings = [
            {
                'url': '/static/',
                'path': f'{PROJECT_PATH}/staticfiles/'
            },
            {
                'url': '/media/', 
                'path': f'{PROJECT_PATH}/media/'
            }
        ]
        
        for mapping in static_mappings:
            response = requests.post(
                f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/webapps/{DOMAIN_NAME}/static_files/",
                headers=self.headers,
                json=mapping
            )
            
            if response.status_code in [200, 201]:
                self.log(f"✅ Mapeamento {mapping['url']} configurado")
            else:
                self.log(f"⚠️ Mapeamento {mapping['url']} pode já existir", "WARN")
        
        return True
    
    def reload_webapp(self):
        """Recarregar web app"""
        self.log("🔄 Recarregando web app...")
        
        response = requests.post(
            f"{self.api_base}/{PYTHONANYWHERE_USERNAME}/webapps/{DOMAIN_NAME}/reload/",
            headers=self.headers
        )
        
        if response.status_code == 200:
            self.log("✅ Web app recarregado!")
            return True
        else:
            self.log(f"❌ Erro ao recarregar: {response.text}", "ERROR")
            return False
    
    def get_console_info(self):
        """Mostrar informações para configuração manual"""
        self.log("📋 Comandos para executar no console do PythonAnywhere:", "INFO")
        
        commands = f"""
# 1. Clonar repositório (se não existe)
cd ~
git clone https://github.com/grupomartinscomunicacao/-agente.git health_system

# 2. Navegar para projeto
cd {PROJECT_PATH}

# 3. Criar virtual environment
python3.10 -m venv venv
source venv/bin/activate

# 4. Instalar dependências
pip install -r requirements-prod.txt

# 5. Configurar .env (IMPORTANTE!)
nano .env
# Adicionar:
# DEBUG=False
# SECRET_KEY=sua-secret-key-super-segura
# ALLOWED_HOSTS={DOMAIN_NAME}
# OPENAI_API_KEY=sua_chave_openai
# ASSISTANT_ID=seu_assistant_id
# (SQLite não precisa de configuração de banco)

# 6. Executar migrações
python manage.py migrate --settings=health_system.settings.production

# 7. Criar superuser
python manage.py createsuperuser --settings=health_system.settings.production

# 8. Coletar arquivos estáticos
python manage.py collectstatic --settings=health_system.settings.production --noinput

# 9. Criar diretórios de log
mkdir -p /home/{PYTHONANYWHERE_USERNAME}/logs

# 10. Ajustar permissões do SQLite (importante!)
chmod 664 db.sqlite3
chmod 775 .  # diretório do projeto
"""
        
        print(commands)
    
    def deploy(self):
        """Executar deploy completo"""
        self.log("🚀 Iniciando deploy automático no PythonAnywhere...")
        
        if not self.check_token():
            return False
        
        steps = [
            ("Criar web app", self.create_webapp),
            ("Atualizar WSGI", self.update_wsgi),
            ("Configurar estáticos", self.configure_static_files),
            ("Recarregar app", self.reload_webapp)
        ]
        
        for step_name, step_func in steps:
            self.log(f"📋 Executando: {step_name}")
            if not step_func():
                self.log(f"❌ Falha em: {step_name}", "ERROR")
                return False
        
        self.log("🎉 Deploy automático concluído!", "INFO")
        self.log(f"🌐 Seu site: https://{DOMAIN_NAME}", "INFO")
        
        self.get_console_info()
        
        return True

def main():
    """Função principal"""
    print("=" * 60)
    print("🏭 PythonAnywhere Auto Deployer")
    print("Sistema de Saúde Pública")
    print("=" * 60)
    
    # Verificar se estamos no diretório correto
    if not Path('manage.py').exists():
        print("❌ Execute este script no diretório raiz do projeto!")
        sys.exit(1)
    
    # Verificar se USERNAME foi alterado
    if PYTHONANYWHERE_USERNAME == "seunome":
        print("❌ Altere a variável PYTHONANYWHERE_USERNAME no início do script!")
        sys.exit(1)
    
    deployer = PythonAnywhereDeployer()
    success = deployer.deploy()
    
    if success:
        print("\n✅ Deploy configurado! Execute os comandos mostrados no console do PythonAnywhere.")
    else:
        print("\n❌ Falha no deploy. Verifique os logs acima.")

if __name__ == "__main__":
    main()