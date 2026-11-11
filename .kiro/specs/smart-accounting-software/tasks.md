# Implementation Plan: Smart Accounting Software

## Overview

Incremental implementation of the multi-tenant cloud accounting platform. Each task builds on the previous, starting with infrastructure and core data models, progressing through accounting engine, financial operations, integrations, compliance, ML, NLP, the OWL frontend, and optional MCP agent tooling. All 24 correctness properties are covered by Hypothesis property-based tests placed close to the implementation they validate.

## Tasks

- [x] 1. Project scaffolding and infrastructure
  - Create monorepo directory layout: `backend/`, `frontend/`, `infra/`, `migrations/`, `tests/`
  - Write `docker-compose.yml` with services: svc-frontend (nginx), svc-accounting (fastapi + celery-worker), svc-ml (fastapi-ml + celery-ml-worker + mlflow), svc-nlp (fastapi-nlp + vllm-dev), postgres (registry), redis, vault-dev, prometheus, grafana, loki, jaeger, alertmanager
  - Write `Dockerfile` for FastAPI backend (Python 3.11-slim, multi-stage)
  - Write `Dockerfile` for OWL frontend (Node build stage + Nginx serve stage)
  - Write `backend/pyproject.toml` with all dependencies: fastapi, sqlalchemy[asyncio], alembic, celery, pydantic[v2], python-jose, cryptography, hvac, httpx, pytest, hypothesis, pytest-asyncio, prometheus-fastapi-instrumentator, opentelemetry-sdk, opentelemetry-exporter-jaeger, langchain, sentence-transformers, spacy, prophet, torch, pytorch-forecasting, scikit-learn, mlflow, pandas, numpy, joblib, weasyprint, openpyxl
  - Write GitHub Actions CI workflow: lint (ruff, mypy), test (pytest --run), build Docker images
  - Write Kubernetes manifests: Deployments for svc-accounting (fastapi + celery-worker), svc-ml (fastapi-ml + celery-ml-worker on GPU node pool), svc-nlp (fastapi-nlp + vllm on GPU node pool), svc-frontend (nginx); Services; HPA configs per service; ConfigMaps; Istio/Linkerd service mesh config for mTLS between services
  - Write HashiCorp Vault dev config and `vault_client.py` helper (hvac) for secret read/write
  - _Requirements: 8.2, 8.3_

- [x] 2. Observability stack wiring
  - Add `prometheus-fastapi-instrumentator` to all three FastAPI apps (svc-accounting, svc-ml, svc-nlp) at startup; expose `/metrics` endpoint on each
  - Instrument every API endpoint with OpenTelemetry spans (`account_set_id`, `user_id`, `operation`, `duration_ms`, `status_code`) using `opentelemetry-sdk`
  - Instrument every Celery task with spans (`task_name`, `account_set_id`, `duration_ms`, `status`)
  - Add SQLAlchemy event hooks to emit DB query spans (`query_hash`, `duration_ms`, `tenant_db`)
  - Configure structured JSON logging to stdout: `{"timestamp","level","service","account_set_id","user_id","trace_id","message"}`
  - Write Grafana dashboard JSON provisioning files: System Overview, Tenant Health, Accounting Operations, Background Jobs, Database Fleet, Security, ML Forecast, NLP Assistant
  - Write Alertmanager rules file with all key alerts (API error rate, p99 latency, DB pool exhaustion, bank sync failure, Celery queue depth, Vault unreachable, OOMKilled, vLLM unavailable, NLP fallback rate, NLP RBAC rejection rate)
  - Write Prometheus scrape config for FastAPI, Celery, postgres_exporter, kube-state-metrics, node-exporter, blackbox-exporter
  - _Requirements: (operational non-functional)_

- [x] 3. Multi-database SaaS platform — registry and tenant provisioning
  - Define `backend/platform/registry/models.py`: `TenantRegistry` SQLAlchemy model (`tenant_id`, `account_set_id`, `db_type`, `db_host`, `db_port`, `db_name`, `db_user`, `credentials_vault_path`, `provisioned_at`, `status`)
  - Implement `backend/platform/registry/service.py`: `get_tenant_db_config(account_set_id)` with Redis 5-minute cache; `register_tenant(account_set_id, db_type, db_config)`
  - Implement `backend/platform/db_router.py`: FastAPI middleware that reads `account_set_id` from JWT, looks up registry (cached), injects async SQLAlchemy engine into request context; supports asyncpg (PostgreSQL) and aiomysql (MySQL) pools (min=2, max=10/8)
  - Implement `backend/platform/provisioner.py`: `provision_tenant_database(account_set_id, db_type)` — creates DB, runs Alembic migrations, seeds chart of accounts template; must complete in < 30 s
  - Write `platform-admin` CLI (`python -m platform_admin migrate --tenant=all`) that runs Alembic migrations across all tenant DBs in parallel (max 10 concurrent)
  - Write Alembic `env.py` with dialect-aware migration runner; handle PostgreSQL vs MySQL differences via `op.get_bind().dialect.name`
  - _Requirements: 7.1, 7.2, 11.1_

