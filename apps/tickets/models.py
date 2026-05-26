import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TicketType(models.Model):
    """
    A ticket tier for an event (e.g. General, VIP, VVIP).
    Created as part of the multi-step event wizard (Step 5).
    """
    event           = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='ticket_types',
        verbose_name=_('event'),
    )
    name            = models.CharField(_('name'), max_length=100)
    description     = models.CharField(
        _('description'), max_length=255, blank=True,
        help_text=_('Short perks summary, e.g. "Front row + backstage access"'),
    )
    price           = models.DecimalField(
        _('price'), max_digits=10, decimal_places=2,
        help_text=_('Set to 0.00 for free tickets.'),
    )
    quantity        = models.PositiveIntegerField(
        _('total quantity'),
        help_text=_('Total tickets available for this tier.'),
    )
    quantity_sold   = models.PositiveIntegerField(_('quantity sold'), default=0)
    max_per_order   = models.PositiveSmallIntegerField(
        _('max per order'), default=10,
        help_text=_('Maximum tickets a single buyer can purchase in one order.'),
    )
    sale_starts_at  = models.DateTimeField(_('sale starts at'), null=True, blank=True)
    sale_ends_at    = models.DateTimeField(_('sale ends at'), null=True, blank=True)
    is_sold_out     = models.BooleanField(
        _('sold out'), default=False,
        help_text=_(
            'Manually mark as sold out regardless of remaining capacity. '
            'Organizer can toggle this at any time.'
        ),
    )
    is_active       = models.BooleanField(
        _('active'), default=True,
        help_text=_('Inactive ticket types are hidden from buyers.'),
    )
    sort_order      = models.PositiveSmallIntegerField(_('sort order'), default=0)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('ticket type')
        verbose_name_plural = _('ticket types')
        ordering            = ['sort_order', 'price']

    def __str__(self):
        return f'{self.name} — {self.event.title}'

    @property
    def quantity_remaining(self):
        return max(0, self.quantity - self.quantity_sold)

    @property
    def is_effectively_sold_out(self):
        return self.is_sold_out or self.quantity_sold >= self.quantity

    @property
    def is_on_sale(self):
        if self.is_effectively_sold_out:
            return False
        now = timezone.now()
        if self.sale_starts_at and now < self.sale_starts_at:
            return False
        if self.sale_ends_at and now > self.sale_ends_at:
            return False
        return True

    @property
    def is_free(self):
        return self.price == 0

    @property
    def sell_through_percentage(self):
        if self.quantity == 0:
            return 100
        return round((self.quantity_sold / self.quantity) * 100, 1)


# ---------------------------------------------------------------------------
# Guest buyer — person record for unauthenticated purchasers
# ---------------------------------------------------------------------------

