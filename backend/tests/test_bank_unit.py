"""
Unit tests for Bank Integration — retry, cache, routing validation, vault storage.

_Requirements: 2.1–2.5, 4.1–4.6, 10.1–10.5, 25.1–25.9 (Task 22.1)_
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bank import routing, vault_store
from bank.cache import BALANCE_CACHE_TTL_SECONDS, balance_cache_key
from bank.errors import RoutingValidationError
from bank.retry import backoff_delays, retry_with_backoff
from bank.routing import ROUTING_CNAPS, ROUTING_CIPS, ROUTING_SWIFT


class TestRetryBackoff:
    def test_backoff_delays_exponential(self):
        delays = backoff_delays(max_retries=3, base_delay=1.0)
        assert delays == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_failure(self):
        calls = {"count": 0}

        async def flaky() -> str:
            calls["count"] += 1
            if calls["count"] < 3:
                raise TimeoutError("timeout")
            return "ok"

        with patch("bank.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(flaky, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert calls["count"] == 3

    @pytest.mark.asyncio
    async def test_retry_raises_after_max_attempts(self):
        async def always_fail() -> None:
            raise ConnectionError("down")

        with patch("bank.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ConnectionError):
                await retry_with_backoff(always_fail, max_retries=2, base_delay=0.01)


class TestBalanceCache:
    def test_cache_key_includes_connection_and_date(self):
        assert balance_cache_key("conn-1", "2025-01-15") == "bank:balance:conn-1:2025-01-15"
        assert balance_cache_key("conn-1") == "bank:balance:conn-1:current"

    def test_cache_ttl_one_hour(self):
        assert BALANCE_CACHE_TTL_SECONDS == 3600

    @pytest.mark.asyncio
    async def test_get_balance_uses_cache_on_failure(self):
        from bank import service as bank_svc

        connection = MagicMock()
        connection.id = "conn-1"
        connection.bank_code = "ICBC"
        connection.account_number = "622200001"
        connection.credentials_vault_path = "bank/as-1/connections/conn-1"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = connection
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        cached_payload = {
            "currency": "CNY",
            "current_balance": 999.0,
            "cached_at": "2025-01-01T00:00:00+00:00",
        }

        with patch.object(bank_svc.vault_store, "read_connection_credentials", return_value={"k": "v"}), \
             patch.object(
                 bank_svc.cache,
                 "get_cached_balance",
                 AsyncMock(side_effect=[None, cached_payload]),
             ), \
             patch.object(bank_svc, "retry_with_backoff", AsyncMock(side_effect=TimeoutError("timeout"))):
            result = await bank_svc.get_balance(
                db, account_set_id="00000000-0000-0000-0000-000000000001", connection_id="conn-1"
            )

        assert result["stale"] is True
        assert result["from_cache"] is True
        assert result["current_balance"] == 999.0


class TestRoutingValidation:
    def test_swift_bic_valid_8_chars(self):
        routing.validate_routing_params(ROUTING_SWIFT, {"bic": "BKCHCNBJ"})

    def test_swift_bic_valid_11_chars(self):
        routing.validate_routing_params(ROUTING_SWIFT, {"bic": "BKCHCNBJXXX"})

    def test_swift_bic_invalid(self):
        with pytest.raises(RoutingValidationError) as exc_info:
            routing.validate_routing_params(ROUTING_SWIFT, {"bic": "BAD"})
        assert exc_info.value.details.get("standard_reference") == "SWIFT"

    def test_cnaps_must_be_12_digits(self):
        routing.validate_routing_params(ROUTING_CNAPS, {"cnaps_routing_number": "123456789012"})
        with pytest.raises(RoutingValidationError):
            routing.validate_routing_params(ROUTING_CNAPS, {"cnaps_routing_number": "12345"})

    def test_cips_participant_code_format(self):
        routing.validate_routing_params(ROUTING_CIPS, {"cips_participant_code": "CIPS0000001"})
        with pytest.raises(RoutingValidationError):
            routing.validate_routing_params(ROUTING_CIPS, {"cips_participant_code": "SHORT"})


class TestVaultCredentialStorage:
    @pytest.mark.asyncio
    async def test_connect_stores_credentials_in_vault_not_payload(self):
        from bank import service as bank_svc

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch.object(
            bank_svc.vault_store,
            "store_connection_credentials",
            return_value="bank/as-1/connections/c1",
        ) as store_mock, patch.object(
            bank_svc,
            "verify_connection",
            AsyncMock(return_value={"connected": True}),
        ), patch.object(bank_svc, "write_tenant_audit", AsyncMock()):
            result = await bank_svc.connect_bank(
                db,
                account_set_id="00000000-0000-0000-0000-000000000001",
                bank_code="ICBC",
                account_number="622200001",
                credentials={"client_id": "abc", "client_secret": "secret"},
                user_id="user-1",
            )

        store_mock.assert_called_once()
        args = store_mock.call_args[0]
        assert args[2]["client_secret"] == "secret"
        assert result["credentials_vault_path"].startswith("bank/")
        assert "client_secret" not in result

    def test_routing_params_vault_path_format(self):
        path = routing.routing_vault_path("conn-99", ROUTING_SWIFT)
        assert path == "bank-routing/conn-99/SWIFT"

    def test_store_routing_params_delegates_to_vault(self):
        mock_vault = MagicMock()
        with patch("bank.vault_store._get_vault", return_value=mock_vault):
            vault_store.store_routing_params("bank-routing/c1/SWIFT", {"bic": "BKCHCNBJ"})
        mock_vault.write_secret.assert_called_once_with(
            "bank-routing/c1/SWIFT", {"bic": "BKCHCNBJ"}
        )


class TestConfigureRouting:
    @pytest.mark.asyncio
    async def test_invalid_swift_rejected_before_vault_write(self):
        from bank import service as bank_svc

        connection = MagicMock()
        connection.id = "conn-1"
        connection.bank_code = "BOC"

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = connection
        db.execute = AsyncMock(return_value=result_mock)

        with patch.object(bank_svc.vault_store, "store_routing_params") as store_mock:
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await bank_svc.configure_routing_method(
                    db,
                    account_set_id="as-1",
                    connection_id="conn-1",
                    routing_method=ROUTING_SWIFT,
                    params={"bic": "INVALID"},
                    is_default=True,
                    user_id="user-1",
                )
        assert exc_info.value.status_code == 422
        store_mock.assert_not_called()
