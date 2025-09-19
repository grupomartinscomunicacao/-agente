# Sistema de Saúde Pública - Django

Sistema completo de gestão de saúde pública com Django, incluindo API REST, integração com OpenAI e dashboard para secretaria de saúde.

## 🚀 Funcionalidades

- ✅ Estrutura do projeto criada
- ✅ Modelos de dados implementados  
- ✅ Validação e normalização de dados
- ✅ API endpoints desenvolvidos
- ✅ Integração OpenAI implementada
- ✅ Frontend e dashboard criados
- ✅ Segurança e LGPD implementados
- ✅ Recomendações de hidratação personalizada
- ✅ Contexto médico completo com condições crônicas

## 📋 Requisitos

- Python 3.9+
- Django 5.2+
- OpenAI API Key
- Celery + RabbitMQ
- OpenAI API
- PostgreSQL

## 🛠 Instalação

1. **Clone o repositório:**
```bash
git clone <repository-url>
cd health_system
```

2. **Criar ambiente virtual:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac  
source venv/bin/activate
```

3. **Instalar dependências:**
```bash
pip install -r requirements.txt
```

4. **Configurar variáveis de ambiente:**
```bash
# Copie o arquivo de exemplo
cp .env.example .env
# Edite .env e adicione suas chaves reais
```

5. **Executar migrações:**
```bash
python manage.py migrate
```

6. **Criar superusuário:**
```bash
python manage.py createsuperuser
```

7. **Executar servidor:**
```bash
python manage.py runserver
```

3. Configurar banco de dados:
```bash
python manage.py migrate
```

4. Criar superusuário:
```bash
python manage.py createsuperuser
```

5. Executar servidor:
```bash
python manage.py runserver
```

## Estrutura do Projeto

- `health_system/` - Configurações principais do Django
- `citizens/` - App para gerenciamento de cidadãos
- `health_data/` - App para coleta de dados de saúde
- `anamnesis/` - App para anamnese automática
- `dashboard/` - App para dashboard da secretaria
- `api/` - Endpoints da API REST
- `ai_integration/` - Integração com OpenAI
- `utils/` - Utilitários e validações

## APIs Principais

- `/api/citizens/` - Gerenciamento de cidadãos
- `/api/health-data/` - Coleta de dados de saúde
- `/api/anamnesis/` - Anamnese automática
- `/api/dashboard/` - Dados do dashboard

## Conformidade LGPD

O sistema implementa:
- Anonimização automática de dados
- Logs de auditoria
- Controle de acesso
- Sistema de revisão humana