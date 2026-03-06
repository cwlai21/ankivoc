import time
from django.utils.deprecation import MiddlewareMixin


class RequestLoggerMiddleware(MiddlewareMixin):
    """Simple middleware to log incoming requests to backend/django.log."""

    def process_request(self, request):
        try:
            user = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
        except Exception:
            user = 'unknown'

        method = request.method
        path = request.get_full_path()
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        # Attempt to capture username from POST payload if present
        username_field = ''
        if method == 'POST':
            try:
                username_field = request.POST.get('username', '')
            except Exception:
                username_field = ''

        line = f"{ts} {method} {path} user={user} form_username={username_field}\n"
        try:
            with open(__file__.rsplit('/', 2)[0] + '/django.log', 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass
