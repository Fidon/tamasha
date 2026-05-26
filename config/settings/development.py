from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'senorita-banking-isolation.ngrok-free.dev']

INSTALLED_APPS += ['debug_toolbar']  # noqa: F405

MIDDLEWARE = [  # noqa: F405
    'debug_toolbar.middleware.DebugToolbarMiddleware',
] + MIDDLEWARE  # noqa: F405

INTERNAL_IPS = ['127.0.0.1']

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')
EMAIL_PORT = env.int('EMAIL_PORT', 587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

# ---------------------------------------------------------------------------
# django-csp 4.0 — relaxed for dev
# unsafe-inline/eval required for debug toolbar
# Quill CDN + Nominatim allowed for wizard
# ---------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src':  (
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'",
            'cdn.quilljs.com',
            'cdn.jsdelivr.net',
        ),
        'style-src':   (
            "'self'",
            "'unsafe-inline'",
            'fonts.googleapis.com',
            'cdn.quilljs.com',
            'cdn.jsdelivr.net',
        ),
        'font-src':    ("'self'", 'fonts.gstatic.com'),
        'img-src':     ("'self'", 'data:', 'blob:'),
        # Nominatim AJAX calls from the venue search in the wizard
        'connect-src': (
            "'self'",
            'https://nominatim.openstreetmap.org',
            'https://cdn.quilljs.com',
        ),
    }
}

# Whitenoise serves media in dev (no Nginx)
WHITENOISE_USE_FINDERS = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'apps.payments': {
            'handlers':  ['console'],
            'level':     'DEBUG',
            'propagate': False,
        },
        'apps.tickets': {
            'handlers':  ['console'],
            'level':     'DEBUG',
            'propagate': False,
        },
    },
}