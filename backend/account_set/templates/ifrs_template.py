"""
IFRS (International Financial Reporting Standards) chart of accounts seed template.

Uses flexible numbering per IASB guidance — no mandated code ranges.
"""

from __future__ import annotations

from typing import Any

IFRS_ACCOUNTS: list[dict[str, Any]] = [
    # ── Assets ───────────────────────────────────────────────────────────────
    {"code": "1100", "name": "Cash and Cash Equivalents",          "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1200", "name": "Trade and Other Receivables",        "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1300", "name": "Inventories",                        "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1400", "name": "Prepayments",                        "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1500", "name": "Property, Plant and Equipment",      "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1510", "name": "Accumulated Depreciation — PP&E",    "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1600", "name": "Right-of-Use Assets",                "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1610", "name": "Accumulated Depreciation — ROU",     "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1700", "name": "Intangible Assets",                  "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1710", "name": "Accumulated Amortisation",           "account_type": "Asset",     "parent_code": None, "level": 1},
    {"code": "1800", "name": "Financial Assets at Fair Value",     "account_type": "Asset",     "parent_code": None, "level": 1},
    # ── Liabilities ──────────────────────────────────────────────────────────
    {"code": "2100", "name": "Trade and Other Payables",           "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2200", "name": "Lease Liabilities",                  "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2300", "name": "Tax Liabilities",                    "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2400", "name": "Deferred Tax Liabilities",           "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2500", "name": "Borrowings",                         "account_type": "Liability", "parent_code": None, "level": 1},
    {"code": "2600", "name": "Employee Benefits Payable",          "account_type": "Liability", "parent_code": None, "level": 1},
    # ── Equity ───────────────────────────────────────────────────────────────
    {"code": "3100", "name": "Share Capital",                      "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3200", "name": "Share Premium",                      "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3300", "name": "Retained Earnings",                  "account_type": "Equity",    "parent_code": None, "level": 1},
    {"code": "3400", "name": "Other Comprehensive Income",         "account_type": "Equity",    "parent_code": None, "level": 1},
    # ── Revenue / Income ─────────────────────────────────────────────────────
    {"code": "4100", "name": "Revenue from Contracts with Customers", "account_type": "Revenue", "parent_code": None, "level": 1},
    {"code": "4200", "name": "Other Income",                       "account_type": "Revenue",   "parent_code": None, "level": 1},
    {"code": "4300", "name": "Finance Income",                     "account_type": "Revenue",   "parent_code": None, "level": 1},
    {"code": "4400", "name": "Gains on Disposal of Assets",        "account_type": "Revenue",   "parent_code": None, "level": 1},
    # ── Expenses ─────────────────────────────────────────────────────────────
    {"code": "5100", "name": "Cost of Sales",                      "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5200", "name": "Distribution Costs",                 "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5300", "name": "Administrative Expenses",            "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5400", "name": "Finance Costs",                      "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5500", "name": "Income Tax Expense",                 "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5600", "name": "Depreciation and Amortisation",      "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5700", "name": "Impairment Losses",                  "account_type": "Expense",   "parent_code": None, "level": 1},
    {"code": "5800", "name": "Employee Benefits Expense",          "account_type": "Expense",   "parent_code": None, "level": 1},
]
