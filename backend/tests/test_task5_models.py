"""
Task 5 — verify tenant SQLAlchemy metadata and migration revision chain.

# Feature: smart-accounting-software, Task 5: Core data models and Alembic initial migration
"""

from __future__ import annotations

import importlib

import pytest


EXPECTED_TENANT_TABLES = {
    "account_sets",
    "account_set_roles",
    "account_set_members",
    "accounts",
    "periods",
    "vouchers",
    "voucher_entries",
    "voucher_attachments",
    "ledger_entries",
    "account_balances",
    "employees",
    "payroll_runs",
    "payroll_lines",
    "fixed_assets",
    "bank_connections",
    "bank_transactions",
    "routing_configs",
    "payment_transaction_types",
    "payments",
    "payment_stage_transitions",
    "payment_field_configs",
    "reconciliation_sessions",
    "reconciliation_matches",
    "invoice_scan_jobs",
    "tax_filings",
    "audit_logs",
    "ifrs_lease_contracts",
    "ifrs_revenue_contracts",
    "ifrs_performance_obligations",
    "ifrs_fair_value_adjustments",
    "forecast_models",
    "forecast_results",
    "forecast_periods",
    "forecast_snapshots",
    "conversation_sessions",
    "conversation_turns",
    "nlp_interaction_logs",
}


def _tenant_metadata():
    import models.account  # noqa: F401
    import models.account_set  # noqa: F401
    import models.assets  # noqa: F401
    import models.bank  # noqa: F401
    import models.ledger  # noqa: F401
    import models.ml  # noqa: F401
    import models.nlp  # noqa: F401
    import models.payment  # noqa: F401
    import models.payroll  # noqa: F401
    import models.reports  # noqa: F401
    import models.tenant_audit  # noqa: F401
    import models.voucher  # noqa: F401
    from models.base import Base

    return Base.metadata


class TestTenantMetadata:
    def test_all_expected_tables_registered(self):
        tables = set(_tenant_metadata().tables.keys())
        missing = EXPECTED_TENANT_TABLES - tables
        assert not missing, f"Missing tables in metadata: {missing}"

    def test_users_not_in_tenant_metadata(self):
        tables = set(_tenant_metadata().tables.keys())
        assert "users" not in tables
        assert "otp_records" not in tables

    def test_account_set_has_no_users_foreign_key(self):
        table = _tenant_metadata().tables["account_set_members"]
        fks = {fk.target_fullname for fk in table.foreign_keys}
        assert "users.id" not in fks

    def test_voucher_created_by_no_users_fk(self):
        table = _tenant_metadata().tables["vouchers"]
        fks = {fk.target_fullname for fk in table.foreign_keys}
        assert "users.id" not in fks

    def test_tenant_audit_has_account_set_id(self):
        table = _tenant_metadata().tables["audit_logs"]
        assert "account_set_id" in table.c


class TestMigrationRevisions:
    def test_tenant_migration_chain(self):
        from pathlib import Path

        versions = Path(__file__).resolve().parents[2] / "migrations" / "versions"
        tenant_files = {p.name: p for p in versions.glob("tenant_*.py")}
        assert "tenant_0001_core_schema.py" in tenant_files
        assert "tenant_0002_cashier.py" in tenant_files
        assert "tenant_0003_payroll.py" in tenant_files
        assert "tenant_0004_assets.py" in tenant_files
        assert "tenant_0005_smart_import.py" in tenant_files
        assert "tenant_0006_reports.py" in tenant_files
        t1 = tenant_files["tenant_0001_core_schema.py"].read_text(encoding="utf-8")
        t2 = tenant_files["tenant_0002_cashier.py"].read_text(encoding="utf-8")
        t3 = tenant_files["tenant_0003_payroll.py"].read_text(encoding="utf-8")
        t4 = tenant_files["tenant_0004_assets.py"].read_text(encoding="utf-8")
        t5 = tenant_files["tenant_0005_smart_import.py"].read_text(encoding="utf-8")
        t6 = tenant_files["tenant_0006_reports.py"].read_text(encoding="utf-8")
        assert 'revision = "tenant_0001"' in t1
        assert "down_revision = None" in t1
        assert 'revision = "tenant_0002"' in t2
        assert 'down_revision = "tenant_0001"' in t2
        assert 'revision = "tenant_0003"' in t3
        assert 'down_revision = "tenant_0002"' in t3
        assert 'revision = "tenant_0004"' in t4
        assert 'down_revision = "tenant_0003"' in t4
        assert 'revision = "tenant_0005"' in t5
        assert 'down_revision = "tenant_0004"' in t5
        assert 'revision = "tenant_0006"' in t6
        assert 'down_revision = "tenant_0005"' in t6

    def test_platform_chain_ends_at_0002(self):
        from pathlib import Path

        versions = Path(__file__).resolve().parents[2] / "migrations" / "versions"
        assert (versions / "0001_initial_tenant_registry.py").is_file()
        assert (versions / "0002_add_users_and_otp_records.py").is_file()
        assert not (versions / "0003_core_models.py").is_file()
