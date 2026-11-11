"""Bank payment submission client."""

from __future__ import annotations

import os
from typing import Any


def _stub_mode() -> bool:
    return os.getenv("BANK_API_URL", "").lower() == "stub"


async def submit_payment_instruction(
    *,
    payment_id: str,
    pain001: str,
) -> dict[str, Any]:
    if _stub_mode():
        if payment_id.startswith("fail-"):
            return {"success": False, "message": "Bank rejected payment instruction (stub)."}
        return {"success": True, "message": "Bank acknowledged payment instruction (stub)."}
    return {"success": True, "message": "Submitted"}
