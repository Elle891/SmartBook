"""Core data models — all tenant tables

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "tenant_0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_col(dialect: str) -> sa.types.TypeEngine:
    """Return UUID type appropriate for the dialect."""
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import UUID
        return UUID(as_uuid=False)
    return sa.String(36)


def _json_col(dialect: str) -> sa.types.TypeEngine:
    """Return JSON type appropriate for the dialect."""
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB
        return JSONB
    return sa.JSON()


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    uid = _uuid_col(dialect)
    jsn = _json_col(dialect)

    # ── account_sets ──────────────────────────────────────────────────────────
    op.create_table(
        "account_sets",
        sa.Column("id", uid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("standard", sa.String(8), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("start_period", sa.String(8), nullable=False),
        sa.Column("datasource_type", sa.String(16), nullable=False, server_default="Shared"),
        sa.Column("created_by_user_id", uid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_sets_created_by", "account_sets", ["created_by_user_id"])

    # ── account_set_roles ─────────────────────────────────────────────────────
    op.create_table(
        "account_set_roles",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("permissions", jsn, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_set_roles_account_set_id", "account_set_roles", ["account_set_id"])

    # ── account_set_members ───────────────────────────────────────────────────
    op.create_table(
        "account_set_members",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("user_id", uid, nullable=False),
        sa.Column("role_id", uid, sa.ForeignKey("account_set_roles.id"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_account_set_members_account_set_id", "account_set_members", ["account_set_id"])
    op.create_index("ix_account_set_members_user_id", "account_set_members", ["user_id"])
    op.create_index("ix_account_set_members_role_id", "account_set_members", ["role_id"])

    # ── accounts ──────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("standard", sa.String(8), nullable=False),
        sa.Column("parent_code", sa.String(32), nullable=True),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_leaf", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("aux_dimensions", jsn, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_accounts_account_set_id", "accounts", ["account_set_id"])
    op.create_index("ix_accounts_code", "accounts", ["code"])
    op.create_index("ix_accounts_parent_code", "accounts", ["parent_code"])

    # ── periods ───────────────────────────────────────────────────────────────
    op.create_table(
        "periods",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("is_closed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_periods_account_set_id", "periods", ["account_set_id"])
    op.create_index("ix_periods_period_code", "periods", ["period_code"])

    # ── vouchers ──────────────────────────────────────────────────────────────
    op.create_table(
        "vouchers",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("voucher_number", sa.Integer, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="Draft"),
        sa.Column("created_by", uid, nullable=False),
        sa.Column("reviewed_by", uid, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vouchers_account_set_id", "vouchers", ["account_set_id"])
    op.create_index("ix_vouchers_period_code", "vouchers", ["period_code"])
    op.create_index("ix_vouchers_status", "vouchers", ["status"])
    op.create_index("ix_vouchers_created_by", "vouchers", ["created_by"])

    # ── voucher_entries ───────────────────────────────────────────────────────
    op.create_table(
        "voucher_entries",
        sa.Column("id", uid, primary_key=True),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False),
        sa.Column("debit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("aux_dimension_values", jsn, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_voucher_entries_voucher_id", "voucher_entries", ["voucher_id"])
    op.create_index("ix_voucher_entries_account_code", "voucher_entries", ["account_code"])

    # ── voucher_attachments ───────────────────────────────────────────────────
    op.create_table(
        "voucher_attachments",
        sa.Column("id", uid, primary_key=True),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("file_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_voucher_attachments_voucher_id", "voucher_attachments", ["voucher_id"])

    # ── ledger_entries ────────────────────────────────────────────────────────
    op.create_table(
        "ledger_entries",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("entry_id", uid, sa.ForeignKey("voucher_entries.id"), nullable=False),
        sa.Column("debit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("running_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ledger_entries_account_set_id", "ledger_entries", ["account_set_id"])
    op.create_index("ix_ledger_entries_account_code", "ledger_entries", ["account_code"])
    op.create_index("ix_ledger_entries_period_code", "ledger_entries", ["period_code"])
    op.create_index("ix_ledger_entries_entry_date", "ledger_entries", ["entry_date"])
    op.create_index("ix_ledger_entries_voucher_id", "ledger_entries", ["voucher_id"])
    op.create_index("ix_ledger_entries_entry_id", "ledger_entries", ["entry_id"])

    # ── account_balances ──────────────────────────────────────────────────────
    op.create_table(
        "account_balances",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("opening_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_debits", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("total_credits", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_set_id", "account_code", "period_code", name="uq_account_balance"),
    )
    op.create_index("ix_account_balances_account_set_id", "account_balances", ["account_set_id"])
    op.create_index("ix_account_balances_account_code", "account_balances", ["account_code"])
    op.create_index("ix_account_balances_period_code", "account_balances", ["period_code"])

    # ── employees ─────────────────────────────────────────────────────────────
    op.create_table(
        "employees",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("department", sa.String(128), nullable=False, server_default=""),
        sa.Column("position", sa.String(128), nullable=False, server_default=""),
        sa.Column("base_salary", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_employees_account_set_id", "employees", ["account_set_id"])

    # ── payroll_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "payroll_runs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="Draft"),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_runs_account_set_id", "payroll_runs", ["account_set_id"])
    op.create_index("ix_payroll_runs_period_code", "payroll_runs", ["period_code"])
    op.create_index("ix_payroll_runs_status", "payroll_runs", ["status"])

    # ── payroll_lines ─────────────────────────────────────────────────────────
    op.create_table(
        "payroll_lines",
        sa.Column("id", uid, primary_key=True),
        sa.Column("payroll_run_id", uid, sa.ForeignKey("payroll_runs.id"), nullable=False),
        sa.Column("employee_id", uid, sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("gross_salary", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("deductions", jsn, nullable=False),
        sa.Column("net_salary", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("payslip_sent", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_payroll_lines_payroll_run_id", "payroll_lines", ["payroll_run_id"])
    op.create_index("ix_payroll_lines_employee_id", "payroll_lines", ["employee_id"])

    # ── fixed_assets ──────────────────────────────────────────────────────────
    op.create_table(
        "fixed_assets",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(128), nullable=False, server_default=""),
        sa.Column("acquisition_date", sa.Date, nullable=False),
        sa.Column("cost", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("useful_life_months", sa.Integer, nullable=False, server_default="0"),
        sa.Column("depreciation_method", sa.String(32), nullable=False, server_default="StraightLine"),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_book_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_disposed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("disposed_at", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_fixed_assets_account_set_id", "fixed_assets", ["account_set_id"])

    # ── bank_connections ──────────────────────────────────────────────────────
    op.create_table(
        "bank_connections",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("bank_code", sa.String(32), nullable=False),
        sa.Column("account_number", sa.String(64), nullable=False),
        sa.Column("credentials_vault_path", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="Active"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bank_connections_account_set_id", "bank_connections", ["account_set_id"])
    op.create_index("ix_bank_connections_status", "bank_connections", ["status"])

    # ── bank_transactions ─────────────────────────────────────────────────────
    op.create_table(
        "bank_transactions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("connection_id", uid, sa.ForeignKey("bank_connections.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("description", sa.String(512), nullable=False, server_default=""),
        sa.Column("reference_number", sa.String(128), nullable=False, server_default=""),
        sa.Column("is_reconciled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("account_set_id", "date", "amount", "reference_number", name="uq_bank_transaction"),
    )
    op.create_index("ix_bank_transactions_account_set_id", "bank_transactions", ["account_set_id"])
    op.create_index("ix_bank_transactions_connection_id", "bank_transactions", ["connection_id"])
    op.create_index("ix_bank_transactions_date", "bank_transactions", ["date"])

    # ── routing_configs ───────────────────────────────────────────────────────
    op.create_table(
        "routing_configs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("connection_id", uid, sa.ForeignKey("bank_connections.id"), nullable=False),
        sa.Column("routing_method", sa.String(64), nullable=False),
        sa.Column("params_vault_path", sa.String(512), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_routing_configs_connection_id", "routing_configs", ["connection_id"])

    # ── payment_transaction_types ─────────────────────────────────────────────
    op.create_table(
        "payment_transaction_types",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("prepare_mode", sa.String(8), nullable=False, server_default="Auto"),
        sa.Column("instruct_mode", sa.String(8), nullable=False, server_default="Manual"),
        sa.Column("check_mode", sa.String(8), nullable=False, server_default="Auto"),
        sa.Column("authorise_mode", sa.String(8), nullable=False, server_default="Manual"),
        sa.Column("confirm_mode", sa.String(8), nullable=False, server_default="Auto"),
        sa.Column("settle_mode", sa.String(8), nullable=False, server_default="Manual"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_transaction_types_account_set_id", "payment_transaction_types", ["account_set_id"])

    # ── payments ──────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("connection_id", uid, sa.ForeignKey("bank_connections.id"), nullable=False),
        sa.Column("transaction_type_id", uid, sa.ForeignKey("payment_transaction_types.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=False),
        sa.Column("recipient_account", sa.String(128), nullable=False),
        sa.Column("routing_method", sa.String(64), nullable=False),
        sa.Column("settlement_method", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(24), nullable=False, server_default="Prepare"),
        sa.Column("scheduled_date", sa.Date, nullable=True),
        sa.Column("uetr", sa.String(64), nullable=True),
        sa.Column("iso_pain001", sa.Text, nullable=True),
        sa.Column("first_authoriser_id", uid, nullable=True),
        sa.Column("created_by", uid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payments_account_set_id", "payments", ["account_set_id"])
    op.create_index("ix_payments_connection_id", "payments", ["connection_id"])
    op.create_index("ix_payments_transaction_type_id", "payments", ["transaction_type_id"])
    op.create_index("ix_payments_stage", "payments", ["stage"])
    op.create_index("ix_payments_created_by", "payments", ["created_by"])

    # ── payment_stage_transitions ─────────────────────────────────────────────
    op.create_table(
        "payment_stage_transitions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("payment_id", uid, sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("from_stage", sa.String(24), nullable=False),
        sa.Column("to_stage", sa.String(24), nullable=False),
        sa.Column("triggered_by", sa.String(128), nullable=False),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_stage_transitions_payment_id", "payment_stage_transitions", ["payment_id"])

    # ── payment_field_configs ─────────────────────────────────────────────────
    op.create_table(
        "payment_field_configs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("routing_method", sa.String(64), nullable=False),
        sa.Column("settlement_method", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="Optional"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "account_set_id", "routing_method", "settlement_method", "field_name",
            name="uq_payment_field_config",
        ),
    )
    op.create_index("ix_payment_field_configs_account_set_id", "payment_field_configs", ["account_set_id"])

    # ── reconciliation_sessions ───────────────────────────────────────────────
    op.create_table(
        "reconciliation_sessions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("connection_id", uid, sa.ForeignKey("bank_connections.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="InProgress"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reconciliation_sessions_account_set_id", "reconciliation_sessions", ["account_set_id"])
    op.create_index("ix_reconciliation_sessions_connection_id", "reconciliation_sessions", ["connection_id"])
    op.create_index("ix_reconciliation_sessions_period_code", "reconciliation_sessions", ["period_code"])
    op.create_index("ix_reconciliation_sessions_status", "reconciliation_sessions", ["status"])

    # ── reconciliation_matches ────────────────────────────────────────────────
    op.create_table(
        "reconciliation_matches",
        sa.Column("id", uid, primary_key=True),
        sa.Column("session_id", uid, sa.ForeignKey("reconciliation_sessions.id"), nullable=False),
        sa.Column("bank_transaction_id", uid, sa.ForeignKey("bank_transactions.id"), nullable=False),
        sa.Column("voucher_entry_id", uid, sa.ForeignKey("voucher_entries.id"), nullable=True),
        sa.Column("match_type", sa.String(16), nullable=False),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reconciliation_matches_session_id", "reconciliation_matches", ["session_id"])
    op.create_index("ix_reconciliation_matches_bank_transaction_id", "reconciliation_matches", ["bank_transaction_id"])
    op.create_index("ix_reconciliation_matches_voucher_entry_id", "reconciliation_matches", ["voucher_entry_id"])

    # ── invoice_scan_jobs ─────────────────────────────────────────────────────
    op.create_table(
        "invoice_scan_jobs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("image_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="Pending"),
        sa.Column("extracted_data", jsn, nullable=True),
        sa.Column("verification_result", jsn, nullable=True),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_invoice_scan_jobs_account_set_id", "invoice_scan_jobs", ["account_set_id"])
    op.create_index("ix_invoice_scan_jobs_status", "invoice_scan_jobs", ["status"])

    # ── tax_filings ───────────────────────────────────────────────────────────
    op.create_table(
        "tax_filings",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("tax_type", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="Draft"),
        sa.Column("report_data", jsn, nullable=False),
        sa.Column("confirmation_number", sa.String(128), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tax_filings_account_set_id", "tax_filings", ["account_set_id"])
    op.create_index("ix_tax_filings_period_code", "tax_filings", ["period_code"])
    op.create_index("ix_tax_filings_status", "tax_filings", ["status"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(128), nullable=False),
        sa.Column("entity_id", sa.String(256), nullable=True),
        sa.Column("old_value", jsn, nullable=True),
        sa.Column("new_value", jsn, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_account_set_id", "audit_logs", ["account_set_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── fixed_assets (IFRS) ───────────────────────────────────────────────────
    op.create_table(
        "ifrs_lease_contracts",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("asset_id", uid, sa.ForeignKey("fixed_assets.id"), nullable=False),
        sa.Column("lease_term_months", sa.Integer, nullable=False),
        sa.Column("lease_liability", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("rou_asset_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("commencement_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ifrs_lease_contracts_account_set_id", "ifrs_lease_contracts", ["account_set_id"])
    op.create_index("ix_ifrs_lease_contracts_asset_id", "ifrs_lease_contracts", ["asset_id"])

    op.create_table(
        "ifrs_revenue_contracts",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("contract_reference", sa.String(128), nullable=False),
        sa.Column("total_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ifrs_revenue_contracts_account_set_id", "ifrs_revenue_contracts", ["account_set_id"])

    op.create_table(
        "ifrs_performance_obligations",
        sa.Column("id", uid, primary_key=True),
        sa.Column("contract_id", uid, sa.ForeignKey("ifrs_revenue_contracts.id"), nullable=False),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column("allocated_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("recognized_to_date", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("is_satisfied", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_ifrs_performance_obligations_contract_id", "ifrs_performance_obligations", ["contract_id"])

    op.create_table(
        "ifrs_fair_value_adjustments",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("account_code", sa.String(32), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("carrying_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("fair_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("adjustment_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("voucher_id", uid, sa.ForeignKey("vouchers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ifrs_fair_value_adjustments_account_set_id", "ifrs_fair_value_adjustments", ["account_set_id"])
    op.create_index("ix_ifrs_fair_value_adjustments_account_code", "ifrs_fair_value_adjustments", ["account_code"])
    op.create_index("ix_ifrs_fair_value_adjustments_period_code", "ifrs_fair_value_adjustments", ["period_code"])
    op.create_index("ix_ifrs_fair_value_adjustments_voucher_id", "ifrs_fair_value_adjustments", ["voucher_id"])

    # ── forecast_models ───────────────────────────────────────────────────────
    op.create_table(
        "forecast_models",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("model_type", sa.String(64), nullable=False),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mape", sa.Float, nullable=False, server_default="0"),
        sa.Column("rmse", sa.Float, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_forecast_models_account_set_id", "forecast_models", ["account_set_id"])

    op.create_table(
        "forecast_results",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("model_id", uid, sa.ForeignKey("forecast_models.id"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_months", sa.Integer, nullable=False),
    )
    op.create_index("ix_forecast_results_account_set_id", "forecast_results", ["account_set_id"])
    op.create_index("ix_forecast_results_model_id", "forecast_results", ["model_id"])

    op.create_table(
        "forecast_periods",
        sa.Column("id", uid, primary_key=True),
        sa.Column("result_id", uid, sa.ForeignKey("forecast_results.id"), nullable=False),
        sa.Column("period_code", sa.String(8), nullable=False),
        sa.Column("predicted_inflow", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("predicted_outflow", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("confidence_lower", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("confidence_upper", sa.Numeric(18, 4), nullable=False, server_default="0"),
    )
    op.create_index("ix_forecast_periods_result_id", "forecast_periods", ["result_id"])

    op.create_table(
        "forecast_snapshots",
        sa.Column("id", uid, primary_key=True),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("result_id", uid, sa.ForeignKey("forecast_results.id"), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(512), nullable=True),
    )
    op.create_index("ix_forecast_snapshots_account_set_id", "forecast_snapshots", ["account_set_id"])
    op.create_index("ix_forecast_snapshots_result_id", "forecast_snapshots", ["result_id"])

    # ── conversation_sessions ─────────────────────────────────────────────────
    op.create_table(
        "conversation_sessions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("user_id", uid, nullable=False),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_sessions_user_id", "conversation_sessions", ["user_id"])
    op.create_index("ix_conversation_sessions_account_set_id", "conversation_sessions", ["account_set_id"])

    op.create_table(
        "conversation_turns",
        sa.Column("id", uid, primary_key=True),
        sa.Column("session_id", uid, sa.ForeignKey("conversation_sessions.id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_turns_session_id", "conversation_turns", ["session_id"])

    op.create_table(
        "nlp_interaction_logs",
        sa.Column("id", uid, primary_key=True),
        sa.Column("session_id", uid, sa.ForeignKey("conversation_sessions.id"), nullable=False),
        sa.Column("user_id", uid, nullable=False),
        sa.Column("account_set_id", uid, sa.ForeignKey("account_sets.id"), nullable=False),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("action_taken", sa.String(256), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_nlp_interaction_logs_session_id", "nlp_interaction_logs", ["session_id"])
    op.create_index("ix_nlp_interaction_logs_user_id", "nlp_interaction_logs", ["user_id"])
    op.create_index("ix_nlp_interaction_logs_account_set_id", "nlp_interaction_logs", ["account_set_id"])
    op.create_index("ix_nlp_interaction_logs_intent", "nlp_interaction_logs", ["intent"])

    # ── PostgreSQL Row-Level Security (RLS) ───────────────────────────────────
    # Enforce account_set_id isolation at the database level for PostgreSQL.
    # MySQL tenants rely on application-layer enforcement (account_set_id in every query).
    if dialect == "postgresql":
        op.execute("ALTER TABLE account_sets ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE account_sets FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY account_sets_isolation ON account_sets "
            "USING (id::text = current_setting('app.current_account_set_id', true))"
        )
        op.execute(
            "CREATE POLICY account_sets_superuser_bypass ON account_sets "
            "TO postgres USING (true)"
        )

        rls_tables = [
            "account_set_roles",
            "account_set_members",
            "accounts",
            "periods",
            "vouchers",
            "ledger_entries",
            "account_balances",
            "employees",
            "payroll_runs",
            "fixed_assets",
            "bank_connections",
            "bank_transactions",
            "payment_transaction_types",
            "payments",
            "payment_field_configs",
            "reconciliation_sessions",
            "invoice_scan_jobs",
            "tax_filings",
            "audit_logs",
            "ifrs_lease_contracts",
            "ifrs_revenue_contracts",
            "ifrs_fair_value_adjustments",
            "forecast_models",
            "forecast_results",
            "forecast_snapshots",
            "conversation_sessions",
            "nlp_interaction_logs",
        ]
        for table in rls_tables:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            # Allow rows where the session variable matches account_set_id
            # Application sets: SET LOCAL app.current_account_set_id = '<uuid>'
            op.execute(
                f"CREATE POLICY {table}_account_set_isolation ON {table} "
                f"USING (account_set_id::text = current_setting('app.current_account_set_id', true))"
            )
            # Superuser / migration bypass policy
            op.execute(
                f"CREATE POLICY {table}_superuser_bypass ON {table} "
                f"TO postgres USING (true)"
            )

        # Tables without account_set_id (child tables) — no RLS needed at this level
        # They are protected transitively via their parent FK


def downgrade() -> None:
    dialect = op.get_bind().dialect.name

    if dialect == "postgresql":
        rls_tables = [
            "account_sets", "account_set_roles", "account_set_members", "accounts",
            "periods", "vouchers", "ledger_entries", "account_balances", "employees",
            "payroll_runs", "fixed_assets", "bank_connections", "bank_transactions",
            "payment_transaction_types", "payments", "payment_field_configs",
            "reconciliation_sessions", "invoice_scan_jobs", "tax_filings",
            "ifrs_lease_contracts", "ifrs_revenue_contracts", "ifrs_fair_value_adjustments",
            "forecast_models", "forecast_results", "forecast_snapshots",
            "conversation_sessions", "nlp_interaction_logs",
        ]
        for table in rls_tables:
            op.execute(f"DROP POLICY IF EXISTS {table}_account_set_isolation ON {table}")
            op.execute(f"DROP POLICY IF EXISTS {table}_superuser_bypass ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    for tbl in [
        "nlp_interaction_logs", "conversation_turns", "conversation_sessions",
        "forecast_snapshots", "forecast_periods", "forecast_results", "forecast_models",
        "ifrs_fair_value_adjustments", "ifrs_performance_obligations",
        "ifrs_revenue_contracts", "ifrs_lease_contracts",
        "audit_logs", "tax_filings", "invoice_scan_jobs",
        "reconciliation_matches", "reconciliation_sessions",
        "payment_field_configs", "payment_stage_transitions", "payments",
        "payment_transaction_types", "routing_configs",
        "bank_transactions", "bank_connections",
        "fixed_assets", "payroll_lines", "payroll_runs", "employees",
        "account_balances", "ledger_entries",
        "voucher_attachments", "voucher_entries", "vouchers",
        "periods", "accounts", "account_set_members", "account_set_roles", "account_sets",
    ]:
        op.drop_table(tbl)
