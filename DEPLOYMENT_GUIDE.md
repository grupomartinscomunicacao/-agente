# 🚀 Guia de Instalação e Deploy

Este guia mostra como configurar o projeto para rodar em **localhost** (desenvolvimento) e fazer **deploy no PythonAnywhere** (produção).

## 📦 Instalação Local (Desenvolvimento)

### 1. Pré-requisitos
- Python 3.9+
- Git
- Virtual Environment

### 2. Clonar o projeto
```bash
git clone https://github.com/grupomartinscomunicacao/-agente.git
cd -agente
```

### 3. Criar ambiente virtual
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### 4. Instalar dependências
```bash
# Para desenvolvimento (inclui ferramentas de debug)
pip install -r requirements-dev.txt

# Ou apenas produção
pip install -r requirements.txt
```

### 5. Configurar variáveis de ambiente
```bash
# Copiar arquivo de exemplo
cp .env.example .env

# Editar .env com suas configurações
# Necessário: SECRET_KEY e OPENAI_API_KEY
```

### 6. Executar migrações
```bash
python manage.py migrate
```

### 7. Criar superuser
```bash
python manage.py createsuperuser
```

### 8. Iniciar servidor

#### Opção 1: Script automático (recomendado)
```bash
python run_dev.py
```

#### Opção 2: Manual
```bash
python manage.py runserver 0.0.0.0:8000
```

### 9. Acessar aplicação
- **Site:** http://127.0.0.1:8000/
- **Admin:** http://127.0.0.1:8000/admin/
- **Dashboard:** http://127.0.0.1:8000/dashboard/
- **API:** http://127.0.0.1:8000/api/

---

## 🏭 Deploy no PythonAnywhere

### 1. Preparar conta no PythonAnywhere
1. Crie uma conta em [pythonanywhere.com](https://www.pythonanywhere.com)
2. Escolha um plano (Beginner é suficiente para testes)

### 2. Upload do código

#### Opção 1: Git (recomendado)
```bash
# No console do PythonAnywhere
git clone https://github.com/grupomartinscomunicacao/-agente.git
cd -agente
```

#### Opção 2: Upload de arquivos
- Use a aba "Files" no dashboard
- Faça upload dos arquivos do projeto

### 3. Configurar ambiente virtual
```bash
# No console do PythonAnywhere
cd ~/-agente
python3.10 -m venv venv  # ou python3.9
source venv/bin/activate
pip install -r requirements-prod.txt
```

### 4. Configurar banco de dados

#### Para PostgreSQL (planos pagos):
```bash
# No dashboard: Databases > PostgreSQL
# Criar banco e usuário
# Anotar: HOST, DATABASE, USER, PASSWORD
```

#### Para MySQL (gratuito):
```bash
# No dashboard: Databases > MySQL
# Criar banco de dados
# Usar o usuário automático criado
```

### 5. Configurar variáveis de ambiente
```bash
# Criar arquivo .env no servidor
nano .env
```

```properties
DEBUG=False
SECRET_KEY=sua-secret-key-super-segura
ALLOWED_HOSTS=seuusuario.pythonanywhere.com

# Database (exemplo PostgreSQL)
DATABASE_URL=postgres://usuario:senha@host:5432/nome_db

# OpenAI
OPENAI_API_KEY=sua-chave-openai
ASSISTANT_ID=seu-assistant-id

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=senha-do-app
EMAIL_USE_TLS=True
```

### 6. Executar migrações
```bash
cd ~/-agente
source venv/bin/activate
python manage.py migrate --settings=health_system.settings.production
```

### 7. Criar superuser
```bash
python manage.py createsuperuser --settings=health_system.settings.production
```

### 8. Coletar arquivos estáticos
```bash
python manage.py collectstatic --settings=health_system.settings.production --noinput
```

### 9. Configurar Web App

1. **Web tab** no dashboard
2. **Add a new web app**
3. Escolher **Manual configuration**
4. Selecionar **Python 3.10**

### 10. Configurar WSGI

1. Editar `/var/www/seuusuario_pythonanywhere_com_wsgi.py`
2. Substituir conteúdo por:

```python
import os
import sys

# Adicionar projeto ao path
project_home = '/home/seuusuario/-agente'  # MUDAR seuusuario
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Ativar virtual environment
activate_this = '/home/seuusuario/-agente/venv/bin/activate_this.py'  # MUDAR seuusuario
exec(open(activate_this).read(), dict(__file__=activate_this))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'health_system.settings.production')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

### 11. Configurar arquivos estáticos

1. **Web tab** > **Static files**
2. Adicionar:
   - **URL:** `/static/`
   - **Directory:** `/home/seuusuario/staticfiles/`
3. Adicionar:
   - **URL:** `/media/`
   - **Directory:** `/home/seuusuario/media/`

### 12. Reload da aplicação
1. **Web tab** > **Reload**
2. Aguardar o reload completar

---

## 🔧 Comandos Úteis

### Desenvolvimento
```bash
# Rodar testes
python manage.py test

# Criar nova migração
python manage.py makemigrations

# Shell interativo
python manage.py shell

# Verificar configuração
python manage.py check

# Verificar deploy
python manage.py check --deploy
```

### Produção (PythonAnywhere)
```bash
# Atualizar código
cd ~/-agente
git pull origin master

# Executar migrações
python manage.py migrate --settings=health_system.settings.production

# Coletar estáticos
python manage.py collectstatic --settings=health_system.settings.production --noinput

# Reload (via console ou web interface)
touch /var/www/seuusuario_pythonanywhere_com_wsgi.py
```

---

## 🔍 Solução de Problemas

### Erro "Module not found"
- Verificar se virtual environment está ativado
- Verificar se requirements estão instalados
- Verificar paths no WSGI

### Erro de banco de dados
- Verificar configuração DATABASE_URL
- Verificar se migrações foram executadas
- Verificar permissões do banco

### Erro de arquivos estáticos
- Executar `collectstatic`
- Verificar configuração STATIC_ROOT
- Verificar mapeamento no Web tab

### Erro OpenAI
- Verificar se OPENAI_API_KEY está definida
- Verificar se chave tem saldo
- Verificar logs em `/home/seuusuario/logs/`

---

## 📊 Monitoramento

### Logs locais
```bash
tail -f django.log
tail -f ai_audit.log
```

### Logs PythonAnywhere
- **Error logs:** Web tab > Log files
- **Custom logs:** `/home/seuusuario/logs/`

---

## 🔄 Atualizações

### Local para Produção
```bash
# Local
git add .
git commit -m "Nova funcionalidade"
git push origin master

# PythonAnywhere
cd ~/-agente
git pull origin master
python manage.py migrate --settings=health_system.settings.production
python manage.py collectstatic --settings=health_system.settings.production --noinput
touch /var/www/seuusuario_pythonanywhere_com_wsgi.py
```

---

## 🛡️ Segurança

- ✅ SECRET_KEY único por ambiente
- ✅ DEBUG=False em produção
- ✅ Arquivos sensíveis no .gitignore
- ✅ HTTPS recomendado (configurar no PythonAnywhere)
- ✅ Backup regular do banco de dados

---

**🎯 Ambientes configurados com sucesso!**
- **Local:** `health_system.settings.development`
- **Produção:** `health_system.settings.production`