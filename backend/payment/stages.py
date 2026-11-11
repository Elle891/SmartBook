"""
Payment workflow stages, role enforcement, and transition rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auth.rbac import (
    ROLE_ACCOUNT_SET_ADMIN,
    ROLE_CASHIER,
    ROLE_SUPERVISOR,
    ROLE_VOUCHER_CLERK,
)

STAGE_PREPARE = "Prepare"
STAGE_INSTRUCTED = "Instructed"
STAGE_CHECKED = "Checked"
STAGE_PENDING_SECOND = "PendingSecondAuth"
STAGE_AUTHORISED = "Authorised"
STAGE_CONFIRMED = "Confirmed"
STAGE_SETTLED = "Settled"

SEQUENTIAL_STAGES = [
    STAGE_PREPARE,
    STAGE_INSTRUCTED,
    STAGE_CHECKED,
    STAGE_AUTHORISED,
    STAGE_CONFIRMED,
    STAGE_SETTLED,
]

ACTION_INSTRUCT = "instruct"
ACTION_CHECK_APPROVE = "check_approve"
ACTION_CHECK_REJECT = "check_reject"
ACTION_AUTHORISE = "authorise"
ACTION_CONFIRM = "confirm"
ACTION_SETTLE = "settle"

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STAGE_PREPARE: {STAGE_INSTRUCTED},
    STAGE_INSTRUCTED: {STAGE_CHECKED, STAGE_PREPARE},
    STAGE_CHECKED: {STAGE_AUTHORISED, STAGE_PENDING_SECOND, STAGE_PREPARE},
    STAGE_PENDING_SECOND: {STAGE_AUTHORISED},
    STAGE_AUTHORISED: {STAGE_CONFIRMED, STAGE_PREPARE},
    STAGE_CONFIRMED: {STAGE_SETTLED, STAGE_PREPARE},
    STAGE_SETTLED: set(),
}

ACTION_TRANSITIONS: dict[str, tuple[str, str]] = {
    ACTION_INSTRUCT: (STAGE_PREPARE, STAGE_INSTRUCTED),
    ACTION_CHECK_APPROVE: (STAGE_INSTRUCTED, STAGE_CHECKED),
    ACTION_CHECK_REJECT: (STAGE_INSTRUCTED, STAGE_PREPARE),
    ACTION_CONFIRM: (STAGE_AUTHORISED, STAGE_CONFIRMED),
    ACTION_SETTLE: (STAGE_CONFIRMED, STAGE_SETTLED),
}

ROLE_INSTRUCT = {ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR, ROLE_VOUCHER_CLERK, ROLE_CASHIER}
ROLE_REVIEWER = {ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR}
ROLE_AUTHORISER = {ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR}

ACTION_REQUIRED_ROLES: dict[str, set[str]] = {
    ACTION_INSTRUCT: ROLE_INSTRUCT,
    ACTION_CHECK_APPROVE: ROLE_REVIEWER,
    ACTION_CHECK_REJECT: ROLE_REVIEWER,
    ACTION_AUTHORISE: ROLE_AUTHORISER,
    ACTION_CONFIRM: ROLE_AUTHORISER,
    ACTION_SETTLE: ROLE_AUTHORISER,
}


class WorkflowError(Exception):
    code: str = "workflow_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass
class StageModeMap:
    prepare_mode: str = "Auto"
    instruct_mode: str = "Manual"
    check_mode: str = "Auto"
    authorise_mode: str = "Manual"
    confirm_mode: str = "Auto"
    settle_mode: str = "Manual"

    @classmethod
    def from_transaction_type(cls, txn_type: Any) -> StageModeMap:
        return cls(
            prepare_mode=txn_type.prepare_mode,
            instruct_mode=txn_type.instruct_mode,
            check_mode=txn_type.check_mode,
            authorise_mode=txn_type.authorise_mode,
            confirm_mode=txn_type.confirm_mode,
            settle_mode=txn_type.settle_mode,
        )

    def mode_for_stage(self, stage: str) -> str:
        return {
            STAGE_PREPARE: self.prepare_mode,
            STAGE_INSTRUCTED: self.instruct_mode,
            STAGE_CHECKED: self.check_mode,
            STAGE_AUTHORISED: self.authorise_mode,
            STAGE_PENDING_SECOND: self.authorise_mode,
            STAGE_CONFIRMED: self.confirm_mode,
            STAGE_SETTLED: self.settle_mode,
        }.get(stage, "Manual")


def is_transition_allowed(from_stage: str, to_stage: str) -> bool:
    return to_stage in ALLOWED_TRANSITIONS.get(from_stage, set())


def validate_role_for_action(action: str, role: str) -> None:
    allowed = ACTION_REQUIRED_ROLES.get(action, set())
    if role not in allowed:
        raise WorkflowError(
            f"Role '{role}' cannot perform action '{action}'.",
            details={"action": action, "role": role},
        )


def validate_transition(from_stage: str, to_stage: str, *, action: str, role: str) -> None:
    if not is_transition_allowed(from_stage, to_stage):
        raise WorkflowError(
            f"Transition {from_stage} → {to_stage} is not allowed.",
            details={"from_stage": from_stage, "to_stage": to_stage, "action": action},
        )
    validate_role_for_action(action, role)


def authorise_target_stage(
    *,
    amount: float,
    threshold: float,
    current_stage: str,
    first_authoriser_id: str | None,
    user_id: str,
) -> str:
    """Return next stage for authorise action (Property 26)."""
    if current_stage == STAGE_PENDING_SECOND:
        if first_authoriser_id and first_authoriser_id == user_id:
            raise WorkflowError(
                "Second authoriser must differ from the first authoriser.",
                details={"standard_reference": "dual_auth"},
            )
        return STAGE_AUTHORISED

    if current_stage != STAGE_CHECKED:
        raise WorkflowError(
            f"Cannot authorise payment in stage {current_stage}.",
            details={"stage": current_stage},
        )

    if amount >= threshold:
        return STAGE_PENDING_SECOND
    return STAGE_AUTHORISED


def next_auto_stages(
    modes: StageModeMap,
    *,
    from_stage: str,
) -> list[str]:
    """
    Stages that should auto-advance immediately after *from_stage* completes.
    Property 27: Auto stages chain until a Manual stage is reached.
    """
    order_after: dict[str, list[str]] = {
        STAGE_PREPARE: [STAGE_INSTRUCTED, STAGE_CHECKED, STAGE_AUTHORISED, STAGE_CONFIRMED, STAGE_SETTLED],
        STAGE_INSTRUCTED: [STAGE_CHECKED, STAGE_AUTHORISED, STAGE_CONFIRMED, STAGE_SETTLED],
        STAGE_CHECKED: [STAGE_AUTHORISED, STAGE_CONFIRMED, STAGE_SETTLED],
        STAGE_AUTHORISED: [STAGE_CONFIRMED, STAGE_SETTLED],
        STAGE_CONFIRMED: [STAGE_SETTLED],
    }
    chain: list[str] = []
    for stage in order_after.get(from_stage, []):
        if modes.mode_for_stage(stage) == "Auto":
            chain.append(stage)
        else:
            break
    return chain