- [x] 4. Security — JWT authentication, RBAC, and audit log
  - Implement `backend/auth/jwt.py`: RS256 JWT issue/verify using python-jose; 15-minute inactivity timeout enforced server-side; FastAPI dependency `get_current_user`
  - Implement `backend/auth/rbac.py`: per-Account_Set role resolution — built-in roles: Account_Set_Admin, Supervisor, Voucher_Clerk, Cashier, Viewer; `get_user_role(user_id, account_set_id)` looks up `AccountSetMember`; `require_permission(permission)` FastAPI dependency decorator; custom roles supported via `AccountSetRole.permissions` array
  - Implement `backend/auth/session.py`: Redis-backed session inactivity tracker; auto-logout after 15 minutes of inactivity
  - Define `AuditLog` SQLAlchemy model and `backend/audit/service.py`: `write_audit(user_id, action, entity_type, entity_id, old_value, new_value, ip_address)` — append-only; accessible only to Admin/Auditor roles
  - Implement AES-256-GCM encryption helpers in `backend/crypto/aes.py` using the `cryptography` library; keys fetched from Vault via `vault_client.py`
  - Add TLS 1.3 enforcement to all outbound httpx clients
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 4a. User Registration and Login
  - Define `User` and `OTPRecord` SQLAlchemy models in `backend/models/`; add to Alembic initial migration
  - Implement `backend/auth/registration.py`: `register_with_email`, `register_with_mobile` (validate uniqueness, enforce password strength: min 8 chars, upper+lower+digit+special, hash with bcrypt cost=12, generate 6-digit OTP, hash OTP before storage, send via email/SMS)
  - Implement `backend/auth/otp.py`: `send_otp` (email via SMTP / SMS via gateway), `verify_otp` (compare bcrypt hash, check expiry 10 min, mark used, invalidate previous OTPs for same session), `resend_otp` (rate-limit: max 5 per target per hour via Redis counter with 1-hour TTL)
  - Implement `backend/auth/login.py`: `login_with_email` (verify password hash, enforce lockout: 15-min lock after 10 consecutive failures via Redis), `login_with_mobile` (send fresh OTP), `verify_login_otp`
  - Implement `backend/auth/password_reset.py`: `request_reset_email`, `request_reset_mobile`, `verify_reset_otp` (verify OTP, enforce password strength, update password hash)
  - Integrate email OTP delivery: configurable SMTP provider (SendGrid / AWS SES) via `backend/notifications/email.py`
  - Integrate SMS OTP delivery: configurable SMS gateway (Aliyun SMS / Twilio) via `backend/notifications/sms.py`
  - Expose public FastAPI routes (no JWT): `POST /auth/register/email`, `/register/mobile`, `/register/verify-otp`, `/login/email`, `/login/mobile`, `/login/verify-otp`, `/password-reset/email`, `/password-reset/mobile`, `/password-reset/verify-otp`, `/otp/resend`
  - Write all registration and login events to AuditLog
  - [x] 4a.1 Write property test for OTP verification rejects expired or already-used codes
    - **Property 28: OTP verification rejects expired or already-used codes**
    - **Validates: Requirements 31.4, 31.5**
  - [x] 4a.2 Write unit tests for rate limiting, account lockout, password strength enforcement, and duplicate registration rejection
    - _Requirements: 31.6, 31.7, 31.13, 31.14_
  - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5, 31.6, 31.7, 31.8, 31.9, 31.10, 31.11, 31.12, 31.13, 31.14_

- [x] 5. Core data models and Alembic initial migration
  - Define all SQLAlchemy async models in `backend/models/`: `User`, `OTPRecord`, `AccountSet`, `AccountSetRole`, `AccountSetMember`, `Account`, `Period`, `Voucher`, `VoucherEntry`, `VoucherAttachment`, `LedgerEntry`, `AccountBalance`, `Employee`, `PayrollRun`, `PayrollLine`, `FixedAsset`, `BankConnection`, `BankTransaction`, `Payment`, `PaymentTransactionType`, `PaymentStageTransition`, `PaymentFieldConfig`, `RoutingConfig`, `ReconciliationSession`, `ReconciliationMatch`, `InvoiceScanJob`, `TaxFiling`, `AuditLog`, `IFRSLeaseContract`, `IFRSRevenueContract`, `IFRSPerformanceObligation`, `IFRSFairValueAdjustment`, `ForecastModel`, `ForecastResult`, `ForecastPeriod`, `ForecastSnapshot`, `ConversationSession`, `ConversationTurn`, `NLPInteractionLog`
  - Write Alembic initial migration script generating all tables with correct types, constraints, and indexes
  - Add PostgreSQL Row-Level Security (RLS) policies on all tenant tables enforcing `account_set_id` isolation; add application-layer enforcement for MySQL tenants
  - Write Pydantic v2 request/response schemas in `backend/schemas/` mirroring each model
  - _Requirements: 7.2, 8.2_

- [x] 6. Account Set Manager
  - Implement `backend/account_set/service.py`: `create_account_set` (accepts `datasource_type`: Shared or Individual; if Individual, validates external DB connectivity before provisioning; auto-assigns Account_Set_Admin role to creator), `list_account_sets`, `switch_account_set`, `set_opening_balances` (validates total debits = total credits), `get_tenant_database_config`, `provision_tenant_database`, `delete_account_set` (Account_Set_Admin only), `backup_account_set`, `restore_account_set`, `reinitialize_account_set`
  - Implement user access management: `invite_user(account_set_id, mobile_number, role_id)` (looks up user by mobile, creates `AccountSetMember`), `change_user_role`, `remove_user`
  - Implement custom role management: `create_custom_role(account_set_id, name, permissions[])`, `update_custom_role` (built-in roles immutable), `list_roles(account_set_id)`
  - Seed 5 built-in `AccountSetRole` records on every new Account_Set: Account_Set_Admin, Supervisor, Voucher_Clerk, Cashier, Viewer with correct permission arrays
  - Implement CAS and IFRS chart of accounts seed templates in `backend/account_set/templates/cas_template.py` and `ifrs_template.py`; `create_account_set` calls provisioner and seeds the correct template
  - Expose FastAPI router `POST /account-sets`, `GET /account-sets`, `POST /account-sets/{id}/opening-balances`, `POST /account-sets/{id}/switch`, `DELETE /account-sets/{id}`, `POST /account-sets/{id}/backup`, `POST /account-sets/{id}/restore`, `POST /account-sets/{id}/reinitialize`, `POST /account-sets/{id}/members`, `PATCH /account-sets/{id}/members/{userId}`, `DELETE /account-sets/{id}/members/{userId}`, `GET /account-sets/{id}/roles`, `POST /account-sets/{id}/roles`, `PATCH /account-sets/{id}/roles/{roleId}`
  - [ ] 6.1 Write property test for Account Set creation seeds correct standard template
    - **Property 1: Account Set creation seeds the correct standard template**
    - **Validates: Requirements 11.2, 11.3**
  - [ ] 6.2 Write property test for account code numbering scheme conformance
    - **Property 2: Account codes follow the standard's numbering scheme**
    - **Validates: Requirements 12.2, 12.3**
  - _Requirements: 7.1, 7.2, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 7. Chart of Accounts (Account Manager)
  - Implement `backend/chart_of_accounts/service.py`: `get_account_tree`, `create_account` (validates unique code, max 4 levels), `delete_account` (rejects if voucher entries exist), `enable_aux_dimension`, `validate_code`, `get_standard_template`
  - Enforce CAS numbering ranges (1xxx assets, 2xxx liabilities, 3xxx equity, 4xxx–5xxx revenue, 6xxx expenses) and IFRS flexible scheme in `validate_code`
  - Expose FastAPI router `GET /account-sets/{id}/accounts`, `POST /account-sets/{id}/accounts`, `DELETE /account-sets/{id}/accounts/{code}`, `PATCH /account-sets/{id}/accounts/{code}/aux-dimensions`
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9_

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Voucher Engine
  - Implement `backend/voucher/service.py`: `create_voucher`, `save_voucher` (validates sum(debits) = sum(credits), rejects with imbalance amount if not), `submit_for_review`, `approve_voucher` (records reviewer + timestamp), `reject_voucher` (records reason), `delete_voucher` (writes audit log), `batch_approve`, `batch_delete`
  - Implement sequential voucher numbering per `(account_set_id, period_code)` with tombstone on deletion (no gaps)
  - Enforce aux dimension requirement: when an account has `aux_dimensions` enabled, `save_voucher` rejects entries missing the dimension value
  - Publish voucher-approved events to Redis Streams for Ledger Engine consumption
  - Expose FastAPI router for all voucher CRUD and workflow operations
  - [x] 9.1 Write unit tests for voucher debit/credit balance validation, sequential numbering, and aux dimension enforcement
    - _Requirements: 13.1–13.12_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10, 13.11, 13.12_

