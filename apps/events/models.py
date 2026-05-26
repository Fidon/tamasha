import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    name        = models.CharField(_('name'), max_length=100, unique=True)
    slug        = models.SlugField(_('slug'), max_length=120, unique=True)
    icon        = models.CharField(
        _('Bootstrap Icon name'), max_length=80,
        help_text=_('e.g. bi-music-note-beamed'),
        default='bi-calendar-event',
    )
    sort_order  = models.PositiveSmallIntegerField(_('sort order'), default=0)

    class Meta:
        verbose_name        = _('category')
        verbose_name_plural = _('categories')
        ordering            = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Tag(models.Model):
    name        = models.CharField(_('name'), max_length=60, unique=True)
    slug        = models.SlugField(_('slug'), max_length=80, unique=True)
    is_predefined = models.BooleanField(
        _('predefined'),
        default=False,
        help_text=_('Predefined tags are shown as quick-select chips on the event form.'),
    )

    class Meta:
        verbose_name        = _('tag')
        verbose_name_plural = _('tags')
        ordering            = ['-is_predefined', 'name']

    def __str__(self):
        return self.name


class Venue(models.Model):
    name        = models.CharField(_('name'), max_length=255)
    address     = models.CharField(_('address'), max_length=512, blank=True)
    city        = models.CharField(_('city'), max_length=100)
    country     = models.CharField(_('country'), max_length=100, default='Tanzania')
    latitude    = models.DecimalField(
        _('latitude'), max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude   = models.DecimalField(
        _('longitude'), max_digits=9, decimal_places=6, null=True, blank=True,
    )
    # Nominatim OSM ID — used for deduplication on save
    osm_id      = models.CharField(
        _('OSM ID'), max_length=64, blank=True, db_index=True,
    )
    capacity    = models.PositiveIntegerField(_('capacity'), null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('venue')
        verbose_name_plural = _('venues')
        ordering            = ['city', 'name']
        # Prevent exact duplicates; OSM venues deduped via osm_id in service layer
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'city'],
                name='unique_venue_name_city',
            )
        ]

    def __str__(self):
        return f'{self.name}, {self.city}'

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None


