"""Bank Integration errors."""


class BankError(Exception):
    code: str = "bank_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class BankConnectionError(BankError):
    code = "connection_error"


class RoutingValidationError(BankError):
    code = "routing_validation_error"
