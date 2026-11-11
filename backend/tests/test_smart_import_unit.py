"""
Unit tests for Smart Import — parsing, deduplication, mapping, summary.

_Requirements: 19.1–19.7 (Task 16.1)_
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smart_import.mappings import (
    DEFAULT_EXPENSE_ACCOUNT,
    DEFAULT_REVENUE_ACCOUNT,
    suggest_account_mapping,
)
from smart_import.parser import (
    ParsedTransaction,
    dedup_key,
    export_canonical_csv,
    parse_canonical_csv,
    parse_file_content,
    transactions_equivalent,
)
from smart_import.mappings import DIRECTION_INFLOW, DIRECTION_OUTFLOW


BANK_CSV = """交易日期,交易金额,对方户名,摘要,凭证号
2025-01-10,1500.00,客户A,销售收入,REF001
2025-01-11,-800.00,供应商B,采购货款,REF002
"""

WECHAT_CSV = """交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注
2025-01-12 10:00:00,商户消费,便利店,日用品,支出,25.50,零钱,支付成功,WX001,M001,
2025-01-13 15:30:00,转账,张三,,收入,200.00,银行卡,支付成功,WX002,,退款
"""

ALIPAY_CSV = """交易时间,交易分类,交易对方,对方账号,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号,商家订单号,备注
2025-01-14 09:00:00,餐饮,餐厅,,午餐,支出,68.00,余额,交易成功,ALI001,ORD001,
2025-01-15 18:00:00,转账,李四,,,收入,500.00,余额宝,交易成功,ALI002,ORD002,工资
"""


class TestBankParser:
    def test_parses_bank_csv(self):
        txns = parse_file_content(file_name="icbc.csv", content=BANK_CSV.encode("utf-8"))
        assert len(txns) == 2
        assert txns[0].amount == 1500.0
        assert txns[0].direction == DIRECTION_INFLOW
        assert txns[0].counterparty == "客户A"
        assert txns[1].direction == DIRECTION_OUTFLOW
        assert txns[1].reference_number == "REF002"


class TestWeChatAlipayParser:
    def test_parses_wechat_csv(self):
        txns = parse_file_content(file_name="wechat_bill.csv", content=WECHAT_CSV.encode("utf-8"))
        assert len(txns) == 2
        assert txns[0].direction == DIRECTION_OUTFLOW
        assert txns[1].direction == DIRECTION_INFLOW

    def test_parses_alipay_csv(self):
        txns = parse_file_content(file_name="alipay_bill.csv", content=ALIPAY_CSV.encode("utf-8"))
        assert len(txns) == 2
        assert txns[0].counterparty == "餐厅"
        assert txns[1].amount == 500.0


class TestRoundTrip:
    def test_export_reparse_equivalent(self):
        original = [
            ParsedTransaction(
                txn_date=date(2025, 1, 10),
                amount=1500.0,
                direction=DIRECTION_INFLOW,
                counterparty="客户A",
                description="销售收入",
                reference_number="REF001",
            ),
            ParsedTransaction(
                txn_date=date(2025, 1, 11),
                amount=800.0,
                direction=DIRECTION_OUTFLOW,
                counterparty="供应商B",
                description="采购货款",
                reference_number="REF002",
            ),
        ]
        exported = export_canonical_csv(original)
        reparsed = parse_canonical_csv(exported)
        assert transactions_equivalent(original, reparsed)


class TestAccountSuggestion:
    def test_salary_keyword_maps_to_payable(self):
        suggestion = suggest_account_mapping(
            direction=DIRECTION_OUTFLOW,
            counterparty="财务部",
            description="1月工资发放",
        )
        assert suggestion.debit_account == "2211"
        assert suggestion.credit_account == "1001"
        assert suggestion.matched_keyword == "工资"

    def test_revenue_keyword_for_inflow(self):
        suggestion = suggest_account_mapping(
            direction=DIRECTION_INFLOW,
            counterparty="客户A",
            description="销售收入回款",
        )
        assert suggestion.credit_account == DEFAULT_REVENUE_ACCOUNT
        assert suggestion.debit_account == "1001"

    def test_default_expense_for_unknown_outflow(self):
        suggestion = suggest_account_mapping(
            direction=DIRECTION_OUTFLOW,
            counterparty="未知",
            description="杂项支出",
        )
        assert suggestion.debit_account == DEFAULT_EXPENSE_ACCOUNT


class TestDeduplication:
    def test_dedup_key_normalizes_amount(self):
        key = dedup_key("as-1", date(2025, 1, 10), 100.0, "REF1")
        key2 = dedup_key("as-1", date(2025, 1, 10), 100.0000, "REF1")
        assert key == key2

    @pytest.mark.asyncio
    async def test_import_skips_duplicate_records(self):
        from smart_import import service as si_svc

        existing = MagicMock()
        existing.txn_date = date(2025, 1, 10)
        existing.amount = Decimal("1500.0000")
        existing.reference_number = "REF001"
        existing.status = "Pending"

        db = AsyncMock()
        existing_result = MagicMock()
        existing_result.scalars.return_value.all.return_value = [existing]
        db.execute = AsyncMock(return_value=existing_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        session = await si_svc.import_file(
            db,
            account_set_id="as-1",
            file_name="icbc.csv",
            content=BANK_CSV.encode("utf-8"),
            user_id="u1",
        )

        assert session.total_records == 2
        assert session.records_skipped == 1
        added_txns = [call.args[0] for call in db.add.call_args_list if hasattr(call.args[0], "status")]
        skipped = [t for t in added_txns if t.status == "SkippedDuplicate"]
        pending = [t for t in added_txns if t.status == "Pending"]
        assert len(skipped) == 1
        assert len(pending) == 1


class TestImportSummary:
    @pytest.mark.asyncio
    async def test_summary_counts(self):
        from smart_import import service as si_svc

        session = MagicMock()
        session.id = "sess-1"
        session.file_name = "icbc.csv"
        session.file_format = "bank_csv"
        session.status = "Confirmed"
        session.total_records = 10
        session.vouchers_generated = 8
        session.records_skipped = 2

        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = session
        db.execute = AsyncMock(return_value=result)

        summary = await si_svc.get_import_summary(
            db, session_id="sess-1", account_set_id="as-1"
        )
        assert summary["total_records_processed"] == 10
        assert summary["vouchers_generated"] == 8
        assert summary["records_skipped"] == 2

    @pytest.mark.asyncio
    async def test_confirm_generates_voucher(self):
        from smart_import import service as si_svc

        session = MagicMock()
        session.id = "sess-1"
        session.account_set_id = "as-1"
        session.vouchers_generated = 0
        session.records_skipped = 0

        txn = MagicMock()
        txn.id = "txn-1"
        txn.txn_date = date(2025, 1, 10)
        txn.amount = 1500.0
        txn.direction = DIRECTION_INFLOW
        txn.description = "销售收入"
        txn.reference_number = "REF001"
        txn.suggested_debit_account = "1001"
        txn.suggested_credit_account = "6001"
        txn.status = "Pending"

        session_result = MagicMock()
        session_result.scalar_one_or_none.return_value = session
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn

        voucher = MagicMock()
        voucher.id = "v-1"

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[session_result, txn_result, session_result])
        db.flush = AsyncMock()

        with (
            patch.object(si_svc, "assert_period_open", AsyncMock()),
            patch.object(si_svc, "create_voucher", AsyncMock(return_value=voucher)),
            patch.object(
                si_svc,
                "get_import_summary",
                AsyncMock(
                    return_value={
                        "session_id": "sess-1",
                        "file_name": "icbc.csv",
                        "file_format": "bank_csv",
                        "status": "Confirmed",
                        "total_records_processed": 1,
                        "vouchers_generated": 1,
                        "records_skipped": 0,
                    }
                ),
            ),
        ):
            result = await si_svc.confirm_mapping(
                db,
                session_id="sess-1",
                account_set_id="as-1",
                user_id="u1",
                mappings=[{"transaction_id": "txn-1"}],
            )

        assert result["vouchers_generated"] == 1
        assert result["voucher_ids"] == ["v-1"]
        assert txn.status == "Confirmed"
