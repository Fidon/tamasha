from django.conf import settings

def theme_processor(request):
    theme = 'dark'
    if request.user.is_authenticated:
        theme = getattr(request.user, 'theme_preference', 'dark') or 'dark'
    return {'current_theme': theme}

def site_processor(request):
    return {
        'SITE_NAME': settings.SITE_NAME,
        'SITE_DOMAIN': settings.SITE_DOMAIN,
        'SITE_DESCRIPTION': settings.SITE_DESCRIPTION,
    }