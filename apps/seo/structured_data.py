"""
JSON-LD structured data generators.

Each function returns a plain dict that gets serialised to JSON-LD
inside the {% block structured_data %} template block.

Usage in a view:
    from apps.seo.structured_data import event_schema, breadcrumb_schema

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['structured_data'] = [
            event_schema(self.object, self.request),
            breadcrumb_schema([
                ('Home', '/'),
                ('Events', '/events/'),
                (self.object.title, self.request.path),
            ], self.request),
        ]
        return ctx
"""

import json
from django.conf import settings
from django.utils.safestring import mark_safe


def _base_url(request):
    return request.build_absolute_uri('/').rstrip('/')


def render_json_ld(data: dict | list) -> str:
    """Return a <script type="application/ld+json"> tag as a safe string."""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')


def organization_schema(request) -> dict:
    base = _base_url(request)
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": settings.SITE_NAME,
        "url": base,
        "logo": f"{base}{settings.STATIC_URL}images/logo.png",
        "sameAs": [],  # populate with social URLs when available
    }


def website_schema(request) -> dict:
    base = _base_url(request)
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": settings.SITE_NAME,
        "url": base,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{base}/events/?q={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }


def breadcrumb_schema(crumbs: list[tuple[str, str]], request) -> dict:
    """
    crumbs: list of (name, path) tuples, e.g.:
        [('Home', '/'), ('Events', '/events/'), ('Event Title', '/events/slug/')]
    """
    base = _base_url(request)
    items = [
        {
            "@type": "ListItem",
            "position": i + 1,
            "name": name,
            "item": f"{base}{path}",
        }
        for i, (name, path) in enumerate(crumbs)
    ]
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }


def event_schema(event, request) -> dict:
    """
    Accepts a Tamasha Event model instance.
    Called from EventDetailView once the events app is built.
    """
    base   = _base_url(request)
    url    = request.build_absolute_uri(request.path)
    schema = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "url": url,
        "description": event.description[:500] if event.description else "",
        "startDate": event.starts_at.isoformat(),
        "endDate":   event.ends_at.isoformat() if event.ends_at else None,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "organizer": {
            "@type": "Organization",
            "name": event.organizer.organization_name,
            "url":  base,
        },
    }

    # Banner image
    if event.banner:
        schema["image"] = request.build_absolute_uri(event.banner.url)

    # Venue
    if event.venue:
        schema["location"] = {
            "@type": "Place",
            "name":    event.venue.name,
            "address": {
                "@type":           "PostalAddress",
                "streetAddress":   event.venue.address,
                "addressLocality": event.venue.city,
                "addressCountry":  "TZ",
            },
        }
        if event.venue.lat and event.venue.lng:
            schema["location"]["geo"] = {
                "@type":     "GeoCoordinates",
                "latitude":  event.venue.lat,
                "longitude": event.venue.lng,
            }

    # Ticket offers
    ticket_types = event.ticket_types.filter(
        quantity__gt=0
    ).select_related() if hasattr(event, 'ticket_types') else []

    if ticket_types:
        schema["offers"] = [
            {
                "@type":         "Offer",
                "name":          tt.name,
                "price":         str(tt.price),
                "priceCurrency": "TZS",
                "availability":  (
                    "https://schema.org/InStock"
                    if tt.quantity_sold < tt.quantity
                    else "https://schema.org/SoldOut"
                ),
                "url": url,
                "validFrom": tt.sale_starts_at.isoformat() if tt.sale_starts_at else None,
            }
            for tt in ticket_types
        ]

    return schema


def faq_schema(faqs: list[tuple[str, str]]) -> dict:
    """
    faqs: list of (question, answer) tuples.
    """
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }