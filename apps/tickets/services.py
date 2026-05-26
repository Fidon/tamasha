"""
Order creation, QR generation, free ticket fast path, commission math.
All ticket business logic lives here.
"""
import io
import logging
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import GuestBuyer, Order, OrderItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TicketType helpers (Phase 3 — preserved)
# ---------------------------------------------------------------------------

def toggle_sold_out(ticket_type, organizer_profile):
    from apps.events.services import _assert_primary_organizer
    _assert_primary_organizer(ticket_type.event, organizer_profile)
    ticket_type.is_sold_out = not ticket_type.is_sold_out
    ticket_type.save(update_fields=['is_sold_out', 'updated_at'])
    return ticket_type


def get_available_ticket_types(event) -> list:
    return list(
        event.ticket_types
        .filter(is_active=True)
        .order_by('sort_order', 'price')
    )


def validate_ticket_type_data(data: dict, existing_instance=None) -> None:
    from decimal import Decimal, InvalidOperation
    name = (data.get('name') or '').strip()
    if not name:
        raise ValidationError(_('Ticket type name is required.'))
    try:
        price = Decimal(str(data.get('price', '0')))
    except InvalidOperation:
        raise ValidationError(_('Price must be a valid number.'))
    if price < 0:
        raise ValidationError(_('Price cannot be negative.'))
    try:
        quantity = int(data.get('quantity', 0))
    except (TypeError, ValueError):
        raise ValidationError(_('Quantity must be a whole number.'))
    if quantity < 1:
        raise ValidationError(_('Quantity must be at least 1.'))
    if existing_instance and quantity < existing_instance.quantity_sold:
        raise ValidationError(
            _('Quantity cannot be less than tickets already sold (%(sold)s sold so far).')
            % {'sold': existing_instance.quantity_sold}
        )
    try:
        max_per_order = int(data.get('max_per_order', 10))
    except (TypeError, ValueError):
        raise ValidationError(_('Max per order must be a whole number.'))
    if max_per_order < 1:
        raise ValidationError(_('Max per order must be at least 1.'))


# ---------------------------------------------------------------------------
# Commission
# ---------------------------------------------------------------------------

