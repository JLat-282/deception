from __future__ import annotations


class DomainError(Exception):
    """An expected game or API failure with a stable public code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class GuessValidationError(ValueError):
    """A pure-engine validation failure mapped at the service boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