- [x] 10. Ledger Engine
  - Implement `backend/ledger/service.py`: `get_general_ledger` (with running balance), `get_subsidiary_ledger` (grouped by dimension), `get_cash_journal` (account type 1010), `get_bank_journal` (account type 1020), `get_account_summary` (opening, debits, credits, closing), `export_ledger` (PDF via WeasyPrint / Excel via openpyxl, ≤15 s)
  - Implement Redis Streams consumer that materializes `LedgerEntry` and updates `AccountBalance` on each voucher-approved event
  - Expose FastAPI router `GET /account-sets/{id}/ledger/general`, `/ledger/subsidiary`, `/ledger/cash-journal`, `/ledger/bank-journal`, `/ledger/account-summary`, `/ledger/export`
  - [x] 10.1 Write unit tests for running balance calculation, subsidiary grouping, and export format correctness
    - _Requirements: 14.1–14.7_
  - _Requirements: 1.6, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [x] 11. Period-End Processor
  - Implement `backend/period_end/service.py`: `carry_cost_forward`, `carry_profit_loss` (resolves correct retained earnings account per standard via `get_carry_forward_account`), `calculate_depreciation`, `close_period` (pre-flight: all vouchers approved; on close: carry forward balance sheet closing balances as next period opening balances; lock period against new vouchers), `get_next_period_opening_balances`
  - Implement `get_carry_forward_account(standard, type)` returning CAS-designated or IAS 1 equity retained earnings account code
  - [x] 11.1 Write property test for profit/loss carry-forward targets correct retained earnings account
    - **Property 3: Profit/loss carry-forward targets the correct retained earnings account**
    - **Validates: Requirements 15.2, 15.3**
  - [x] 11.2 Write unit tests for close_period pre-flight rejection and balance carry-forward
    - _Requirements: 15.4, 15.5, 15.6, 15.7_
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8_

- [x] 12. Cashier Module
  - Implement `backend/cashier/service.py`: `register_account`, `record_receipt` (creates receipt voucher via Voucher Engine), `record_payment` (creates payment voucher), `record_transfer` (validates income = expenditure), `reconcile_physical_cash` (compares system balance vs physical count), `get_fx_balance` (calculates functional currency balance using recorded exchange rates)
  - Handle multi-currency: store foreign currency amount, exchange rate, and functional currency equivalent per transaction
  - Expose FastAPI router for all cashier operations
  - [x] 12.1 Write unit tests for transfer validation, FX balance calculation, and cash reconciliation discrepancy report
    - _Requirements: 16.1–16.8_
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8_

- [x] 13. Payroll Module
  - Implement `backend/payroll/service.py`: `register_employee`, `record_adjustment`, `accrue_payroll` (calculates gross salary + adjustments, calculates 五险一金 deductions using configurable rates, generates payroll voucher via Voucher Engine), `generate_payslips` (≤30 s, Celery async task), `distribute_payslips` (WeChat/email/SMS via Celery; records failures with employee ID + reason)
  - Store social insurance contribution rates as configurable per-Account_Set settings
  - Expose FastAPI router for all payroll operations
  - [x] 13.1 Write unit tests for salary calculation, deduction computation, and payslip generation
    - _Requirements: 17.1–17.8_
  - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8_

- [x] 14. Fixed Asset Module
  - Implement `backend/assets/service.py`: `register_asset`, `calculate_depreciation` (straight-line: `cost / useful_life_months`; declining-balance: `net_book_value × rate`), `confirm_depreciation` (updates accumulated depreciation + net book value, generates depreciation voucher via Voucher Engine), `dispose_asset` (calculates gain/loss, generates disposal voucher), `get_asset_register`
  - Expose FastAPI router for all asset operations
  - [x] 14.1 Write unit tests for both depreciation methods, disposal gain/loss calculation, and asset register display
    - _Requirements: 18.1–18.7_
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_

- [x] 15. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Smart Import
  - Implement `backend/smart_import/parser.py`: parsers for major Chinese bank CSV/XLS exports, WeChat Pay bill CSV, Alipay bill CSV; extracts date, amount, counterparty, description
  - Implement `backend/smart_import/service.py`: `import_file`, `parse_transactions`, `suggest_account_mapping` (keyword-rule matching), `confirm_mapping` (generates voucher batch via Voucher Engine), `get_import_summary`; deduplication key: `(account_set_id, date, amount, reference_number)`
  - Expose FastAPI router `POST /account-sets/{id}/smart-import/upload`, `/smart-import/{session}/confirm`
  - [x] 16.1 Write unit tests for deduplication, account suggestion, and import summary counts
    - _Requirements: 19.1–19.7_
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_

- [x] 17. Invoice Scanner
  - Implement `backend/invoice_scanner/service.py`: `submit_invoice` (stores image in S3, creates `InvoiceScanJob`), `extract_invoice_data` (calls OCR service via httpx async), `verify_invoice` (calls tax authority API, ≤10 s), `generate_voucher` (debit expense + tax accounts, credit payable; attaches original image as `VoucherAttachment`), `get_attachment`
  - Implement Celery task for async OCR processing
  - Expose FastAPI router for invoice scanner operations
  - [x] 17.1 Write unit tests for OCR field extraction, verification failure handling, and voucher generation with attachment
    - _Requirements: 20.1–20.7_
  - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

