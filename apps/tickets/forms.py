"""
apps/tickets/forms.py

Checkout form — buyer info + payment method.
Ticket quantity selection is handled via JS on the checkout page
and submitted as JSON, not through this form.
"""
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Order


class CheckoutBuyerForm(forms.Form):
    """
    Collects buyer contact info.
    Pre-filled for authenticated users; fully editable for guests.
    """
    full_name = forms.CharField(
        max_length=255,
        label=_('Full Name'),
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'placeholder':  'e.g. John Mwangi',
            'autocomplete': 'name',
        }),
    )
    email = forms.EmailField(
        label=_('Email Address'),
        widget=forms.EmailInput(attrs={
            'class':        'form-control',
            'placeholder':  'you@example.com',
            'autocomplete': 'email',
        }),
    )
    phone = forms.CharField(
        max_length=30,
        label=_('Phone Number'),
        help_text=_(
            'Include country code, e.g. +255712345678. '
            'Used for mobile money payment and ticket delivery.'
        ),
        widget=forms.TextInput(attrs={
            'class':        'form-control',
            'placeholder':  '+255712345678',
            'autocomplete': 'tel',
            'inputmode':    'tel',
        }),
    )
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        choices=[
            (Order.PaymentMethod.MOBILE_MONEY, _('Mobile Money (Airtel, Tigo, Halopesa, Mpesa)')),
            (Order.PaymentMethod.CARD,         _('Bank Card (CRDB, NMB, NBC, etc.)')),
        ],
        widget=forms.RadioSelect(),
        initial=Order.PaymentMethod.MOBILE_MONEY,
    )
    # Mobile money network — shown/required only when MOBILE_MONEY selected
    mobile_network = forms.ChoiceField(
        label=_('Mobile Network'),
        required=False,
        choices=[
            ('',          _('Select network')),
            ('Airtel',    'Airtel Money'),
            ('Tigo',      'Tigo Pesa'),
            ('Halopesa',  'Halopesa'),
            ('Mpesa',     'M-Pesa'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean(self):
        cleaned = super().clean()
        method  = cleaned.get('payment_method')
        network = cleaned.get('mobile_network')

        if method == Order.PaymentMethod.MOBILE_MONEY and not network:
            self.add_error('mobile_network', _('Please select your mobile network.'))

        return cleaned

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        # Strip spaces and dashes
        phone = phone.replace(' ', '').replace('-', '')
        if not phone:
            raise forms.ValidationError(_('Phone number is required.'))
        # Must be exactly 10 digits starting with 0
        if not phone.startswith('0') or not phone.isdigit() or len(phone) != 10:
            raise forms.ValidationError(
                _('Enter a valid 10-digit phone number starting with 0, e.g. 0784561427.')
            )
        return phone

    def clean_full_name(self):
        return self.cleaned_data['full_name'].strip()