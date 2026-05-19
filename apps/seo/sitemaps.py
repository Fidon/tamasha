from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority    = 0.6
    changefreq  = 'monthly'
    protocol    = 'https'

    def items(self):
        return ['core:home', 'core:about', 'core:contact', 'core:help']

    def location(self, item):
        return reverse(item)


class EventSitemap(Sitemap):
    """
    Populated once the Event model exists (Phase 3).
    Returns only PUBLISHED events.
    """
    priority   = 0.9
    changefreq = 'daily'
    protocol   = 'https'

    def items(self):
        # Guard: import lazily so this file doesn't crash before Phase 3
        try:
            from apps.events.models import Event
            return Event.objects.filter(
                status='PUBLISHED'
            ).select_related('venue', 'organizer').order_by('-starts_at')
        except Exception:
            return []

    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else None

    def location(self, obj):
        return reverse('events:detail', kwargs={'slug': obj.slug})


# Registry consumed by config/urls.py
sitemaps = {
    'static': StaticViewSitemap,
    'events': EventSitemap,
}