- [x] 18. Report Engine
  - Implement `backend/reports/service.py` core financial statements from Ledger Engine aggregates (Req 9.1–9.7):
    - `generate_balance_sheet` — CAS balance sheet terminology/format when Account Set uses CAS (9.1); IFRS Statement of Financial Position when IFRS (9.2)
    - `generate_income_statement` — CAS income statement when CAS (9.3); IFRS Statement of Profit or Loss and Other Comprehensive Income when IFRS (9.4)
    - `generate_cash_flow_statement` — CAS cash flow format when CAS (9.5); IAS 7 cash flow with both direct and indirect method when IFRS (9.6)
    - `generate_account_summary` — aggregate debit and credit totals by account for the specified period (9.7)
  - Performance and export (Req 9.8–9.10):
    - Complete report generation within 10 seconds for up to 10,000 transactions (9.8)
    - `export_report` — PDF (WeasyPrint) and CSV export (9.9)
    - Currency formatting using the Account Set base currency locale; support optional `report_currency` override when specified (9.10)
  - Report parameters (Req 9.11):
    - Accept per-report filters: custom date range, custom currency, custom entity, and entity group; validate filter combinations and scope ledger queries accordingly
  - Report templates and data sources (Req 9.12–9.15):
    - Implement `backend/reports/templates.py`: `create_report_template`, `publish_report_template` — Finance_User selects a data source, defines layout/fields, and releases the template to designated user roles (9.12)
    - Implement `backend/reports/data_sources.py`: `register_data_source`, `list_data_sources`, `test_data_source_connection` — allow Finance_Users to add report data sources (9.13)
    - Support data source connection modes: **API** (HTTP endpoint + auth config) and **Data Server** (JDBC-style database connection) (9.14)
    - Data Server connectors for vendor databases: **MySQL**, **Oracle**, and **SQL Server**; store credentials in Vault, never in the main DB (9.15)
  - Implement `generate_disclosure_notes` (IFRS only) — included in IFRS financial statement output per IFRS compliance (Req 22.6); return `StandardMismatchError` on CAS sets
  - Return `StandardMismatchError` for IFRS-only operations on CAS sets; `MethodNotSupportedError` for IFRS-only cash flow method options on CAS sets
  - Expose FastAPI router for standard reports, export, template management, and data source management
  - [x] 18.1 Write property test for report format and terminology matching the account set standard
    - **Property 4: Generated reports use the format and terminology of the Account Set's standard**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**
  - [x] 18.2 Write property test for IFRS cash flow direct vs indirect method net cash equality
    - **Property 5: IFRS cash flow statement respects the method parameter**
    - **Validates: Requirement 9.6**
  - [x] 18.3 Write unit tests for account summary aggregation, export formats, and 10 s performance budget for ≤10,000 transactions
    - _Requirements: 9.7, 9.8, 9.9_
  - [x] 18.4 Write unit tests for currency/locale formatting and custom report filters (date range, currency, entity, entity group)
    - _Requirements: 9.10, 9.11_
  - [x] 18.5 Write unit tests for report template lifecycle and role-based template access
    - _Requirements: 9.12_
  - [x] 18.6 Write unit tests for data source registration, API vs Data Server modes, and MySQL/Oracle/SQL Server connection validation
    - _Requirements: 9.13, 9.14, 9.15_
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11, 9.12, 9.13, 9.14, 9.15_

- [x] 19. Tax Module
  - Implement `backend/tax/service.py`: `generate_filing_report` (aggregates VAT and CIT account balances from Ledger Engine), `adjust_line_item`, `submit_filing` (transmits to tax authority API via httpx; records confirmation number + timestamp on success; preserves data on failure), `get_filing_history`
  - Expose FastAPI router for all tax module operations
  - [x] 19.1 Write unit tests for filing report aggregation, line item adjustment, and submission failure preservation
    - _Requirements: 21.1–21.7_
  - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7_

- [x] 20. IFRS Compliance Module
  - Implement `backend/ifrs/service.py`: `record_fair_value_adjustment` (generates balanced voucher; adjustment = fair_value − carrying_amount; IFRS 9), `register_right_of_use_asset` (creates FixedAsset + IFRSLeaseContract; generates initial recognition voucher debiting ROU asset and crediting lease liability; IFRS 16), `recognize_revenue` (records against performance obligation; enforces cumulative ≤ allocated_value; IFRS 15), `perform_impairment_test` (generates impairment voucher iff carrying > recoverable; IAS 36), `validate_ifrs_transaction` (returns ValidationResult with standard_reference on failure)
  - All operations return `StandardMismatchError` when called on a CAS Account Set
  - [x] 20.1 Write property test for fair value adjustment produces balanced voucher
    - **Property 6: Fair value adjustment produces a balanced voucher**
    - **Validates: Requirement 22.1**
  - [x] 20.2 Write property test for IFRS 16 right-of-use asset initial recognition voucher
    - **Property 7: IFRS 16 right-of-use asset registration produces correct initial recognition voucher**
    - **Validates: Requirements 22.2, 22.3**
  - [x] 20.3 Write property test for IFRS 15 revenue recognition does not exceed allocated obligation value
    - **Property 8: IFRS 15 revenue recognition does not exceed allocated obligation value**
    - **Validates: Requirement 22.4**
  - [x] 20.4 Write property test for impairment voucher generated iff carrying amount exceeds recoverable amount
    - **Property 9: Impairment loss voucher generated iff carrying amount exceeds recoverable amount**
    - **Validates: Requirement 22.5**
  - [x] 20.5 Write property test for IFRS disclosure notes non-empty and contains required sections
    - **Property 10: IFRS disclosure notes are present in all IFRS financial statements**
    - **Validates: Requirement 22.6**
  - [x] 20.6 Write property test for invalid IFRS transactions rejected with standard reference
    - **Property 11: Invalid IFRS transactions are rejected with a standard reference**
    - **Validates: Requirement 22.7**
  - _Requirements: 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_

- [x] 21. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 22. Bank Integration
  - Implement `backend/bank/service.py`: `connect_bank` (stores credentials in Vault, never in main DB), `verify_connection`, `sync_transactions` (scheduled daily via Celery beat + on-demand; deduplication by `(account_set_id, date, amount, reference_number)`), `get_balance` (≤5 s, Redis 1-hour cache), `retry_with_backoff` (up to 3 retries, exponential backoff)
  - Implement routing configuration: `configure_routing_method` (validates BIC = 8/11 alphanumeric, CNAPS = 12 digits, CIPS format; stores params in Vault; writes audit log), `get_available_routing_methods`, `set_default_routing_method`, `get_routing_config`, `mark_routing_method_unavailable` (notifies Finance_User)
  - Implement error handling: timeout retry, error logging, cached-data fallback when bank unavailable, auto-resume on reconnect, Finance_User notification on restore
  - Expose FastAPI router for all bank integration operations
  - [x] 22.1 Write unit tests for retry backoff, balance caching, routing parameter validation, and credential vault storage
    - _Requirements: 2.1–2.5, 4.1–4.6, 10.1–10.5, 25.1–25.9_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 10.1, 10.2, 10.3, 10.4, 10.5, 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8, 25.9_

