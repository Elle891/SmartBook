"""
Unit tests for Reconciliation Engine — exact/fuzzy match, manual match, difference.

_Requirements: 5.1–5.8 (Task 23.1)_
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reconciliation.matching import (
    BankCandidate,
    InternalCandidate,
    auto_match_candidates,
    compute_difference,
    find_exact_matches,
    find_fuzzy_matches,
    levenshtein_distance,
    signed_voucher_amount,
)


class TestLevenshtein:
    def test_identical_strings_zero_distance(self):
        assert levenshtein_distance("payment", "payment") == 0

    def test_one_edit_distance(self):
        assert levenshtein_distance("payment", "paymen") == 1


class TestExactMatch:
    def test_matches_same_date_amount_and_description(self):
        bank = [
            BankCandidate("b1", date(2025, 1, 10), 1000.0, "Inflow", "Customer A payment"),
        ]
        internal = [
            InternalCandidate("v1", date(2025, 1, 10), 1000.0, "Customer A payment"),
        ]
        matches = find_exact_matches(bank, internal)
        assert len(matches) == 1
        assert matches[0].match_type == "Exact"
        assert matches[0].bank_transaction_id == "b1"
        assert matches[0].voucher_entry_id == "v1"

    def test_skips_different_amount(self):
        bank = [BankCandidate("b1", date(2025, 1, 10), 1000.0, "Inflow", "A")]
        internal = [InternalCandidate("v1", date(2025, 1, 10), 900.0, "A")]
        assert find_exact_matches(bank, internal) == []


class TestFuzzyMatch:
    def test_matches_similar_descriptions(self):
        bank = [
            BankCandidate("b1", date(2025, 1, 10), 500.0, "Outflow", "Supplier payment ABC"),
        ]
        internal = [
            InternalCandidate("v1", date(2025, 1, 10), -500.0, "Supplier payment ABCX"),
        ]
        exact = find_exact_matches(bank, internal)
        assert exact == []
        fuzzy = find_fuzzy_matches(bank, internal, threshold=2)
        assert len(fuzzy) == 1
        assert fuzzy[0].match_type == "Fuzzy"

    def test_rejects_dissimilar_descriptions(self):
        bank = [
            BankCandidate("b1", date(2025, 1, 10), 500.0, "Outflow", "Rent January"),
        ]
        internal = [
            InternalCandidate("v1", date(2025, 1, 10), -500.0, "Payroll batch 42"),
        ]
        assert find_fuzzy_matches(bank, internal, threshold=3) == []


class TestAutoMatchPipeline:
    def test_exact_before_fuzzy(self):
        bank = [
            BankCandidate("b1", date(2025, 1, 5), 100.0, "Inflow", "Exact desc"),
            BankCandidate("b2", date(2025, 1, 6), 200.0, "Inflow", "Fuzzy supplier pay"),
        ]
        internal = [
            InternalCandidate("v1", date(2025, 1, 5), 100.0, "Exact desc"),
            InternalCandidate("v2", date(2025, 1, 6), 200.0, "Fuzzy supplier payment"),
        ]
        matches = auto_match_candidates(bank, internal, fuzzy_threshold=4)
        assert len(matches) == 2
        types = {m.bank_transaction_id: m.match_type for m in matches}
        assert types["b1"] == "Exact"
        assert types["b2"] == "Fuzzy"


class TestDifference:
    def test_compute_difference_signed_amounts(self):
        unmatched_bank = [{"signed_amount": 1000.0}, {"signed_amount": -200.0}]
        unmatched_internal = [{"signed_amount": 800.0}]
        assert compute_difference(unmatched_bank, unmatched_internal) == 0.0

    def test_signed_voucher_amount_debit_inflow(self):
        assert signed_voucher_amount(1500.0, 0.0) == 1500.0
        assert signed_voucher_amount(0.0, 1500.0) == -1500.0


class TestManualMatchService:
    @pytest.mark.asyncio
    async def test_manual_match_marks_bank_reconciled(self):
        from reconciliation import service as rec_svc

        session = MagicMock()
        session.connection_id = "00000000-0000-0000-0000-000000000010"
        session.period_code = "202501"

        bank_txn = MagicMock()
        bank_txn.id = "00000000-0000-0000-0000-000000000020"
        bank_txn.is_reconciled = False

        entry = MagicMock()
        entry.id = "00000000-0000-0000-0000-000000000030"
        voucher = MagicMock()
        voucher.account_set_id = "00000000-0000-0000-0000-000000000001"
        voucher.period_code = "202501"

        db = AsyncMock()
        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = session
        bank_result = MagicMock()
        bank_result.scalar_one_or_none.return_value = bank_txn
        entry_result = MagicMock()
        entry_result.first.return_value = (entry, voucher)
        db.execute = AsyncMock(
            side_effect=[session_result, bank_result, entry_result]
        )
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch.object(rec_svc, "write_tenant_audit", AsyncMock()):
            result = await rec_svc.manual_match(
                db,
                account_set_id="00000000-0000-0000-0000-000000000001",
                session_id="00000000-0000-0000-0000-000000000002",
                bank_transaction_id="00000000-0000-0000-0000-000000000020",
                voucher_entry_id="00000000-0000-0000-0000-000000000030",
                user_id="user-1",
            )

        assert result["reconciled"] is True
        assert result["match_type"] == "Manual"
        assert bank_txn.is_reconciled is True
