from django.conf import settings


class SEOMixin:
    """
    Inject SEO metadata into template context.

    Usage in a CBV:
        class EventDetailView(SEOMixin, DetailView):
            seo_title       = "Event Name — Tamasha Events"
            seo_description = "Event description..."

    Or override get_seo_* methods for dynamic values:
        def get_seo_title(self):
            return f"{self.object.title} — {settings.SITE_NAME}"
    """

    seo_title            = None
    seo_description      = None
    seo_image            = None   # absolute URL
    seo_robots           = 'index, follow'
    seo_og_type          = 'website'
    seo_canonical        = None   # overrides request.path-based canonical

    def get_seo_title(self):
        return self.seo_title or settings.SITE_NAME

    def get_seo_description(self):
        return self.seo_description or settings.SITE_DESCRIPTION

    def get_seo_image(self):
        if self.seo_image:
            return self.seo_image
        request = self.request
        return request.build_absolute_uri(
            f"{settings.STATIC_URL}images/og-default.jpg"
        )

    def get_seo_canonical(self):
        if self.seo_canonical:
            return self.seo_canonical
        return self.request.build_absolute_uri(self.request.path)

    def get_seo_robots(self):
        return self.seo_robots

    def get_seo_og_type(self):
        return self.seo_og_type

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'seo_title':       self.get_seo_title(),
            'seo_description': self.get_seo_description(),
            'seo_image':       self.get_seo_image(),
            'seo_canonical':   self.get_seo_canonical(),
            'seo_robots':      self.get_seo_robots(),
            'seo_og_type':     self.get_seo_og_type(),
        })
        return ctx


class NoIndexMixin(SEOMixin):
    """Convenience mixin for private/dashboard pages that must not be indexed."""
    seo_robots = 'noindex, nofollow'