- [x] 23. Reconciliation Engine
  - Implement `backend/reconciliation/service.py`: `initiate_reconciliation`, `auto_match` (exact match on date+amount; fuzzy match on description via Levenshtein distance), `manual_match` (updates reconciliation status immediately), `get_reconciliation_report` (matched, unmatched, missing), `get_difference` (sum of unreconciled amounts)
  - Expose FastAPI router for all reconciliation operations
  - [x] 23.1 Write unit tests for auto-match exact and fuzzy logic, manual match, and difference calculation
    - _Requirements: 5.1–5.8_
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [x] 24. Payment Hub — settlement process workflow engine
  - Implement `backend/payment/workflow.py`: 6-stage machine enforcing Prepare → Instructed → Checked → PendingSecondAuth (dual-auth) → Authorised → Confirmed → Settled; `instruct_payment` (generates ISO 20022 pain.001, validates Required fields, generates UETR for SWIFT, transitions Prepare → Instructed); `check_payment` (Reviewer role; approve → Checked, reject → Prepare; only invoked when Check=Manual); `authorise_payment` (Authoriser role; dual-auth threshold check; first auth → PendingSecondAuth if threshold met, else → Authorised; second auth by different user → Authorised); `confirm_payment` (transmits to bank; ≤30 s bank acknowledgement; → Confirmed on success; → Prepare on bank rejection); `settle_payment` (bank webhook/poller; records actual settlement date; → Settled); `pay_now` (Authoriser role; immediately triggers confirm_payment)
  - Implement **auto-advance engine**: after every stage transition, check `PaymentTransactionType.{stage}_mode` for the next stage; if Auto, immediately execute the transition and record `triggered_by = system` in `PaymentStageTransition`; continue until a Manual stage or Settled
  - Implement `PaymentStageTransition` writes on every stage change: `from_stage`, `to_stage`, `triggered_by`, `reason`, `transitioned_at`; write to AuditLog
  - Implement Celery beat task: every minute, query Authorised payments where `scheduled_date ≤ today` and cut-off not passed; trigger `confirm_payment` automatically
  - Implement `get_scheduling_queue(account_set_id)` — returns Prepare + Instructed payments ordered by requested settlement date
  - Implement `batch_instruct(payment_ids[])` and `batch_pay(payment_ids[])` for bulk queue operations
  - Implement dual-authorisation threshold config per Account_Set; enforce second authoriser must differ from first
  - Notify originating Finance_User on Check rejection and bank rejection via notification service
  - [x] 24.1 Write property test for payment stage transitions are strictly sequential and role-enforced
    - **Property 25: Payment stage transitions are strictly sequential and role-enforced**
    - **Validates: Requirements 29.1, 29.7**
  - [x] 24.2 Write property test for dual-authorisation enforced when amount meets or exceeds threshold
    - **Property 26: Dual-authorisation is enforced when payment amount meets or exceeds the threshold**
    - **Validates: Requirement 29.8**
  - [x] 24.3 Write property test for auto stages advance immediately; manual stages wait for user action
    - **Property 27: Auto stages advance immediately with system trigger; Manual stages wait for explicit user action**
    - **Validates: Requirements 30.6, 30.7**
  - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7, 29.8, 29.9, 29.10, 29.11, 29.12_

- [x] 24a. Payment Hub — Payment Transaction Type configuration
  - Implement `backend/payment/transaction_type_service.py`: `get_transaction_types(account_set_id)`, `save_transaction_type` (validates Instruct/Authorise/Settle always Manual; writes audit log with before/after; Admin only), `get_default_transaction_type(account_set_id)`
  - Seed default "Standard" `PaymentTransactionType` on tenant provisioning: Prepare=Auto, Instruct=Manual, Check=Auto, Authorise=Manual, Confirm=Auto, Settle=Manual
  - Implement deactivation: `deactivate_transaction_type(typeId)` — sets `is_active=False`; existing payments using the type continue unaffected; new payments cannot select it
  - Expose FastAPI router `GET /account-sets/{id}/payment-transaction-types`, `POST /account-sets/{id}/payment-transaction-types`, `PATCH /account-sets/{id}/payment-transaction-types/{typeId}`
  - _Requirements: 30.1, 30.2, 30.3, 30.4, 30.9, 30.10, 30.11_

- [x] 25. Payment Hub — core pipeline and ISO 20022 field configuration
  - Implement `backend/payment/field_config_service.py`: `get_field_configuration(account_set_id, routing_method, settlement_method)`, `save_field_configuration` (validates six mandatory fields always Required; writes audit log with before/after; Admin only); seed default ISO 20022 field configs for all routing/settlement combinations on tenant provisioning
  - Implement `backend/payment/service.py` core: `get_payment_status`, `schedule_payment`, `set_default_settlement_method`, `get_settlement_cutoff_info`, `get_indicative_exchange_rate`
  - Implement `get_available_routing_and_settlement(source_connection_id, recipient_connection_id, payment_scope)` — filters by scope (Domestic/International), source account routing config, and recipient compatibility
  - [x] 25.1 Write property test for ISO 20022 field configuration always marks mandatory fields as Required
    - **Property 23: ISO 20022 field configuration always includes the mandatory minimum fields as Required**
    - **Validates: Requirement 28.7**
  - [x] 25.2 Write property test for payment form fields rendered match exactly the field configuration
    - **Property 24: Payment form fields rendered match exactly the field configuration for the selected routing/settlement combination**
    - **Validates: Requirements 28.4, 28.5**
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 28.1, 28.2, 28.3, 28.4, 28.5, 28.6, 28.7, 28.8, 28.9, 28.10_

- [x] 26. Payment Hub — Domestic Payment page
  - Implement `backend/payment/domestic_service.py`: `create_domestic_payment` (supports CNY + foreign currency; creates payment in Prepare status); enforce routing→settlement matrix (Direct_Debit→Same_Day/Next_Day; Online_Banking_Transfer→RTGS/Batch_T+1; CNAPS→Real_Time/Scheduled; CIPS→Real_Time/End_Of_Day; Local_ACH→Next_Day/Two_Day; Internal_Transfer→Immediate); balance pre-check at Prepare; warn on cut-off passed
  - Wire `create_domestic_payment` through workflow engine; record `payment_scope=Domestic`, routing method, settlement method, currency on Payment record
  - [x] 26.1 Write property test for settlement methods presented are always valid for the selected routing method
    - **Property 21: Settlement methods presented are always valid for the selected routing method**
    - **Validates: Requirements 26.2, 26.4**
  - [x] 26.2 Write property test for routing methods presented are always a subset of configured and available methods
    - **Property 22: Routing methods presented are always a subset of those configured and available for the source account**
    - **Validates: Requirements 25.2, 25.3, 26.3**
  - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 26.6, 26.7, 26.8, 26.9, 26.10, 26.11_