class Event(models.Model):

    class Status(models.TextChoices):
        DRAFT       = 'DRAFT',      _('Draft')
        PUBLISHED   = 'PUBLISHED',  _('Published')
        CANCELLED   = 'CANCELLED',  _('Cancelled')
        COMPLETED   = 'COMPLETED',  _('Completed')

    # ------------------------------------------------------------------ identity
    title       = models.CharField(_('title'), max_length=255)
    slug        = models.SlugField(_('slug'), max_length=280, unique=True, db_index=True)

    # ------------------------------------------------------------------ relations
    organizer   = models.ForeignKey(
        'accounts.OrganizerProfile',
        on_delete=models.PROTECT,
        related_name='events',
        verbose_name=_('organizer'),
    )
    category    = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='events',
        verbose_name=_('category'),
    )
    venue       = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name='events',
        verbose_name=_('venue'),
    )
    tags        = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='events',
        verbose_name=_('tags'),
    )

    # ------------------------------------------------------------------ content
    description = models.TextField(_('description'), blank=True)   # Quill HTML output
    banner      = models.ImageField(
        _('banner'),
        upload_to='events/banners/originals/',
        null=True,
        blank=True,
    )
    banner_display = models.ImageField(
        _('display banner'),
        upload_to='events/banners/display/',
        null=True,
        blank=True,
        help_text=_('Auto-generated optimized version (1400×520 WebP).'),
        editable=False,
    )

    # ------------------------------------------------------------------ schedule
    timezone    = models.CharField(
        _('timezone'),
        max_length=50,
        default='Africa/Nairobi',
        help_text=_('Event local timezone.'),
    )
    starts_at   = models.DateTimeField(_('starts at'))
    ends_at     = models.DateTimeField(_('ends at'))

    # ------------------------------------------------------------------ status & flags
    status      = models.CharField(
        _('status'),
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_featured         = models.BooleanField(_('featured'), default=False, db_index=True)
    max_capacity        = models.PositiveIntegerField(
        _('max capacity'),
        null=True,
        blank=True,
        help_text=_('Leave blank for unlimited.'),
    )

    # ------------------------------------------------------------------ SEO overrides
    seo_title       = models.CharField(_('SEO title'), max_length=70, blank=True)
    seo_description = models.CharField(_('SEO description'), max_length=160, blank=True)

    # ------------------------------------------------------------------ timestamps
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('event')
        verbose_name_plural = _('events')
        ordering            = ['-starts_at']
        indexes             = [
            models.Index(fields=['status', '-starts_at']),
            models.Index(fields=['organizer', 'status']),
            models.Index(fields=['is_featured', 'status', '-starts_at']),
        ]

    def __str__(self):
        return self.title

    # ------------------------------------------------------------------ properties
    @property
    def is_published(self):
        return self.status == self.Status.PUBLISHED

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_past(self):
        return self.ends_at < timezone.now()

    @property
    def is_ongoing(self):
        return self.starts_at <= timezone.now() <= self.ends_at

    @property
    def can_be_republished(self):
        """Cancelled events may be republished if end datetime has not passed."""
        return self.is_cancelled and not self.is_past

    @property
    def effective_seo_title(self):
        return self.seo_title or self.title

    @property
    def effective_seo_description(self):
        if self.seo_description:
            return self.seo_description
        import re
        plain = re.sub(r'<[^>]+>', '', self.description)
        return plain[:157].strip() + '...' if len(plain) > 157 else plain

    # ------------------------------------------------------------------ capacity helpers
    @property
    def total_tickets_sold(self):
        return sum(
            tt.quantity_sold for tt in self.ticket_types.all()
        )

    @property
    def is_sold_out(self):
        """True if all ticket types are sold out or manually flagged."""
        types = list(self.ticket_types.filter(is_active=True))
        if not types:
            return False
        return all(tt.is_effectively_sold_out for tt in types)


class EventCollaborator(models.Model):
    event       = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='collaborators',
        verbose_name=_('event'),
    )
    organizer   = models.ForeignKey(
        'accounts.OrganizerProfile',
        on_delete=models.CASCADE,
        related_name='collaborations',
        verbose_name=_('collaborator'),
    )
    added_by    = models.ForeignKey(
        'accounts.OrganizerProfile',
        on_delete=models.PROTECT,
        related_name='added_collaborators',
        verbose_name=_('added by'),
    )
    added_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('event collaborator')
        verbose_name_plural = _('event collaborators')
        unique_together     = [('event', 'organizer')]

    def __str__(self):
        return f'{self.organizer} @ {self.event}'


class EventDraft(models.Model):
    """
    Temporary storage for the multi-step event creation wizard.
    One draft per organizer at a time — replaced on each save, deleted on publish.
    Stores the linked Event PK once the Event row is created (edit mode).
    """
    organizer   = models.OneToOneField(
        'accounts.OrganizerProfile',
        on_delete=models.CASCADE,
        related_name='event_draft',
        verbose_name=_('organizer'),
    )
    # The real Event row (exists only when editing a published/draft event)
    event       = models.OneToOneField(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='draft',
        verbose_name=_('event being edited'),
    )
    step_reached    = models.PositiveSmallIntegerField(_('step reached'), default=1)
    # Each step's data serialised as JSON
    step_data       = models.JSONField(_('step data'), default=dict)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('event draft')
        verbose_name_plural = _('event drafts')

    def __str__(self):
        return f'Draft by {self.organizer} (step {self.step_reached})'

    def get_step(self, step: int) -> dict:
        return self.step_data.get(str(step), {})

    def save_step(self, step: int, data: dict) -> None:
        self.step_data[str(step)] = data
        if step > self.step_reached:
            self.step_reached = step
        self.save(update_fields=['step_data', 'step_reached', 'updated_at'])