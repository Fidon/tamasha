import os
from pathlib import Path
import environ

# config/settings/base.py → config/settings/ → config/ → project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    COMMISSION_RATE=(float, 0.03),
)

environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

AUTH_USER_MODEL = 'accounts.CustomUser'

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'axes',
    'django_celery_beat',
    'django_celery_results',
    'markdownx',
    'csp',
]

LOCAL_APPS = [
    'apps.core',
    'apps.seo',
    'apps.accounts',
    'apps.events',
    'apps.tickets',
    'apps.payments',
    'apps.checkin',
    'apps.dashboard',
    'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'csp.middleware.CSPMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.theme_processor',
                'apps.core.context_processors.site_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------
COMMISSION_RATE = env('COMMISSION_RATE')

# ---------------------------------------------------------------------------
# Africa's Talking
# ---------------------------------------------------------------------------
AFRICASTALKING_USERNAME = env('AFRICASTALKING_USERNAME')
AFRICASTALKING_API_KEY = env('AFRICASTALKING_API_KEY')
AFRICASTALKING_SENDER_ID = env('AFRICASTALKING_SENDER_ID', default=None)

# ---------------------------------------------------------------------------
# AzamPay
# ---------------------------------------------------------------------------
AZAMPAY_APP_NAME = env('AZAMPAY_APP_NAME')
AZAMPAY_CLIENT_ID = env('AZAMPAY_CLIENT_ID')
AZAMPAY_CLIENT_SECRET = env('AZAMPAY_CLIENT_SECRET')
AZAMPAY_BASE_URL = env('AZAMPAY_BASE_URL', default='https://sandbox.azampay.co.tz')

# ---------------------------------------------------------------------------
# django-axes  (brute-force login protection)
# ---------------------------------------------------------------------------
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_CALLABLE = 'apps.accounts.handlers.axes_lockout_handler'
AXES_RESET_ON_SUCCESS = True

# ---------------------------------------------------------------------------
# Auth redirects
# ---------------------------------------------------------------------------
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# ---------------------------------------------------------------------------
# Email (overridden per environment)
# ---------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Tamasha Events <noreply@tamasha.co.tz>')
SERVER_EMAIL = env('SERVER_EMAIL', default='errors@tamasha.co.tz')
ADMIN_NOTIFICATION_EMAIL = env('ADMIN_NOTIFICATION_EMAIL', default='')

# ---------------------------------------------------------------------------
# Site meta — consumed by context processors & SEO mixins
# ---------------------------------------------------------------------------
SITE_NAME = 'Tamasha Events'
SITE_DOMAIN = env('SITE_DOMAIN', default='http://127.0.0.1:8000')
SITE_DESCRIPTION = (
    'Premium event ticketing for concerts, festivals, '
    'nightlife and curated events in Tanzania.'
)