- [x] 27. Payment Hub — International Payment page
  - Implement `backend/payment/international_service.py`: `create_international_payment` (SWIFT only; settlement methods: Standard_Settlement T+2, Express_Settlement T+1, Same_Day_Value; creates payment in Prepare status); collect all SWIFT fields (beneficiary BIC validated 8/11 alphanumeric; UETR generated at Instruct stage); display indicative exchange rate when currencies differ; display estimated value date and cut-off per settlement method
  - Wire through workflow engine; record `payment_scope=International`, all SWIFT-specific fields, UETR at Instruct, actual settlement date on Payment record
  - [x] 27.1 Write unit tests for BIC format validation, UETR generation at Instruct stage, exchange rate display, and cut-off enforcement
    - _Requirements: 27.1–27.9_
  - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6, 27.7, 27.8, 27.9_

- [x] 27. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 28. ML Forecast Engine
  - Implement `backend/ml/feature_engineering.py`: build pandas DataFrames from `BankTransaction` and `LedgerEntry`; compute lag features (lag_1, lag_3, lag_6), rolling statistics (mean_3m, std_3m, mean_6m), calendar features (month, quarter, is_year_end, is_quarter_end)
  - Implement `backend/ml/training.py` Celery task: `train_model(account_set_id)` — selects Prophet (6–23 months) or Prophet+N-BEATS challenger (24+ months); evaluates on TimeSeriesSplit walk-forward validation; compares MAPE with current model in MLflow; promotes only if new MAPE ≤ current MAPE; stores model in S3 under `models/{account_set_id}/current/`; saves forecast snapshot at period start
  - Implement `backend/ml/inference.py`: `get_forecast(account_set_id, horizon_months)` — loads model from S3; generates predictions with confidence intervals (Prophet Monte Carlo / N-BEATS quantile); returns exactly `horizon_months` ForecastPeriod records; ≤10 s; returns `InsufficientDataError` for < 6 months data; `ModelNotReadyError` if no active model
  - Implement `backend/ml/service.py`: `get_model_metrics`, `compare_forecast_vs_actual`, `export_forecast` (PDF/CSV), `schedule_retraining` (triggered when 30+ new transactions since last training)
  - Register MLflow experiment per Account Set; log MAPE, RMSE, MAE, hyperparameters, and model artifacts per training run
  - Expose FastAPI router `GET /account-sets/{id}/forecast`, `GET /account-sets/{id}/forecast/metrics`, `GET /account-sets/{id}/forecast/comparison`, `POST /account-sets/{id}/forecast/export`
  - [x] 28.1 Write property test for forecast returns InsufficientDataError for < 6 months data
    - **Property 12: Forecast is not generated when insufficient data exists**
    - **Validates: Requirement 23.8**
  - [x] 28.2 Write property test for forecast confidence intervals are well-formed
    - **Property 13: Forecast confidence intervals are well-formed**
    - **Validates: Requirement 23.4**
  - [x] 28.3 Write property test for model promotion only occurs when new model MAPE ≤ replaced model MAPE
    - **Property 14: Model promotion only occurs when new model is at least as accurate**
    - **Validates: Requirement 23.6**
  - [x] 28.4 Write property test for forecast horizon returns exactly N ForecastPeriod records
    - **Property 15: Forecast horizon bounds are respected**
    - **Validates: Requirements 23.2, 23.3**
  - [x] 28.5 Write property test for forecast snapshot actual values consistent with AccountBalance ledger
    - **Property 16: Forecast snapshot actual values are consistent with ledger**
    - **Validates: Requirement 23.9**
  - _Requirements: 23.1, 23.2, 23.3, 23.4, 23.5, 23.6, 23.7, 23.8, 23.9, 23.10, 23.11, 23.12_

- [x] 29. NLP Assistant
  - Implement `backend/nlp/intent_classifier.py`: embed user message via `sentence-transformers` (`all-MiniLM-L6-v2`); match against known intents; fall back to spaCy + regex rule-based classifier when confidence < 0.7; record `model_used` in `NLPInteractionLog`
  - Implement `backend/nlp/conversation_context.py`: Redis 7+ store with 10-turn sliding window; key `nlp:session:{session_id}`; `get_context`, `append_turn`, `clear_context`
  - Implement `backend/nlp/langchain_pipeline.py`: LangChain tool-calling pipeline routing intents to system API functions; `execute_query` (read-only APIs), `execute_action` (write APIs — RBAC check first, then explicit confirmation required before calling API), `generate_guidance` (DeepSeek-R1-Distill via vLLM/Ollama)
  - Implement `backend/nlp/service.py`: `classify_intent` (≤3 s), `execute_query`, `execute_action` (returns `UnauthorizedActionError` for insufficient RBAC; never calls system API without authorization), `generate_guidance`, `get_conversation_context`, `clear_context`; write every interaction to `NLPInteractionLog` and `AuditLog`; never expose SQL, API endpoints, or credentials in responses; language auto-detection (en / zh-CN)
  - Implement DeepSeek-R1-Distill vLLM client in `backend/nlp/deepseek_client.py`; fallback to rule-based classifier on model unavailability
  - Expose FastAPI router `POST /nlp/chat`, `DELETE /nlp/sessions/{id}/context`
  - [x] 29.1 Write property test for intent classification consistency for semantically equivalent inputs
    - **Property 17: Intent classification is consistent for semantically equivalent inputs**
    - **Validates: Requirement 24.3**
  - [x] 29.2 Write property test for NLP layer enforces RBAC — no action executes without authorization
    - **Property 18: NLP layer enforces RBAC — no action executes without authorization**
    - **Validates: Requirement 24.9**
  - [x] 29.3 Write property test for no credential or sensitive data leakage in NLP responses
    - **Property 19: No credential or sensitive data leakage in NLP responses**
    - **Validates: Requirement 24.10**
  - [x] 29.4 Write property test for fallback classifier activates when model confidence is below threshold
    - **Property 20: Fallback classifier activates when model confidence is below threshold**
    - **Validates: Requirement 24.12**
  - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8, 24.9, 24.10, 24.11, 24.12, 24.13, 24.14_

