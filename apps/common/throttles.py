from hashlib import sha256

from rest_framework.throttling import SimpleRateThrottle


def _request_email(request) -> str:
    try:
        data = request.data
    except Exception:  # pragma: no cover - defensive for malformed bodies
        return ""
    if isinstance(data, dict):
        return str(data.get("email", "")).strip().lower()
    return ""


class LoginThrottle(SimpleRateThrottle):
    scope = "login"

    def get_cache_key(self, request, view) -> str:
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class PasswordResetThrottle(SimpleRateThrottle):
    scope = "password_reset"

    def get_cache_key(self, request, view) -> str:
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class EmailResendThrottle(SimpleRateThrottle):
    scope = "email_resend"

    def get_cache_key(self, request, view) -> str:
        email = _request_email(request)
        identity = email or self.get_ident(request)
        digest = sha256(identity.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}


class EmailResendIPThrottle(SimpleRateThrottle):
    scope = "email_resend_ip"

    def get_cache_key(self, request, view) -> str:
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
