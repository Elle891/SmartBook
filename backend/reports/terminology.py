"""
CAS / IFRS report titles and section headings (Property 4).
"""

from __future__ import annotations

STANDARD_CAS = "CAS"
STANDARD_IFRS = "IFRS"

REPORT_TITLES = {
    STANDARD_CAS: {
        "balance_sheet": "资产负债表",
        "income_statement": "利润表",
        "cash_flow": "现金流量表",
        "account_summary": "科目汇总表",
        "disclosure_notes": "财务报表附注",
    },
    STANDARD_IFRS: {
        "balance_sheet": "Statement of Financial Position",
        "income_statement": "Statement of Profit or Loss and Other Comprehensive Income",
        "cash_flow": "Statement of Cash Flows",
        "account_summary": "Account Summary",
        "disclosure_notes": "Notes to the Financial Statements",
    },
}

BALANCE_SECTIONS = {
    STANDARD_CAS: {
        "assets": "资产",
        "liabilities": "负债",
        "equity": "所有者权益",
    },
    STANDARD_IFRS: {
        "assets": "Assets",
        "liabilities": "Liabilities",
        "equity": "Equity",
    },
}

INCOME_SECTIONS = {
    STANDARD_CAS: {
        "revenue": "营业收入",
        "expenses": "营业成本及费用",
        "net_profit": "净利润",
    },
    STANDARD_IFRS: {
        "revenue": "Revenue",
        "expenses": "Expenses",
        "net_profit": "Profit for the period",
    },
}


def report_title(standard: str, report_type: str) -> str:
    return REPORT_TITLES[standard][report_type]


def balance_section(standard: str, section: str) -> str:
    return BALANCE_SECTIONS[standard][section]