- [x] 30. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 31. OWL Frontend — scaffolding and shared infrastructure
  - Set up OWL app entry point in `frontend/src/main.js`: register OWL app, configure OWL client-side router with hash-based navigation, initialize reactive stores
  - Implement `frontend/src/stores/`: `AccountSetStore` (reactive, current account set, list), `AuthStore` (JWT, user, role, inactivity timer), `NotificationStore`
  - Implement shared OWL components: `AppShell`, `Sidebar`, `TopBar`, `LoadingSpinner`, `ErrorBanner`, `ConfirmDialog`, `PaginatedTable`
  - Configure Odoo asset bundling pipeline (SCSS + OWL JS via Odoo asset bundle system); set up PWA manifest for mobile access
  - Implement RPC layer: `useService("rpc")` wrapper for all JSON-RPC calls to FastAPI backend; `useService("orm")` for ORM-style calls
  - _Requirements: 7.3_

- [x] 31a. OWL Frontend — Registration and Login pages
  - Implement `RegistrationPage` OWL component:
    - Channel selector: Email or Mobile tab
    - Email tab: display name, email, password (with strength indicator), confirm password → "Send OTP" button
    - Mobile tab: display name, mobile number (country code selector + number), password, confirm password → "Send OTP" button
    - OTP entry step: 6-digit OTP input, countdown timer (10 min), "Resend OTP" link (rate-limited, shows cooldown)
    - On success: auto-redirect to Account Set creation page
  - Implement `LoginPage` OWL component:
    - Email login tab: email + password → login button
    - Mobile login tab: mobile number → "Send OTP" → 6-digit OTP entry
    - "Forgot password?" link visible on both tabs
  - Implement `PasswordResetPage` OWL component:
    - Channel selector: reset via email or mobile
    - OTP request step → OTP entry step → new password + confirm password step
    - Password strength indicator; success redirects to login
  - All forms: inline validation, clear error messages for wrong OTP / expired OTP / account locked / duplicate registration
  - _Requirements: 31.1–31.14_

- [x] 32. OWL Frontend — Account Set, Chart of Accounts, and Voucher pages
  - Implement `AccountSetListPage`, `AccountSetCreatePage`:
    - Name, standard selector (CAS/IFRS), base currency, start period
    - Datasource selector: "Shared (platform managed)" vs "Individual (my own database)" — when Individual selected, show host/port/db name/user/password fields with a "Test Connection" button
  - Implement `AccountSetPermissionsPage` (Account_Set_Admin only):
    - Current account set name displayed at top
    - Invite user by mobile number with role selector (all built-in + custom roles listed)
    - User list showing each member's name, mobile, and current role with change/remove actions
    - Built-in roles displayed with their permission tags (read-only); custom roles show an Edit link
    - "+ Add Custom Role" button: opens form to name the role and toggle individual permissions
  - Implement `OpeningBalancePage` (table of accounts with debit/credit inputs, validates total debits = total credits)
  - Implement `ChartOfAccountsPage` (hierarchical tree view up to 4 levels, create/edit/delete custom accounts, enable aux dimensions)
  - Implement `VoucherListPage` (filterable by period, status, type), `VoucherCreatePage` (type selector, date, entries table with account picker + debit/credit + aux dimension, attachment upload, submit for review), `VoucherDetailPage` (approve/reject workflow, audit trail display)
  - _Requirements: 8.7–8.13, 11.1–11.12, 12.1–12.9, 13.1–13.12_

- [x] 33. OWL Frontend — Ledger, Period-End, and Report pages
  - Implement `GeneralLedgerPage`, `SubsidiaryLedgerPage`, `CashJournalPage`, `BankJournalPage`, `AccountSummaryPage` (all with period/account/dimension filters and PDF/Excel export)
  - Implement `PeriodEndPage` (cost carry-forward, profit/loss carry-forward, depreciation calculation, month-end close with pre-flight status display)
  - Implement `ReportPage` (balance sheet, income statement, cash flow statement with method selector for IFRS, account summary; PDF/CSV export; date range / currency / entity / entity group filters; report template designer and data source management)
  - _Requirements: 9.1–9.15, 14.1–14.7, 15.1–15.8_

- [x] 34. OWL Frontend — Cashier, Payroll, and Fixed Asset pages
  - Implement `CashierPage` (register accounts, record receipt/payment/transfer, FX balance display, physical cash reconciliation)
  - Implement `PayrollPage` (employee list, register employee, salary accrual, payslip generation, distribution channel selector)
  - Implement `FixedAssetPage` (asset register table, register asset form, depreciation calculation, disposal form)
  - _Requirements: 16.1–16.8, 17.1–17.8, 18.1–18.7_

- [x] 35. OWL Frontend — Smart Import, Invoice Scanner, and Tax pages
  - Implement `SmartImportPage` (file upload, parsed transaction table with account mapping suggestions, confirm/skip controls, import summary)
  - Implement `InvoiceScannerPage` (image upload, extracted fields display, verification status, manual correction, voucher generation confirmation)
  - Implement `TaxFilingPage` (filing report with editable line items, submit button, filing history table)
  - _Requirements: 19.1–19.7, 20.1–20.7, 21.1–21.7_

- [x] 36. OWL Frontend — Bank Integration and Reconciliation pages
  - Implement `BankConnectionPage` (connect bank, verify connection, routing method configuration per connection with parameter inputs, default routing method selector, routing history)
  - Implement `ReconciliationPage` (initiate reconciliation, auto-matched pairs table, unmatched items with manual match controls, reconciliation report, difference display)
  - _Requirements: 2.1–2.5, 5.1–5.8, 25.1–25.9_

- [x] 37. OWL Frontend — Domestic Payment page
  - Implement `DomesticPaymentPage` OWL component:
    - Source account selector (shows only accounts with configured routing methods)
    - Routing method selector (shows only configured + available methods for selected account)
    - Settlement method selector (dynamically updates based on routing method using routing→settlement matrix; shows estimated settlement date; warns if cut-off passed)
    - Recipient account selector (further filters routing/settlement options for compatibility)
    - Currency selector (CNY + foreign; shows applicable routing/settlement for selected currency)
    - Dynamic ISO 20022 field form: calls `getFieldConfiguration` on routing+settlement selection; renders Required fields (visually marked) and Optional fields; omits Hidden fields
    - Balance pre-check display; saves payment in Prepare status and adds to scheduling queue
  - _Requirements: 26.1–26.11, 28.4, 28.5_

- [x] 38. OWL Frontend — International Payment page
  - Implement `InternationalPaymentPage` OWL component:
    - Source account selector (SWIFT-configured accounts only)
    - Settlement method selector (Standard T+2, Express T+1, Same_Day_Value) with estimated value date and cut-off warning
    - SWIFT fields form: beneficiary name, account (IBAN/account number), BIC (validated 8/11 chars), bank name, bank address, correspondent BIC, payment currency, amount, value date, purpose code, remittance info
    - Indicative exchange rate display when currencies differ
    - Dynamic ISO 20022 field form: calls `getFieldConfiguration` for SWIFT + selected settlement method
    - Saves payment in Prepare status and adds to scheduling queue
  - _Requirements: 27.1–27.9, 28.4, 28.5_

