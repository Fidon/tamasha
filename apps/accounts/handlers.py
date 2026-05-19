from django.http import JsonResponse
from django.shortcuts import render


def axes_lockout_handler(request, credentials, *args, **kwargs):
    """
    Called by django-axes when a user exceeds AXES_FAILURE_LIMIT.
    Returns JSON for AJAX login attempts, HTML for standard form submissions.
    """
    message = (
        'Your account has been temporarily locked due to too many failed '
        'login attempts. Please try again in 1 hour.'
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': message}, status=403)

    return render(request, 'accounts/lockout.html', {'message': message}, status=403)