class GuestBuyer(models.Model):
    """
    Stores contact info for unauthenticated (guest) ticket buyers.
    Each purchase creates a new row — no deduplication by design.
    Analytics on guest purchases come from Order queries, not this model.
    """
    name        = models.CharField(_('full name'), max_length=255)
    email       = models.EmailField(_('email'))
    phone       = models.CharField(_('phone'), max_length=30)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('guest buyer')
        verbose_name_plural = _('guest buyers')
        ordering            = ['-created_at']

    def __str__(self):
        return f'{self.name} <{self.email}>'


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(models.Model):

    class Status(models.TextChoices):
        PENDING   = 'PENDING',   _('Pending Payment')
        PAID      = 'PAID',      _('Paid')
        CANCELLED = 'CANCELLED', _('Cancelled')
        REFUNDED  = 'REFUNDED',  _('Refunded')
        FREE      = 'FREE',      _('Free — No Payment Required')

    class PaymentMethod(models.TextChoices):
        MOBILE_MONEY = 'MOBILE_MONEY', _('Mobile Money (USSD)')
        CARD         = 'CARD',         _('Bank Card')
        FREE         = 'FREE',         _('Free')

    # ---------------------------------------------------------------- identity
    reference   = models.UUIDField(
        _('reference'), default=uuid.uuid4, editable=False,
        unique=True, db_index=True,
    )

    # ---------------------------------------------------------------- buyer
    # Exactly one of these is set per order — never both
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='orders',
        verbose_name=_('user'),
    )
    guest       = models.ForeignKey(
        GuestBuyer,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='orders',
        verbose_name=_('guest buyer'),
    )

    # ---------------------------------------------------------------- event
    event       = models.ForeignKey(
        'events.Event',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name=_('event'),
    )

    # ---------------------------------------------------------------- status
    status          = models.CharField(
        _('status'), max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    payment_method  = models.CharField(
        _('payment method'), max_length=14,
        choices=PaymentMethod.choices,
        blank=True,
    )

    # ---------------------------------------------------------------- financials
    # All amounts stored in TZS (no decimals needed — TZS has no subunit)
    gross_amount    = models.DecimalField(
        _('gross amount'), max_digits=12, decimal_places=2, default=0,
        help_text=_('Total paid by buyer before commission deduction.'),
    )
    platform_fee    = models.DecimalField(
        _('platform fee'), max_digits=12, decimal_places=2, default=0,
        help_text=_(f'Commission deducted by platform.'),
    )
    organizer_amount = models.DecimalField(
        _('organizer amount'), max_digits=12, decimal_places=2, default=0,
        help_text=_('Amount payable to organizer after commission.'),
    )
    commission_rate  = models.DecimalField(
        _('commission rate'), max_digits=5, decimal_places=4, default=0,
        help_text=_('Rate applied at time of purchase — snapshot, not live setting.'),
    )

    # ---------------------------------------------------------------- contact
    # Denormalised buyer contact — used for ticket delivery regardless of
    # whether buyer is authenticated or guest
    buyer_name  = models.CharField(_('buyer name'), max_length=255, blank=True)
    buyer_email = models.EmailField(_('buyer email'), blank=True)
    buyer_phone = models.CharField(_('buyer phone'), max_length=30, blank=True)

    # ---------------------------------------------------------------- timestamps
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at  = models.DateTimeField(auto_now=True)
    paid_at     = models.DateTimeField(_('paid at'), null=True, blank=True)

    class Meta:
        verbose_name        = _('order')
        verbose_name_plural = _('orders')
        ordering            = ['-created_at']
        indexes             = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
        ]
        constraints = [
            # Exactly one of user or guest must be set — enforced at service layer too
            models.CheckConstraint(
                condition=(
                    models.Q(user__isnull=False, guest__isnull=True) |
                    models.Q(user__isnull=True,  guest__isnull=False)
                ),
                name='order_buyer_exactly_one',
            )
        ]

    def __str__(self):
        return f'Order {str(self.reference)[:8].upper()} — {self.event.title}'

    @property
    def reference_short(self):
        return str(self.reference).split('-')[0].upper()

    @property
    def is_paid(self):
        return self.status in (self.Status.PAID, self.Status.FREE)

    @property
    def total_tickets(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def buyer_display_name(self):
        return self.buyer_name or (
            self.user.get_full_name() if self.user else
            self.guest.name if self.guest else '—'
        )


# ---------------------------------------------------------------------------
# Order Item
# ---------------------------------------------------------------------------

class OrderItem(models.Model):
    """
    One row per ticket tier per order.
    Prices are snapshotted at purchase time — changing ticket prices later
    does not affect historical orders.
    """
    order           = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('order'),
    )
    ticket_type     = models.ForeignKey(
        TicketType,
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name=_('ticket type'),
    )
    quantity        = models.PositiveSmallIntegerField(_('quantity'))
    unit_price      = models.DecimalField(
        _('unit price'), max_digits=10, decimal_places=2,
        help_text=_('Price per ticket at time of purchase.'),
    )
    subtotal        = models.DecimalField(
        _('subtotal'), max_digits=12, decimal_places=2,
    )

    class Meta:
        verbose_name        = _('order item')
        verbose_name_plural = _('order items')

    def __str__(self):
        return f'{self.quantity}× {self.ticket_type.name} @ {self.unit_price}'

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Ticket (individual QR ticket)
# ---------------------------------------------------------------------------

class Ticket(models.Model):
    """
    One row per individual ticket within an order item.
    If a buyer purchases 3 General tickets, 3 Ticket rows are created.
    Each has a unique UUID4 token used for QR scanning at the venue.
    """
    order_item  = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name=_('order item'),
    )
    token       = models.UUIDField(
        _('token'), default=uuid.uuid4, editable=False,
        unique=True, db_index=True,
    )
    qr_image    = models.ImageField(
        _('QR code image'),
        upload_to='tickets/qr/',
        null=True, blank=True,
        editable=False,
    )
    is_used     = models.BooleanField(_('used'), default=False, db_index=True)
    used_at     = models.DateTimeField(_('used at'), null=True, blank=True)
    used_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='checked_in_tickets',
        verbose_name=_('checked in by'),
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = _('ticket')
        verbose_name_plural = _('tickets')
        ordering            = ['created_at']

    def __str__(self):
        return f'Ticket {str(self.token)[:8].upper()} — {self.order_item.ticket_type.name}'

    @property
    def event(self):
        return self.order_item.ticket_type.event

    @property
    def order(self):
        return self.order_item.order

    @property
    def ticket_type(self):
        return self.order_item.ticket_type

    @property
    def token_short(self):
        return str(self.token).split('-')[0].upper()

    def mark_used(self, checked_in_by=None):
        """Mark ticket as used. Called by check-in view."""
        self.is_used  = True
        self.used_at  = timezone.now()
        self.used_by  = checked_in_by
        self.save(update_fields=['is_used', 'used_at', 'used_by'])