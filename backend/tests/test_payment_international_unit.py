"""
Unit tests for international (SWIFT) payments (Task 27.1).

_Requirements: 27.1–27.9_
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from payment import international_service as intl_svc
from payment import service as payment_svc
from payment import swift
from payment import workflow
from payment.stages import STAGE_PREPARE, STAGE_INSTRUCTED
from payment.swift import SwiftValidationError


class TestBicValidation:
    def test_valid_8_char_bic(self):
        assert swift.validate_bic("BKCHCNBJ") == "BKCHCNBJ"

    def test_valid_11_char_bic(self):
        assert swift.validate_bic("bkchcnbjxxx") == "BKCHCNBJXXX"

    def test_invalid_bic_rejected(self):
        with pytest.raises(SwiftValidationError) as exc:
            swift.validate_bic("BAD")
        assert exc.value.field == "beneficiary_bic"

    def test_invalid_intermediary_bic_field(self):
        with pytest.raises(SwiftValidationError) as exc:
            swift.validate_bic("123", field="intermediary_bic")
        assert exc.value.field == "intermediary_bic"


class TestExchangeRateDisplay:
    def test_same_currency_debit_equals_amount(self):
        preview = intl_svc._compute_debit_preview(
            amount=1000.0,
            payment_currency="USD",
            source_currency="USD",
        )
        assert preview["rate"] == 1.0
        assert preview["estimated_debit_amount"] == 1000.0

    def test_cross_currency_shows_indicative_rate(self):
        preview = intl_svc._compute_debit_preview(
            amount=100.0,
            payment_currency="USD",
            source_currency="CNY",
        )
        assert preview["indicative"] is True
        assert preview["estimated_debit_amount"] == pytest.approx(725.0)


class TestCutoffEnforcement:
    def test_swift_standard_settlement_has_t_plus_2_value_date(self):
        info = payment_svc.get_settlement_cutoff_info(
            routing_method="SWIFT",
            settlement_method="Standard_Settlement_T+2",
            as_of=date(2025, 6, 2),
        )
        assert info["settlement_method"] == "Standard_Settlement_T+2"
        assert "cutoff_time" in info
        assert "estimated_value_date" in info
        assert info["estimated_settlement_date"] == info["estimated_value_date"]

    def test_express_settlement_offset_is_shorter_than_standard(self):
        standard = payment_svc.get_settlement_cutoff_info(
            routing_method="SWIFT",
            settlement_method="Standard_Settlement_T+2",
            as_of=date(2025, 6, 2),
        )
        express = payment_svc.get_settlement_cutoff_info(
            routing_method="SWIFT",
            settlement_method="Express_Settlement_T+1",
            as_of=date(2025, 6, 2),
        )
        assert express["estimated_settlement_date"] < standard["estimated_settlement_date"]


class TestUetrAtInstruct:
    @pytest.mark.asyncio
    async def test_swift_payment_gets_uetr_on_instruct(self):
        payment = MagicMock()
        payment.id = uuid.uuid4()
        payment.stage = STAGE_PREPARE
        payment.routing_method = "SWIFT"
        payment.recipient_account = "DE89370400440532013000"
        payment.recipient_name = "Beneficiary GmbH"
        payment.currency = "EUR"
        payment.amount = 500.0
        payment.scheduled_date = date(2025, 6, 15)
        payment.connection_id = uuid.uuid4()
        payment.uetr = None
        payment.iso_pain001 = None

        txn_type = MagicMock()
        txn_type.instruct_mode = "Manual"

        db = AsyncMock()

        async def _set_instructed(*args, **kwargs):
            payment.stage = STAGE_INSTRUCTED

        with patch.object(workflow, "_get_payment", AsyncMock(return_value=payment)), \
             patch.object(workflow, "_get_txn_type", AsyncMock(return_value=txn_type)), \
             patch.object(workflow, "_record_transition", AsyncMock(side_effect=_set_instructed)), \
             patch.object(workflow, "_auto_advance", AsyncMock(return_value=[])), \
             patch.object(workflow, "write_tenant_audit", AsyncMock()):
            result = await workflow.instruct_payment(
                db,
                account_set_id=str(uuid.uuid4()),
                payment_id=str(payment.id),
                user_id=str(uuid.uuid4()),
                role="Supervisor",
            )

        assert payment.uetr is not None
        assert len(payment.uetr) == 36
        assert result["stage"] == STAGE_INSTRUCTED


class TestCreateInternationalPayment:
    @pytest.mark.asyncio
    async def test_creates_swift_payment_with_scope_and_fx(self):
        account_set_id = str(uuid.uuid4())
        source_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())

        source = MagicMock()
        source.bank_code = "BOC"
        txn_type = MagicMock()
        txn_type.id = uuid.uuid4()

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch.object(intl_svc, "_get_connection", AsyncMock(return_value=source)), \
             patch.object(intl_svc, "_configured_routing", AsyncMock(return_value={"SWIFT"})), \
             patch.object(intl_svc, "_assert_routing_configured", AsyncMock()), \
             patch.object(intl_svc.bank_svc, "get_balance", AsyncMock(return_value={
                 "current_balance": 100000.0,
                 "currency": "CNY",
             })), \
             patch.object(intl_svc, "ensure_standard_transaction_type", AsyncMock(return_value=txn_type)), \
             patch.object(intl_svc.workflow, "initiate_payment_in_prepare", AsyncMock(return_value={
                 "payment_id": payment_id,
                 "stage": "Prepare",
                 "auto_advanced_stages": [],
             })), \
             patch.object(intl_svc, "Payment") as payment_cls:
            payment_cls.return_value = MagicMock(id=uuid.UUID(payment_id))
            result = await intl_svc.create_international_payment(
                db,
                account_set_id=account_set_id,
                user_id=user_id,
                role="Supervisor",
                source_connection_id=source_id,
                recipient_name="ACME Corp",
                recipient_account="DE89370400440532013000",
                beneficiary_bic="DEUTDEFF",
                beneficiary_bank_name="Deutsche Bank",
                beneficiary_bank_address="Frankfurt, Germany",
                amount=1000.0,
                currency="USD",
                settlement_method="Express_Settlement_T+1",
                scheduled_date=date(2025, 6, 15),
                payment_purpose_code="SALA",
            )

        assert result["payment_scope"] == "International"
        assert result["routing_method"] == "SWIFT"
        assert result["exchange_rate"]["indicative"] is True
        assert result["beneficiary_bic"] == "DEUTDEFF"
        kwargs = payment_cls.call_args.kwargs
        assert kwargs["payment_scope"] == "International"
        assert kwargs["recipient_agent_bic"] == "DEUTDEFF"

    @pytest.mark.asyncio
    async def test_rejects_invalid_bic_before_create(self):
        db = AsyncMock()
        with pytest.raises(HTTPException) as exc:
            await intl_svc.create_international_payment(
                db,
                account_set_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                role="Supervisor",
                source_connection_id=str(uuid.uuid4()),
                recipient_name="ACME Corp",
                recipient_account="123",
                beneficiary_bic="INVALID",
                beneficiary_bank_name="Bank",
                beneficiary_bank_address="Address",
                amount=100.0,
                currency="USD",
                settlement_method="Standard_Settlement_T+2",
                scheduled_date=date(2025, 6, 15),
                payment_purpose_code="SALA",
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "invalid_swift_field"

    @pytest.mark.asyncio
    async def test_settle_records_actual_settlement_date(self):
        payment = MagicMock()
        payment.stage = "Confirmed"
        payment.actual_settlement_date = None

        txn_type = MagicMock()
        txn_type.settle_mode = "Manual"

        db = AsyncMock()

        with patch.object(workflow, "_get_payment", AsyncMock(return_value=payment)), \
             patch.object(workflow, "_get_txn_type", AsyncMock(return_value=txn_type)), \
             patch.object(workflow, "_record_transition", AsyncMock()), \
             patch.object(workflow, "write_tenant_audit", AsyncMock()):
            await workflow.settle_payment(
                db,
                account_set_id=str(uuid.uuid4()),
                payment_id=str(uuid.uuid4()),
                settlement_date=date(2025, 6, 20),
                user_id=str(uuid.uuid4()),
                role="Supervisor",
            )

        assert payment.actual_settlement_date == date(2025, 6, 20)
