"""
All event business logic lives here. Views call these functions only.
No business logic in views, forms, or models (beyond simple properties).
"""
import io
import logging
from decimal import Decimal

import bleach
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image

from apps.seo.slugs import generate_unique_slug
from .models import Category, Tag, Venue, Event, EventCollaborator, EventDraft

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANNER_MAX_BYTES        = 10 * 1024 * 1024          # 10 MB
BANNER_ALLOWED_TYPES    = {'image/jpeg', 'image/png', 'image/webp'}
BANNER_DISPLAY_SIZE     = (1400, 520)               # px  width × height
BANNER_DISPLAY_QUALITY  = 82                        # WebP quality

ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 's',
    'h2', 'h3', 'blockquote', 'ul', 'ol', 'li',
    'a', 'span',
]
ALLOWED_HTML_ATTRS = {
    'a':    ['href', 'title', 'target', 'rel'],
    'span': ['class'],
}

EAST_AFRICA_TIMEZONES = [
    ('Africa/Nairobi',       'East Africa Time — Nairobi / Dar es Salaam / Kampala (EAT, UTC+3)'),
    ('Africa/Dar_es_Salaam', 'East Africa Time — Dar es Salaam (EAT, UTC+3)'),
    ('Africa/Kampala',       'East Africa Time — Kampala (EAT, UTC+3)'),
    ('Africa/Kigali',        'East Africa Time — Kigali (EAT, UTC+3)'),
    ('Africa/Addis_Ababa',   'East Africa Time — Addis Ababa (EAT, UTC+3)'),
    ('Africa/Mogadishu',     'East Africa Time — Mogadishu (EAT, UTC+3)'),
    ('Africa/Lusaka',        'Central Africa Time — Lusaka (CAT, UTC+2)'),
    ('Africa/Harare',        'Central Africa Time — Harare (CAT, UTC+2)'),
    ('Africa/Cairo',         'Eastern European Time — Cairo (EET, UTC+2)'),
]


# ---------------------------------------------------------------------------
# Venue helpers
# ---------------------------------------------------------------------------

def search_local_venues(query: str, limit: int = 8) -> list[dict]:
    """
    Query the local Venue table. Returns a list of dicts for JSON response.
    Called first before hitting Nominatim.
    """
    if not query or len(query.strip()) < 2:
        return []

    venues = (
        Venue.objects
        .filter(name__icontains=query)
        .order_by('city', 'name')[:limit]
    )
    return [
        {
            'id':       v.pk,
            'name':     v.name,
            'address':  v.address,
            'city':     v.city,
            'country':  v.country,
            'lat':      str(v.latitude)  if v.latitude  else '',
            'lng':      str(v.longitude) if v.longitude else '',
            'osm_id':   v.osm_id,
            'source':   'local',
        }
        for v in venues
    ]


def get_or_create_venue(
    *,
    name: str,
    city: str,
    address: str = '',
    country: str = 'Tanzania',
    lat=None,
    lng=None,
    osm_id: str = '',
) -> Venue:
    latitude  = lat
    longitude = lng
    """
    Upsert a venue.
    - If osm_id is provided, try to match on that first (most accurate dedup).
    - Fall back to (name, city) unique constraint.
    - On match, update coordinates/address if we now have better data.
    """
    name    = name.strip()
    city    = city.strip()

    if not name or not city:
        raise ValidationError(_('Venue name and city are required.'))

    # 1. Dedup by osm_id when available
    if osm_id:
        venue = Venue.objects.filter(osm_id=osm_id).first()
        if venue:
            _update_venue_if_better(venue, address, lat, lng)
            return venue

    # 2. Dedup by (name, city) — get_or_create does not support iexact in lookup
    existing = Venue.objects.filter(name__iexact=name, city__iexact=city).first()
    if existing:
        _update_venue_if_better(existing, address, lat, lng, osm_id)
        return existing

    venue = Venue.objects.create(
        name      = name,
        city      = city,
        address   = address,
        country   = country,
        latitude  = lat,
        longitude = lng,
        osm_id    = osm_id,
    )
    return venue


def _update_venue_if_better(
    venue: Venue,
    address: str,
    latitude,
    longitude,
    osm_id: str = '',
) -> None:
    """Update venue fields only when incoming data is more complete."""
    changed = False
    if address and not venue.address:
        venue.address  = address
        changed = True
    if latitude and not venue.latitude:
        venue.latitude  = latitude
        changed = True
    if longitude and not venue.longitude:
        venue.longitude = longitude
        changed = True
    if osm_id and not venue.osm_id:
        venue.osm_id    = osm_id
        changed = True
    if changed:
        venue.save(update_fields=['address', 'latitude', 'longitude', 'osm_id'])


