"""
Safe slug generation with collision handling.
Used by Event and any other model that needs unique slugs.
"""

import re
from django.utils.text import slugify


def generate_unique_slug(model_class, title: str, instance=None, slug_field: str = 'slug') -> str:
    """
    Generate a URL-safe slug from title, appending an incrementing suffix
    on collision. Excludes the instance itself when checking for duplicates
    (needed for edit operations).

    Args:
        model_class: The Django model class to check uniqueness against.
        title:       Source string (event title, etc.).
        instance:    Existing model instance being updated, or None for creates.
        slug_field:  Name of the slug field on the model (default: 'slug').

    Returns:
        A unique slug string.

    Example:
        slug = generate_unique_slug(Event, "Dar Live Music Festival 2026")
        # → "dar-live-music-festival-2026"
        # → "dar-live-music-festival-2026-2"  (if first exists)
    """
    base_slug = _clean_slug(slugify(title))
    if not base_slug:
        base_slug = 'event'

    slug      = base_slug
    qs        = model_class.objects.filter(**{slug_field: slug})

    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)

    counter = 2
    while qs.exists():
        slug = f"{base_slug}-{counter}"
        qs   = model_class.objects.filter(**{slug_field: slug})
        if instance and instance.pk:
            qs = qs.exclude(pk=instance.pk)
        counter += 1

    return slug


def _clean_slug(slug: str) -> str:
    """Remove consecutive hyphens and strip leading/trailing hyphens."""
    slug = re.sub(r'-{2,}', '-', slug)
    return slug.strip('-')