"""
Domain error taxonomy.

Services raise these; exactly one handler maps them to HTTP. No service
imports `fastapi`, which is what keeps the business layer testable without a
web framework and reusable from a worker.
"""


class DomainError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(DomainError):
    status_code = 401
    code = "authentication_failed"


class PermissionDeniedError(DomainError):
    status_code = 403
    code = "permission_denied"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(DomainError):
    status_code = 413
    code = "payload_too_large"


class RateLimitedError(DomainError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(DomainError):
    status_code = 503
    code = "service_unavailable"


class AIServiceUnavailableError(ServiceUnavailableError):
    """Structured 503 when the configured AI endpoint cannot serve the request."""

    code = "AI_SERVICE_UNAVAILABLE"

    def __init__(
        self,
        message: str = "The configured AI service is currently unavailable.",
        *,
        provider: str,
        retryable: bool = True,
        reason: str | None = None,
    ) -> None:
        details: dict = {"provider": provider, "retryable": retryable}
        if reason:
            details["reason"] = reason
        super().__init__(message, details=details)
        self.provider = provider
        self.retryable = retryable
