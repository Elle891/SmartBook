"""Unit tests for Account Set journal_set_no and status fields."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from account_set.service import create_account_set
from schemas.account_set import AccountSetCreate


class TestAccountSetCreateSchema:
    def test_defaults_status_active_and_strips_journal_set_no(self):
        body = AccountSetCreate(
            name="Acme",
            journal_set_no="  AS001  ",
            standard="CAS",
            base_currency="CNY",
            start_period="202601",
        )
        assert body.journal_set_no == "AS001"
        assert body.status == "Active"

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            AccountSetCreate(
                name="Acme",
                journal_set_no="AS001",
                standard="CAS",
                base_currency="CNY",
                start_period="202601",
                status="Paused",
            )

    def test_rejects_blank_journal_set_no(self):
        with pytest.raises(ValidationError):
            AccountSetCreate(
                name="Acme",
                journal_set_no="   ",
                standard="CAS",
                base_currency="CNY",
                start_period="202601",
            )


@pytest.mark.asyncio
async def test_create_rejects_duplicate_journal_set_no():
    session = AsyncMock()
    existing = MagicMock()
    existing.scalar_one_or_none.return_value = SimpleNamespace(journal_set_no="AS001")
    session.execute = AsyncMock(return_value=existing)

    with pytest.raises(ValueError, match="already exists"):
        await create_account_set(
            session,
            name="Acme",
            journal_set_no="AS001",
            standard="CAS",
            base_currency="CNY",
            start_period="202601",
            created_by_user_id="00000000-0000-0000-0000-000000000001",
        )


@pytest.mark.asyncio
async def test_create_rejects_invalid_status():
    session = AsyncMock()
    with pytest.raises(ValueError, match="Invalid status"):
        await create_account_set(
            session,
            name="Acme",
            journal_set_no="AS002",
            standard="CAS",
            base_currency="CNY",
            start_period="202601",
            status="Paused",
            created_by_user_id="00000000-0000-0000-0000-000000000001",
        )
