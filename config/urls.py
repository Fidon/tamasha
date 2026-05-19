from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from apps.seo.sitemaps import sitemaps

urlpatterns = [
    path('admin/', admin.site.urls),
    path('markdownx/', include('markdownx.urls')),

    # ── SEO ──────────────────────────────────────────────────────────────
    path(
        'sitemap.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap',
    ),
    path(
        'robots.txt',
        TemplateView.as_view(template_name='seo/robots.txt', content_type='text/plain'),
        name='robots_txt',
    ),

    # ── Apps ─────────────────────────────────────────────────────────────
    path('', include('apps.core.urls', namespace='core')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('events/', include('apps.events.urls', namespace='events')),
    path('tickets/', include('apps.tickets.urls', namespace='tickets')),
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('checkin/', include('apps.checkin.urls', namespace='checkin')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)