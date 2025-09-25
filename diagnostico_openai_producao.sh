#!/bin/bash
# Script de diagnóstico OpenAI para ambiente de produção
echo "🔍 DIAGNÓSTICO OPENAI - AMBIENTE DE PRODUÇÃO"
echo "=============================================="

# 1. Verificar se estamos no diretório correto
echo "📂 Diretório atual:"
pwd

# 2. Verificar variáveis de ambiente
echo ""
echo "🔑 Variáveis de ambiente:"
echo "OPENAI_API_KEY configurada: $([ -n "$OPENAI_API_KEY" ] && echo "✅ SIM" || echo "❌ NÃO")"
echo "ASSISTANT_ID configurado: $([ -n "$ASSISTANT_ID" ] && echo "✅ SIM" || echo "❌ NÃO")"

# 3. Verificar arquivo .env
echo ""
echo "📋 Arquivo .env:"
if [ -f ".env" ]; then
    echo "✅ .env existe"
    echo "Conteúdo relevante:"
    grep -E "OPENAI|ASSISTANT" .env | sed 's/=.*/=***/' # Oculta valores sensíveis
else
    echo "❌ .env não encontrado"
fi

# 4. Verificar versão do Python e OpenAI
echo ""
echo "🐍 Versões:"
python3 --version
python3 -c "import openai; print(f'OpenAI versão: {openai.__version__}')" 2>/dev/null || echo "❌ OpenAI não instalado"

# 5. Teste de importação Django
echo ""
echo "🔧 Teste Django:"
export DJANGO_SETTINGS_MODULE=health_system.settings
python3 -c "
import django
django.setup()
from django.conf import settings
print('✅ Django inicializado')
print(f'OPENAI_API_KEY: {\"✅ Configurado\" if settings.OPENAI_API_KEY else \"❌ Vazio\"}')
print(f'ASSISTANT_ID: {\"✅ Configurado\" if getattr(settings, \"ASSISTANT_ID\", None) else \"❌ Vazio\"}')
" 2>/dev/null || echo "❌ Erro ao inicializar Django"

echo ""
echo "📊 Diagnóstico concluído!"