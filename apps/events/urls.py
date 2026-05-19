from django.urls import path
from django.views.generic import TemplateView

app_name = 'events'

urlpatterns = [
    # ── Stubs — replaced with real views in Phase 3 ──────────────────────
    path('',        TemplateView.as_view(template_name='events/list.html'),   name='list'),
    path('create/', TemplateView.as_view(template_name='events/create.html'), name='create'),
]