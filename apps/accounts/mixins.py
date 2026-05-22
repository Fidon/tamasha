from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class AnonymousRedirectMixin(LoginRequiredMixin):
    """
    Redirect unauthenticated users to login with ?next= preserved.
    Subclasses LoginRequiredMixin — no extra config needed.
    LOGIN_URL is set globally in settings.py as 'accounts:login'.
    """
    pass


class VerifiedUserMixin(AnonymousRedirectMixin):
    """
    Requires the user to be authenticated AND have a verified email.
    Unverified users are redirected to the verification-sent page.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # super() already redirects unauthenticated users
        if request.user.is_authenticated and not request.user.email_verified:
            return redirect('accounts:verification_sent')
        return response


class OrganizerRequiredMixin(VerifiedUserMixin):
    """
    Requires the user to be an approved organizer.
    Raises 403 for authenticated non-organizers — not a redirect,
    because silently redirecting organizer-only pages leaks information.
    """

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and not request.user.is_approved_organizer:
            raise PermissionDenied
        return response