from django.urls import path

from . import views

app_name = 'tickets'

urlpatterns = [
    # ── Fixed paths MUST come before <uuid:reference>/ ──────────────────────
    path('payment/callback/',                    views.PaymentCallbackView.as_view(), name='payment_callback'),
    path('payment/status/<uuid:reference>/',     views.PaymentStatusView.as_view(),   name='payment_status'),
    path('checkout/<slug:slug>/',                views.CheckoutView.as_view(),        name='checkout'),

    # ── Ticket detail — UUID last ────────────────────────────────────────────
    path('<uuid:reference>/',                    views.TicketDetailView.as_view(),    name='detail'),
]