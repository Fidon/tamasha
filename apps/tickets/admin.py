from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import GuestBuyer, Order, OrderItem, Ticket, TicketType


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display    = (
        'name', 'event', 'price', 'quantity',
        'quantity_sold', 'quantity_remaining_display',
        'is_sold_out', 'is_active', 'sort_order',
    )
    list_filter     = ('is_sold_out', 'is_active', 'event__status')
    list_editable   = ('is_sold_out', 'is_active', 'sort_order')
    search_fields   = ('name', 'event__title')
    autocomplete_fields = ('event',)
    readonly_fields = ('quantity_sold', 'created_at', 'updated_at')

    @admin.display(description=_('Remaining'))
    def quantity_remaining_display(self, obj):
        return obj.quantity_remaining

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event', 'event__organizer')


@admin.register(GuestBuyer)
class GuestBuyerAdmin(admin.ModelAdmin):
    list_display    = ('name', 'email', 'phone', 'created_at')
    search_fields   = ('name', 'email', 'phone')
    readonly_fields = ('created_at',)

    def has_add_permission(self, request):
        return False


class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    fk_name         = 'order'
    extra           = 0
    readonly_fields = ('ticket_type', 'quantity', 'unit_price', 'subtotal')
    can_delete      = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = (
        'reference_short', 'event', 'buyer_display_name',
        'status', 'gross_amount', 'payment_method', 'created_at',
    )
    list_filter     = ('status', 'payment_method', 'event__status')
    search_fields   = (
        'reference', 'buyer_name', 'buyer_email',
        'buyer_phone', 'event__title',
    )
    readonly_fields = (
        'reference', 'gross_amount', 'platform_fee',
        'organizer_amount', 'commission_rate',
        'created_at', 'updated_at', 'paid_at',
    )
    inlines         = [OrderItemInline]
    date_hierarchy  = 'created_at'
    fieldsets       = (
        (_('Identity'), {
            'fields': ('reference', 'event', 'user', 'guest'),
        }),
        (_('Buyer Contact'), {
            'fields': ('buyer_name', 'buyer_email', 'buyer_phone'),
        }),
        (_('Status'), {
            'fields': ('status', 'payment_method'),
        }),
        (_('Financials'), {
            'fields': (
                'gross_amount', 'platform_fee',
                'organizer_amount', 'commission_rate',
            ),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at', 'paid_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'event', 'user', 'guest'
        )


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display    = (
        'token_short', 'ticket_type_name', 'event_name',
        'buyer_name', 'is_used', 'used_at',
    )
    list_filter     = ('is_used',)
    search_fields   = ('token', 'order_item__order__buyer_name',
                       'order_item__order__buyer_email')
    readonly_fields = (
        'token', 'qr_image', 'is_used',
        'used_at', 'used_by', 'created_at',
    )

    @admin.display(description=_('Ticket Type'))
    def ticket_type_name(self, obj):
        return obj.order_item.ticket_type.name

    @admin.display(description=_('Event'))
    def event_name(self, obj):
        return obj.order_item.ticket_type.event.title

    @admin.display(description=_('Buyer'))
    def buyer_name(self, obj):
        return obj.order_item.order.buyer_display_name

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order_item__ticket_type__event',
            'order_item__order__user',
            'order_item__order__guest',
        )