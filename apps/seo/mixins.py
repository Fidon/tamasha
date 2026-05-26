from django.conf import settings

class SEOMixin:
    """
    Inject SEO metadata into template context.

    Class-level defaults for static pages:
        class AboutView(SEOMixin, TemplateView):
            seo_title       = "About — Tamasha Events"
            seo_description = "Learn about Tamasha Events."

    Override get_seo_* methods for dynamic values (detail pages):
        def get_seo_title(self):
            return f"{self.object.title} — {settings.SITE_NAME}"

        def get_seo_og_image(self):
            # Return an absolute URL string or None to fall back to default.
            if self.object.banner_display:
                return self.request.build_absolute_uri(self.object.banner_display.url)
            return None
    """

    seo_title       = None
    seo_description = None
    seo_image       = None   # absolute URL — static fallback
    seo_robots      = 'index, follow'
    seo_og_type     = 'website'
    seo_canonical   = None   # overrides request.path-based canonical

    # ------------------------------------------------------------------ getters

    def get_seo_title(self):
        return self.seo_title or settings.SITE_NAME

    def get_seo_description(self):
        return self.seo_description or settings.SITE_DESCRIPTION

    def get_seo_og_image(self):
        """
        Override in subclasses to return a page-specific absolute image URL.
        Falls back to the static OG default.
        """
        return None

    def get_seo_image(self):
        """
        Final resolved OG image URL. Checks get_seo_og_image() first,
        then the class-level seo_image attr, then the site default.
        """
        override = self.get_seo_og_image()
        if override:
            return override
        if self.seo_image:
            return self.seo_image
        return self.request.build_absolute_uri(
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

    # ------------------------------------------------------------------ context

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
    """Convenience mixin for private/dashboard/auth pages that must not be indexed."""
    seo_robots = 'noindex, nofollow'