"""
apps/tickets/tasks.py

Async tasks: QR generation, ticket delivery via email + SMS,
and paid order confirmation triggered by payment callback.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def confirm_paid_order(self, order_pk: int) -> None:
    """
    Called by payment callback handler after AzamPay confirms success.
    Confirms the order and triggers ticket generation + delivery.
    """
    from apps.tickets.models import Order
    from apps.tickets.services import confirm_order

    try:
        order = Order.objects.get(pk=order_pk)
    except Order.DoesNotExist:
        logger.error('confirm_paid_order: Order pk=%s not found.', order_pk)
        return

    try:
        confirm_order(order)
    except Exception as exc:
        logger.exception('confirm_paid_order failed for order %s: %s', order_pk, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_and_deliver_tickets(self, order_pk: int) -> None:
    """
    1. Generate QR PNG for every Ticket on the order.
    2. Send confirmation email with ticket details.
    3. Send SMS with ticket access link.
    """
    from apps.tickets.models import Order
    from apps.tickets.services import generate_qr_for_ticket

    try:
        order = (
            Order.objects
            .select_related('event__venue', 'user', 'guest')
            .prefetch_related(
                'items__ticket_type',
                'items__tickets',
            )
            .get(pk=order_pk)
        )
    except Order.DoesNotExist:
        logger.error('generate_and_deliver_tickets: Order pk=%s not found.', order_pk)
        return

    # ---- Generate QR for each ticket ----
    all_tickets = []
    for item in order.items.all():
        for ticket in item.tickets.all():
            if not ticket.qr_image:
                try:
                    generate_qr_for_ticket(ticket)
                except Exception as exc:
                    logger.error(
                        'QR generation failed for ticket %s: %s', ticket.pk, exc
                    )
            all_tickets.append(ticket)

    if not all_tickets:
        logger.warning('generate_and_deliver_tickets: no tickets found for order %s', order_pk)
        return

    ticket_url = f"{settings.SITE_DOMAIN}/tickets/{order.reference}/"

    # ---- Email ----
    try:
        _send_ticket_email(order, all_tickets, ticket_url)
    except Exception as exc:
        logger.error('Ticket email failed for order %s: %s', order_pk, exc)
        raise self.retry(exc=exc)

    # ---- SMS ----
    if order.buyer_phone:
        _send_ticket_sms(order, ticket_url)


def _send_ticket_email(order, tickets: list, ticket_url: str) -> None:
    html_body = render_to_string('tickets/emails/ticket_confirmation.html', {
        'order':      order,
        'tickets':    tickets,
        'ticket_url': ticket_url,
        'site_name':  settings.SITE_NAME,
        'event':      order.event,
    })
    text_body = strip_tags(html_body)

    msg = EmailMultiAlternatives(
        subject        = f'Your tickets for {order.event.title} — {settings.SITE_NAME}',
        body           = text_body,
        from_email     = settings.DEFAULT_FROM_EMAIL,
        to             = [order.buyer_email],
    )
    msg.attach_alternative(html_body, 'text/html')

    # Attach QR images inline
    for ticket in tickets:
        if ticket.qr_image:
            try:
                ticket.qr_image.open('rb')
                msg.attach(
                    f'ticket-{ticket.token_short}.png',
                    ticket.qr_image.read(),
                    'image/png',
                )
                ticket.qr_image.close()
            except Exception as exc:
                logger.warning('Could not attach QR for ticket %s: %s', ticket.pk, exc)

    msg.send(fail_silently=False)


def _send_ticket_sms(order, ticket_url: str) -> None:
    phone = order.buyer_phone
    if not phone:
        return

    # Africa's Talking requires international format: +255XXXXXXXXX
    # Convert local 10-digit format (0XXXXXXXXX) to international
    if phone.startswith('0') and len(phone) == 10:
        phone = '+255' + phone[1:]
    elif not phone.startswith('+'):
        phone = '+255' + phone

    try:
        import africastalking
        africastalking.initialize(
            username = settings.AFRICASTALKING_USERNAME,
            api_key  = settings.AFRICASTALKING_API_KEY,
        )
        total = sum(item.quantity for item in order.items.all())
        message = (
            f"Hi {order.buyer_name}, your {total} ticket(s) for "
            f"{order.event.title} are confirmed! "
            f"View & download: {ticket_url}"
        )
        africastalking.SMS.send(
            message    = message,
            recipients = [phone],
            sender_id  = settings.AFRICASTALKING_SENDER_ID or None,
        )
    except Exception:
        logger.warning(
            'SMS delivery failed for order %s to %s',
            order.pk, phone, exc_info=True,
        )