from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import OrganizerPayout, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display    = (
        'internal_ref_short', 'order', 'provider',
        'status', 'amount', 'currency', 'created_at',
    )
    list_filter     = ('status', 'provider')
    search_fields   = ('internal_ref', 'provider_ref', 'order__reference',
                       'order__buyer_email')
    readonly_fields = (
        'internal_ref', 'provider_ref', 'order',
        'raw_request', 'raw_callback',
        'created_at', 'updated_at',
    )
    date_hierarchy  = 'created_at'
    fieldsets       = (
        (_('Transaction'), {
            'fields': (
                'internal_ref', 'provider_ref', 'order',
                'provider', 'status', 'amount', 'currency', 'phone',
            ),
        }),
        (_('Raw Payloads'), {
            'fields': ('raw_request', 'raw_callback'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Ref'))
    def internal_ref_short(self, obj):
        return str(obj.internal_ref).split('-')[0].upper()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order__event')

    def has_add_permission(self, request):
        return False


@admin.register(OrganizerPayout)
class OrganizerPayoutAdmin(admin.ModelAdmin):
    list_display    = (
        'organizer', 'event', 'amount', 'currency',
        'status', 'triggered_by', 'paid_at',
    )
    list_filter     = ('status', 'currency')
    search_fields   = ('organizer__organization_name', 'event__title')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('organizer', 'event')
    fieldsets       = (
        (None, {
            'fields': (
                'organizer', 'event', 'amount', 'currency',
                'status', 'notes', 'triggered_by', 'paid_at',
            ),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'organizer', 'event', 'triggered_by'
        )