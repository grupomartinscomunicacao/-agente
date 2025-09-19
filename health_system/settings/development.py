"""
Settings para desenvolvimento local
"""

from .base import *
from decouple import config, Csv

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-development-key-change-in-production')

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver', '.ngrok-free.app']

# Database para desenvolvimento (SQLite)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# WSGI application (para desenvolvimento)
WSGI_APPLICATION = "health_system.wsgi.application"

# Email backend para desenvolvimento (console)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Logging para desenvolvimento
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'django.log',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'ai_integracao': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Debug toolbar (opcional)
INTERNAL_IPS = [
    '127.0.0.1',
]

# Static files para desenvolvimento
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configurações específicas do OpenAI para dev
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
ASSISTANT_ID = config('ASSISTANT_ID', default='')

print("🚀 Rodando em modo DESENVOLVIMENTO")
print(f"📂 BASE_DIR: {BASE_DIR}")
print(f"🔑 OpenAI configurada: {'✅' if OPENAI_API_KEY else '❌'}")