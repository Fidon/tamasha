"""
JSON-LD structured data generators.

Each function returns a plain dict that gets serialised to JSON-LD
inside the {% block structured_data %} template block via render_json_ld().
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
        "@type":    "Organization",
        "name":     settings.SITE_NAME,
        "url":      base,
        "logo":     f"{base}{settings.STATIC_URL}images/logo.png",
        "sameAs":   [],
    }


def website_schema(request) -> dict:
    base = _base_url(request)
    return {
        "@context": "https://schema.org",
        "@type":    "WebSite",
        "name":     settings.SITE_NAME,
        "url":      base,
        "potentialAction": {
            "@type":       "SearchAction",
            "target": {
                "@type":       "EntryPoint",
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
    base  = _base_url(request)
    items = [
        {
            "@type":    "ListItem",
            "position": i + 1,
            "name":     name,
            "item":     f"{base}{path}",
        }
        for i, (name, path) in enumerate(crumbs)
    ]
    return {
        "@context":        "https://schema.org",
        "@type":           "BreadcrumbList",
        "itemListElement": items,
    }


def event_schema(event, request) -> dict:
    """
    Accepts a Tamasha Event model instance.
    Field names match apps/events/models.py exactly:
      venue.latitude / venue.longitude (not .lat / .lng)
      banner_display preferred over banner for image
    """
    url    = request.build_absolute_uri(request.path)
    schema = {
        "@context":            "https://schema.org",
        "@type":               "Event",
        "name":                event.title,
        "url":                 url,
        "description":         _plain_text(event.description)[:500],
        "startDate":           event.starts_at.isoformat(),
        "endDate":             event.ends_at.isoformat() if event.ends_at else None,
        "eventStatus":         "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "organizer": {
            "@type": "Organization",
            "name":  event.organizer.organization_name,
            "url":   request.build_absolute_uri('/'),
        },
    }

    # Prefer display banner (optimised WebP), fall back to original
    banner = event.banner_display or event.banner
    if banner:
        schema["image"] = request.build_absolute_uri(banner.url)

    # Venue
    if event.venue:
        location = {
            "@type": "Place",
            "name":  event.venue.name,
            "address": {
                "@type":           "PostalAddress",
                "streetAddress":   event.venue.address,
                "addressLocality": event.venue.city,
                "addressCountry":  "TZ",
            },
        }
        # latitude / longitude — correct field names from Venue model
        if event.venue.latitude and event.venue.longitude:
            location["geo"] = {
                "@type":     "GeoCoordinates",
                "latitude":  str(event.venue.latitude),
                "longitude": str(event.venue.longitude),
            }
        schema["location"] = location

    # Ticket offers
    if hasattr(event, 'ticket_types'):
        ticket_types = list(
            event.ticket_types
            .filter(is_active=True)
            .order_by('sort_order', 'price')
        )
        if ticket_types:
            schema["offers"] = [
                {
                    "@type":         "Offer",
                    "name":          tt.name,
                    "price":         str(tt.price),
                    "priceCurrency": "TZS",
                    "availability":  (
                        "https://schema.org/SoldOut"
                        if tt.is_effectively_sold_out
                        else "https://schema.org/InStock"
                    ),
                    "url":           url,
                    "validFrom":     tt.sale_starts_at.isoformat() if tt.sale_starts_at else None,
                }
                for tt in ticket_types
            ]

    return schema


def faq_schema(faqs: list[tuple[str, str]]) -> dict:
    """faqs: list of (question, answer) tuples."""
    return {
        "@context":   "https://schema.org",
        "@type":      "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name":  q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faqs
        ],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _plain_text(html: str) -> str:
    """Strip HTML tags for use in schema description fields."""
    import re
    return re.sub(r'<[^>]+>', '', html or '').strip()