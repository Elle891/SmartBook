"""Report Engine errors."""


class ReportError(Exception):
    code: str = "report_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class StandardMismatchError(ReportError):
    code = "standard_mismatch"


class MethodNotSupportedError(ReportError):
    code = "method_not_supported"


class ReportTimeoutError(ReportError):
    code = "report_timeout"


class ReportValidationError(ReportError):
    code = "validation_error"
