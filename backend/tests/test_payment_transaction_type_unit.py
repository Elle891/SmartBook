"""
Unit tests for Payment Transaction Type configuration (Task 24a).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from payment.transaction_type_service import (
    TransactionTypeValidationError,
    ensure_standard_transaction_type,
    save_transaction_type,
    validate_stage_modes,
)


class TestStageModeValidation:
    def test_instruct_cannot_be_auto(self):
        with pytest.raises(TransactionTypeValidationError):
            validate_stage_modes(
                instruct_mode="Auto",
                authorise_mode="Manual",
                settle_mode="Manual",
            )

    def test_authorise_cannot_be_auto(self):
        with pytest.raises(TransactionTypeValidationError):
            validate_stage_modes(
                instruct_mode="Manual",
                authorise_mode="Auto",
                settle_mode="Manual",
            )

    def test_settle_cannot_be_auto(self):
        with pytest.raises(TransactionTypeValidationError):
            validate_stage_modes(
                instruct_mode="Manual",
                authorise_mode="Manual",
                settle_mode="Auto",
            )

    def test_standard_modes_valid(self):
        validate_stage_modes(
            prepare_mode="Auto",
            instruct_mode="Manual",
            check_mode="Auto",
            authorise_mode="Manual",
            confirm_mode="Auto",
            settle_mode="Manual",
        )


class TestEnsureStandardType:
    @pytest.mark.asyncio
    async def test_creates_standard_type_when_missing(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        txn_type = await ensure_standard_transaction_type(
            db, account_set_id="00000000-0000-0000-0000-000000000001"
        )

        assert txn_type.name == "Standard"
        assert txn_type.prepare_mode == "Auto"
        assert txn_type.instruct_mode == "Manual"
        assert txn_type.check_mode == "Auto"
        assert txn_type.authorise_mode == "Manual"
        assert txn_type.confirm_mode == "Auto"
        assert txn_type.settle_mode == "Manual"
        db.add.assert_called_once()


class TestSaveTransactionType:
    @pytest.mark.asyncio
    async def test_rejects_auto_instruct(self):
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc_info:
            await save_transaction_type(
                db,
                account_set_id="00000000-0000-0000-0000-000000000001",
                user_id="admin-1",
                name="FastTrack",
                instruct_mode="Auto",
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_create_writes_audit(self):
        db = AsyncMock()
        dup_mock = MagicMock()
        dup_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=dup_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch(
            "payment.transaction_type_service.write_tenant_audit", AsyncMock()
        ) as audit_mock:
            result = await save_transaction_type(
                db,
                account_set_id="00000000-0000-0000-0000-000000000001",
                user_id="admin-1",
                name="Express",
                prepare_mode="Auto",
                instruct_mode="Manual",
                check_mode="Manual",
                authorise_mode="Manual",
                confirm_mode="Manual",
                settle_mode="Manual",
            )

        assert result["name"] == "Express"
        audit_mock.assert_awaited_once()
