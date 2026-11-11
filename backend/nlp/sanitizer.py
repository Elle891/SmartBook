"""Response sanitization — strip credentials and internal details (Req 24.13)."""

from __future__ import annotations

import re

_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(vault|credentials_vault_path)[^\s]*[/:]\S+"),
    re.compile(r"(?i)(postgresql|mysql)://\S+"),
    re.compile(r"(?i)\bSELECT\b.+\bFROM\b.+\bWHERE\b", re.DOTALL),
    re.compile(r"/account-sets/[0-9a-f-]{36}/[a-z-]+"),
    re.compile(r"(?i)bank-routing/\S+"),
)


def contains_sensitive_data(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def sanitize_response(text: str) -> str:
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[redacted]", sanitized)
    return sanitized