# ---------------------------------------------------------------------------
# Banner processing
# ---------------------------------------------------------------------------

def validate_banner(file) -> None:
    """
    Raises ValidationError for invalid banner uploads.
    Called in the form clean method before the file is saved.
    """
    if file.size > BANNER_MAX_BYTES:
        raise ValidationError(
            _('Banner must be under 10 MB. Your file is %(mb)s MB.') % {
                'mb': round(file.size / 1024 / 1024, 1)
            }
        )
    content_type = getattr(file, 'content_type', '')
    if content_type not in BANNER_ALLOWED_TYPES:
        raise ValidationError(
            _('Banner must be a JPG, PNG, or WebP image.')
        )


def generate_display_banner(original_file, event_slug: str) -> ContentFile:
    """
    Opens the uploaded banner, crops/resizes to BANNER_DISPLAY_SIZE,
    returns a ContentFile of the WebP-encoded result.
    Called in the service layer after Event is saved.
    """
    original_file.seek(0)
    img = Image.open(original_file)

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    elif img.mode == 'RGBA':
        # Flatten transparency for WebP with no alpha
        background = Image.new('RGB', img.size, (13, 13, 13))
        background.paste(img, mask=img.split()[3])
        img = background

    target_w, target_h = BANNER_DISPLAY_SIZE
    src_ratio   = img.width / img.height
    target_ratio = target_w / target_h

    if src_ratio > target_ratio:
        # Source wider than target — crop sides
        new_h = img.height
        new_w = int(new_h * target_ratio)
        left  = (img.width - new_w) // 2
        img   = img.crop((left, 0, left + new_w, new_h))
    else:
        # Source taller than target — crop top/bottom
        new_w = img.width
        new_h = int(new_w / target_ratio)
        top   = (img.height - new_h) // 2
        img   = img.crop((0, top, new_w, top + new_h))

    img = img.resize(BANNER_DISPLAY_SIZE, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format='WEBP', quality=BANNER_DISPLAY_QUALITY, method=6)
    buffer.seek(0)

    filename = f'{event_slug}-display.webp'
    return ContentFile(buffer.read(), name=filename)


# ---------------------------------------------------------------------------
# HTML sanitisation (Quill output)
# ---------------------------------------------------------------------------

def sanitize_description(html: str) -> str:
    """Strip disallowed tags/attributes from Quill HTML output."""
    return bleach.clean(
        html,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRS,
        strip=True,
    )


# ---------------------------------------------------------------------------
# Draft management
# ---------------------------------------------------------------------------

def get_or_create_draft(organizer_profile, event: Event = None) -> EventDraft:
    """
    Return the organizer's active draft.
    - New event: creates a blank draft (or returns existing one).
    - Editing existing event: creates/returns draft linked to that event,
      pre-populating step_data from the event's current values if draft is new.
    """
    if event is not None:
        draft, created = EventDraft.objects.get_or_create(
            organizer=organizer_profile,
            defaults={'event': event, 'step_data': {}, 'step_reached': 1},
        )
        if created or not draft.step_data:
            _prepopulate_draft_from_event(draft, event)
        return draft

    draft, _ = EventDraft.objects.get_or_create(
        organizer=organizer_profile,
        defaults={'step_data': {}, 'step_reached': 1},
    )
    return draft


def _prepopulate_draft_from_event(draft: EventDraft, event: Event) -> None:
    """Seed draft step_data from an existing Event for the edit flow."""
    collaborator_ids = list(
        event.collaborators
        .select_related('organizer')
        .values_list('organizer__pk', flat=True)
    )
    ticket_data = []
    for tt in event.ticket_types.order_by('sort_order', 'price'):
        ticket_data.append({
            'id':             tt.pk,
            'name':           tt.name,
            'description':    tt.description,
            'price':          str(tt.price),
            'quantity':       tt.quantity,
            'max_per_order':  tt.max_per_order,
            'sale_starts_at': tt.sale_starts_at.isoformat() if tt.sale_starts_at else '',
            'sale_ends_at':   tt.sale_ends_at.isoformat()   if tt.sale_ends_at   else '',
            'is_sold_out':    tt.is_sold_out,
            'is_active':      tt.is_active,
            'sort_order':     tt.sort_order,
        })
    tag_ids        = list(event.tags.values_list('pk', flat=True))
    predefined_pks = set(
        Tag.objects.filter(is_predefined=True).values_list('pk', flat=True)
    )
    custom_tags     = event.tags.filter(is_predefined=False)
    custom_pk_names = {str(t.pk): t.name for t in custom_tags}
    custom_names    = [t.name for t in custom_tags]

    draft.step_data = {
        '1': {
            'title':          event.title,
            'category_id':    event.category_id,
            'tag_ids':        tag_ids,
            'custom_names':   custom_names,
            'custom_pk_names': custom_pk_names,
            'description':    event.description,
        },
        '2': {
            'timezone':   event.timezone,
            'starts_at':  event.starts_at.isoformat(),
            'ends_at':    event.ends_at.isoformat(),
            'venue_id':   event.venue_id,
            'venue_name': event.venue.name,
            'venue_city': event.venue.city,
        },
        '3': {},   # banner not re-stored in draft; kept from event.banner
        '4': {'collaborator_ids': collaborator_ids},
        '5': {'ticket_types': ticket_data},
    }
    draft.step_reached = 6
    draft.event        = event
    draft.save(update_fields=['step_data', 'step_reached', 'event', 'updated_at'])


