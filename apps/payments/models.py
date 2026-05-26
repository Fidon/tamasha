import uuid
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Transaction(models.Model):
    """
    AzamPay payment transaction record.
    Created when a payment is initiated, updated via webhook callback.
    Raw AzamPay payload stored in full for audit/debugging.
    """

    class Status(models.TextChoices):
        INITIATED = 'INITIATED', _('Initiated')
        PENDING   = 'PENDING',   _('Pending — Awaiting Callback')
        SUCCESS   = 'SUCCESS',   _('Success')
        FAILED    = 'FAILED',    _('Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class Provider(models.TextChoices):
        AZAMPAY_MOBILE = 'AZAMPAY_MOBILE', _('AzamPay — Mobile Money')
        AZAMPAY_CARD   = 'AZAMPAY_CARD',   _('AzamPay — Bank Card')

    # ---------------------------------------------------------------- relations
    order           = models.ForeignKey(
        'tickets.Order',
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name=_('order'),
    )

    # ---------------------------------------------------------------- identity
    internal_ref    = models.UUIDField(
        _('internal reference'), default=uuid.uuid4, editable=False,
        unique=True, db_index=True,
        help_text=_('Our reference sent to AzamPay as external_id.'),
    )
    provider_ref    = models.CharField(
        _('provider reference'), max_length=255, blank=True, db_index=True,
        help_text=_('AzamPay transaction ID returned in callback.'),
    )

    # ---------------------------------------------------------------- details
    provider        = models.CharField(
        _('provider'), max_length=20, choices=Provider.choices,
    )
    status          = models.CharField(
        _('status'), max_length=12, choices=Status.choices,
        default=Status.INITIATED, db_index=True,
    )
    amount          = models.DecimalField(
        _('amount'), max_digits=12, decimal_places=2,
    )
    currency        = models.CharField(
        _('currency'), max_length=5, default='TZS',
    )
    phone           = models.CharField(
        _('phone'), max_length=30, blank=True,
        help_text=_('Mobile number used for USSD push (mobile money only).'),
    )

    # ---------------------------------------------------------------- raw payload
    raw_request     = models.JSONField(
        _('raw request payload'), default=dict,
        help_text=_('Payload sent to AzamPay.'),
    )
    raw_callback    = models.JSONField(
        _('raw callback payload'), null=True, blank=True,
        help_text=_('Raw POST body received from AzamPay callback.'),
    )

    # ---------------------------------------------------------------- timestamps
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('transaction')
        verbose_name_plural = _('transactions')
        ordering            = ['-created_at']
        # provider_ref must be unique when set — prevents duplicate callbacks
        constraints = [
            models.UniqueConstraint(
                fields=['provider_ref'],
                condition=~models.Q(provider_ref=''),
                name='unique_provider_ref_when_set',
            )
        ]

    def __str__(self):
        return f'{self.provider} — {self.status} — {self.amount} {self.currency}'

    @property
    def is_successful(self):
        return self.status == self.Status.SUCCESS


class OrganizerPayout(models.Model):
    """
    Tracks payouts from platform to organizers.
    Phase 4: manual trigger by admin.
    Phase 6+: automated.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PAID    = 'PAID',    _('Paid')

    organizer       = models.ForeignKey(
        'accounts.OrganizerProfile',
        on_delete=models.PROTECT,
        related_name='payouts',
        verbose_name=_('organizer'),
    )
    event           = models.ForeignKey(
        'events.Event',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='payouts',
        verbose_name=_('event'),
        help_text=_('Null = cumulative payout across multiple events.'),
    )
    amount          = models.DecimalField(
        _('amount'), max_digits=12, decimal_places=2,
    )
    currency        = models.CharField(
        _('currency'), max_length=5, default='TZS',
    )
    status          = models.CharField(
        _('status'), max_length=8, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    notes           = models.TextField(_('notes'), blank=True)
    triggered_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='triggered_payouts',
        verbose_name=_('triggered by'),
    )
    paid_at         = models.DateTimeField(_('paid at'), null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = _('organizer payout')
        verbose_name_plural = _('organizer payouts')
        ordering            = ['-created_at']

    def __str__(self):
        return f'Payout {self.amount} {self.currency} → {self.organizer} [{self.status}]'