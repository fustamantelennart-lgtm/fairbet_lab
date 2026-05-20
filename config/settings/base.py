# config/settings/base.py
"""
Settings base de FairBet Lab.

Variables sensibles se leen desde el `.env` (no versionado) usando
python-decouple. Los valores por defecto solo se usan en desarrollo si
falta una variable; en CI/producción todas las variables deben venir
del entorno explícitamente.
"""
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# === Seguridad ===
# SECRET_KEY se lee del entorno. NUNCA committear el valor real.
# Para generar una: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-FALLBACK-ONLY-FOR-FIRST-BOOT-CHANGE-ME')

# DEBUG controla traces de error visibles al usuario. Solo True en dev.
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)

# Lista de hosts permitidos (separados por coma en el .env)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='*', cast=Csv())


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'wallet',
    'events',
    'accounts',
    'compliance',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
# Channels usa ASGI; corregido: antes apuntaba a wsgi por error.
ASGI_APPLICATION = 'config.asgi.application'

# === Base de datos ===
# Credenciales se leen del .env. Los defaults son para arranque mínimo
# en una compu nueva sin .env aún.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='fairbet_db'),
        'USER': config('POSTGRES_USER', default='fairbet_admin'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='fairbet_pass'),
        'HOST': config('POSTGRES_HOST', default='db'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'