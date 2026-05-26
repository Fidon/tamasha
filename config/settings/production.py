from .base import *  # noqa: F401, F403

DEBUG = False

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
SECURE_HSTS_SECONDS             = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS  = True
SECURE_HSTS_PRELOAD             = True
SECURE_SSL_REDIRECT             = True
SESSION_COOKIE_SECURE           = True
CSRF_COOKIE_SECURE              = True
SECURE_BROWSER_XSS_FILTER       = True
SECURE_CONTENT_TYPE_NOSNIFF     = True
X_FRAME_OPTIONS                 = 'DENY'

# ---------------------------------------------------------------------------
# Email via SMTP
# ---------------------------------------------------------------------------
EMAIL_BACKEND    = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST       = env('EMAIL_HOST')            # noqa: F405
EMAIL_PORT       = env.int('EMAIL_PORT', 587)   # noqa: F405
EMAIL_USE_TLS    = True
EMAIL_HOST_USER  = env('EMAIL_HOST_USER')       # noqa: F405
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')  # noqa: F405

# ---------------------------------------------------------------------------
# django-csp 4.0 format — strict for production
# Quill CDN + Nominatim allowed for wizard
# ---------------------------------------------------------------------------
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src':  (
            "'self'",
            'cdn.quilljs.com',
            'cdn.jsdelivr.net',
        ),
        'style-src':   (
            "'self'",
            'fonts.googleapis.com',
            'cdn.quilljs.com',
            'cdn.jsdelivr.net',
        ),
        'font-src':    ("'self'", 'fonts.gstatic.com'),
        'img-src':     ("'self'", 'data:', 'blob:'),
        'connect-src': ("'self'", 'https://nominatim.openstreetmap.org'),
    }
}