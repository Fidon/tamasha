"""
apps/events/views.py
"""
import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView
from django.views.decorators.http import require_POST

from apps.accounts.mixins import OrganizerRequiredMixin
from apps.seo.mixins import NoIndexMixin, SEOMixin
from apps.seo.structured_data import breadcrumb_schema, event_schema, render_json_ld

from .models import Category, Event, Tag, Venue, EventDraft
from .forms import (
    EventStep1Form, EventStep2Form, EventStep3Form,
    EventStep4Form, TicketTypeInlineForm,
)
from .services import (
    cancel_event,
    discard_draft,
    get_or_create_draft,
    get_or_create_tag,
    get_or_create_venue,
    publish_event_from_draft,
    republish_event,
    retract_to_draft,
    save_draft_step,
    save_event_as_draft,
    search_collaborators,
    search_local_venues,
)

logger = logging.getLogger(__name__)

EVENTS_PER_PAGE = 12


# ---------------------------------------------------------------------------
# Public: Event List (infinite scroll)
# ---------------------------------------------------------------------------

class EventListView(SEOMixin, ListView):
    model               = Event
    template_name       = 'events/list.html'
    context_object_name = 'events'
    paginate_by         = EVENTS_PER_PAGE

    seo_title       = 'Events — Tamasha Events'
    seo_description = (
        'Browse upcoming concerts, festivals, nightlife and curated events in Tanzania.'
    )

    def get_queryset(self):
        from apps.tickets.models import TicketType
        from django.db.models import Prefetch

        qs = (
            Event.objects
            .filter(status=Event.Status.PUBLISHED)
            .select_related('venue', 'organizer', 'category')
            .prefetch_related(
                Prefetch(
                    'ticket_types',
                    queryset=TicketType.objects.filter(
                        is_active=True
                    ).order_by('price'),
                ),
                'tags',
            )
            .order_by('-is_featured', '-starts_at')
        )

        q         = self.request.GET.get('q', '').strip()
        category  = self.request.GET.get('category', '').strip()
        city      = self.request.GET.get('city', '').strip()
        date_from = self.request.GET.get('date_from', '').strip()
        date_to   = self.request.GET.get('date_to', '').strip()
        price_min = self.request.GET.get('price_min', '').strip()
        price_max = self.request.GET.get('price_max', '').strip()
        free_only = self.request.GET.get('free', '').strip() == '1'
        this_weekend = self.request.GET.get('weekend', '').strip() == '1'
        after_id  = self.request.GET.get('after', '').strip()  # cursor for infinite scroll

        if q:
            from django.contrib.postgres.search import SearchVector, SearchQuery
            from django.db.models import Q

            # Full-text search on title/description/venue
            search_query = SearchQuery(q)
            fts_qs = qs.annotate(
                search=SearchVector('title', 'description', 'venue__name', 'venue__city')
            ).filter(search=search_query)

            # Tag search via icontains (avoids JOIN duplication from SearchVector)
            tag_qs = qs.filter(tags__name__icontains=q)

            # Union both querysets and deduplicate by pk
            matched_pks = set(
                list(fts_qs.values_list('pk', flat=True)) +
                list(tag_qs.values_list('pk', flat=True))
            )
            qs = qs.filter(pk__in=matched_pks)

        if category:
            qs = qs.filter(category__slug=category)

        if city:
            qs = qs.filter(venue__city__icontains=city)

        if date_from:
            qs = qs.filter(starts_at__date__gte=date_from)

        if date_to:
            qs = qs.filter(starts_at__date__lte=date_to)

        if free_only:
            qs = qs.filter(ticket_types__price=0).distinct()

        if this_weekend:
            now  = timezone.now()
            # Next Saturday and Sunday
            days_until_sat = (5 - now.weekday()) % 7
            saturday = now + timedelta(days=days_until_sat)
            sunday   = saturday + timedelta(days=1)
            qs = qs.filter(
                starts_at__date__gte=saturday.date(),
                starts_at__date__lte=sunday.date(),
            )

        if price_min:
            try:
                qs = qs.filter(ticket_types__price__gte=float(price_min)).distinct()
            except ValueError:
                pass

        if price_max:
            try:
                qs = qs.filter(ticket_types__price__lte=float(price_max)).distinct()
            except ValueError:
                pass

        # Cursor-based infinite scroll: load events with pk < after_id
        if after_id:
            try:
                qs = qs.filter(pk__lt=int(after_id))
            except ValueError:
                pass

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories']          = Category.objects.all().order_by('sort_order', 'name')
        ctx['active_filters']      = self._get_active_filters()
        ctx['active_filters_json'] = json.dumps(ctx['active_filters'])

        # Pre-compute values needed by the inline JS block —
        # cannot call .last() or len() on a sliced queryset in the template.
        event_list = ctx['object_list']
        event_list_evaluated = list(event_list)
        ctx['initial_last_id'] = event_list_evaluated[-1].pk if event_list_evaluated else None
        ctx['has_more']        = len(event_list_evaluated) == EVENTS_PER_PAGE

        ctx['structured_data'] = [
            render_json_ld(breadcrumb_schema([('Home', '/'), ('Events', '/events/')], self.request))
        ]
        return ctx

    def _get_active_filters(self):
        keys = ['q', 'category', 'city', 'date_from', 'date_to',
                'price_min', 'price_max', 'free', 'weekend']
        return {k: self.request.GET.get(k, '') for k in keys}

    def render_to_response(self, context, **response_kwargs):
        """Return JSON for infinite scroll AJAX requests."""
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.template.loader import render_to_string

            event_list = list(context['object_list'])
            has_more   = len(event_list) == EVENTS_PER_PAGE
            last_id    = event_list[-1].pk if event_list else None

            html = ''.join(
                render_to_string(
                    'events/components/_event_card.html',
                    {'event': ev},
                    request=self.request,
                )
                for ev in event_list
            )
            return JsonResponse({
                'html':     html,
                'has_more': has_more,
                'last_id':  last_id,
            })
        return super().render_to_response(context, **response_kwargs)


