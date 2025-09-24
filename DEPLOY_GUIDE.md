# 🚀 Guia de Deploy - Sistema de Saúde Municipal
## Implantação no Hostinger VPS - maisagente.site

### 📋 Pré-requisitos no Servidor

1. **Servidor Ubuntu/Debian atualizado**:
```bash
sudo apt update && sudo apt upgrade -y
```

2. **Python 3.8+ e pip**:
```bash
sudo apt install python3 python3-pip python3-venv -y
```

3. **Nginx**:
```bash
sudo apt install nginx -y
```

4. **Git**:
```bash
sudo apt install git -y
```

### 📦 1. Clonagem e Configuração do Projeto

```bash
# 1. Clonar o repositório
cd /home/usuario/
git clone https://github.com/grupomartinscomunicacao/-agente.git maisagente
cd maisagente

# 2. Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
```

### 🔧 2. Configuração do Ambiente

```bash
# 1. Copiar e editar arquivo .env
cp .env .env.production
nano .env

# Configurar:
# DEBUG=False
# ALLOWED_HOSTS=maisagente.site,www.maisagente.site
# SECRET_KEY=seu-secret-key-seguro-aqui
```

### 🗄️ 3. Configuração do Banco de Dados

```bash
# Executar migrações
python manage.py makemigrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Coletar arquivos estáticos
python manage.py collectstatic --noinput
```

### 🔐 4. Configuração de Permissões

```bash
# Ajustar propriedade dos arquivos
sudo chown -R www-data:www-data /home/usuario/maisagente
sudo chmod -R 755 /home/usuario/maisagente

# Permissões especiais para SQLite
chmod 664 /home/usuario/maisagente/db.sqlite3
chmod 664 /home/usuario/maisagente/
```

### 🌐 5. Configuração do Gunicorn

```bash
# 1. Copiar arquivos de serviço
sudo cp gunicorn.socket /etc/systemd/system/
sudo cp gunicorn.service /etc/systemd/system/

# 2. Editar caminhos no arquivo de serviço
sudo nano /etc/systemd/system/gunicorn.service
# Ajustar User, Group, WorkingDirectory e caminhos

# 3. Ativar e iniciar serviços
sudo systemctl daemon-reload
sudo systemctl enable gunicorn.socket
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.service
sudo systemctl start gunicorn.service

# 4. Verificar status
sudo systemctl status gunicorn.socket
sudo systemctl status gunicorn.service
```

### 🌍 6. Configuração do Nginx

```bash
# 1. Criar configuração do site
sudo nano /etc/nginx/sites-available/maisagente.site

# 2. Copiar conteúdo do arquivo nginx_config.txt
# Ajustar caminhos conforme sua instalação

# 3. Ativar o site
sudo ln -s /etc/nginx/sites-available/maisagente.site /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 🔒 7. SSL com Let's Encrypt (Opcional)

```bash
# 1. Instalar Certbot
sudo apt install snapd
sudo snap install --classic certbot

# 2. Obter certificado
sudo certbot --nginx -d maisagente.site -d www.maisagente.site

# 3. Testar renovação automática
sudo certbot renew --dry-run
```

### 📊 8. Monitoramento e Logs

```bash
# Logs do Gunicorn
sudo journalctl -u gunicorn.service -f

# Logs do Nginx
sudo tail -f /var/log/nginx/maisagente_access.log
sudo tail -f /var/log/nginx/maisagente_error.log

# Logs do Django
tail -f /home/usuario/maisagente/django.log
```

### 🔄 9. Script de Deploy Automático

```bash
# Tornar o script executável
chmod +x deploy.sh

# Executar deploy
./deploy.sh
```

### ✅ 10. Verificação Final

1. **Teste de conectividade**: `http://maisagente.site`
2. **Admin panel**: `http://maisagente.site/admin/`
3. **Dashboard**: `http://maisagente.site/dashboard/`
4. **API**: `http://maisagente.site/api/`

### 🚨 Troubleshooting

**Erro de permissão no SQLite:**
```bash
sudo chown www-data:www-data /home/usuario/maisagente/db.sqlite3
sudo chmod 664 /home/usuario/maisagente/db.sqlite3
```

**Gunicorn não inicia:**
```bash
sudo systemctl status gunicorn.service
sudo journalctl -u gunicorn.service --no-pager
```

**Arquivos estáticos não carregam:**
```bash
python manage.py collectstatic --noinput
sudo nginx -t && sudo systemctl reload nginx
```

### 📞 Informações de Acesso

- **URL Principal**: https://maisagente.site
- **Painel Admin**: https://maisagente.site/admin/
- **Dashboard**: https://maisagente.site/dashboard/
- **API Docs**: https://maisagente.site/api/

---

*Sistema de Saúde Municipal - Versão 1.0*  
*Deploy preparado para Hostinger VPS*