from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, OrganizerRequest


class SignupForm(forms.ModelForm):
    password1 = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label=_('Confirm password'),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model  = CustomUser
        fields = ('email', 'full_name', 'phone')
        
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            phone = phone.replace(' ', '')
            if len(phone) != 13 or not phone.startswith('+') or not phone[1:].isdigit():
                raise forms.ValidationError(_('Please enter a valid phone number (e.g., +255 713 000 000).'))
        return phone
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        names = full_name.split()
        if len(names) not in [2, 3]:
            raise forms.ValidationError(_("Full name must consist of exactly 2 or 3 names."))
            
        cleaned_names = []
        for name in names:
            if not name[0].isalpha():
                raise forms.ValidationError(_("The name '{name}' must start with a letter."))
                
            if len(name) < 3:
                raise forms.ValidationError(_("Each name must be at least 3 characters long ('{name}' is too short)."))
                
            cleaned_names.append(name.capitalize())
            
        return " ".join(cleaned_names)

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError(_('An account with this email already exists.'))
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', _('Passwords do not match.'))
        return cleaned

    def save(self, commit=True):
        # Never call super().save() here — use the service layer instead
        raise NotImplementedError(
            'Use accounts.services.register_user() instead of form.save().'
        )


class LoginForm(AuthenticationForm):
    """
    Extends Django's AuthenticationForm with email field label adjustment.
    django-axes hooks into this via AUTHENTICATION_BACKENDS.
    """
    username = forms.EmailField(
        label=_('Email address'),
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'autofocus': True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model  = CustomUser
        fields = ('full_name', 'phone', 'avatar')
        widgets = {
            'full_name': forms.TextInput(attrs={'autocomplete': 'name'}),
            'phone':     forms.TextInput(attrs={'autocomplete': 'tel'}),
        }
        
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            phone = phone.replace(' ', '')
            if len(phone) != 13 or not phone.startswith('+') or not phone[1:].isdigit():
                raise forms.ValidationError(_('Please enter a valid phone number (e.g., +255 713 000 000).'))
        return phone
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        names = full_name.split()
        if len(names) not in [2, 3]:
            raise forms.ValidationError(_("Full name must consist of exactly 2 or 3 names."))
            
        cleaned_names = []
        for name in names:
            if not name[0].isalpha():
                raise forms.ValidationError(_("The name '{name}' must start with a letter."))
                
            if len(name) < 3:
                raise forms.ValidationError(_("Each name must be at least 3 characters long ('{name}' is too short)."))
                
            cleaned_names.append(name.capitalize())
            
        return " ".join(cleaned_names)

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'size'):
            if avatar.size > 2 * 1024 * 1024:  # 2 MB
                raise forms.ValidationError(_('Avatar must be smaller than 2 MB.'))
            allowed = ('image/jpeg', 'image/png', 'image/webp')
            if hasattr(avatar, 'content_type') and avatar.content_type not in allowed:
                raise forms.ValidationError(_('Only JPEG, PNG, or WebP images are allowed.'))
        return avatar


class OrganizerRequestForm(forms.ModelForm):
    class Meta:
        model  = OrganizerRequest
        fields = ('organization_name', 'bio', 'phone', 'website', 'pitch')
        widgets = {
            'bio':   forms.Textarea(attrs={'rows': 4}),
            'pitch': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {
            'pitch': _('Why do you want to become an organizer?'),
        }
        help_texts = {
            'pitch': _('Tell us about the types of events you plan to host.'),
        }
        
    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone:
            phone = phone.replace(' ', '')
            if len(phone) != 13 or not phone.startswith('+') or not phone[1:].isdigit():
                raise forms.ValidationError(_('Please enter a valid phone number (e.g., +255 713 000 000).'))
        return phone

    def clean_organization_name(self):
        name = self.cleaned_data.get('organization_name', '').strip()
        if len(name) < 3:
            raise forms.ValidationError(_('Organization name must be at least 3 characters.'))
        return name

    def clean_pitch(self):
        pitch = self.cleaned_data.get('pitch', '').strip()
        if len(pitch) < 50:
            raise forms.ValidationError(_('Please write at least 50 characters about your plans.'))
        return pitch