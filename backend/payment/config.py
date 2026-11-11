"""Payment Hub configuration."""

DEFAULT_DUAL_AUTH_THRESHOLD = 10000.0

# Per-account-set overrides (tests / runtime config)
_dual_auth_thresholds: dict[str, float] = {}


def get_dual_auth_threshold(account_set_id: str) -> float:
    return _dual_auth_thresholds.get(account_set_id, DEFAULT_DUAL_AUTH_THRESHOLD)


def set_dual_auth_threshold(account_set_id: str, threshold: float) -> None:
    _dual_auth_thresholds[account_set_id] = threshold
