"""
Property tests for Payment Hub workflow.

# Feature: smart-accounting-software, Properties 25–27
**Validates: Requirements 29.1, 29.7, 29.8, 30.6, 30.7 (Tasks 24.1–24.3)**
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from auth.rbac import ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR, ROLE_VIEWER
from payment.stages import (
    ACTION_AUTHORISE,
    ACTION_CHECK_APPROVE,
    ACTION_INSTRUCT,
    ALLOWED_TRANSITIONS,
    STAGE_AUTHORISED,
    STAGE_CHECKED,
    STAGE_CONFIRMED,
    STAGE_INSTRUCTED,
    STAGE_PENDING_SECOND,
    STAGE_PREPARE,
    StageModeMap,
    WorkflowError,
    authorise_target_stage,
    is_transition_allowed,
    next_auto_stages,
    validate_role_for_action,
    validate_transition,
)

_ALL_STAGES = list(ALLOWED_TRANSITIONS.keys()) + [STAGE_PENDING_SECOND]
_STAGE_ST = st.sampled_from(_ALL_STAGES)
_ROLE_ST = st.sampled_from([ROLE_ACCOUNT_SET_ADMIN, ROLE_SUPERVISOR, ROLE_VIEWER])
_AMOUNT = st.floats(min_value=0.01, max_value=500000.0, allow_nan=False)
_THRESHOLD = st.floats(min_value=1000.0, max_value=100000.0, allow_nan=False)


class TestProperty25SequentialRoleEnforced:
    @given(
        from_stage=_STAGE_ST,
        to_stage=_STAGE_ST,
        role=_ROLE_ST,
    )
    @settings(max_examples=80)
    def test_invalid_transitions_rejected(self, from_stage: str, to_stage: str, role: str) -> None:
        if is_transition_allowed(from_stage, to_stage):
            return
        with pytest.raises(WorkflowError):
            validate_transition(
                from_stage,
                to_stage,
                action=ACTION_INSTRUCT,
                role=ROLE_ACCOUNT_SET_ADMIN,
            )

    def test_viewer_cannot_instruct(self):
        with pytest.raises(WorkflowError):
            validate_role_for_action(ACTION_INSTRUCT, ROLE_VIEWER)

    def test_valid_instruct_transition_for_supervisor(self):
        validate_transition(
            STAGE_PREPARE,
            STAGE_INSTRUCTED,
            action=ACTION_INSTRUCT,
            role=ROLE_SUPERVISOR,
        )

    def test_reviewer_required_for_check(self):
        with pytest.raises(WorkflowError):
            validate_role_for_action(ACTION_CHECK_APPROVE, ROLE_VIEWER)
        validate_role_for_action(ACTION_CHECK_APPROVE, ROLE_SUPERVISOR)


class TestProperty26DualAuthorisation:
    @given(amount=_AMOUNT, threshold=_THRESHOLD)
    @settings(max_examples=50)
    def test_high_amount_requires_pending_second_auth(self, amount: float, threshold: float) -> None:
        if amount < threshold:
            assert (
                authorise_target_stage(
                    amount=amount,
                    threshold=threshold,
                    current_stage=STAGE_CHECKED,
                    first_authoriser_id=None,
                    user_id="user-a",
                )
                == STAGE_AUTHORISED
            )
        else:
            assert (
                authorise_target_stage(
                    amount=amount,
                    threshold=threshold,
                    current_stage=STAGE_CHECKED,
                    first_authoriser_id=None,
                    user_id="user-a",
                )
                == STAGE_PENDING_SECOND
            )

    def test_same_user_cannot_provide_second_auth(self):
        with pytest.raises(WorkflowError):
            authorise_target_stage(
                amount=50000.0,
                threshold=10000.0,
                current_stage=STAGE_PENDING_SECOND,
                first_authoriser_id="user-a",
                user_id="user-a",
            )

    def test_different_user_completes_second_auth(self):
        target = authorise_target_stage(
            amount=50000.0,
            threshold=10000.0,
            current_stage=STAGE_PENDING_SECOND,
            first_authoriser_id="user-a",
            user_id="user-b",
        )
        assert target == STAGE_AUTHORISED


class TestProperty27AutoVsManualStages:
    def test_standard_type_stops_auto_at_manual_instruct(self):
        modes = StageModeMap(
            prepare_mode="Auto",
            instruct_mode="Manual",
            check_mode="Auto",
            authorise_mode="Manual",
            confirm_mode="Auto",
            settle_mode="Manual",
        )
        assert next_auto_stages(modes, from_stage=STAGE_PREPARE) == []

    def test_all_auto_except_authorise_chains_through_checked_and_confirm(self):
        modes = StageModeMap(
            prepare_mode="Auto",
            instruct_mode="Auto",
            check_mode="Auto",
            authorise_mode="Manual",
            confirm_mode="Auto",
            settle_mode="Manual",
        )
        chain = next_auto_stages(modes, from_stage=STAGE_INSTRUCTED)
        assert chain == [STAGE_CHECKED]

    def test_manual_check_blocks_auto_chain(self):
        modes = StageModeMap(
            prepare_mode="Auto",
            instruct_mode="Auto",
            check_mode="Manual",
            authorise_mode="Manual",
            confirm_mode="Auto",
            settle_mode="Auto",
        )
        assert next_auto_stages(modes, from_stage=STAGE_INSTRUCTED) == []

    @given(
        check_mode=st.sampled_from(["Auto", "Manual"]),
        confirm_mode=st.sampled_from(["Auto", "Manual"]),
    )
    @settings(max_examples=20)
    def test_auto_chain_never_includes_manual_stage(
        self, check_mode: str, confirm_mode: str
    ) -> None:
        modes = StageModeMap(
            instruct_mode="Auto",
            check_mode=check_mode,
            authorise_mode="Manual",
            confirm_mode=confirm_mode,
            settle_mode="Manual",
        )
        chain = next_auto_stages(modes, from_stage=STAGE_INSTRUCTED)
        for stage in chain:
            assert modes.mode_for_stage(stage) == "Auto"
        if check_mode == "Manual":
            assert STAGE_CHECKED not in chain
        if confirm_mode == "Manual":
            assert STAGE_CONFIRMED not in chain
