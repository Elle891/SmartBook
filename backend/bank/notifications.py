"""
Finance user notifications for bank connectivity events (Req 10.5, 25.8).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_pending_notifications: list[dict] = []


def notify_finance_users(
    *,
    account_set_id: str,
    event: str,
    message: str,
    connection_id: str | None = None,
) -> None:
    payload = {
        "account_set_id": account_set_id,
        "event": event,
        "message": message,
        "connection_id": connection_id,
    }
    _pending_notifications.append(payload)
    logger.info("Bank notification [%s] account_set=%s: %s", event, account_set_id, message)


def drain_notifications() -> list[dict]:
    items = list(_pending_notifications)
    _pending_notifications.clear()
    return items
