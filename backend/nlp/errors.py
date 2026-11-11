"""NLP Assistant errors."""

from __future__ import annotations


class NLPError(Exception):
    code: str = "nlp_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class UnauthorizedActionError(NLPError):
    code = "unauthorized_action"


class ConfirmationRequiredError(NLPError):
    code = "confirmation_required"
