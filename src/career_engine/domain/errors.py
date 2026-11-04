"""Typed business errors; transports map `code` to HTTP statuses or CLI exit codes."""


class DomainError(Exception):
    code = "DOMAIN_ERROR"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ValidationFailed(DomainError):
    code = "VALIDATION_FAILED"


class NotFound(DomainError):
    code = "NOT_FOUND"


class Conflict(DomainError):
    code = "CONFLICT"


class InvalidTransition(DomainError):
    code = "INVALID_TRANSITION"


class IntegrityFailure(DomainError):
    code = "INTEGRITY_FAILURE"
