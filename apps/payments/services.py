"""
apps/payments/services.py

AzamPay integration — token fetch, USSD push, card checkout, callback handling.
"""
import logging
import ssl
import uuid
from decimal import Decimal

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AzamPay endpoints
# ---------------------------------------------------------------------------
_BASE             = settings.AZAMPAY_BASE_URL.rstrip('/')
_TOKEN_URL        = getattr(
    settings, 'AZAMPAY_TOKEN_URL',
    'https://authenticator-sandbox.azampay.co.tz/AppRegistration/GenerateToken'
)
_MOBILE_URL       = f'{_BASE}/azampay/mno/checkout'
_CARD_URL         = f'{_BASE}/azampay/api/Partner/GenerateToken'
_CALLBACK_URL     = getattr(settings, 'AZAMPAY_CALLBACK_URL', '')
_REQUEST_TIMEOUT  = 30   # seconds — default
_MNO_TIMEOUT      = 12   # seconds — MNO times out but payment still processes async


# ---------------------------------------------------------------------------
# TLS adapter
# ---------------------------------------------------------------------------

class _TLSAdapter(HTTPAdapter):
    """Force TLS 1.2+ for AzamPay connections."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = ctx
        super().init_poolmanager(*args, **kwargs)


def _session() -> requests.Session:
    s = requests.Session()
    s.mount('https://', _TLSAdapter())
    return s


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

def _fetch_token() -> str:
    """
    Fetch a bearer token from AzamPay auth endpoint.
    Always hits the endpoint — the portal 'Token' field is the apiKey parameter.
    """
    payload = {
        'appName':      settings.AZAMPAY_APP_NAME,
        'clientId':     settings.AZAMPAY_CLIENT_ID,
        'clientSecret': settings.AZAMPAY_CLIENT_SECRET,
        'apiKey':       getattr(settings, 'AZAMPAY_TOKEN', ''),
    }
    try:
        resp = _session().post(_TOKEN_URL, json=payload, timeout=_REQUEST_TIMEOUT)
        raw  = resp.text.strip()
        logger.debug('AzamPay token response: status=%s body=%s', resp.status_code, raw[:300])

        if not raw:
            raise ValidationError(_('AzamPay token endpoint returned empty response.'))

        data  = resp.json()
        token = (
            (data.get('data') or {}).get('accessToken')
            or data.get('accessToken')
            or data.get('token')
        )
        if not token:
            raise ValidationError(
                _('AzamPay authentication failed: %(msg)s') % {
                    'msg': data.get('message', 'Unknown error')
                }
            )
        logger.debug('AzamPay token fetched successfully.')
        return token

    except requests.RequestException as exc:
        logger.error('AzamPay token fetch failed: %s', exc)
        raise ValidationError(_('Could not connect to payment provider. Please try again.'))


# ---------------------------------------------------------------------------
# USSD push (mobile money)
# ---------------------------------------------------------------------------

def initiate_mobile_payment(*, order, phone: str, provider: str = 'Airtel') -> dict:
    """
    Initiate a USSD push payment for a mobile money order.
    AzamPay sandbox often times out on the HTTP response but processes the
    payment async and fires a callback — timeout is treated as PENDING.
    """
    from apps.payments.models import Transaction

    token        = _fetch_token()
    internal_ref = str(uuid.uuid4())

    payload = {
        'accountNumber': phone,
        'amount':        str(int(order.gross_amount)),
        'currency':      'TZS',
        'externalId':    internal_ref,
        'provider':      provider,
    }
    logger.debug('AzamPay USSD payload: %s', payload)

    txn = Transaction.objects.create(
        order        = order,
        provider     = Transaction.Provider.AZAMPAY_MOBILE,
        internal_ref = internal_ref,
        status       = Transaction.Status.INITIATED,
        amount       = order.gross_amount,
        currency     = 'TZS',
        phone        = phone,
        raw_request  = payload,
    )

    try:
        resp = _session().post(
            _MOBILE_URL,
            json=payload,
            headers={
                'Authorization': f'Bearer {token}',
                'X-API-KEY':     getattr(settings, 'AZAMPAY_TOKEN', ''),
                'Content-Type':  'application/json',
                'Accept':        'application/json',
            },
            timeout=_MNO_TIMEOUT,
        )

        raw = resp.text.strip()

        # AzamPay sandbox returns HTTP 200 with empty body on successful USSD push
        if resp.status_code == 200 and not raw:
            txn.status = Transaction.Status.PENDING
            txn.save(update_fields=['status', 'updated_at'])
            return {
                'success':        True,
                'message':        str(_('Payment prompt sent to your phone. Enter your PIN to complete.')),
                'transaction_id': str(txn.internal_ref),
            }

        if not raw:
            logger.error('AzamPay USSD: empty response. Status=%s order=%s', resp.status_code, order.reference)
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status', 'updated_at'])
            return {'success': False, 'message': str(_('Payment provider returned no response. Please try again.'))}

        try:
            data = resp.json()
        except ValueError:
            logger.error('AzamPay USSD: non-JSON. Status=%s body=%s', resp.status_code, raw[:200])
            txn.status = Transaction.Status.FAILED
            txn.save(update_fields=['status', 'updated_at'])
            return {'success': False, 'message': str(_('Payment provider error. Please try again.'))}

        success = resp.status_code == 200 and data.get('success', False)
        txn.status       = Transaction.Status.PENDING if success else Transaction.Status.FAILED
        txn.raw_callback = data
        txn.save(update_fields=['status', 'raw_callback', 'updated_at'])

        if success:
            return {
                'success':        True,
                'message':        str(_('Payment prompt sent to your phone. Enter your PIN to complete.')),
                'transaction_id': str(txn.internal_ref),
            }

        msg = data.get('message') or str(_('Payment initiation failed. Please try again.'))
        return {'success': False, 'message': msg}

    except requests.exceptions.ReadTimeout:
        # AzamPay sandbox times out on HTTP but processes async and fires callback.
        logger.info('AzamPay MNO timed out for order %s — treating as PENDING.', order.reference)
        txn.status = Transaction.Status.PENDING
        txn.save(update_fields=['status', 'updated_at'])
        return {
            'success': True,
            'message': str(_(
                'Payment request sent. Check your phone for the payment prompt '
                'and enter your PIN to complete.'
            )),
            'transaction_id': str(txn.internal_ref),
        }

    except requests.RequestException as exc:
        logger.error('AzamPay USSD push failed for order %s: %s', order.reference, exc)
        txn.status = Transaction.Status.FAILED
        txn.save(update_fields=['status', 'updated_at'])
        return {'success': False, 'message': str(_('Payment request failed. Please try again.'))}


# ---------------------------------------------------------------------------
# Card checkout (hosted redirect)
# ---------------------------------------------------------------------------

def initiate_card_payment(*, order, callback_url: str = '', redirect_url: str) -> dict:
    """
    Generate an AzamPay hosted checkout URL for bank card payment.
    callback_url defaults to AZAMPAY_CALLBACK_URL from settings.
    """
    if not callback_url:
        callback_url = _CALLBACK_URL

    token        = _fetch_token()
    internal_ref = str(uuid.uuid4())

    payload = {
        'merchantId':  settings.AZAMPAY_CLIENT_ID,
        'amount':      str(int(order.gross_amount)),
        'currency':    'TZS',
        'externalId':  internal_ref,
        'callbackUrl': callback_url,
        'redirectUrl': redirect_url,
        'language':    'SW',
        'vendorName':  settings.AZAMPAY_APP_NAME,
    }

    from apps.payments.models import Transaction
    txn = Transaction.objects.create(
        order        = order,
        provider     = Transaction.Provider.AZAMPAY_CARD,
        internal_ref = internal_ref,
        status       = Transaction.Status.INITIATED,
        amount       = order.gross_amount,
        currency     = 'TZS',
        raw_request  = payload,
    )

    try:
        resp = _session().post(
            _CARD_URL,
            json=payload,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type':  'application/json',
            },
            timeout=_REQUEST_TIMEOUT,
        )
        data = resp.json()
    except requests.RequestException as exc:
        logger.error('AzamPay card checkout failed for order %s: %s', order.reference, exc)
        txn.status = Transaction.Status.FAILED
        txn.save(update_fields=['status', 'updated_at'])
        return {'success': False, 'checkout_url': None, 'message': str(_('Could not connect to payment provider.'))}

    checkout_url = (data.get('data') or {}).get('url') or data.get('url')
    success      = bool(checkout_url)

    txn.status       = Transaction.Status.PENDING if success else Transaction.Status.FAILED
    txn.raw_callback = data
    txn.save(update_fields=['status', 'raw_callback', 'updated_at'])

    if success:
        return {'success': True, 'checkout_url': checkout_url, 'message': ''}

    msg = data.get('message') or str(_('Could not generate checkout link. Please try again.'))
    return {'success': False, 'checkout_url': None, 'message': msg}


# ---------------------------------------------------------------------------
# Webhook / callback handling
# ---------------------------------------------------------------------------

def handle_payment_callback(payload: dict) -> bool:
    """
    Process AzamPay's async callback POST.
    AzamPay sandbox sends our internal reference in 'utilityref'.
    """
    from apps.payments.models import Transaction

    # AzamPay sandbox sends our externalId back in 'utilityref'
    internal_ref = (
        payload.get('utilityref') or
        payload.get('externalId') or
        payload.get('external_id') or
        ''
    ).strip()

    provider_ref = (
        payload.get('transid') or
        payload.get('transactionId') or
        payload.get('reference') or
        ''
    ).strip()

    if not internal_ref:
        logger.warning('AzamPay callback missing internal ref: %s', payload)
        return False

    try:
        txn = Transaction.objects.select_related('order').get(internal_ref=internal_ref)
    except Transaction.DoesNotExist:
        logger.warning('AzamPay callback: no transaction for ref=%s', internal_ref)
        return False

    if txn.status == Transaction.Status.SUCCESS:
        logger.info('Duplicate callback for txn %s — ignored.', internal_ref)
        return True

    status_str = (
        payload.get('transactionstatus') or
        payload.get('status') or
        ''
    ).lower()
    is_success = status_str in ('success', 'successful', 'completed', '200')

    txn.raw_callback = payload
    if provider_ref:
        txn.provider_ref = provider_ref

    if is_success:
        txn.status = Transaction.Status.SUCCESS
        txn.save(update_fields=['status', 'provider_ref', 'raw_callback', 'updated_at'])
        from apps.tickets.tasks import confirm_paid_order
        confirm_paid_order.delay(txn.order.pk)
        logger.info('Payment confirmed for order %s via callback.', txn.order.reference)
    else:
        txn.status = Transaction.Status.FAILED
        txn.save(update_fields=['status', 'provider_ref', 'raw_callback', 'updated_at'])

    return True


# ---------------------------------------------------------------------------
# Payment status polling
# ---------------------------------------------------------------------------

def get_payment_status(order) -> dict:
    """Return the latest transaction status for an order."""
    from apps.payments.models import Transaction

    txn = (
        Transaction.objects
        .filter(order=order)
        .order_by('-created_at')
        .first()
    )
    if not txn:
        return {'status': 'NOT_FOUND', 'confirmed': False}

    # Check transaction success OR order already confirmed
    confirmed = (
        txn.status == Transaction.Status.SUCCESS
        or order.status in ('PAID', 'FREE')
    )

    # If transaction succeeded but order not yet updated (Celery lag),
    # confirm the order synchronously here so the user isn't stuck
    if txn.status == Transaction.Status.SUCCESS and order.status == 'PENDING':
        try:
            from apps.tickets.services import confirm_order
            # Refresh order from DB to get latest status
            order.refresh_from_db()
            if order.status == 'PENDING':
                confirm_order(order)
                confirmed = True
        except Exception:
            logger.exception('Inline order confirmation failed for order %s', order.pk)

    return {
        'status':    txn.status,
        'confirmed': confirmed,
    }