def _calculate_commission(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Returns (platform_fee, organizer_amount) for a given gross amount."""
    rate              = Decimal(str(settings.COMMISSION_RATE))
    platform_fee      = (gross * rate).quantize(Decimal('0.01'))
    organizer_amount  = gross - platform_fee
    return platform_fee, organizer_amount


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------

@db_transaction.atomic
def create_order(
    *,
    event,
    selections: list[dict],   # [{'ticket_type_id': int, 'quantity': int}, ...]
    buyer_name: str,
    buyer_email: str,
    buyer_phone: str,
    user=None,
    guest=None,
    payment_method: str,
) -> 'Order':
    """
    Validate selections, lock ticket type rows, create Order + OrderItem rows.
    Does NOT generate QR codes or send notifications — those happen after payment.

    Args:
        selections:     List of dicts with ticket_type_id and quantity.
        user:           Authenticated CustomUser or None.
        guest:          GuestBuyer instance or None.
        payment_method: Order.PaymentMethod choice string.

    Raises:
        ValidationError on any availability, capacity, or data issue.
    """

    if not selections:
        raise ValidationError(_('No tickets selected.'))

    if user is None and guest is None:
        raise ValidationError(_('Either user or guest must be provided.'))

    if user is not None and guest is not None:
        raise ValidationError(_('Cannot set both user and guest on an order.'))

    # ---- Lock ticket types for atomic availability check ----
    from apps.tickets.models import TicketType
    ticket_type_ids = [s['ticket_type_id'] for s in selections]
    ticket_types    = {
        tt.pk: tt
        for tt in TicketType.objects.select_for_update().filter(
            pk__in=ticket_type_ids,
            event=event,
            is_active=True,
        )
    }

    if len(ticket_types) != len(ticket_type_ids):
        raise ValidationError(_('One or more selected ticket types are unavailable.'))

    gross_amount = Decimal('0')
    validated    = []

    for sel in selections:
        tt  = ticket_types[sel['ticket_type_id']]
        qty = int(sel['quantity'])

        if qty < 1:
            raise ValidationError(
                _('Quantity for %(name)s must be at least 1.') % {'name': tt.name}
            )
        if qty > tt.max_per_order:
            raise ValidationError(
                _('Maximum %(max)s tickets per order for %(name)s.')
                % {'max': tt.max_per_order, 'name': tt.name}
            )
        if tt.is_effectively_sold_out:
            raise ValidationError(
                _('%(name)s is sold out.') % {'name': tt.name}
            )
        if qty > tt.quantity_remaining:
            raise ValidationError(
                _('Only %(rem)s tickets remaining for %(name)s.')
                % {'rem': tt.quantity_remaining, 'name': tt.name}
            )

        subtotal      = tt.price * qty
        gross_amount += subtotal
        validated.append({'tt': tt, 'qty': qty, 'unit_price': tt.price, 'subtotal': subtotal})

    # ---- Determine if order is free ----
    is_free = gross_amount == Decimal('0')

    # ---- Commission ----
    if is_free:
        platform_fee     = Decimal('0')
        organizer_amount = Decimal('0')
        rate             = Decimal('0')
    else:
        platform_fee, organizer_amount = _calculate_commission(gross_amount)
        rate = Decimal(str(settings.COMMISSION_RATE))

    # ---- Create Order ----
    order = Order.objects.create(
        event            = event,
        user             = user,
        guest            = guest,
        status           = Order.Status.FREE if is_free else Order.Status.PENDING,
        payment_method   = Order.PaymentMethod.FREE if is_free else payment_method,
        gross_amount     = gross_amount,
        platform_fee     = platform_fee,
        organizer_amount = organizer_amount,
        commission_rate  = rate,
        buyer_name       = buyer_name.strip(),
        buyer_email      = buyer_email.strip(),
        buyer_phone      = buyer_phone.strip(),
    )

    # ---- Create OrderItems and reserve capacity ----
    for v in validated:
        OrderItem.objects.create(
            order       = order,
            ticket_type = v['tt'],
            quantity    = v['qty'],
            unit_price  = v['unit_price'],
            subtotal    = v['subtotal'],
        )
        # Reserve quantity immediately
        v['tt'].quantity_sold = v['tt'].quantity_sold + v['qty']
        v['tt'].save(update_fields=['quantity_sold'])

    return order


# ---------------------------------------------------------------------------
# Order confirmation (called after payment success or free order)
# ---------------------------------------------------------------------------

@db_transaction.atomic
def confirm_order(order) -> None:
    """
    Mark order as PAID/FREE, set paid_at, generate Ticket rows.
    Called synchronously for free orders, via Celery task for paid orders.
    """
    from .models import Order, Ticket

    if order.status not in (Order.Status.PENDING, Order.Status.FREE):
        logger.info('confirm_order called on already-processed order %s — skipped.', order.pk)
        return

    now = timezone.now()

    if order.status == Order.Status.PENDING:
        order.status  = Order.Status.PAID
        order.paid_at = now
        order.save(update_fields=['status', 'paid_at', 'updated_at'])

    # Generate individual Ticket rows (one per seat)
    for item in order.items.select_related('ticket_type').all():
        existing_count = item.tickets.count()
        for _ in range(item.quantity - existing_count):
            Ticket.objects.create(order_item=item)

    # Queue async QR generation + delivery
    from apps.tickets.tasks import generate_and_deliver_tickets
    generate_and_deliver_tickets.delay(order.pk)


# ---------------------------------------------------------------------------
# QR code generation
# ---------------------------------------------------------------------------

def generate_qr_for_ticket(ticket) -> None:
    """
    Generate a QR code PNG for a single Ticket and save to ticket.qr_image.
    The QR encodes the full token UUID as a URL for easy scanning.
    """
    import qrcode
    from qrcode.image.pure import PyPNGImage

    token_url = f"{settings.SITE_DOMAIN}/checkin/scan/?token={ticket.token}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(token_url)
    qr.make(fit=True)

    img    = qr.make_image(fill_color='black', back_color='white')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    filename = f'ticket-{str(ticket.token)}.png'
    ticket.qr_image.save(filename, ContentFile(buffer.read()), save=True)


# ---------------------------------------------------------------------------
# Cancel order (buyer-initiated — Phase 6 adds admin refund)
# ---------------------------------------------------------------------------

@db_transaction.atomic
def cancel_order(order) -> None:
    """
    Cancel a PENDING order and release reserved capacity.
    Paid orders cannot be cancelled here — that's a refund (Phase 6).
    """
    from .models import Order

    if order.status != Order.Status.PENDING:
        raise ValidationError(_('Only pending orders can be cancelled.'))

    for item in order.items.select_related('ticket_type').all():
        tt = item.ticket_type
        tt.quantity_sold = max(0, tt.quantity_sold - item.quantity)
        tt.save(update_fields=['quantity_sold'])

    order.status = Order.Status.CANCELLED
    order.save(update_fields=['status', 'updated_at'])