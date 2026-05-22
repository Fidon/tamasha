from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, OrganizerProfile, OrganizerRequest
from .services import approve_organizer_request, reject_organizer_request
from .tasks import (
    send_organizer_approved_notifications,
    send_organizer_rejected_notifications,
)


class OrganizerProfileInline(admin.StackedInline):
    model               = OrganizerProfile
    fk_name             = 'user'
    can_delete          = False
    verbose_name_plural = _('Organizer Profile')
    fields              = ('organization_name', 'bio', 'website', 'approved_at', 'approved_by')
    readonly_fields     = ('approved_at', 'approved_by')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines       = [OrganizerProfileInline]
    ordering      = ['-date_joined']
    list_display  = (
        'email', 'full_name', 'phone',
        'is_organizer', 'organizer_status',
        'email_verified', 'is_active', 'is_staff', 'date_joined',
    )
    list_filter   = ('is_active', 'is_staff', 'is_organizer', 'organizer_status', 'email_verified')
    search_fields = ('email', 'full_name', 'phone')
    readonly_fields = ('date_joined', 'email_verified_at', 'last_login', 'email_verification_token')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'phone', 'avatar')}),
        (_('Organizer'), {'fields': ('is_organizer', 'organizer_status')}),
        (_('Preferences'), {'fields': ('theme_preference',)}),
        (_('Verification'), {'fields': ('email_verified', 'email_verified_at', 'email_verification_token')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields':  ('email', 'full_name', 'password1', 'password2'),
        }),
    )


@admin.register(OrganizerProfile)
class OrganizerProfileAdmin(admin.ModelAdmin):
    list_display    = ('organization_name', 'user', 'approved_at', 'approved_by')
    search_fields   = ('organization_name', 'user__email')
    readonly_fields = ('approved_at', 'approved_by')


class RejectionReasonFilter(admin.SimpleListFilter):
    title        = _('has rejection reason')
    parameter_name = 'has_reason'

    def lookups(self, request, model_admin):
        return [('yes', _('Yes')), ('no', _('No'))]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(rejection_reason='')
        if self.value() == 'no':
            return queryset.filter(rejection_reason='')
        return queryset


@admin.register(OrganizerRequest)
class OrganizerRequestAdmin(admin.ModelAdmin):
    list_display    = (
        'user', 'organization_name', 'status',
        'submitted_at', 'reviewed_at', 'reviewed_by',
    )
    list_filter     = ('status', RejectionReasonFilter)
    search_fields   = ('user__email', 'organization_name', 'pitch')
    readonly_fields = ('submitted_at', 'reviewed_at', 'reviewed_by')
    ordering        = ['-submitted_at']
    actions         = ['approve_requests', 'reject_requests']

    @admin.display(description=_('Approve selected requests'))
    def approve_requests(self, request, queryset):
        pending = queryset.filter(status=OrganizerRequest.Status.PENDING)
        count   = 0
        for org_request in pending.select_related('user'):
            approve_organizer_request(org_request, reviewed_by=request.user)
            send_organizer_approved_notifications.delay(org_request.user.pk)
            count += 1
        self.message_user(request, _(f'{count} request(s) approved successfully.'))

    @admin.display(description=_('Reject selected requests'))
    def reject_requests(self, request, queryset):
        """
        Bulk rejection is intentionally blocked — each rejection requires
        an individual reason. Admin must use the change form per request.
        """
        self.message_user(
            request,
            _('To reject a request, open it individually and provide a rejection reason.'),
            level='warning',
        )

    def save_model(self, request, obj, form, change):
        """
        Handle approve/reject via the change form.
        Enforces rejection_reason when status is set to REJECTED.
        """
        if change:
            original = OrganizerRequest.objects.get(pk=obj.pk)
            if original.status == OrganizerRequest.Status.PENDING:

                if obj.status == OrganizerRequest.Status.APPROVED:
                    approve_organizer_request(obj, reviewed_by=request.user)
                    send_organizer_approved_notifications.delay(obj.user.pk)
                    return  # service layer saved the object

                if obj.status == OrganizerRequest.Status.REJECTED:
                    if not obj.rejection_reason.strip():
                        from django.core.exceptions import ValidationError
                        raise ValidationError(_('A rejection reason is required.'))
                    reject_organizer_request(
                        obj,
                        reviewed_by=request.user,
                        rejection_reason=obj.rejection_reason,
                    )
                    send_organizer_rejected_notifications.delay(
                        obj.user.pk, obj.rejection_reason
                    )
                    return  # service layer saved the object

        super().save_model(request, obj, form, change)