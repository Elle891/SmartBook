"""
Unit tests for domestic payment initiation (Task 26).
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from payment import domestic_service as domestic_svc
from payment.routing_matrix import validate_routing_settlement_pair


class TestRoutingSettlementValidation:
    def test_valid_cnaps_pair(self):
        validate_routing_settlement_pair(
            "CNAPS",
            "Real_Time_Settlement",
            payment_scope="Domestic",
        )

    def test_invalid_pair_raises(self):
        with pytest.raises(ValueError):
            validate_routing_settlement_pair(
                "CNAPS",
                "Immediate_Settlement",
                payment_scope="Domestic",
            )


class TestCreateDomesticPayment:
    @pytest.mark.asyncio
    async def test_creates_payment_in_prepare_with_scope(self):
        account_set_id = str(uuid.uuid4())
        source_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        source = MagicMock()
        source.bank_code = "ICBC"
        source.id = source_id

        txn_type = MagicMock()
        txn_type.id = uuid.uuid4()

        db = AsyncMock()
        connection_result = MagicMock()
        connection_result.scalar_one_or_none.return_value = source
        routing_result = MagicMock()
        routing_result.scalars.return_value = [
            MagicMock(routing_method="CNAPS"),
        ]
        db.execute = AsyncMock(side_effect=[connection_result, routing_result, routing_result])
        db.add = MagicMock()
        db.flush = AsyncMock()

        payment_id = str(uuid.uuid4())
        with patch.object(domestic_svc, "_get_connection", AsyncMock(return_value=source)), \
             patch.object(domestic_svc, "_configured_routing", AsyncMock(return_value={"CNAPS"})), \
             patch.object(domestic_svc, "_assert_routing_configured", AsyncMock()), \
             patch.object(domestic_svc.bank_svc, "get_balance", AsyncMock(return_value={
                 "current_balance": 50000.0,
                 "currency": "CNY",
                 "stale": False,
             })), \
             patch.object(domestic_svc, "ensure_standard_transaction_type", AsyncMock(return_value=txn_type)), \
             patch.object(domestic_svc.workflow, "initiate_payment_in_prepare", AsyncMock(return_value={
                 "payment_id": payment_id,
                 "stage": "Prepare",
                 "auto_advanced_stages": [],
             })), \
             patch.object(domestic_svc, "Payment") as payment_cls:
            payment_cls.return_value = MagicMock(id=uuid.UUID(payment_id))
            result = await domestic_svc.create_domestic_payment(
                db,
                account_set_id=account_set_id,
                user_id=user_id,
                role="Supervisor",
                source_connection_id=source_id,
                recipient_connection_id=None,
                recipient_name="Vendor A",
                recipient_account="622200001",
                amount=1000.0,
                currency="CNY",
                routing_method="CNAPS",
                settlement_method="Real_Time_Settlement",
                scheduled_date=date(2025, 6, 15),
            )

        assert result["payment_scope"] == "Domestic"
        assert result["routing_method"] == "CNAPS"
        assert result["balance_check"]["sufficient"] is True
        payment_cls.assert_called_once()
        kwargs = payment_cls.call_args.kwargs
        assert kwargs["payment_scope"] == "Domestic"

    @pytest.mark.asyncio
    async def test_rejects_insufficient_balance(self):
        source = MagicMock()
        source.bank_code = "ICBC"
        db = AsyncMock()
        routing_result = MagicMock()
        routing_result.scalars.return_value = [MagicMock(routing_method="CNAPS")]
        db.execute = AsyncMock(return_value=routing_result)

        with patch.object(domestic_svc, "_get_connection", AsyncMock(return_value=source)), \
             patch.object(domestic_svc, "_configured_routing", AsyncMock(return_value={"CNAPS"})), \
             patch.object(domestic_svc.bank_svc, "get_balance", AsyncMock(return_value={
                 "current_balance": 100.0,
                 "currency": "CNY",
             })):
            with pytest.raises(HTTPException) as exc:
                await domestic_svc.create_domestic_payment(
                    db,
                    account_set_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    role="Supervisor",
                    source_connection_id=str(uuid.uuid4()),
                    recipient_connection_id=None,
                    recipient_name="Vendor A",
                    recipient_account="622200001",
                    amount=1000.0,
                    currency="CNY",
                    routing_method="CNAPS",
                    settlement_method="Real_Time_Settlement",
                    scheduled_date=date(2025, 6, 15),
                )
        assert exc.value.status_code == 422
        assert exc.value.detail["code"] == "insufficient_balance"

    @pytest.mark.asyncio
    async def test_rejects_invalid_settlement_for_routing(self):
        source = MagicMock()
        source.bank_code = "ICBC"
        db = AsyncMock()
        routing_result = MagicMock()
        routing_result.scalars.return_value = [MagicMock(routing_method="CNAPS")]
        db.execute = AsyncMock(return_value=routing_result)

        with patch.object(domestic_svc, "_get_connection", AsyncMock(return_value=source)), \
             patch.object(domestic_svc, "_configured_routing", AsyncMock(return_value={"CNAPS"})), \
             patch.object(domestic_svc.bank_svc, "get_balance", AsyncMock(return_value={
                 "current_balance": 50000.0,
             })):
            with pytest.raises(HTTPException) as exc:
                await domestic_svc.create_domestic_payment(
                    db,
                    account_set_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    role="Supervisor",
                    source_connection_id=str(uuid.uuid4()),
                    recipient_connection_id=None,
                    recipient_name="Vendor A",
                    recipient_account="622200001",
                    amount=1000.0,
                    currency="CNY",
                    routing_method="CNAPS",
                    settlement_method="Immediate_Settlement",
                    scheduled_date=date(2025, 6, 15),
                )
        assert exc.value.status_code == 422
