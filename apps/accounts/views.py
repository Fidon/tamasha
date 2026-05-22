from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView, UpdateView

from apps.seo.mixins import NoIndexMixin

from .forms import LoginForm, SignupForm, ProfileUpdateForm, OrganizerRequestForm
from .mixins import AnonymousRedirectMixin, VerifiedUserMixin
from .models import CustomUser, OrganizerRequest
from . import services
from .tasks import (
    send_verification_email,
    send_organizer_approved_notifications,
    send_organizer_rejected_notifications,
    send_password_reset_email,
)


# ── Signup ─────────────────────────────────────────────────────────────────

class SignupView(NoIndexMixin, TemplateView):
    template_name = 'accounts/signup.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = SignupForm()
        return ctx

    def post(self, request, *args, **kwargs):
        form = SignupForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        user = services.register_user(
            email     = form.cleaned_data['email'],
            full_name = form.cleaned_data['full_name'],
            password  = form.cleaned_data['password1'],
        )
        if form.cleaned_data.get('phone'):
            user.phone = form.cleaned_data['phone']
            user.save(update_fields=['phone'])

        send_verification_email.delay(user.pk)
        return JsonResponse({
            'success':  True,
            'redirect': '/accounts/verification-sent/',
        })


# ── Email verification ─────────────────────────────────────────────────────

class VerificationSentView(NoIndexMixin, TemplateView):
    template_name = 'accounts/email_verification_sent.html'


class VerifyEmailView(NoIndexMixin, View):
    def get(self, request, token, *args, **kwargs):
        user = services.verify_email(str(token))
        if user is None:
            messages.error(request, 'This verification link is invalid or has already been used.')
            return redirect('accounts:login')
        messages.success(request, 'Your email has been verified. You can now sign in.')
        return redirect('accounts:login')


# ── Login ──────────────────────────────────────────────────────────────────

class LoginView(NoIndexMixin, TemplateView):
    template_name = 'accounts/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = LoginForm(request=self.request)
        return ctx

    def post(self, request, *args, **kwargs):
        form = LoginForm(request=request, data=request.POST)
        if not form.is_valid():
            # Flatten all errors into a single message for the client
            errors = form.errors.get_json_data()
            # '__all__' holds non-field errors (wrong credentials, axes, etc.)
            all_errors = errors.get('__all__', [])
            if all_errors:
                msg = all_errors[0].get('message', 'Invalid email or password.')
            else:
                # Field-level errors — return them mapped by field name
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            return JsonResponse({'success': False, 'error': msg}, status=400)

        user = form.get_user()
        login(request, user)

        # Sync localStorage theme to DB on login
        ls_theme = request.POST.get('theme')
        if ls_theme in ('dark', 'light'):
            services.sync_theme(user, ls_theme)

        next_url = request.GET.get('next') or '/'
        from django.utils.http import url_has_allowed_host_and_scheme
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = '/'

        return JsonResponse({'success': True, 'redirect': next_url})


# ── Logout ─────────────────────────────────────────────────────────────────

class LogoutView(NoIndexMixin, View):
    """POST-only logout. GET requests are redirected to home."""

    def get(self, request, *args, **kwargs):
        return redirect('core:home')

    def post(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been signed out.')
        return redirect('core:home')


# ── Profile ────────────────────────────────────────────────────────────────

class ProfileView(NoIndexMixin, AnonymousRedirectMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = ProfileUpdateForm(instance=self.request.user)
        ctx['latest_organizer_request'] = (
            OrganizerRequest.objects
            .filter(user=self.request.user)
            .order_by('-submitted_at')
            .first()
        )
        return ctx

    def post(self, request, *args, **kwargs):
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        services.update_profile(
            user      = request.user,
            full_name = form.cleaned_data['full_name'],
            phone     = form.cleaned_data['phone'],
            avatar    = form.cleaned_data.get('avatar'),
        )
        return JsonResponse({'success': True, 'message': 'Profile updated successfully.'})


# ── Theme sync ─────────────────────────────────────────────────────────────

class ThemeSyncView(View):
    """
    Receives theme preference from JS and persists it for authenticated users.
    Anonymous users are handled entirely in localStorage — this endpoint is a no-op for them.
    """

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'ok': True})

        import json
        try:
            data  = json.loads(request.body)
            theme = data.get('theme', '')
        except (ValueError, KeyError):
            return JsonResponse({'ok': False, 'error': 'Invalid payload.'}, status=400)

        services.sync_theme(request.user, theme)
        return JsonResponse({'ok': True})


# ── Become an organizer ────────────────────────────────────────────────────

class BecomeOrganizerView(NoIndexMixin, VerifiedUserMixin, TemplateView):
    template_name = 'accounts/become_organizer.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_approved_organizer or request.user.is_staff:
                return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = OrganizerRequestForm()
        ctx['latest_request'] = (
            OrganizerRequest.objects
            .filter(user=self.request.user)
            .order_by('-submitted_at')
            .first()
        )
        return ctx

    def post(self, request, *args, **kwargs):
        # Block if already pending
        if request.user.is_pending_organizer:
            return JsonResponse(
                {'success': False, 'error': 'Your application is already under review.'},
                status=400,
            )

        form = OrganizerRequestForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

        services.submit_organizer_request(
            user              = request.user,
            organization_name = form.cleaned_data['organization_name'],
            bio               = form.cleaned_data['bio'],
            phone             = form.cleaned_data['phone'],
            website           = form.cleaned_data['website'],
            pitch             = form.cleaned_data['pitch'],
        )
        return JsonResponse({
            'success': True,
            'message': 'Your application has been submitted. We\'ll review it shortly.',
        })


# ── Password reset (Django built-in + custom templates) ───────────────────

class TamashaPasswordResetView(NoIndexMixin, PasswordResetView):
    template_name = 'accounts/password_reset.html'
    success_url   = '/accounts/password-reset/done/'

    def form_valid(self, form):
        """
        Override completely — do not call super().form_valid() which uses
        Django's built-in plain-text email mechanism.
        Build the reset URL manually and fire our branded Celery task.
        """
        email = form.cleaned_data['email']
        try:
            user = CustomUser.objects.get(email__iexact=email, is_active=True)
        except CustomUser.DoesNotExist:
            # Never reveal whether an account exists — redirect silently
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(self.success_url)

        uid       = urlsafe_base64_encode(force_bytes(user.pk))
        token     = default_token_generator.make_token(user)
        reset_url = (
            f"{self.request.scheme}://{self.request.get_host()}"
            f"/accounts/password-reset/confirm/{uid}/{token}/"
        )

        send_password_reset_email.delay(user.pk, reset_url)

        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.success_url)


class TamashaPasswordResetDoneView(NoIndexMixin, PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class TamashaPasswordResetConfirmView(NoIndexMixin, PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url   = '/accounts/password-reset/complete/'


class TamashaPasswordResetCompleteView(NoIndexMixin, PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'