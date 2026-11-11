"""
Unit tests for Voucher Engine — balance validation, sequential numbering,
aux dimension enforcement, and approval event publishing.

_Requirements: 13.1–13.12 (Task 9.1)_
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from voucher.service import (
    STATUS_APPROVED,
    STATUS_DELETED,
    STATUS_DRAFT,
    STATUS_PENDING_REVIEW,
    _next_voucher_number,
    approve_voucher,
    create_voucher,
    delete_voucher,
    save_voucher,
    validate_aux_dimensions,
    validate_balance,
    validate_entry_sides,
)


# ── Balance validation (Requirements 13.3, 13.4) ─────────────────────────────


class TestBalanceValidation:
    def test_balanced_entries_pass(self):
        entries = [
            {"debit_amount": 100.0, "credit_amount": 0},
            {"debit_amount": 0, "credit_amount": 100.0},
        ]
        debits, credits = validate_balance(entries)
        assert debits == Decimal("100")
        assert credits == Decimal("100")

    def test_unbalanced_entries_include_imbalance_amount(self):
        entries = [
            {"debit_amount": 100.0, "credit_amount": 0},
            {"debit_amount": 0, "credit_amount": 60.0},
        ]
        with pytest.raises(HTTPException) as exc:
            validate_balance(entries)
        assert exc.value.status_code == 422
        detail = exc.value.detail
        assert detail["imbalance_amount"] == 40.0
        assert detail["total_debits"] == 100.0
        assert detail["total_credits"] == 60.0


class TestEntrySides:
    def test_requires_debit_and_credit_lines(self):
        with pytest.raises(HTTPException) as exc:
            validate_entry_sides(
                [
                    {"debit_amount": 50, "credit_amount": 0},
                    {"debit_amount": 50, "credit_amount": 0},
                ]
            )
        assert exc.value.status_code == 422

    def test_valid_debit_and_credit(self):
        validate_entry_sides(
            [
                {"debit_amount": 100, "credit_amount": 0},
                {"debit_amount": 0, "credit_amount": 100},
            ]
        )


# ── Aux dimension enforcement ─────────────────────────────────────────────────


class TestAuxDimensionValidation:
    def test_missing_dimension_rejected(self):
        account = MagicMock()
        account.aux_dimensions = ["department", "project"]
        accounts = {"6001": account}
        entries = [
            {
                "account_code": "6001",
                "debit_amount": 100,
                "credit_amount": 0,
                "aux_dimension_values": {"department": "Sales"},
            },
        ]
        with pytest.raises(HTTPException) as exc:
            validate_aux_dimensions(entries, accounts)
        assert "project" in str(exc.value.detail)

    def test_all_required_dimensions_present(self):
        account = MagicMock()
        account.aux_dimensions = ["department"]
        accounts = {"6001": account}
        entries = [
            {
                "account_code": "6001",
                "debit_amount": 100,
                "credit_amount": 0,
                "aux_dimension_values": {"department": "Sales"},
            },
        ]
        validate_aux_dimensions(entries, accounts)


# ── Sequential numbering (Requirement 13.5) ───────────────────────────────────


class TestSequentialNumbering:
    @pytest.mark.asyncio
    async def test_first_voucher_is_number_one(self):
        db = AsyncMock()
        scalar = MagicMock()
        scalar.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=scalar)

        num = await _next_voucher_number("as-1", "202501", db)
        assert num == 1

    @pytest.mark.asyncio
    async def test_increments_from_max_including_deleted_tombstones(self):
        db = AsyncMock()
        scalar = MagicMock()
        scalar.scalar_one_or_none.return_value = 7
        db.execute = AsyncMock(return_value=scalar)

        num = await _next_voucher_number("as-1", "202501", db)
        assert num == 8


# ── Service integration with mocked DB ────────────────────────────────────────


def _mock_db_for_create() -> AsyncMock:
    db = AsyncMock()
    max_scalar = MagicMock()
    max_scalar.scalar_one_or_none.return_value = 2
    db.execute = AsyncMock(return_value=max_scalar)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


class TestCreateVoucher:
    @pytest.mark.asyncio
    async def test_create_assigns_next_sequential_number(self):
        db = _mock_db_for_create()
        with patch("period_end.periods.is_period_closed", AsyncMock(return_value=False)):
            entries = [
                {
                    "account_code": "1001",
                    "debit_amount": 50,
                    "credit_amount": 0,
                    "description": "d",
                },
                {
                    "account_code": "2001",
                    "debit_amount": 0,
                    "credit_amount": 50,
                    "description": "c",
                },
            ]
            voucher = await create_voucher(
                db,
                account_set_id=str(uuid.uuid4()),
                period_code="202501",
                voucher_type="Receipt",
                voucher_date=date(2025, 1, 15),
                entries=entries,
                attachments=[],
                created_by_user_id=str(uuid.uuid4()),
            )
        assert voucher.voucher_number == 3
        assert voucher.status == STATUS_DRAFT


class TestSaveVoucher:
    @pytest.mark.asyncio
    async def test_save_rejects_imbalance(self):
        from voucher import service as vs

        voucher = MagicMock()
        voucher.id = uuid.uuid4()
        voucher.status = STATUS_DRAFT
        voucher.account_set_id = uuid.uuid4()

        entry_debit = MagicMock()
        entry_debit.account_code = "1001"
        entry_debit.debit_amount = 100
        entry_debit.credit_amount = 0
        entry_debit.description = ""
        entry_debit.aux_dimension_values = {}
        entry_debit.sequence = 0

        entry_credit = MagicMock()
        entry_credit.account_code = "2001"
        entry_credit.debit_amount = 0
        entry_credit.credit_amount = 40
        entry_credit.description = ""
        entry_credit.aux_dimension_values = {}
        entry_credit.sequence = 1

        db = AsyncMock()

        with patch.object(vs, "get_voucher", AsyncMock(return_value=voucher)):
            entries_result = MagicMock()
            entries_result.scalars.return_value.all.return_value = [
                entry_debit,
                entry_credit,
            ]
            db.execute = AsyncMock(return_value=entries_result)

            with pytest.raises(HTTPException) as exc:
                await save_voucher(
                    db,
                    account_set_id=str(voucher.account_set_id),
                    voucher_id=str(voucher.id),
                )
            assert exc.value.detail["imbalance_amount"] == 60.0


class TestApprovePublishesEvent:
    @pytest.mark.asyncio
    async def test_approve_publishes_redis_stream(self):
        from voucher import service as vs

        voucher_id = uuid.uuid4()
        account_set_id = uuid.uuid4()
        voucher = MagicMock()
        voucher.id = voucher_id
        voucher.account_set_id = account_set_id
        voucher.period_code = "202501"
        voucher.voucher_number = 1
        voucher.type = "Receipt"
        voucher.date = date(2025, 1, 1)
        voucher.status = STATUS_PENDING_REVIEW
        voucher.reviewed_at = None

        entry = MagicMock()
        entry.account_code = "1001"
        entry.debit_amount = 100
        entry.credit_amount = 0
        entry.description = "test"
        entry.aux_dimension_values = {}
        entry.sequence = 0

        db = AsyncMock()
        entries_result = MagicMock()
        entries_result.scalars.return_value.all.return_value = [entry]
        db.execute = AsyncMock(return_value=entries_result)
        db.flush = AsyncMock()

        loaded = MagicMock()
        loaded.status = STATUS_APPROVED

        mock_redis = AsyncMock()
        mock_redis.xadd = AsyncMock()

        with (
            patch.object(vs, "get_voucher", AsyncMock(side_effect=[voucher, loaded])),
            patch.object(vs, "_get_redis", return_value=mock_redis),
        ):
            result = await approve_voucher(
                db,
                account_set_id=str(account_set_id),
                voucher_id=str(voucher_id),
                reviewer_id=str(uuid.uuid4()),
            )
        assert result.status == STATUS_APPROVED
        mock_redis.xadd.assert_awaited_once()


class TestDeleteVoucher:
    @pytest.mark.asyncio
    async def test_delete_tombstones_and_writes_audit(self):
        from voucher import service as vs

        voucher = MagicMock()
        voucher.id = uuid.uuid4()
        voucher.account_set_id = uuid.uuid4()
        voucher.status = STATUS_DRAFT
        voucher.voucher_number = 5
        voucher.period_code = "202501"
        voucher.type = "Payment"

        db = AsyncMock()
        db.flush = AsyncMock()

        with patch.object(vs, "get_voucher", AsyncMock(return_value=voucher)):
            audit = await delete_voucher(
                db,
                account_set_id=str(voucher.account_set_id),
                voucher_id=str(voucher.id),
                user_id="user-1",
            )
        assert voucher.status == STATUS_DELETED
        assert audit.action == "voucher.delete"
