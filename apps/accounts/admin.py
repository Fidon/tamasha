from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, OrganizerProfile


class OrganizerProfileInline(admin.StackedInline):
    model               = OrganizerProfile
    fk_name             = 'user'
    can_delete          = False
    verbose_name_plural = _('Organizer Profile')
    fields              = ('organization_name', 'bio', 'website', 'approved_at', 'approved_by')
    readonly_fields     = ('approved_at', 'approved_by')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines         = [OrganizerProfileInline]
    ordering        = ['-date_joined']
    list_display    = (
        'email', 'full_name', 'phone',
        'is_organizer', 'organizer_status',
        'email_verified', 'is_active', 'is_staff', 'date_joined',
    )
    list_filter     = ('is_active', 'is_staff', 'is_organizer', 'organizer_status', 'email_verified')
    search_fields   = ('email', 'full_name', 'phone')
    readonly_fields = ('date_joined', 'email_verified_at', 'last_login')

    fieldsets = (
        (None, {
            'fields': ('email', 'password'),
        }),
        (_('Personal info'), {
            'fields': ('full_name', 'phone', 'avatar'),
        }),
        (_('Organizer'), {
            'fields': ('is_organizer', 'organizer_status'),
        }),
        (_('Preferences'), {
            'fields': ('theme_preference',),
        }),
        (_('Verification'), {
            'fields': ('email_verified', 'email_verified_at'),
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined'),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2'),
        }),
    )


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display    = ('organization_name', 'user', 'approved_at', 'approved_by')
    search_fields   = ('organization_name', 'user__email')
    readonly_fields = ('approved_at', 'approved_by')