def save_draft_step(organizer_profile, step: int, data: dict) -> EventDraft:
    """Persist a single step's cleaned form data into the draft."""
    draft = get_or_create_draft(organizer_profile)
    draft.save_step(step, data)
    return draft


def discard_draft(organizer_profile) -> None:
    """Delete the organizer's active draft unconditionally."""
    EventDraft.objects.filter(organizer=organizer_profile).delete()


# ---------------------------------------------------------------------------
# Tag helpers
# ---------------------------------------------------------------------------

def get_or_create_tag(name: str) -> Tag:
    """
    Return existing tag by name (case-insensitive) or create a new custom one.
    Custom tags created by organizers have is_predefined=False.
    """
    name = name.strip()
    if not name:
        raise ValidationError(_('Tag name cannot be empty.'))
    tag = Tag.objects.filter(name__iexact=name).first()
    if tag:
        return tag
    from django.utils.text import slugify
    slug = slugify(name)[:80]
    # Ensure slug uniqueness
    base, counter = slug, 1
    while Tag.objects.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return Tag.objects.create(name=name, slug=slug, is_predefined=False)


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------

@transaction.atomic
def publish_event_from_draft(organizer_profile, banner_file=None) -> Event:
    """
    Validate the complete draft and atomically create or update the Event
    + TicketType rows, then delete the draft.

    Raises ValidationError with a dict of step → error messages if any
    step data is incomplete.
    """
    from apps.tickets.models import TicketType

    draft = EventDraft.objects.filter(organizer=organizer_profile).first()
    if not draft:
        raise ValidationError(_('No active draft found.'))

    errors = _validate_full_draft(draft)
    if errors:
        raise ValidationError(errors)

    step1 = draft.get_step(1)
    step2 = draft.get_step(2)
    step4 = draft.get_step(4)
    step5 = draft.get_step(5)

    # ---- Resolve venue ----
    venue_id = step2.get('venue_id')
    if venue_id:
        venue = Venue.objects.get(pk=venue_id)
    else:
        venue = get_or_create_venue(
            name    = step2['venue_name'],
            city    = step2['venue_city'],
            address = step2.get('venue_address', ''),
            lat     = step2.get('venue_lat'),
            lng     = step2.get('venue_lng'),
            osm_id  = step2.get('venue_osm_id', ''),
        )

    # ---- Build event field values ----
    title       = step1['title'].strip()
    description = sanitize_description(step1.get('description', ''))
    category    = Category.objects.get(pk=step1['category_id'])

    editing = draft.event is not None

    if editing:
        event = draft.event
        # Regenerate slug only if title changed — preserves existing URLs otherwise
        if event.title != title:
            event.slug = generate_unique_slug(Event, title, instance=event)
        event.title       = title
        event.category    = category
        event.venue       = venue
        event.description = description
        event.timezone    = step2['timezone']
        event.starts_at   = step2['starts_at']
        event.ends_at     = step2['ends_at']
        event.status      = Event.Status.PUBLISHED
        event.save()
    else:
        slug = generate_unique_slug(Event, title)
        event = Event.objects.create(
            title       = title,
            slug        = slug,
            organizer   = organizer_profile,
            category    = category,
            venue       = venue,
            description = description,
            timezone    = step2['timezone'],
            starts_at   = step2['starts_at'],
            ends_at     = step2['ends_at'],
            status      = Event.Status.PUBLISHED,
        )

    # ---- Tags ----
    tag_ids  = step1.get('tag_ids', [])
    tag_objs = list(Tag.objects.filter(pk__in=tag_ids))
    event.tags.set(tag_objs)

    # ---- Banner ----
    if banner_file:
        validate_banner(banner_file)
        event.banner.save(
            f'{event.slug}-original{_ext(banner_file.name)}',
            banner_file,
            save=False,
        )
        display = generate_display_banner(banner_file, event.slug)
        event.banner_display.save(display.name, display, save=False)
        event.save(update_fields=['banner', 'banner_display'])

    # ---- Collaborators ----
    from apps.accounts.models import OrganizerProfile
    collab_ids = step4.get('collaborator_ids', [])
    # Remove collaborators no longer in the list
    event.collaborators.exclude(organizer__pk__in=collab_ids).delete()
    for collab_pk in collab_ids:
        try:
            collab_profile = OrganizerProfile.objects.get(pk=collab_pk)
            EventCollaborator.objects.get_or_create(
                event     = event,
                organizer = collab_profile,
                defaults  = {'added_by': organizer_profile},
            )
        except OrganizerProfile.DoesNotExist:
            logger.warning('Collaborator OrganizerProfile pk=%s not found; skipped.', collab_pk)

    # ---- Ticket types ----
    incoming_ticket_data = step5.get('ticket_types', [])
    incoming_ids = {t['id'] for t in incoming_ticket_data if t.get('id')}
    # Delete removed ticket types (only safe if no sales yet)
    for tt in event.ticket_types.all():
        if tt.pk not in incoming_ids:
            if tt.quantity_sold > 0:
                # Cannot delete a sold ticket type — deactivate instead
                tt.is_active = False
                tt.save(update_fields=['is_active'])
            else:
                tt.delete()

    for idx, td in enumerate(incoming_ticket_data):
        defaults = {
            'name':           td['name'].strip(),
            'description':    td.get('description', '').strip(),
            'price':          Decimal(str(td['price'])),
            'quantity':       int(td['quantity']),
            'max_per_order':  int(td.get('max_per_order', 10)),
            'sale_starts_at': td.get('sale_starts_at') or None,
            'sale_ends_at':   td.get('sale_ends_at')   or None,
            'is_sold_out':    bool(td.get('is_sold_out', False)),
            'is_active':      bool(td.get('is_active', True)),
            'sort_order':     idx,
        }
        if td.get('id'):
            TicketType.objects.filter(pk=td['id'], event=event).update(**defaults)
        else:
            TicketType.objects.create(event=event, **defaults)

    # ---- Cleanup draft ----
    draft.delete()

    return event


