"""
accounts.services
~~~~~~~~~~~~~~~~~
All business logic for auth and organizer onboarding.
Views stay thin — they call these functions only.
"""

from django.utils import timezone

from .models import CustomUser, OrganizerProfile, OrganizerRequest


# ── Axes helper ────────────────────────────────────────────────────────────

def _clear_axes_records(email: str) -> None:
    """
    Delete any django-axes AccessAttempt records for the given email.
    Called after registration and email verification so stale failure
    records never block a legitimate first login.
    Silent on any error — axes cleanup must never break the main flow.
    """
    try:
        from axes.models import AccessAttempt
        AccessAttempt.objects.filter(username=email).delete()
    except Exception:
        pass


# ── Registration ───────────────────────────────────────────────────────────

def register_user(email: str, full_name: str, password: str) -> CustomUser:
    """
    Create a new user and return the instance.
    Clears any pre-existing axes records for this email (edge case: someone
    tried to log in before registering, leaving a stale failure record).
    Does NOT send the verification email — caller queues the Celery task.
    """
    user = CustomUser.objects.create_user(
        email=email,
        full_name=full_name,
        password=password,
    )
    _clear_axes_records(email)
    return user


def verify_email(token: str) -> CustomUser | None:
    """
    Look up user by verification token, mark email as verified.
    Returns the user on success, None if token is invalid/already used.
    Clears axes records so the first post-verification login is never blocked.
    """
    try:
        user = CustomUser.objects.get(
            email_verification_token=token,
            email_verified=False,
        )
    except CustomUser.DoesNotExist:
        return None

    user.email_verified    = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=['email_verified', 'email_verified_at'])
    user.rotate_verification_token()
    _clear_axes_records(user.email)
    return user


# ── Profile ────────────────────────────────────────────────────────────────

def update_profile(user: CustomUser, full_name: str, phone: str, avatar=None) -> CustomUser:
    user.full_name = full_name
    user.phone     = phone
    if avatar:
        user.avatar = avatar
    user.save(update_fields=['full_name', 'phone', 'avatar'])
    return user


def sync_theme(user: CustomUser, theme: str) -> None:
    """Persist theme preference for authenticated users."""
    if theme not in ('dark', 'light'):
        return
    user.theme_preference = theme
    user.save(update_fields=['theme_preference'])


# ── Organizer onboarding ───────────────────────────────────────────────────

def submit_organizer_request(
    user: CustomUser,
    organization_name: str,
    bio: str,
    phone: str,
    website: str,
    pitch: str,
) -> OrganizerRequest:
    """
    Create a new OrganizerRequest row and set user status to PENDING.
    Previous requests are preserved as audit trail — never deleted.
    Queues an async admin notification email via Celery.
    """
    org_request = OrganizerRequest.objects.create(
        user              = user,
        organization_name = organization_name,
        bio               = bio,
        phone             = phone,
        website           = website,
        pitch             = pitch,
        status            = OrganizerRequest.Status.PENDING,
    )
    user.organizer_status = CustomUser.OrganizerStatus.PENDING
    user.save(update_fields=['organizer_status'])

    # Notify admin asynchronously — import inside function to avoid
    # circular imports at module load time
    from .tasks import notify_admin_new_organizer_request
    notify_admin_new_organizer_request.delay(org_request.pk)

    return org_request


def approve_organizer_request(
    organizer_request: OrganizerRequest,
    reviewed_by: CustomUser,
) -> OrganizerProfile:
    """
    Approve a pending request:
    - Updates OrganizerRequest row
    - Sets CustomUser.is_organizer + status
    - Creates or updates OrganizerProfile
    Does NOT send notifications — caller queues the Celery task.
    """
    now = timezone.now()

    organizer_request.status      = OrganizerRequest.Status.APPROVED
    organizer_request.reviewed_at = now
    organizer_request.reviewed_by = reviewed_by
    organizer_request.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])

    user = organizer_request.user
    user.is_organizer     = True
    user.organizer_status = CustomUser.OrganizerStatus.APPROVED
    user.save(update_fields=['is_organizer', 'organizer_status'])

    profile, _ = OrganizerProfile.objects.update_or_create(
        user=user,
        defaults={
            'organization_name': organizer_request.organization_name,
            'bio':               organizer_request.bio,
            'website':           organizer_request.website,
            'approved_at':       now,
            'approved_by':       reviewed_by,
        },
    )
    return profile


def reject_organizer_request(
    organizer_request: OrganizerRequest,
    reviewed_by: CustomUser,
    rejection_reason: str,
) -> OrganizerRequest:
    """
    Reject a pending request:
    - Updates OrganizerRequest row with mandatory reason
    - Sets CustomUser.organizer_status to REJECTED
    Does NOT send notifications — caller queues the Celery task.
    """
    if not rejection_reason.strip():
        raise ValueError('A rejection reason is required.')

    now = timezone.now()

    organizer_request.status           = OrganizerRequest.Status.REJECTED
    organizer_request.rejection_reason = rejection_reason.strip()
    organizer_request.reviewed_at      = now
    organizer_request.reviewed_by      = reviewed_by
    organizer_request.save(update_fields=[
        'status', 'rejection_reason', 'reviewed_at', 'reviewed_by',
    ])

    user = organizer_request.user
    user.organizer_status = CustomUser.OrganizerStatus.REJECTED
    user.save(update_fields=['organizer_status'])

    return organizer_request