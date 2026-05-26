from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _


class AnonymousRedirectMixin(LoginRequiredMixin):
    """
    Redirect unauthenticated users to login with ?next= preserved.
    LOGIN_URL is set globally in settings as 'accounts:login'.
    """
    pass


class VerifiedUserMixin(AnonymousRedirectMixin):
    """
    Requires authenticated + email-verified user.
    Unverified users are redirected to the verification-sent page.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.email_verified:
            return redirect('accounts:verification_sent')
        return super().dispatch(request, *args, **kwargs)


class OrganizerRequiredMixin(VerifiedUserMixin):
    """
    Requires an approved organizer account.

    Checks authentication and organizer status BEFORE calling super(),
    so the view body never executes for non-organizers.

    Non-organizers are redirected to the become-organizer page with
    an informative message rather than a hard 403, which would be
    confusing for users who simply haven't applied yet.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # Explicitly guard against missing organizer_profile relation
        # (user.is_organizer=True but OrganizerProfile row absent is an
        # admin data-integrity issue; handle it gracefully regardless)
        is_approved = (
            request.user.is_approved_organizer
            and hasattr(request.user, 'organizer_profile')
        )

        if not is_approved:
            messages.warning(
                request,
                _(
                    'You need an approved organizer account to access this page. '
                    'Apply below to get started.'
                ),
            )
            return redirect('accounts:become_organizer')

        return super().dispatch(request, *args, **kwargs)