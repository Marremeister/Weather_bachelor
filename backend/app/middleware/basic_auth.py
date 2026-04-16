import base64
import binascii
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

_REALM = 'Basic realm="Sea Breeze Analog"'


def _unauthorized() -> Response:
    return Response(status_code=401, headers={"WWW-Authenticate": _REALM})


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Gate the entire app behind a single shared HTTP Basic Auth password.

    - If settings.site_password is empty, the middleware is a no-op (local dev).
    - CORS preflight (OPTIONS) requests are allowed through without credentials.
    - Username is ignored; only the password is checked.
    - Password comparison uses secrets.compare_digest (constant-time).
    """

    async def dispatch(self, request: Request, call_next):
        expected = settings.site_password

        # Auth disabled: pass through (local dev convenience).
        if not expected:
            return await call_next(request)

        # Let CORS preflight through so browsers can complete the handshake.
        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        scheme, _, credentials = auth_header.partition(" ")
        if scheme.lower() != "basic" or not credentials:
            return _unauthorized()

        try:
            decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return _unauthorized()

        # "username:password" — username is ignored.
        _, sep, provided_password = decoded.partition(":")
        if not sep:
            return _unauthorized()

        if not secrets.compare_digest(provided_password, expected):
            return _unauthorized()

        return await call_next(request)
