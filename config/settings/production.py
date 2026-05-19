from .base import *  # noqa: F401, F403

DEBUG = False

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# Email via SMTP
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST')                    # noqa: F405
EMAIL_PORT = env.int('EMAIL_PORT', 587)           # noqa: F405
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')          # noqa: F405
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')  # noqa: F405

# ---------------------------------------------------------------------------
# Strict CSP
# ---------------------------------------------------------------------------
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", 'fonts.googleapis.com')
CSP_FONT_SRC = ("'self'", 'fonts.gstatic.com')
CSP_IMG_SRC = ("'self'", 'data:', 'blob:')
CSP_CONNECT_SRC = ("'self'",)