- [x] 39. OWL Frontend — Payment scheduling queue and settlement workflow pages
  - Implement `PaymentQueuePage` OWL component:
    - Table of all Prepare + Instructed payments ordered by requested settlement date; columns: payment scope, amount, currency, routing method, settlement method, stage badge, transaction type, requested date, actions
    - Per-row actions: Instruct (Prepare → Instructed), View detail, Remove from queue
    - Batch actions: select multiple → Instruct all; select multiple Authorised → Pay all
    - Cut-off warning indicator per row when settlement date is at risk
  - Implement `PaymentDetailPage` OWL component:
    - Full payment field display with current stage badge, transaction type name, and stage configuration indicator (Manual/Auto per stage shown as a pipeline diagram)
    - Stage history timeline showing each transition with user, timestamp, and reason
    - Stage-appropriate action buttons: Check (approve/reject with reason input for Reviewer; only shown when Check=Manual), Authorise (for Authoriser; shows dual-auth status when threshold met), Pay Now button (for Authorised payments)
    - Rejection reason display when returned from Check or bank
    - Dual-authorisation status panel: shows first authoriser, awaiting second authoriser indicator
    - Auto-stage indicator: when next stage is Auto, show "will auto-advance" notice
  - _Requirements: 29.1–29.12_

- [x] 40. OWL Frontend — Payment Transaction Type configuration page
  - Implement `PaymentTransactionTypePage` OWL component (Admin role only):
    - List of existing transaction types with active/inactive status and default indicator
    - Create/edit form: name field; per-stage Manual/Auto toggle for Prepare, Check, Confirm (Instruct, Authorise, Settle locked to Manual with tooltip explaining constraint)
    - Visual pipeline diagram showing the 6 stages with Manual/Auto badges updating live as toggles change
    - Default type selector; deactivate button with confirmation dialog
    - Save with audit log confirmation showing before/after stage mode diff
    - Per-Account_Set scope display
  - _Requirements: 30.1–30.11_

- [x] 41. OWL Frontend — Payment Field Configuration admin page
  - Implement `PaymentFieldConfigPage` OWL component (Admin role only):
    - Routing method + settlement method combination selector
    - ISO 20022 field list with Required/Optional/Hidden radio selectors per field and drag-to-reorder for display_order
    - Validation: six mandatory fields locked to Required (UI enforces, backend validates)
    - Save with audit log confirmation dialog showing before/after diff
    - Per-Account_Set scope display
  - _Requirements: 28.1, 28.2, 28.3, 28.6, 28.7, 28.8, 28.9_

- [x] 42. OWL Frontend — IFRS Compliance, ML Forecast, and NLP Assistant pages
  - Implement `IFRSCompliancePage` (fair value adjustment form, right-of-use asset registration, revenue recognition against performance obligations, impairment test form, disclosure notes viewer)
  - Implement `ForecastPage` (forecast chart with confidence intervals, MAPE metric display, historical vs actual comparison chart, horizon selector 1–12 months, PDF/CSV export; insufficient data notice when < 6 months)
  - Implement `NLPAssistantPanel` (chat interface supporting English and Chinese; intent confirmation form for action intents; conversation history display; fallback mode notice when DeepSeek unavailable)
  - _Requirements: 22.1–22.7, 23.1–23.12, 24.1–24.14_

- [x] 43. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 44. Partial MCP Adapter — read-only agent tool surface
  - Add Python dependency `mcp` (FastMCP) to `backend/requirements.txt` and `backend/pyproject.toml`
  - Implement `backend/smartbook_mcp/` package (avoid naming the package `mcp` so it does not shadow the SDK):
    - `auth.py` — resolve `SMARTBOOK_MCP_TOKEN` / `MCP_AUTH_TOKEN`, verify JWT, enforce Account_Set match + RBAC permissions
    - `serialize.py` — JSON helpers for voucher/account-set payloads
    - `tools.py` — register read-only tools wrapping existing services: `list_account_sets`, `get_account_tree`, `list_vouchers`, `get_voucher`, `get_account_summary`
    - `server.py` — FastMCP factory; stdio runner; optional Streamable HTTP app
    - `__main__.py` — `python -m smartbook_mcp` entry for local agents
  - Add `platform.db_router.open_tenant_session(account_set_id)` for non-HTTP tenant DB access; bypass `/mcp` in TenantDBMiddleware
  - Mount `/mcp` on svc-accounting when `SMARTBOOK_MCP_ENABLED=true`
  - Fix `backend/platform/__init__.py` to re-export stdlib `platform` APIs so `mcp`/`attrs`/`jsonschema` import correctly under `PYTHONPATH=backend`
  - Document Cursor wiring in `scripts/cursor-mcp.json.example`; document env vars in `scripts/dev.env.example`
  - [x] 44.1 Write unit tests for MCP auth gates, serialization, tool registration, and list_vouchers service wrap
    - `backend/tests/test_smartbook_mcp_unit.py`
    - _Requirements: 37.4, 37.5, 37.6, 37.7_
  - _Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6, 37.7, 37.8, 37.9_

- [x] 45. API integration tests (auth + Account Set + core module connectivity)
  - Add `backend/tests/integration/` with pytest marker `integration` (skipped unless `INTEGRATION=1`)
  - Cover register → OTP verify → login → create/list/switch Account Set; auth guards; password reset
  - Cover chart of accounts, voucher lifecycle, ledger, reports, period-end
  - Cover sidebar module smoke: cashier, payroll, assets, bank, payments, tax, ifrs, reconciliation, forecast, nlp
  - Add runner scripts: `scripts/integration-test.ps1`, `scripts/integration-test.sh` (also sanity-check frontend `DEFAULT_BASE` / `API_BASE_URL` wiring)
  - Fix connectivity bugs found by the suite (JWT `sub`, Shared registry, members cross-DB join, tax route order, MySQL NULLS LAST, account tree UUID serialization, registry pool_pre_ping)
  - Document how to run in README
  - _Requirements: (dev quality / FE↔BE integration)_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests use Hypothesis with minimum 100 iterations each; each test includes the comment `# Feature: smart-accounting-software, Property {N}: {property_text}`
- Unit tests cover specific examples, error conditions, and edge cases complementing the property tests
- All property-based test sub-tasks are placed immediately after the implementation task they validate
