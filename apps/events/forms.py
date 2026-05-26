"""
One form class per wizard step. Each form is submitted independently via AJAX.
The view layer calls services.save_draft_step() after each valid form submission.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Category, Tag
from .services import (
    EAST_AFRICA_TIMEZONES,
    validate_banner,
    BANNER_ALLOWED_TYPES,
)


# ---------------------------------------------------------------------------
# Step 1 — Basic Info
# ---------------------------------------------------------------------------

class EventStep1Form(forms.Form):
    title = forms.CharField(
        max_length=255,
        label=_('Event Title'),
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'placeholder':  'e.g. Dar Live Music Festival 2026',
            'autocomplete': 'off',
        }),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all().order_by('sort_order', 'name'),
        label=_('Category'),
        empty_label=_('Select a category'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    # Comma-separated predefined tag PKs sent by the JS chip UI
    predefined_tags = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )
    # Comma-separated custom tag names entered by the organizer
    custom_tags = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_('Comma-separated custom tag names.'),
    )
    # Quill outputs HTML into this hidden field
    description = forms.CharField(
        required=False,
        label=_('Description'),
        widget=forms.HiddenInput(),
    )

    def clean_title(self):
        return self.cleaned_data['title'].strip()

    def clean_predefined_tags(self):
        raw = self.cleaned_data.get('predefined_tags', '').strip()
        if not raw:
            return []
        try:
            return [int(x.strip()) for x in raw.split(',') if x.strip()]
        except ValueError:
            raise forms.ValidationError(_('Invalid tag data.'))

    def clean_custom_tags(self):
        raw = self.cleaned_data.get('custom_tags', '')
        if not raw.strip():
            return []
        names = [n.strip() for n in raw.split(',') if n.strip()]
        if len(names) > 10:
            raise forms.ValidationError(_('Maximum 10 custom tags allowed.'))
        for name in names:
            if len(name) > 60:
                raise forms.ValidationError(
                    _('Tag "%(name)s" is too long (max 60 characters).') % {'name': name}
                )
        return names

    def clean_description(self):
        from .services import sanitize_description
        html = self.cleaned_data.get('description', '')
        return sanitize_description(html)


# ---------------------------------------------------------------------------
# Step 2 — Date, Time & Venue
# ---------------------------------------------------------------------------

class EventStep2Form(forms.Form):
    timezone = forms.ChoiceField(
        choices=EAST_AFRICA_TIMEZONES,
        initial='Africa/Dar_es_Salaam',
        label=_('Timezone'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    starts_at = forms.DateTimeField(
        label=_('Start Date & Time'),
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-control', 'type': 'datetime-local'},
        ),
    )
    ends_at = forms.DateTimeField(
        label=_('End Date & Time'),
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-control', 'type': 'datetime-local'},
        ),
    )

    # Venue fields — populated by the JS autocomplete widget
    venue_id      = forms.IntegerField(required=False, widget=forms.HiddenInput())
    venue_name    = forms.CharField(
        max_length=255,
        label=_('Venue'),
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'id':           'venue-search',
            'placeholder':  'Search for a venue…',
            'autocomplete': 'off',
        }),
    )
    venue_city    = forms.CharField(max_length=100,  widget=forms.HiddenInput())
    venue_address = forms.CharField(max_length=512,  required=False, widget=forms.HiddenInput())
    venue_lat     = forms.CharField(max_length=20,   required=False, widget=forms.HiddenInput())
    venue_lng     = forms.CharField(max_length=20,   required=False, widget=forms.HiddenInput())
    venue_osm_id  = forms.CharField(max_length=64,   required=False, widget=forms.HiddenInput())

    def clean(self):
        cleaned = super().clean()
        starts  = cleaned.get('starts_at')
        ends    = cleaned.get('ends_at')
        if starts and ends:
            if ends <= starts:
                raise forms.ValidationError(
                    {'ends_at': _('End date/time must be after start date/time.')}
                )
            from django.utils import timezone as tz
            if starts < tz.now():
                raise forms.ValidationError(
                    {'starts_at': _('Start date/time cannot be in the past.')}
                )
        return cleaned

    def clean_venue_name(self):
        return self.cleaned_data['venue_name'].strip()

    def clean_venue_city(self):
        city = self.cleaned_data.get('venue_city', '').strip()
        if not city:
            raise forms.ValidationError(_('City is required. Select a venue from the suggestions.'))
        return city


# ---------------------------------------------------------------------------
# Step 3 — Banner Upload
# ---------------------------------------------------------------------------

class EventStep3Form(forms.Form):
    banner = forms.ImageField(
        required=False,
        label=_('Event Banner'),
        widget=forms.FileInput(attrs={
            'class':  'form-control',
            'accept': 'image/jpeg,image/png,image/webp',
            'id':     'banner-upload',
        }),
        help_text=_('JPG, PNG or WebP · Max 10 MB · Recommended 1400 × 520 px'),
    )

    def clean_banner(self):
        file = self.cleaned_data.get('banner')
        if file:
            validate_banner(file)
        return file


# ---------------------------------------------------------------------------
# Step 4 — Collaborators
# ---------------------------------------------------------------------------

class EventStep4Form(forms.Form):
    """
    Collaborator IDs are managed entirely via JS (search + chip UI).
    This form only carries the final serialised list for server validation.
    """
    collaborator_ids = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text=_('Comma-separated OrganizerProfile PKs.'),
    )

    def clean_collaborator_ids(self):
        raw = self.cleaned_data.get('collaborator_ids', '').strip()
        if not raw:
            return []
        try:
            ids = [int(x.strip()) for x in raw.split(',') if x.strip()]
        except ValueError:
            raise forms.ValidationError(_('Invalid collaborator data.'))
        return ids


# ---------------------------------------------------------------------------
# Step 5 — Ticket Types
# ---------------------------------------------------------------------------

class TicketTypeInlineForm(forms.Form):
    """
    Single ticket tier row. Rendered N times dynamically in the wizard JS.
    Validation also happens client-side; server re-validates in services.py.
    """
    ticket_id     = forms.IntegerField(required=False, widget=forms.HiddenInput())
    name          = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class':       'form-control form-control-sm',
            'placeholder': 'e.g. VIP, General Admission',
        }),
    )
    description   = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class':       'form-control form-control-sm',
            'placeholder': 'Short perks summary (optional)',
        }),
    )
    price         = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'step':  '0.01',
            'min':   '0',
        }),
    )
    quantity      = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'min':   '1',
        }),
    )
    max_per_order = forms.IntegerField(
        min_value=1,
        initial=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'min':   '1',
        }),
    )
    sale_starts_at = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'},
        ),
    )
    sale_ends_at   = forms.DateTimeField(
        required=False,
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(
            format='%Y-%m-%dT%H:%M',
            attrs={'class': 'form-control form-control-sm', 'type': 'datetime-local'},
        ),
    )
    is_sold_out   = forms.BooleanField(required=False)
    is_active     = forms.BooleanField(required=False, initial=True)

    def clean(self):
        cleaned = super().clean()
        sale_start = cleaned.get('sale_starts_at')
        sale_end   = cleaned.get('sale_ends_at')
        if sale_start and sale_end and sale_end <= sale_start:
            raise forms.ValidationError(
                {'sale_ends_at': _('Sale end must be after sale start.')}
            )
        return cleaned