# ---------------------------------------------------------------------------
# Public: Event Detail
# ---------------------------------------------------------------------------

class EventDetailView(SEOMixin, DetailView):
    model               = Event
    template_name       = 'events/detail.html'
    context_object_name = 'event'
    slug_url_kwarg      = 'slug'

    def get_queryset(self):
        return (
            Event.objects
            .filter(status__in=[Event.Status.PUBLISHED, Event.Status.CANCELLED])
            .select_related('venue', 'organizer', 'category', 'organizer__user')
            .prefetch_related('tags', 'ticket_types', 'collaborators__organizer__user')
        )

    def get_seo_title(self):
        return f'{self.object.effective_seo_title} — Tamasha Events'

    def get_seo_description(self):
        return self.object.effective_seo_description

    def get_seo_og_image(self):
        if self.object.banner_display:
            from django.conf import settings
            return f'{settings.SITE_DOMAIN}{self.object.banner_display.url}'
        return None

    def get_context_data(self, **kwargs):
        from apps.tickets.services import get_available_ticket_types
        ctx = super().get_context_data(**kwargs)
        ctx['ticket_types'] = get_available_ticket_types(self.object)
        ctx['is_primary_organizer'] = (
            self.request.user.is_authenticated
            and hasattr(self.request.user, 'organizer_profile')
            and self.object.organizer_id == self.request.user.organizer_profile.pk
        )
        ctx['structured_data'] = [
            render_json_ld(event_schema(self.object, self.request)),
            render_json_ld(breadcrumb_schema([
                ('Home',   '/'),
                ('Events', '/events/'),
                (self.object.title, self.request.path),
            ], self.request)),
        ]
        return ctx


# ---------------------------------------------------------------------------
# Organizer: Multi-Step Event Wizard
# ---------------------------------------------------------------------------

class EventWizardView(OrganizerRequiredMixin, NoIndexMixin, TemplateView):
    """
    Renders the wizard shell. Step forms are submitted independently via AJAX
    to EventWizardStepView. This view only serves the initial page + draft state.
    """
    template_name = 'events/create.html'

    def get(self, request, *args, **kwargs):
        organizer = request.user.organizer_profile
        event_slug = kwargs.get('slug')

        if event_slug:
            # Edit mode — load existing event into draft
            event = get_object_or_404(
                Event,
                slug=event_slug,
                organizer=organizer,
            )
            if event.status == Event.Status.COMPLETED:
                messages.error(request, _('Completed events cannot be edited.'))
                return redirect('events:detail', slug=event_slug)
            draft = get_or_create_draft(organizer, event=event)
        else:
            draft = get_or_create_draft(organizer)

        return self.render_to_response(self.get_context_data(draft=draft))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        draft = kwargs.get('draft')
        if draft:
            ctx['draft']         = draft
            ctx['draft_data']    = json.dumps(draft.step_data)
            ctx['step_reached']  = draft.step_reached
            ctx['editing_event'] = draft.event
        from .forms import EventStep1Form, EventStep2Form, EventStep3Form, EventStep4Form
        from .models import Category, Tag
        ctx['categories']       = Category.objects.all().order_by('sort_order', 'name')
        ctx['predefined_tags']  = Tag.objects.filter(is_predefined=True).order_by('name')
        ctx['timezones']        = [
            {'value': tz, 'label': label}
            for tz, label in __import__('apps.events.services', fromlist=['EAST_AFRICA_TIMEZONES']).EAST_AFRICA_TIMEZONES
        ]
        return ctx


