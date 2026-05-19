from django.urls import path
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View


class ThemeSyncStubView(View):
    """Temporary stub — replaced in Phase 2 with the real implementation."""
    def post(self, request, *args, **kwargs):
        return JsonResponse({'ok': True})


app_name = 'accounts'

urlpatterns = [
    # ── Stubs — replaced with real views in Phase 2 ──────────────────────
    path('login/',            TemplateView.as_view(template_name='accounts/login.html'),            name='login'),
    path('signup/',           TemplateView.as_view(template_name='accounts/signup.html'),           name='signup'),
    path('logout/',           TemplateView.as_view(template_name='accounts/logout.html'),           name='logout'),
    path('profile/',          TemplateView.as_view(template_name='accounts/profile.html'),          name='profile'),
    path('become-organizer/', TemplateView.as_view(template_name='accounts/become_organizer.html'), name='become_organizer'),
    path('theme-sync/',       ThemeSyncStubView.as_view(),                                         name='theme_sync'),
]