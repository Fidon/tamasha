import json

from django.http import HttpResponse
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'core/home.html'


class AboutView(TemplateView):
    template_name = 'core/about.html'


class ContactView(TemplateView):
    template_name = 'core/contact.html'


class HelpView(TemplateView):
    template_name = 'core/help.html'


class TermsView(TemplateView):
    template_name = 'core/terms.html'


class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'


class ManifestView(TemplateView):
    """
    Serves the PWA web app manifest dynamically so SITE_NAME and theme_color
    can be injected from settings. Returns application/manifest+json.
    """

    def get(self, request, *args, **kwargs):
        from django.conf import settings
        manifest = {
            "name": settings.SITE_NAME,
            "short_name": "Tamasha",
            "description": settings.SITE_DESCRIPTION,
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0D0D0D",
            "theme_color": "#C9A84C",
            "orientation": "portrait-primary",
            "icons": [
                {
                    "src": request.build_absolute_uri('/static/images/icons/icon-192.png'),
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
                {
                    "src": request.build_absolute_uri('/static/images/icons/icon-512.png'),
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
        }
        return HttpResponse(
            json.dumps(manifest, indent=2),
            content_type='application/manifest+json',
        )