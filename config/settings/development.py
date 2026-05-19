from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

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

# django-csp 4.0 format — relaxed for dev (debug toolbar needs unsafe-inline/eval)
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src':  ("'self'", "'unsafe-inline'", "'unsafe-eval'", 'code.jquery.com'),
        'style-src':   ("'self'", "'unsafe-inline'", 'fonts.googleapis.com'),
        'font-src':    ("'self'", 'fonts.gstatic.com'),
        'img-src':     ("'self'", 'data:', 'blob:'),
    }
}

# Whitenoise serves media in dev (no Nginx)
WHITENOISE_USE_FINDERS = True