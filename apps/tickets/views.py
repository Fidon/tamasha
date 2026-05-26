"""
apps/tickets/views.py
"""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from apps.accounts.mixins import AnonymousRedirectMixin
from apps.events.models import Event
from apps.seo.mixins import NoIndexMixin

from .forms import CheckoutBuyerForm
from .models import GuestBuyer, Order, Ticket
from .services import (
    cancel_order,
    confirm_order,
    create_order,
    get_available_ticket_types,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkout page
# ---------------------------------------------------------------------------

class CheckoutView(NoIndexMixin, View):
    """
    GET  — render checkout page with ticket selection + buyer form
    POST — create order then initiate payment (AJAX)
    """
    template_name = 'tickets/checkout.html'

    def get(self, request, slug, *args, **kwargs):
        event = get_object_or_404(
            Event.objects.select_related('venue', 'organizer', 'category')
            .prefetch_related('ticket_types'),
            slug=slug,
            status=Event.Status.PUBLISHED,
        )

        if event.is_past:
            messages.error(request, 'This event has already ended.')
            return redirect('events:detail', slug=slug)

        if event.is_sold_out:
            messages.warning(request, 'This event is sold out.')
            return redirect('events:detail', slug=slug)

        ticket_types = get_available_ticket_types(event)

        # Pre-fill buyer form for authenticated users
        initial = {}
        if request.user.is_authenticated:
            initial = {
                'full_name': request.user.get_full_name(),
                'email':     request.user.email,
                'phone':     request.user.phone or '',
            }

        form = CheckoutBuyerForm(initial=initial)

        return render(request, self.template_name, {
            'event':        event,
            'ticket_types': ticket_types,
            'form':         form,
            'user_phone':   request.user.phone if request.user.is_authenticated else '',
        })

    def post(self, request, slug, *args, **kwargs):
        event = get_object_or_404(
            Event,
            slug=slug,
            status=Event.Status.PUBLISHED,
        )

        if event.is_past or event.is_sold_out:
            return JsonResponse(
                {'success': False, 'error': 'Event is no longer available.'},
                status=400,
            )

        # Parse selections from JSON body
        try:
            body       = json.loads(request.body)
            selections = body.get('selections', [])
            form_data  = body.get('buyer', {})
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

        form = CheckoutBuyerForm(data=form_data)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=422)

        cd             = form.cleaned_data
        payment_method = cd['payment_method']
        mobile_network = cd.get('mobile_network', '')

        # ---- Resolve buyer ----
        user  = request.user if request.user.is_authenticated else None
        guest = None
        if user is None:
            guest = GuestBuyer.objects.create(
                name  = cd['full_name'],
                email = cd['email'],
                phone = cd['phone'],
            )

        # ---- Reuse existing PENDING order if buyer retrying same event ----
        existing_order = None
        if user:
            existing_order = (
                Order.objects
                .filter(event=event, user=user, status=Order.Status.PENDING)
                .order_by('-created_at')
                .first()
            )

        # ---- Create or reuse order ----
        try:
            if existing_order:
                order = existing_order
                # Update buyer contact in case it changed
                order.buyer_name  = cd['full_name']
                order.buyer_email = cd['email']
                order.buyer_phone = cd['phone']
                order.payment_method = payment_method
                order.save(update_fields=['buyer_name', 'buyer_email', 'buyer_phone', 'payment_method', 'updated_at'])
            else:
                order = create_order(
                    event          = event,
                    selections     = selections,
                    buyer_name     = cd['full_name'],
                    buyer_email    = cd['email'],
                    buyer_phone    = cd['phone'],
                    user           = user,
                    guest          = guest,
                    payment_method = payment_method,
                )
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            return JsonResponse({'success': False, 'error': msg}, status=422)

        # ---- Free order — confirm immediately ----
        if order.status == Order.Status.FREE:
            confirm_order(order)
            return JsonResponse({
                'success':      True,
                'free':         True,
                'redirect_url': f'/tickets/{order.reference}/',
            })

        # ---- Paid order — initiate payment ----
        if payment_method == Order.PaymentMethod.MOBILE_MONEY:
            from apps.payments.services import initiate_mobile_payment
            try:
                result = initiate_mobile_payment(
                    order    = order,
                    phone    = cd['phone'],
                    provider = mobile_network,
                )
            except ValidationError as exc:
                return JsonResponse(
                    {'success': False, 'error': exc.message},
                    status=502,
                )
            if result['success']:
                return JsonResponse({
                    'success':        True,
                    'free':           False,
                    'mobile':         True,
                    'order_ref':      str(order.reference),
                    'poll_url':       f'/tickets/payment/status/{order.reference}/',
                    'message':        result['message'],
                })
            # Payment initiation failed — do NOT cancel order, let user retry
            return JsonResponse({'success': False, 'error': result['message']}, status=502)

        # ---- Card payment ----
        from apps.payments.services import initiate_card_payment
        redirect_url = f"{settings.SITE_DOMAIN}/tickets/{order.reference}/"
        result = initiate_card_payment(
            order        = order,
            redirect_url = redirect_url,
        )
        if result['success']:
            return JsonResponse({
                'success':      True,
                'free':         False,
                'card':         True,
                'checkout_url': result['checkout_url'],
            })
        cancel_order(order)
        return JsonResponse({'success': False, 'error': result['message']}, status=502)


