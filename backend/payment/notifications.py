"""Payment Hub notifications."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_payment_rejection(
    *,
    account_set_id: str,
    payment_id: str,
    created_by: str,
    reason: str,
    stage: str,
) -> None:
    logger.info(
        "Payment rejection notification payment=%s user=%s stage=%s: %s",
        payment_id,
        created_by,
        stage,
        reason,
    )
