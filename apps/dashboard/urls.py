from django.urls import path
from django.views.generic import TemplateView

app_name = 'dashboard'

urlpatterns = [
    # ── Stubs — replaced with real views in Phase 6 ──────────────────────
    path('',           TemplateView.as_view(template_name='dashboard/buyer.html'),     name='buyer'),
    path('organizer/', TemplateView.as_view(template_name='dashboard/organizer.html'), name='organizer'),
]