@transaction.atomic
def save_event_as_draft(organizer_profile, banner_file=None) -> Event:
    """
    Same as publish_event_from_draft but sets status=DRAFT.
    Only step 1 data (title + category) is required.
    """
    from apps.tickets.models import TicketType

    draft = EventDraft.objects.filter(organizer=organizer_profile).first()
    if not draft:
        raise ValidationError(_('No active draft found.'))

    step1 = draft.get_step(1)
    if not step1.get('title') or not step1.get('category_id'):
        raise ValidationError({
            'step_1': _('Title and category are required to save as draft.')
        })

    title    = step1['title'].strip()
    category = Category.objects.get(pk=step1['category_id'])

    editing = draft.event is not None

    if editing:
        event = draft.event
        event.title    = title
        event.category = category
        if step1.get('description'):
            event.description = sanitize_description(step1['description'])
        event.status = Event.Status.DRAFT
        event.save()
    else:
        slug  = generate_unique_slug(Event, title)
        step2 = draft.get_step(2)

        # Venue is optional for a draft
        venue = None
        if step2.get('venue_id'):
            venue = Venue.objects.filter(pk=step2['venue_id']).first()
        elif step2.get('venue_name') and step2.get('venue_city'):
            venue = get_or_create_venue(
                name  = step2['venue_name'],
                city  = step2['venue_city'],
            )

        event = Event.objects.create(
            title       = title,
            slug        = slug,
            organizer   = organizer_profile,
            category    = category,
            venue       = venue,
            description = sanitize_description(step1.get('description', '')),
            timezone    = step2.get('timezone', 'Africa/Dar_es_Salaam'),
            starts_at   = step2.get('starts_at') or timezone.now(),
            ends_at     = step2.get('ends_at')   or timezone.now(),
            status      = Event.Status.DRAFT,
        )

    # Tags
    tag_ids = step1.get('tag_ids', [])
    if tag_ids:
        event.tags.set(Tag.objects.filter(pk__in=tag_ids))

    # Banner
    if banner_file:
        try:
            validate_banner(banner_file)
            event.banner.save(
                f'{event.slug}-original{_ext(banner_file.name)}',
                banner_file,
                save=False,
            )
            display = generate_display_banner(banner_file, event.slug)
            event.banner_display.save(display.name, display, save=False)
            event.save(update_fields=['banner', 'banner_display'])
        except ValidationError:
            pass  # Banner errors don't block saving a draft

    # Link draft to the newly created event
    draft.event = event
    draft.save(update_fields=['event', 'updated_at'])

    return event


