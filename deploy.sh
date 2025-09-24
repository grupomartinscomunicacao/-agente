#!/bin/bash
# Deploy script for maisagente.site - Hostinger VPS

echo "🚀 Iniciando deploy para maisagente.site..."

# Atualizar o repositório
echo "📦 Atualizando código..."
git pull origin main

# Instalar dependências
echo "🔧 Instalando dependências..."
pip install -r requirements.txt

# Executar migrações
echo "🗄️ Aplicando migrações..."
python manage.py makemigrations
python manage.py migrate

# Coletar arquivos estáticos
echo "📁 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Criar superusuário se não existir
echo "👤 Verificando superusuário..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@maisagente.site', 'senha123')
    print('Superusuário admin criado com sucesso!')
else:
    print('Superusuário admin já existe.')
"

# Reiniciar Gunicorn (assumindo systemd)
echo "🔄 Reiniciando serviços..."
sudo systemctl restart gunicorn
sudo systemctl reload nginx

echo "✅ Deploy concluído com sucesso!"
echo "🌐 Site disponível em: https://maisagente.site"