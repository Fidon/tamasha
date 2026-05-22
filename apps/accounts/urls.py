from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────
    path('signup/',              views.SignupView.as_view(),              name='signup'),
    path('login/',               views.LoginView.as_view(),               name='login'),
    path('logout/',              views.LogoutView.as_view(),              name='logout'),

    # ── Email verification ─────────────────────────────────────────────────
    path('verification-sent/',   views.VerificationSentView.as_view(),   name='verification_sent'),
    path('verify-email/<uuid:token>/', views.VerifyEmailView.as_view(),  name='verify_email'),

    # ── Profile ────────────────────────────────────────────────────────────
    path('profile/',             views.ProfileView.as_view(),            name='profile'),

    # ── Theme sync ─────────────────────────────────────────────────────────
    path('theme-sync/',          views.ThemeSyncView.as_view(),          name='theme_sync'),

    # ── Organizer onboarding ───────────────────────────────────────────────
    path('become-organizer/',    views.BecomeOrganizerView.as_view(),    name='become_organizer'),

    # ── Password reset ─────────────────────────────────────────────────────
    path('password-reset/',
         views.TamashaPasswordResetView.as_view(),
         name='password_reset'),
    path('password-reset/done/',
         views.TamashaPasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/',
         views.TamashaPasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('password-reset/complete/',
         views.TamashaPasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]