class EventWizardStepView(OrganizerRequiredMixin, NoIndexMixin, View):
    """
    AJAX endpoint for individual wizard step submissions.
    POST /events/wizard/step/<int:step>/
    Returns JSON: {success, errors, next_step, step_reached}
    """
    STEP_FORMS = {
        1: EventStep1Form,
        2: EventStep2Form,
        3: EventStep3Form,
        4: EventStep4Form,
    }

    def post(self, request, step: int, *args, **kwargs):
        if step not in range(1, 7):
            return JsonResponse({'success': False, 'errors': {'__all__': 'Invalid step.'}}, status=400)

        organizer = request.user.organizer_profile

        # Step 5 is ticket types — handled separately (multiple inline forms)
        if step == 5:
            return self._handle_step5(request, organizer)

        # Step 6 is final publish/save-draft action
        if step == 6:
            return self._handle_step6(request, organizer)

        form_class = self.STEP_FORMS.get(step)
        form = form_class(data=request.POST, files=request.FILES)

        if not form.is_valid():
            # import logging
            # logging.getLogger(__name__).debug('Step %s form errors: %s', step, form.errors.as_json())
            return JsonResponse({'success': False, 'errors': form.errors}, status=422)

        # Build the data dict to persist into the draft
        data = self._extract_step_data(step, form)
        save_draft_step(organizer, step, data)

        return JsonResponse({
            'success':      True,
            'next_step':    step + 1,
            'step_reached': step,
        })

    def _extract_step_data(self, step: int, form) -> dict:
        cd = form.cleaned_data
        if step == 1:
            from .services import get_or_create_tag
            predefined_ids  = cd.get('predefined_tags', [])
            custom_names    = cd.get('custom_tags', [])
            custom_tag_objs = [get_or_create_tag(name) for name in custom_names]
            custom_ids      = [t.pk for t in custom_tag_objs]
            # pk→name map lets the JS restore custom tags in correct order
            custom_pk_names = {str(t.pk): t.name for t in custom_tag_objs}
            return {
                'title':          cd['title'],
                'category_id':    cd['category'].pk,
                'tag_ids':        predefined_ids + custom_ids,
                'custom_names':   custom_names,
                'custom_pk_names': custom_pk_names,
                'description':    cd['description'],
            }
        if step == 2:
            starts = cd['starts_at']
            ends   = cd['ends_at']
            return {
                'timezone':     cd['timezone'],
                'starts_at':    starts.isoformat(),
                'ends_at':      ends.isoformat(),
                'venue_id':     cd.get('venue_id') or None,
                'venue_name':   cd['venue_name'],
                'venue_city':   cd['venue_city'],
                'venue_address':cd.get('venue_address', ''),
                'venue_lat':    cd.get('venue_lat', ''),
                'venue_lng':    cd.get('venue_lng', ''),
                'venue_osm_id': cd.get('venue_osm_id', ''),
            }
        if step == 3:
            # Banner file is not stored in the draft JSON — it is saved to disk
            # only when the event is published/saved as draft via _handle_step6.
            # We just record that a banner was uploaded this session.
            return {'banner_uploaded': bool(cd.get('banner'))}
        if step == 4:
            return {'collaborator_ids': cd.get('collaborator_ids', [])}
        return {}

    def _handle_step5(self, request, organizer):
        """
        Ticket types submitted as a JSON body: [{name, price, quantity, ...}, ...]
        """
        try:
            body = json.loads(request.body)
            ticket_types = body.get('ticket_types', [])
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse(
                {'success': False, 'errors': {'__all__': 'Invalid JSON.'}},
                status=400,
            )

        from apps.tickets.services import validate_ticket_type_data
        from apps.tickets.models import TicketType

        errors = {}
        for i, td in enumerate(ticket_types):
            existing = None
            if td.get('id'):
                existing = TicketType.objects.filter(pk=td['id']).first()
            try:
                validate_ticket_type_data(td, existing_instance=existing)
            except ValidationError as exc:
                errors[f'ticket_{i}'] = exc.message

        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=422)

        save_draft_step(organizer, 5, {'ticket_types': ticket_types})
        return JsonResponse({'success': True, 'next_step': 6, 'step_reached': 5})

    def _handle_step6(self, request, organizer):
        """Publish or save as draft — the final wizard action."""
        action      = request.POST.get('action', 'publish')   # 'publish' | 'draft'
        banner_file = request.FILES.get('banner')

        try:
            if action == 'draft':
                event = save_event_as_draft(organizer, banner_file=banner_file)
                return JsonResponse({
                    'success':     True,
                    'redirect_url': event.get_absolute_url()
                    if hasattr(event, 'get_absolute_url')
                    else f'/events/{event.slug}/',
                    'message': str(_('Event saved as draft.')),
                })
            else:
                event = publish_event_from_draft(organizer, banner_file=banner_file)
                return JsonResponse({
                    'success':     True,
                    'redirect_url': f'/events/{event.slug}/',
                    'message': str(_('Event published successfully!')),
                })
        except ValidationError as exc:
            errors = exc.message_dict if hasattr(exc, 'message_dict') else {'__all__': str(exc)}
            return JsonResponse({'success': False, 'errors': errors}, status=422)
        except Exception:
            logger.exception('Unexpected error in wizard step 6 for organizer pk=%s', organizer.pk)
            return JsonResponse(
                {'success': False, 'errors': {'__all__': str(_('An unexpected error occurred. Please try again.'))}},
                status=500,
            )


