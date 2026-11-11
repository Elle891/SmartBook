"""
CAS (Chinese Accounting Standards) chart of accounts seed template.

Numbering scheme:
  1xxx = Asset
  2xxx = Liability
  3xxx = Equity
  4xxx-5xxx = Revenue
  6xxx = Expense
"""

from __future__ import annotations

from typing import Any

CAS_ACCOUNTS: list[dict[str, Any]] = [
    # ── Assets (1xxx) ────────────────────────────────────────────────────────
    {"code": "1001", "name": "库存现金",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1002", "name": "银行存款",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1012", "name": "其他货币资金",   "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1101", "name": "短期投资",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1121", "name": "应收票据",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1122", "name": "应收账款",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1123", "name": "预付账款",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1131", "name": "应收股利",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1132", "name": "应收利息",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1221", "name": "其他应收款",     "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1401", "name": "材料采购",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1402", "name": "在途物资",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1403", "name": "原材料",         "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1405", "name": "库存商品",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1601", "name": "固定资产",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1602", "name": "累计折旧",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1701", "name": "无形资产",       "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1702", "name": "累计摊销",       "account_type": "Asset",     "parent_code": None, "level": 1},
    # ── Liabilities (2xxx) ───────────────────────────────────────────────────
    {"code": "2001", "name": "短期借款",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2201", "name": "应付票据",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2202", "name": "应付账款",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2203", "name": "预收账款",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2211", "name": "应付职工薪酬",   "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2221", "name": "应交税费",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2231", "name": "应付利息",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2241", "name": "应付股利",       "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2701", "name": "长期借款",       "account_type": "Liability", "parent_code": None, "level": 1},
    # ── Equity (3xxx) ────────────────────────────────────────────────────────
    {"code": "3001", "name": "实收资本",       "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3002", "name": "资本公积",       "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3101", "name": "盈余公积",       "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3131", "name": "本年利润",       "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3141", "name": "利润分配",       "account_type": "Equity",    "parent_code": None, "level": 1},
    # ── Revenue (4xxx-5xxx) ──────────────────────────────────────────────────
    {"code": "5001", "name": "主营业务收入",   "account_type": "Revenue",   "parent_code": None, "level": 1},
    {"code": "5051", "name": "其他业务收入",   "account_type": "Revenue",   "parent_code": None, "level": 1},
    {"code": "5301", "name": "营业外收入",     "account_type": "Revenue",   "parent_code": None, "level": 1},
    # ── Expenses (6xxx) ──────────────────────────────────────────────────────
    {"code": "6001", "name": "主营业务成本",   "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6051", "name": "其他业务成本",   "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6401", "name": "营业外支出",     "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6601", "name": "销售费用",       "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6602", "name": "管理费用",       "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6603", "name": "财务费用",       "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "6711", "name": "所得税费用",     "account_type": "Expense",   "parent_code": None, "level": 1},
]