# ---------------------------------------------------------------------------
# Payment status polling (USSD)
# ---------------------------------------------------------------------------

class PaymentStatusView(NoIndexMixin, View):
    """
    GET /tickets/payment/status/<uuid:reference>/
    Called by checkout page JS every 5s to check if USSD push was confirmed.
    """
    def get(self, request, reference, *args, **kwargs):
        order = get_object_or_404(Order, reference=reference)

        # Security: only the buyer can poll their own order
        if request.user.is_authenticated and order.user and order.user != request.user:
            return JsonResponse({'error': 'Forbidden.'}, status=403)

        from apps.payments.services import get_payment_status
        status = get_payment_status(order)

        return JsonResponse({
            'confirmed':  status['confirmed'],
            'status':     status['status'],
            'redirect_url': f'/tickets/{order.reference}/' if status['confirmed'] else None,
        })


# ---------------------------------------------------------------------------
# AzamPay webhook callback
# ---------------------------------------------------------------------------

@method_decorator(csrf_exempt, name='dispatch')
class PaymentCallbackView(View):
    """
    POST /tickets/payment/callback/
    AzamPay posts here after payment is processed.
    Must return 200 quickly — all work is async.
    """
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError):
            # AzamPay may send form-encoded data
            payload = request.POST.dict()

        from apps.payments.services import handle_payment_callback
        try:
            handle_payment_callback(payload)
        except Exception:
            logger.exception('Payment callback processing error. Payload: %s', payload)

        # Always return 200 to AzamPay — never expose internal errors
        return HttpResponse('OK', status=200)


# ---------------------------------------------------------------------------
# Ticket detail page
# ---------------------------------------------------------------------------

class TicketDetailView(NoIndexMixin, View):
    """
    /tickets/<uuid:reference>/
    Shows order confirmation + individual QR tickets.
    Accessible to authenticated buyer or guest (via reference UUID in URL).
    """
    template_name = 'tickets/detail.html'

    def get(self, request, reference, *args, **kwargs):
        order = get_object_or_404(
            Order.objects
            .select_related('event__venue', 'event__organizer', 'user', 'guest')
            .prefetch_related(
                'items__ticket_type',
                'items__tickets',
            ),
            reference=reference,
        )

        # Security: authenticated users can only see their own orders
        if request.user.is_authenticated and order.user and order.user != request.user:
            messages.error(request, 'You do not have access to this order.')
            return redirect('core:home')

        # Pending orders that haven't been paid redirect back to checkout
        if order.status == Order.Status.PENDING:
            messages.warning(request, 'Payment is still pending for this order.')
            return redirect('tickets:checkout', slug=order.event.slug)

        all_tickets = []
        for item in order.items.all():
            for ticket in item.tickets.all():
                all_tickets.append(ticket)

        return render(request, self.template_name, {
            'order':   order,
            'event':   order.event,
            'tickets': all_tickets,
        })