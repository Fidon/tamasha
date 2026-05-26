from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, Tag, Venue, Event, EventCollaborator, EventDraft


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display    = ('name', 'icon_preview', 'sort_order')
    list_editable   = ('sort_order',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields   = ('name',)
    ordering        = ('sort_order', 'name')

    @admin.display(description=_('Icon Preview'))
    def icon_preview(self, obj):
        return format_html('<i class="{}"></i> {}', obj.icon, obj.icon)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display    = ('name', 'slug', 'is_predefined')
    list_editable   = ('is_predefined',)
    list_filter     = ('is_predefined',)
    search_fields   = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    ordering        = ('-is_predefined', 'name')


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display    = ('name', 'city', 'country', 'has_coordinates', 'capacity', 'created_at')
    list_filter     = ('city', 'country')
    search_fields   = ('name', 'city', 'address')
    readonly_fields = ('created_at',)
    fieldsets       = (
        (None, {
            'fields': ('name', 'address', 'city', 'country', 'capacity'),
        }),
        (_('Coordinates'), {
            'fields': ('latitude', 'longitude', 'osm_id'),
            'classes': ('collapse',),
        }),
        (_('Meta'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description=_('Coordinates'), boolean=True)
    def has_coordinates(self, obj):
        return obj.has_coordinates


class EventCollaboratorInline(admin.TabularInline):
    model           = EventCollaborator
    fk_name         = 'event'
    extra           = 0
    autocomplete_fields = ('organizer',)
    readonly_fields = ('added_by', 'added_at')
    fields          = ('organizer', 'added_by', 'added_at')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display    = (
        'title', 'organizer', 'category', 'status',
        'is_featured', 'starts_at', 'venue', 'created_at',
    )
    list_filter     = ('status', 'is_featured', 'category', 'venue__city')
    list_editable   = ('is_featured', 'status')
    search_fields   = ('title', 'slug', 'organizer__organization_name')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('organizer', 'category', 'venue', 'tags')
    readonly_fields = ('created_at', 'updated_at', 'banner_display')
    date_hierarchy  = 'starts_at'
    inlines         = [EventCollaboratorInline]
    fieldsets       = (
        (_('Identity'), {
            'fields': ('title', 'slug', 'organizer', 'category', 'tags'),
        }),
        (_('Content'), {
            'fields': ('description', 'banner', 'banner_display'),
        }),
        (_('Schedule'), {
            'fields': ('timezone', 'starts_at', 'ends_at'),
        }),
        (_('Venue'), {
            'fields': ('venue',),
        }),
        (_('Status & Capacity'), {
            'fields': ('status', 'is_featured', 'max_capacity'),
        }),
        (_('SEO Overrides'), {
            'fields': ('seo_title', 'seo_description'),
            'classes': ('collapse',),
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'organizer', 'category', 'venue'
        )


@admin.register(EventDraft)
class EventDraftAdmin(admin.ModelAdmin):
    list_display    = ('organizer', 'step_reached', 'event', 'created_at', 'updated_at')
    readonly_fields = ('organizer', 'event', 'step_reached', 'step_data', 'created_at', 'updated_at')
    search_fields   = ('organizer__organization_name',)

    def has_add_permission(self, request):
        return False