def retract_to_draft(event: Event, organizer_profile) -> Event:
    """Retract a PUBLISHED event back to DRAFT for editing."""
    _assert_primary_organizer(event, organizer_profile)
    if event.status not in (Event.Status.PUBLISHED, Event.Status.CANCELLED):
        raise ValidationError(_('Only published or cancelled events can be retracted.'))
    if event.status == Event.Status.CANCELLED and event.is_past:
        raise ValidationError(_('Cannot edit a past cancelled event.'))
    event.status = Event.Status.DRAFT
    event.save(update_fields=['status', 'updated_at'])
    return event


def cancel_event(event: Event, organizer_profile) -> Event:
    """Soft-cancel an event. Sets status=CANCELLED."""
    _assert_primary_organizer(event, organizer_profile)
    if event.status == Event.Status.CANCELLED:
        raise ValidationError(_('Event is already cancelled.'))
    if event.is_past:
        raise ValidationError(_('Cannot cancel a past event.'))
    event.status = Event.Status.CANCELLED
    event.save(update_fields=['status', 'updated_at'])
    return event


def republish_event(event: Event, organizer_profile) -> Event:
    """Re-publish a cancelled event if end datetime has not passed."""
    _assert_primary_organizer(event, organizer_profile)
    if not event.can_be_republished:
        raise ValidationError(
            _('This event cannot be republished. It may have already ended.')
        )
    event.status = Event.Status.PUBLISHED
    event.save(update_fields=['status', 'updated_at'])
    return event


def search_collaborators(query: str, exclude_organizer_pk: int, limit: int = 8) -> list[dict]:
    """
    Search approved organizer profiles by organization name or user email.
    Excludes the primary organizer from results.
    """
    from apps.accounts.models import OrganizerProfile
    if not query or len(query.strip()) < 2:
        return []
    profiles = (
        OrganizerProfile.objects
        .filter(
            user__is_organizer=True,
        )
        .exclude(pk=exclude_organizer_pk)
        .select_related('user')
        .filter(
            organization_name__icontains=query,
        )[:limit]
    )
    return [
        {
            'id':                p.pk,
            'organization_name': p.organization_name,
            'email':             p.user.email,
        }
        for p in profiles
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_primary_organizer(event: Event, organizer_profile) -> None:
    if event.organizer_id != organizer_profile.pk:
        raise PermissionDenied(
            _('Only the primary organizer can perform this action.')
        )


def _validate_full_draft(draft: EventDraft) -> dict:
    errors = {}

    step1 = draft.get_step(1)
    if not step1.get('title'):
        errors['step_1'] = _('Event title is required.')
    if not step1.get('category_id'):
        errors['step_1'] = errors.get('step_1', '') or _('Category is required.')

    step2 = draft.get_step(2)
    if not step2.get('timezone'):
        errors['step_2'] = _('Timezone is required.')
    if not step2.get('starts_at'):
        errors['step_2'] = errors.get('step_2', '') or _('Start date/time is required.')
    if not step2.get('ends_at'):
        errors['step_2'] = errors.get('step_2', '') or _('End date/time is required.')
    if not (step2.get('venue_id') or (step2.get('venue_name') and step2.get('venue_city'))):
        errors['step_2'] = errors.get('step_2', '') or _('Venue is required.')

    step5 = draft.get_step(5)
    ticket_types = step5.get('ticket_types', [])
    if not ticket_types:
        errors['step_5'] = _('At least one ticket type is required.')
    else:
        for i, tt in enumerate(ticket_types):
            if not tt.get('name'):
                errors['step_5'] = _(f'Ticket type #{i + 1}: name is required.')
                break
            try:
                price = Decimal(str(tt.get('price', -1)))
                if price < 0:
                    raise ValueError
            except (ValueError, Exception):
                errors['step_5'] = _(f'Ticket type #{i + 1}: invalid price.')
                break
            if not tt.get('quantity') or int(tt['quantity']) < 1:
                errors['step_5'] = _(f'Ticket type #{i + 1}: quantity must be at least 1.')
                break

    return errors


def _ext(filename: str) -> str:
    """Return the lowercased file extension including the dot."""
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower() or '.jpg'