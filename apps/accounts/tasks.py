"""
accounts.tasks
~~~~~~~~~~~~~~
Celery async tasks for auth and organizer flows.
All external I/O (email, SMS) runs here, never in views.
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags


# ── Email verification ─────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id: int) -> None:
    """Send email verification link to newly registered user."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    verify_url = (
        f"{settings.SITE_DOMAIN}/accounts/verify-email/"
        f"{user.email_verification_token}/"
    )

    html_body = render_to_string('accounts/emails/verify_email.html', {
        'user':       user,
        'verify_url': verify_url,
        'site_name':  settings.SITE_NAME,
    })

    try:
        send_mail(
            subject        = f'Verify your email — {settings.SITE_NAME}',
            message        = strip_tags(html_body),
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            html_message   = html_body,
            fail_silently  = False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Organizer application — admin notification ─────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admin_new_organizer_request(self, request_id: int) -> None:
    """
    Notify ADMIN_NOTIFICATION_EMAIL when a new organizer application
    is submitted. Silently skips if ADMIN_NOTIFICATION_EMAIL is not set.
    """
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', '').strip()
    if not admin_email:
        return

    from .models import OrganizerRequest
    try:
        org_request = OrganizerRequest.objects.select_related('user').get(pk=request_id)
    except OrganizerRequest.DoesNotExist:
        return

    user        = org_request.user
    review_url  = (
        f"{settings.SITE_DOMAIN}/admin/accounts/organizerrequest/"
        f"{org_request.pk}/change/"
    )

    html_body = render_to_string(
        'accounts/emails/admin_organizer_request.html',
        {
            'user':         user,
            'org_request':  org_request,
            'review_url':   review_url,
            'site_name':    settings.SITE_NAME,
        },
    )

    try:
        send_mail(
            subject        = (
                f'[{settings.SITE_NAME}] New organizer application — '
                f'{org_request.organization_name}'
            ),
            message        = strip_tags(html_body),
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [admin_email],
            html_message   = html_body,
            fail_silently  = False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Organizer status notifications ─────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_organizer_approved_notifications(self, user_id: int) -> None:
    """Send approval email + SMS to newly approved organizer."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.select_related('organizer_profile').get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    dashboard_url = f"{settings.SITE_DOMAIN}/dashboard/organizer/"

    html_body = render_to_string('accounts/emails/organizer_approved.html', {
        'user':          user,
        'dashboard_url': dashboard_url,
        'site_name':     settings.SITE_NAME,
    })
    try:
        send_mail(
            subject        = f"Congratulations! You're now an organizer on {settings.SITE_NAME}",
            message        = strip_tags(html_body),
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            html_message   = html_body,
            fail_silently  = False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)

    if user.phone:
        _send_sms(
            phone   = user.phone,
            message = (
                f"Hi {user.get_short_name()}, your organizer application on "
                f"{settings.SITE_NAME} has been approved! "
                f"Start creating events: {dashboard_url}"
            ),
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_organizer_rejected_notifications(self, user_id: int, rejection_reason: str) -> None:
    """Send rejection email + SMS to rejected organizer applicant."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    reapply_url = f"{settings.SITE_DOMAIN}/accounts/become-organizer/"

    html_body = render_to_string('accounts/emails/organizer_rejected.html', {
        'user':             user,
        'rejection_reason': rejection_reason,
        'reapply_url':      reapply_url,
        'site_name':        settings.SITE_NAME,
    })
    try:
        send_mail(
            subject        = f'Update on your organizer application — {settings.SITE_NAME}',
            message        = strip_tags(html_body),
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            html_message   = html_body,
            fail_silently  = False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)

    if user.phone:
        _send_sms(
            phone   = user.phone,
            message = (
                f"Hi {user.get_short_name()}, your organizer application on "
                f"{settings.SITE_NAME} was not approved at this time. "
                f"You can reapply: {reapply_url}"
            ),
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_email(self, user_id: int, reset_url: str) -> None:
    """Send branded HTML password reset email."""
    from .models import CustomUser
    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        return

    html_body = render_to_string('accounts/emails/password_reset.html', {
        'user':        user,
        'reset_url':   reset_url,
        'site_name':   settings.SITE_NAME,
        'site_domain': settings.SITE_DOMAIN,
    })

    try:
        send_mail(
            subject        = f'Reset your password — {settings.SITE_NAME}',
            message        = strip_tags(html_body),
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            html_message   = html_body,
            fail_silently  = False,
        )
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Internal SMS helper ────────────────────────────────────────────────────

def _send_sms(phone: str, message: str) -> None:
    """
    Send SMS via Africa's Talking.
    Converts local Tanzanian format (0XXXXXXXXX) to international (+255XXXXXXXXX).
    Failure is silent — SMS is best-effort and must never break the task chain.
    """
    if not phone:
        return

    # Normalise to international format
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
        africastalking.SMS.send(
            message    = message,
            recipients = [phone],
            sender_id  = settings.AFRICASTALKING_SENDER_ID or None,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            'SMS delivery failed to %s', phone, exc_info=True
        )