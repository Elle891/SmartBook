"""
Pydantic v2 request/response schemas for the accounting API.
"""

from schemas.account import (
    AccountNode,
    AccountResponse,
    AccountTreeResponse,
    AuxDimensionResponse,
    CreateAccountRequest,
    DeleteAccountResponse,
    EnableAuxDimensionRequest,
)
from schemas.account_set import (
    AccountSetCreate,
    AccountSetMemberCreate,
    AccountSetMemberResponse,
    AccountSetMemberUpdate,
    AccountSetResponse,
    AccountSetRoleCreate,
    AccountSetRoleResponse,
    AccountSetRoleUpdate,
    InviteUserRequest,
    RestoreRequest,
    SetOpeningBalancesRequest,
    SetOpeningBalancesResponse,
)
from schemas.assets import FixedAssetCreate, FixedAssetResponse
from schemas.auth import (
    LoginEmailRequest,
    LoginMobileRequest,
    MobileLoginInitResponse,
    PasswordResetEmailRequest,
    PasswordResetInitResponse,
    PasswordResetMobileRequest,
    PasswordResetResponse,
    RegisterEmailRequest,
    RegisterMobileRequest,
    RegisterResponse,
    ResendOTPRequest,
    ResendOTPResponse,
    TokenResponse,
    VerifyLoginOTPRequest,
    VerifyOTPResponse,
    VerifyRegistrationOTPRequest,
    VerifyResetOTPRequest,
)
from schemas.bank import BankConnectionCreate, BankConnectionResponse
from schemas.ledger import AccountBalanceResponse, LedgerEntryResponse, PeriodResponse
from schemas.ml import ForecastPeriodResponse, ForecastResultResponse
from schemas.payment import PaymentCreate, PaymentResponse, PaymentStageTransitionResponse
from schemas.payroll import EmployeeCreate, EmployeeResponse, PayrollRunResponse
from schemas.reports import InvoiceScanJobResponse, TaxFilingResponse
from schemas.voucher import (
    VoucherCreate,
    VoucherEntryCreate,
    VoucherEntryResponse,
    VoucherRejectRequest,
    VoucherResponse,
)
