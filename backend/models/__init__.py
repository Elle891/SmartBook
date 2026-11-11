"""
SQLAlchemy models package.

Platform auth: models.user (PlatformBase) — lives in platform DB only.
Tenant accounting: models.base.Base — all tables in tenant_0001 migration.
"""

from models.base import Base, GUID, JsonType
from models.platform_base import PlatformBase
from models.user import OTPRecord, User

from models.account import Account
from models.cashier import CashierAccount, CashierTransaction
from models.account_set import AccountSet, AccountSetMember, AccountSetRole
from models.assets import FixedAsset
from models.bank import (
    BankConnection,
    BankTransaction,
    ReconciliationMatch,
    ReconciliationSession,
    RoutingConfig,
)
from models.ledger import AccountBalance, LedgerEntry, Period
from models.ml import ForecastModel, ForecastPeriod, ForecastResult, ForecastSnapshot
from models.nlp import ConversationSession, ConversationTurn, NLPInteractionLog
from models.payment import (
    Payment,
    PaymentFieldConfig,
    PaymentStageTransition,
    PaymentTransactionType,
)
from models.payroll import Employee, PayrollLine, PayrollRun
from models.report_engine import GeneratedReport, ReportDataSource, ReportTemplate
from models.reports import (
    IFRSFairValueAdjustment,
    IFRSLeaseContract,
    IFRSPerformanceObligation,
    IFRSRevenueContract,
    InvoiceScanJob,
    TaxFiling,
)
from models.smart_import import ImportSession, ImportTransaction
from models.tenant_audit import TenantAuditLog
from models.voucher import Voucher, VoucherAttachment, VoucherEntry

__all__ = [
    "Base",
    "PlatformBase",
    "GUID",
    "JsonType",
    "User",
    "OTPRecord",
    "Account",
    "CashierAccount",
    "CashierTransaction",
    "AccountSet",
    "AccountSetRole",
    "AccountSetMember",
    "Period",
    "LedgerEntry",
    "AccountBalance",
    "Voucher",
    "VoucherEntry",
    "VoucherAttachment",
    "Employee",
    "PayrollRun",
    "PayrollLine",
    "FixedAsset",
    "BankConnection",
    "BankTransaction",
    "RoutingConfig",
    "ReconciliationSession",
    "ReconciliationMatch",
    "Payment",
    "PaymentTransactionType",
    "PaymentStageTransition",
    "PaymentFieldConfig",
    "InvoiceScanJob",
    "TaxFiling",
    "ImportSession",
    "ImportTransaction",
    "GeneratedReport",
    "ReportTemplate",
    "ReportDataSource",
    "IFRSLeaseContract",
    "IFRSRevenueContract",
    "IFRSPerformanceObligation",
    "IFRSFairValueAdjustment",
    "ForecastModel",
    "ForecastResult",
    "ForecastPeriod",
    "ForecastSnapshot",
    "ConversationSession",
    "ConversationTurn",
    "NLPInteractionLog",
    "TenantAuditLog",
]
