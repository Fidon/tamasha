"""
Canonical URL utilities.

Handles paginated pages and query-string normalization so
search engines receive consistent canonical signals.
"""

from django.conf import settings


def build_canonical(request, path: str = None, page: int = None) -> str:
    """
    Build a canonical URL.

    - Strips UTM and tracking params automatically.
    - For paginated pages: page 1 gets the base URL (no ?page=),
      subsequent pages get ?page=N appended.

    Args:
        request: Django HttpRequest.
        path:    Override path. Defaults to request.path.
        page:    Current page number (int). None = non-paginated.

    Returns:
        Absolute canonical URL string.
    """
    base   = getattr(settings, 'SITE_DOMAIN', request.build_absolute_uri('/').rstrip('/'))
    path   = path or request.path

    if page and page > 1:
        return f"{base}{path}?page={page}"

    return f"{base}{path}"


# Query params that should never appear in canonical URLs
_STRIP_PARAMS = frozenset({
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'mc_cid', 'mc_eid',
})


def clean_query_string(request) -> str:
    """
    Return a query string with tracking params removed.
    Used when building canonicals for filtered listing pages
    where ?category= or ?city= params are meaningful for SEO.
    """
    params = {
        k: v for k, v in request.GET.items()
        if k not in _STRIP_PARAMS
    }
    if not params:
        return ''
    from urllib.parse import urlencode
    return '?' + urlencode(params)