# ---------------------------------------------------------------------------
# Organizer: Event Actions
# ---------------------------------------------------------------------------

class EventCancelView(OrganizerRequiredMixin, NoIndexMixin, View):
    def post(self, request, slug, *args, **kwargs):
        event     = get_object_or_404(Event, slug=slug)
        organizer = request.user.organizer_profile
        try:
            cancel_event(event, organizer)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': str(_('Event cancelled.'))})
            messages.success(request, _('Event cancelled.'))
        except (ValidationError, PermissionDenied) as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
        return redirect('events:detail', slug=slug)


class EventRepublishView(OrganizerRequiredMixin, NoIndexMixin, View):
    def post(self, request, slug, *args, **kwargs):
        event     = get_object_or_404(Event, slug=slug)
        organizer = request.user.organizer_profile
        try:
            republish_event(event, organizer)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': str(_('Event republished.'))})
            messages.success(request, _('Event republished.'))
        except (ValidationError, PermissionDenied) as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
        return redirect('events:detail', slug=slug)


class EventRetractView(OrganizerRequiredMixin, NoIndexMixin, View):
    """Retract a published event back to draft for editing."""
    def post(self, request, slug, *args, **kwargs):
        event     = get_object_or_404(Event, slug=slug)
        organizer = request.user.organizer_profile
        try:
            retract_to_draft(event, organizer)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success':      True,
                    'redirect_url': f'/events/edit/{slug}/',
                })
            messages.success(request, _('Event retracted to draft. You can now edit it.'))
            return redirect('events:edit', slug=slug)
        except (ValidationError, PermissionDenied) as exc:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': str(exc)}, status=400)
            messages.error(request, str(exc))
            return redirect('events:detail', slug=slug)


class EventDiscardDraftView(OrganizerRequiredMixin, NoIndexMixin, View):
    def post(self, request, *args, **kwargs):
        discard_draft(request.user.organizer_profile)
        return JsonResponse({'success': True})


# ---------------------------------------------------------------------------
# AJAX: Venue Search
# ---------------------------------------------------------------------------

class VenueSearchView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query   = request.GET.get('q', '').strip()
        results = search_local_venues(query)
        return JsonResponse({'results': results})


class VenueSaveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)

        try:
            venue = get_or_create_venue(
                name    = body.get('name', ''),
                city    = body.get('city', ''),
                address = body.get('address', ''),
                country = body.get('country', 'Tanzania'),
                latitude  = body.get('lat')  or None,
                longitude = body.get('lng')  or None,
                osm_id    = body.get('osm_id', ''),
            )
        except ValidationError as exc:
            return JsonResponse({'error': str(exc)}, status=400)

        return JsonResponse({
            'id':      venue.pk,
            'name':    venue.name,
            'city':    venue.city,
            'address': venue.address,
        })


# ---------------------------------------------------------------------------
# AJAX: Collaborator Search
# ---------------------------------------------------------------------------

class CollaboratorSearchView(OrganizerRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        query     = request.GET.get('q', '').strip()
        organizer = request.user.organizer_profile
        results   = search_collaborators(query, exclude_organizer_pk=organizer.pk)
        return JsonResponse({'results': results})