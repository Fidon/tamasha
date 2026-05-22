import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):

    class OrganizerStatus(models.TextChoices):
        NONE     = 'NONE',     _('None')
        PENDING  = 'PENDING',  _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    class ThemePreference(models.TextChoices):
        DARK  = 'dark',  _('Dark')
        LIGHT = 'light', _('Light')

    # ── Core identity ──────────────────────────────────────────────────────
    email     = models.EmailField(_('email address'), unique=True)
    full_name = models.CharField(_('full name'), max_length=255)
    phone     = models.CharField(_('phone number'), max_length=20, blank=True)
    avatar    = models.ImageField(
        _('avatar'),
        upload_to='avatars/',
        blank=True,
        null=True,
    )

    # ── Organizer role ─────────────────────────────────────────────────────
    is_organizer     = models.BooleanField(_('organizer'), default=False)
    organizer_status = models.CharField(
        _('organizer status'),
        max_length=10,
        choices=OrganizerStatus.choices,
        default=OrganizerStatus.NONE,
    )

    # ── Preferences ────────────────────────────────────────────────────────
    theme_preference = models.CharField(
        _('theme preference'),
        max_length=5,
        choices=ThemePreference.choices,
        default=ThemePreference.DARK,
    )

    # ── Django internals ───────────────────────────────────────────────────
    is_active   = models.BooleanField(_('active'), default=True)
    is_staff    = models.BooleanField(_('staff status'), default=False)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    # ── Email verification ─────────────────────────────────────────────────
    email_verified    = models.BooleanField(_('email verified'), default=False)
    email_verified_at = models.DateTimeField(_('email verified at'), null=True, blank=True)

    # ── Email verification token ───────────────────────────────────────────
    email_verification_token = models.UUIDField(
        _('email verification token'),
        default=uuid.uuid4,
        editable=False,
    )

    objects = CustomUserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name        = _('user')
        verbose_name_plural = _('users')
        ordering            = ['-date_joined']

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name.strip()

    def get_short_name(self):
        return self.full_name.strip().split()[0] if self.full_name else self.email

    def rotate_verification_token(self):
        """Generate a fresh token — call after successful verification or resend."""
        self.email_verification_token = uuid.uuid4()
        self.save(update_fields=['email_verification_token'])

    @property
    def is_pending_organizer(self):
        return self.organizer_status == self.OrganizerStatus.PENDING

    @property
    def is_approved_organizer(self):
        return self.is_organizer and self.organizer_status == self.OrganizerStatus.APPROVED

    @property
    def is_rejected_organizer(self):
        return self.organizer_status == self.OrganizerStatus.REJECTED


class OrganizerProfile(models.Model):
    user              = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='organizer_profile',
    )
    organization_name = models.CharField(_('organization name'), max_length=255)
    bio               = models.TextField(_('bio'), blank=True)
    website           = models.URLField(_('website'), blank=True)
    approved_at       = models.DateTimeField(_('approved at'), null=True, blank=True)
    approved_by       = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organizer_approvals',
        verbose_name=_('approved by'),
    )

    class Meta:
        verbose_name        = _('organizer profile')
        verbose_name_plural = _('organizer profiles')

    def __str__(self):
        return f'{self.organization_name} ({self.user.email})'


class OrganizerRequest(models.Model):
    """
    Audit trail of every organizer application submitted by a user.
    Never overwritten — each submission is a new row.
    The latest row's status drives CustomUser.organizer_status.
    """

    class Status(models.TextChoices):
        PENDING  = 'PENDING',  _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    user              = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='organizer_requests',
        verbose_name=_('user'),
    )
    organization_name = models.CharField(_('organization name'), max_length=255)
    bio               = models.TextField(_('bio'), blank=True)
    phone             = models.CharField(_('phone'), max_length=20, blank=True)
    website           = models.URLField(_('website'), blank=True)
    pitch             = models.TextField(_('pitch / reason for applying'))
    status            = models.CharField(
        _('status'),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    rejection_reason  = models.TextField(_('rejection reason'), blank=True)
    submitted_at      = models.DateTimeField(_('submitted at'), default=timezone.now)
    reviewed_at       = models.DateTimeField(_('reviewed at'), null=True, blank=True)
    reviewed_by       = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_organizer_requests',
        verbose_name=_('reviewed by'),
    )

    class Meta:
        verbose_name        = _('organizer request')
        verbose_name_plural = _('organizer requests')
        ordering            = ['-submitted_at']

    def __str__(self):
        return f'{self.user.email} — {self.organization_name} ({self.status})'

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED