# Requirements Document

## Introduction

The Smart Accounting Software is a cloud-based financial management system designed for finance professionals managing small enterprises. The system provides comprehensive accounting capabilities including voucher management, chart of accounts, ledger books, period-end processing, financial reporting, cashier management, payroll, fixed asset tracking, and smart import of bank and invoice data. The system supports both Chinese Accounting Standards (CAS) and International Financial Reporting Standards (IFRS) as first-class accounting standard choices, and supports multi-enterprise management. Optionally, a partial Model Context Protocol (MCP) adapter exposes a curated set of read-only tools so external AI agents can query accounting data under the same JWT/RBAC controls as the REST API.

## Glossary

- **Accounting_System**: The smart accounting software system being specified
- **Finance_User**: A finance professional who uses the system to manage accounting for small enterprises
- **Account_Set**: An isolated accounting entity for one enterprise, containing its own chart of accounts, periods, and settings (账套)
- **Voucher**: An accounting document recording one or more debit/credit entries for a financial event (凭证)
- **Voucher_Engine**: The subsystem that creates, validates, and manages accounting vouchers
- **Chart_of_Accounts**: The hierarchical list of account codes and names used within an Account_Set (科目)
- **Account_Manager**: The subsystem that manages the Chart_of_Accounts and account dimensions
- **Ledger_Engine**: The subsystem that maintains and queries general ledger, subsidiary ledger, and journal books
- **Period**: An accounting month identified by year and month, e.g., 202608 (期间)
- **Period_End_Processor**: The subsystem that performs month-end closing, carry-forwards, and depreciation
- **Bank_Integration**: The subsystem that connects to external banking systems
- **Reconciliation_Engine**: The subsystem that matches and verifies transactions between internal records and bank statements
- **Payment_Hub**: The subsystem that processes and initiates payments through connected bank systems
- **Cash_Flow_Tracker**: The subsystem that monitors and reports money movement over time
- **Cashier_Module**: The subsystem that manages cash and bank accounts, fund transfers, and multi-currency operations
- **Payroll_Module**: The subsystem that manages employees, salary calculation, payslip generation, and social insurance
- **Asset_Module**: The subsystem that manages fixed asset registration, tracking, and depreciation
- **Smart_Import**: The subsystem that imports bank transaction data and generates vouchers intelligently
- **Invoice_Scanner**: The subsystem that scans, verifies, and converts invoices into vouchers
- **Tax_Module**: The subsystem that prepares and submits tax filings
- **Report_Engine**: The subsystem that generates financial statements and reports
- **Bank_Account**: An external bank account linked to the system
- **Opening_Balance**: The account balance at the start of a specified period (期初余额)
- **Closing_Balance**: The account balance at the end of a specified period
- **Current_Balance**: The real-time account balance at the moment of query
- **Small_Enterprise**: A business with fewer than 50 employees and annual revenue under $10 million
- **Auxiliary_Dimension**: A secondary classification axis for accounts, such as department, project, customer, supplier, or employee (辅助核算)
- **Depreciation**: The systematic allocation of a fixed asset's cost over its useful life
- **Accounting_Standard**: The financial reporting framework selected for an Account_Set, either Chinese Accounting Standards (CAS) or International Financial Reporting Standards (IFRS)
- **CAS**: Chinese Accounting Standards — the accounting framework mandated for enterprises in mainland China, issued by the Ministry of Finance of the People's Republic of China
- **IFRS**: International Financial Reporting Standards — the globally adopted accounting framework issued by the International Accounting Standards Board (IASB)
- **ML_Forecast_Engine**: The subsystem that trains machine learning models on historical transaction and cash flow data to produce forward-looking cash flow predictions
- **Forecast_Model**: A trained ML model scoped to a single Account_Set, capturing that enterprise's unique cash flow patterns
- **Forecast_Horizon**: The number of future periods (months) for which a cash flow prediction is generated
- **NLP_Assistant**: The subsystem that processes natural language input from Finance_Users and translates it into system actions, queries, or guidance responses
- **DeepSeek_Model**: The locally-hosted DeepSeek-R1-Distill free open-source distilled reasoning model used as the NLP backbone for common interactions
- **Intent**: A classified user goal extracted from a natural language input (e.g., "create voucher", "query balance", "generate report", "explain account")
- **Conversation_Context**: The session-scoped memory of recent user messages and system responses used to maintain coherent multi-turn dialogue
- **Payment_Routing_Method**: The channel or protocol used to transmit a payment instruction to the banking system (e.g., SWIFT, CNAPS, CIPS, Direct_Debit, Online_Banking_Transfer, Local_ACH, Internal_Transfer)
- **Settlement_Method**: The timing and mechanism by which funds are actually transferred and settled between accounts after a payment instruction is submitted (e.g., Real_Time_Gross_Settlement, Same_Day_Settlement, T+1 Batch_Settlement)
- **Domestic_Payment**: A payment initiated between accounts within the same country, supporting both local currency (CNY) and foreign currency
- **International_Payment**: A cross-border payment initiated via SWIFT to a beneficiary account in a different country
- **ISO_20022**: The international standard for financial messaging (pain.001 CustomerCreditTransferInitiation) that defines the data fields used in payment initiation messages
- **Payment_Field_Configuration**: The per-Account_Set settings that control which ISO 20022 payment initiation fields are displayed (Required, Optional, or Hidden) for each routing method and settlement method combination
- **Settlement_Process**: The six-stage workflow (Prepare → Instruct → Check → Authorise → Confirm → Settle) that every payment must pass through before funds are considered settled
- **Scheduling_Queue**: The ordered list of payments in Prepare or Instructed status awaiting progression through the settlement workflow, ordered by requested settlement date
- **Payment_Transaction_Type**: A named configuration per Account_Set that defines, for each of the six settlement stages, whether the stage is Manual (requires explicit user action) or Auto (system advances automatically); the default type "Standard" requires manual action only at Instruct, Authorise, and Settle
- **User_Registration**: The process by which a new user creates an account in the system using an email address or mobile phone number, verified by a 6-digit OTP
- **OTP**: A one-time password — a 6-digit numeric code sent to a user's email or mobile number for identity verification during registration, login, or password reset; valid for 10 minutes
- **Account_Set_Admin**: The role automatically assigned to the user who creates an Account_Set; has full permissions including delete, backup/restore, reinitialize, and user access management for that Account_Set
- **Account_Set_Role**: A named permission set scoped to a single Account_Set, assigned to a user to control which operations they may perform within that Account_Set; built-in roles are Account_Set_Admin, Supervisor, Voucher_Clerk, Cashier, and Viewer; custom roles may be created by the Account_Set_Admin
- **Shared_Datasource**: The default database provisioning mode where the Account_Set's data is stored in the platform's shared multi-tenant database pool
- **Individual_Datasource**: An optional database provisioning mode where the Account_Set owner provides their own PostgreSQL or MySQL 8.0+ connection; the platform provisions the schema on the provided database
- **MCP**: Model Context Protocol — an open protocol that lets external AI agents discover and invoke tools exposed by the Accounting_System
- **MCP_Adapter**: The subsystem that exposes a curated, RBAC-enforced subset of accounting capabilities as MCP tools (without reimplementing business logic)
- **MCP_Tool**: A named, schema-documented operation exposed over MCP (e.g., list vouchers, get account summary); implemented as a thin wrapper over existing services
- **External_Agent**: An MCP client such as Cursor, Claude Desktop, or another agent host that consumes MCP_Tools on behalf of a Finance_User

## Requirements

### Requirement 1: Record Financial Transactions

**User Story:** As a Finance_User, I want to record accounting transactions, so that I can maintain accurate financial records for the enterprise

#### Acceptance Criteria

1. THE Accounting_System SHALL accept transaction entries with date, amount, account, and description
2. WHEN a transaction is recorded, THE Accounting_System SHALL validate that the amount is a positive number
3. WHEN a transaction is recorded, THE Accounting_System SHALL validate that the date is not in the future
4. WHEN a transaction is recorded, THE Accounting_System SHALL assign a unique transaction identifier
5. THE Accounting_System SHALL store all recorded transactions persistently
6. WHEN a Finance_User requests transaction history, THE Accounting_System SHALL retrieve transactions within the specified date range

### Requirement 2: Connect to Banking Systems

**User Story:** As a Finance_User, I want to connect the system to my bank accounts, so that I can automatically track cash flow and retrieve balance information

#### Acceptance Criteria

1. THE Bank_Integration SHALL support secure authentication with banking systems using industry-standard protocols
2. WHEN a Finance_User initiates a bank connection, THE Bank_Integration SHALL request and store necessary credentials securely
3. WHEN a bank connection is established, THE Bank_Integration SHALL verify the connection status
4. IF a bank connection fails, THEN THE Bank_Integration SHALL provide a descriptive error message to the Finance_User
5. THE Bank_Integration SHALL maintain active connections to multiple Bank_Accounts simultaneously

### Requirement 3: Track Cash Flow from Banking Systems

**User Story:** As a Finance_User, I want to automatically import bank transactions, so that I can track cash flow without manual data entry

#### Acceptance Criteria

1. WHEN a Bank_Account is connected, THE Cash_Flow_Tracker SHALL retrieve new transactions from the banking system at least once per day
2. WHEN bank transactions are retrieved, THE Cash_Flow_Tracker SHALL import them into the system with date, amount, description, and reference number
3. THE Cash_Flow_Tracker SHALL categorize imported transactions as inflow or outflow based on transaction type
4. WHEN duplicate transactions are detected, THE Cash_Flow_Tracker SHALL prevent duplicate imports
5. WHEN transactions are imported, THE Cash_Flow_Tracker SHALL calculate the net cash flow for the specified period
6. THE Cash_Flow_Tracker SHALL generate cash flow reports showing inflows, outflows, and net change over time

### Requirement 4: Retrieve Bank Balance Information

**User Story:** As a Finance_User, I want to retrieve current and historical bank balances, so that I can monitor account status and verify financial positions

#### Acceptance Criteria

1. WHEN a Finance_User requests balance information, THE Bank_Integration SHALL retrieve the Current_Balance from the connected Bank_Account within 5 seconds
2. WHEN a Finance_User specifies a date range, THE Bank_Integration SHALL retrieve the Opening_Balance for the start date
3. WHEN a Finance_User specifies a date range, THE Bank_Integration SHALL retrieve the Closing_Balance for the end date
4. THE Bank_Integration SHALL display balance amounts in the currency of the Bank_Account
5. IF balance retrieval fails, THEN THE Bank_Integration SHALL display the last successfully retrieved balance with a timestamp
6. THE Bank_Integration SHALL cache balance information for up to 1 hour to reduce API calls

### Requirement 5: Reconcile Accounting Records with Bank Statements

**User Story:** As a Finance_User, I want to reconcile my internal accounting records with bank statements, so that I can identify discrepancies and ensure accuracy

#### Acceptance Criteria

1. WHEN a Finance_User initiates reconciliation, THE Reconciliation_Engine SHALL compare internal transactions with imported bank transactions for the specified period
2. THE Reconciliation_Engine SHALL match transactions based on date, amount, and description similarity
3. WHEN transactions match, THE Reconciliation_Engine SHALL mark them as reconciled
4. WHEN transactions do not match, THE Reconciliation_Engine SHALL flag them as unreconciled
5. THE Reconciliation_Engine SHALL calculate the reconciliation difference as the sum of unreconciled amounts
6. WHEN reconciliation is complete, THE Reconciliation_Engine SHALL generate a reconciliation report showing matched, unmatched, and missing transactions
7. THE Reconciliation_Engine SHALL allow Finance_Users to manually match transactions that were not automatically matched
8. WHEN a Finance_User manually matches transactions, THE Reconciliation_Engine SHALL update the reconciliation status immediately

### Requirement 6: Process Payments Through Banking Systems

**User Story:** As a Finance_User, I want to initiate payments through the system, so that I can manage outgoing payments efficiently and maintain payment records

#### Acceptance Criteria

1. THE Payment_Hub SHALL allow Finance_Users to create payment instructions with recipient, amount, date, and reference
2. WHEN a payment is created, THE Payment_Hub SHALL validate that sufficient balance exists in the source Bank_Account
3. WHEN a payment is submitted, THE Payment_Hub SHALL transmit the payment instruction to the connected banking system
4. WHEN a payment is transmitted, THE Payment_Hub SHALL receive a confirmation or rejection from the banking system within 30 seconds
5. IF a payment is rejected, THEN THE Payment_Hub SHALL display the rejection reason to the Finance_User
6. WHEN a payment is confirmed, THE Payment_Hub SHALL record the payment in the transaction history
7. THE Payment_Hub SHALL track payment status (pending, completed, failed) for all initiated payments
8. THE Payment_Hub SHALL support scheduling future-dated payments

### Requirement 7: Manage Multiple Small Enterprises

**User Story:** As a Finance_User, I want to manage accounting for multiple small enterprises, so that I can service multiple clients from one system

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to create separate accounting entities for each Small_Enterprise
2. THE Accounting_System SHALL maintain data isolation between different Small_Enterprise entities
3. WHEN a Finance_User switches between enterprises, THE Accounting_System SHALL display only the data for the selected enterprise
4. THE Accounting_System SHALL allow each Small_Enterprise to have multiple connected Bank_Accounts
5. THE Accounting_System SHALL generate separate financial reports for each Small_Enterprise

### Requirement 8: Ensure Data Security and Access Control

**User Story:** As a Finance_User, I want role-based access controls per Account Set, so that each user has only the permissions appropriate for their role within that enterprise

#### Acceptance Criteria

1. THE Accounting_System SHALL require authentication before granting access to any financial data
2. THE Accounting_System SHALL encrypt all stored financial data using AES-256 encryption
3. THE Accounting_System SHALL encrypt all data transmitted to banking systems using TLS 1.3 or higher
4. WHEN a Finance_User session is inactive for 15 minutes, THE Accounting_System SHALL automatically log out the user
5. THE Accounting_System SHALL maintain an audit log of all transaction modifications and deletions
6. THE Accounting_System SHALL restrict access to audit logs to the Account_Set_Admin role only
7. THE Accounting_System SHALL enforce role-based access control (RBAC) per Account_Set; each user is assigned exactly one role per Account_Set they have access to
8. THE Accounting_System SHALL provide the following built-in roles per Account_Set, with the default permission sets shown:
   - **Account_Set_Admin (账套管理员)**: full access — vouchers, cashier, invoices, payroll, assets, tax, period-end, ledger, reports, create account set, delete account set, backup/restore, reinitialize account set, link inventory, link cloud invoices; this role is automatically assigned to the user who created the Account_Set and cannot be removed from that user
   - **Supervisor (主管)**: vouchers, cashier, invoices, payroll, assets, tax, period-end, ledger, reports, create account set
   - **Voucher_Clerk (制单人)**: vouchers, invoices, payroll, assets, tax, period-end, view cashier/ledger/reports, create account set
   - **Cashier (出纳)**: cashier operations, view vouchers/assets/ledger/reports, create account set
   - **Viewer (查看)**: view-only access to vouchers, cashier, assets, ledger, reports; create account set
9. THE Accounting_System SHALL allow the Account_Set_Admin to invite other registered users to an Account_Set by entering their mobile number; the invited user is assigned a selected role
10. THE Accounting_System SHALL allow the Account_Set_Admin to create custom roles for an Account_Set by selecting a subset of available permissions from the permission list; custom roles are scoped to that Account_Set only
11. THE Accounting_System SHALL allow the Account_Set_Admin to edit the permission set of any custom role; built-in role permission sets cannot be modified
12. THE Accounting_System SHALL allow the Account_Set_Admin to change the role assigned to any user within the Account_Set, except the Account_Set_Admin role of the creator cannot be revoked
13. WHEN a user attempts an operation they do not have permission for, THE Accounting_System SHALL reject the request and display a descriptive permission error

### Requirement 9: Generate Financial Reports

**User Story:** As a Finance_User, I want to generate financial reports, so that I can analyze the financial health of the enterprise

#### Acceptance Criteria

1. WHEN a Finance_User requests a balance sheet and the Account_Set uses CAS, THE Report_Engine SHALL auto-generate the balance sheet using CAS terminology and format from the current Account_Set ledger data
2. WHEN a Finance_User requests a balance sheet and the Account_Set uses IFRS, THE Report_Engine SHALL auto-generate the Statement of Financial Position using IFRS terminology and format from the current Account_Set ledger data
3. WHEN a Finance_User requests a profit and loss statement and the Account_Set uses CAS, THE Report_Engine SHALL auto-generate the income statement using CAS terminology and format from the current Account_Set ledger data
4. WHEN a Finance_User requests a profit and loss statement and the Account_Set uses IFRS, THE Report_Engine SHALL auto-generate the Statement of Profit or Loss and Other Comprehensive Income using IFRS terminology and format from the current Account_Set ledger data
5. WHEN a Finance_User requests a cash flow statement and the Account_Set uses CAS, THE Report_Engine SHALL auto-generate the cash flow statement following CAS format from the current Account_Set ledger data
6. WHEN a Finance_User requests a cash flow statement and the Account_Set uses IFRS, THE Report_Engine SHALL auto-generate the cash flow statement following IAS 7, supporting both the direct and indirect method, from the current Account_Set ledger data
7. WHEN a Finance_User requests an account summary report, THE Report_Engine SHALL aggregate debit and credit totals by account for the specified Period
8. WHEN a report is generated, THE Report_Engine SHALL complete the generation within 10 seconds for up to 10,000 transactions
9. THE Report_Engine SHALL allow Finance_Users to export reports in PDF and CSV formats
10. THE Report_Engine SHALL display reports with currency formatting appropriate to the enterprise's base currency
11. THE Report_Engine SHALL allow Finance_Users to specify a custom date range,custom currency, custome entity, entity group for each report
12. THE Report_Engine SHALL support Finance_Users to create report template via select data source and release the report for different access user.
13. THE Report_Engine SHALL support Finance_Users to add data source for report.
14. THE Report_Engine SHALL support data source for API and Data Server connection mode.
15. THE Report_Engine SHALL MySQL，Oracle，SQL Server Data Server connection for differnt type vendors.

### Requirement 10: Handle Banking System Errors

**User Story:** As a Finance_User, I want the system to handle banking errors gracefully, so that temporary issues don't disrupt my workflow

#### Acceptance Criteria

1. IF a banking system connection times out, THEN THE Bank_Integration SHALL retry the connection up to 3 times with exponential backoff
2. IF a banking system returns an error, THEN THE Bank_Integration SHALL log the error details for troubleshooting
3. IF a banking system is unavailable, THEN THE Accounting_System SHALL allow Finance_Users to continue working with cached data
4. WHEN a banking system becomes available again, THE Bank_Integration SHALL automatically resume synchronization
5. THE Bank_Integration SHALL notify Finance_Users when banking system connectivity is restored

### Requirement 11: Manage Account Sets

**User Story:** As a registered user, I want to create and manage account sets for each enterprise, so that each enterprise has its own isolated accounting environment with appropriate settings and I have full administrative control over it

#### Acceptance Criteria

1. THE Accounting_System SHALL allow any registered user to create a new Account_Set for a Small_Enterprise with a name, Journal Set No., Accounting_Standard (CAS or IFRS), base currency, start Period, and Status (default Active)
2. WHEN a user creates an Account_Set, THE Accounting_System SHALL automatically assign that user the Account_Set_Admin role for that Account_Set
3. WHEN creating an Account_Set, THE Accounting_System SHALL allow the user to choose the datasource type:
   - **Shared datasource**: the Account_Set uses the platform's shared multi-tenant database pool (default, no extra cost)
   - **Individual datasource**: the user provides their own database connection (PostgreSQL or MySQL 8.0+); the system provisions the schema and runs migrations on the provided connection
4. WHEN an Account_Set is created with CAS selected, THE Accounting_System SHALL initialize it with the default CAS Chart_of_Accounts
5. WHEN an Account_Set is created with IFRS selected, THE Accounting_System SHALL initialize it with the default IFRS Chart_of_Accounts
6. THE Accounting_System SHALL allow Finance_Users to set Opening_Balance amounts for each account in the Chart_of_Accounts during Account_Set initialization
7. WHEN Opening_Balance entries are saved, THE Accounting_System SHALL validate that total debits equal total credits across all accounts
8. THE Accounting_System SHALL allow Finance_Users to switch between Account_Sets without losing unsaved data in the current Account_Set
9. THE Accounting_System SHALL maintain separate Periods, vouchers, and ledger data for each Account_Set
10. THE Account_Set_Admin SHALL be able to delete an Account_Set; deletion requires explicit confirmation and is irreversible
11. THE Account_Set_Admin SHALL be able to backup and restore an Account_Set
12. THE Account_Set_Admin SHALL be able to reinitialize an Account_Set (reset to initial state, clearing all vouchers and ledger data while preserving the chart of accounts and settings)

### Requirement 12: Manage Chart of Accounts

**User Story:** As a Finance_User, I want to manage a hierarchical chart of accounts, so that I can organize financial data according to the enterprise's accounting structure

#### Acceptance Criteria

1. THE Account_Manager SHALL maintain a hierarchical Chart_of_Accounts with parent and child account relationships up to 4 levels deep
2. WHEN the Account_Set uses CAS, THE Account_Manager SHALL assign a unique account code to each account following the CAS numbering scheme
3. WHEN the Account_Set uses IFRS, THE Account_Manager SHALL assign a unique account code to each account following the IFRS numbering scheme
4. THE Account_Manager SHALL allow Finance_Users to create custom child accounts under any existing parent account
5. WHEN a Finance_User creates a custom account, THE Account_Manager SHALL validate that the account code is unique within the Account_Set
6. THE Account_Manager SHALL allow Finance_Users to modify the name of custom accounts
7. WHEN a Finance_User attempts to delete an account that has existing voucher entries, THE Account_Manager SHALL reject the deletion and display a descriptive error
8. THE Account_Manager SHALL allow Finance_Users to enable Auxiliary_Dimensions (department, project, customer, supplier, employee) on any leaf-level account
9. WHEN an Auxiliary_Dimension is enabled on an account, THE Voucher_Engine SHALL require the Finance_User to specify the dimension value when recording entries to that account

### Requirement 13: Manage Accounting Vouchers

**User Story:** As a Finance_User, I want to create and manage accounting vouchers, so that I can record all financial events with proper double-entry bookkeeping

#### Acceptance Criteria

1. THE Voucher_Engine SHALL allow Finance_Users to create vouchers of type receipt (收款凭证), payment (付款凭证), or transfer (转账凭证)
2. WHEN a voucher is created, THE Voucher_Engine SHALL require at least one debit entry and one credit entry
3. WHEN a voucher is saved, THE Voucher_Engine SHALL validate that the sum of all debit amounts equals the sum of all credit amounts
4. IF the sum of debit amounts does not equal the sum of credit amounts, THEN THE Voucher_Engine SHALL reject the save and display the imbalance amount to the Finance_User
5. WHEN a voucher is saved, THE Voucher_Engine SHALL assign a sequential voucher number within the current Period
6. THE Voucher_Engine SHALL allow Finance_Users to attach supporting documents to a voucher, with each attachment stored as a file reference
7. THE Voucher_Engine SHALL allow Finance_Users to edit vouchers that have not yet been reviewed
8. WHEN a Finance_User submits a voucher for review, THE Voucher_Engine SHALL change the voucher status to "pending review"
9. WHEN a reviewer approves a voucher, THE Voucher_Engine SHALL change the voucher status to "approved" and record the reviewer's identity and approval timestamp
10. WHEN a reviewer rejects a voucher, THE Voucher_Engine SHALL change the voucher status to "rejected" and record the rejection reason
11. THE Voucher_Engine SHALL allow Finance_Users to perform batch operations (batch delete, batch approve) on multiple vouchers within the same Period
12. WHEN a Finance_User deletes a voucher, THE Voucher_Engine SHALL record the deletion in the audit log with the user identity and timestamp

### Requirement 14: Query Ledger Books

**User Story:** As a Finance_User, I want to query ledger books, so that I can review account activity and balances in detail

#### Acceptance Criteria

1. WHEN a Finance_User queries the general ledger for an account, THE Ledger_Engine SHALL display all voucher entries for that account in the specified Period with running balance
2. WHEN a Finance_User queries the subsidiary ledger for an account with Auxiliary_Dimensions, THE Ledger_Engine SHALL display entries grouped by each dimension value
3. WHEN a Finance_User queries the cash journal, THE Ledger_Engine SHALL display all entries for cash accounts (account type 1010) in date order for the specified Period
4. WHEN a Finance_User queries the bank journal, THE Ledger_Engine SHALL display all entries for bank accounts (account type 1020) in date order for the specified Period
5. WHEN a Finance_User queries the account summary table, THE Ledger_Engine SHALL display the opening balance, total debits, total credits, and closing balance for each account in the specified Period
6. THE Ledger_Engine SHALL allow Finance_Users to filter ledger queries by account code, date range, and Auxiliary_Dimension value
7. WHEN a Finance_User exports a ledger query result, THE Ledger_Engine SHALL produce the export in PDF or Excel format within 15 seconds

### Requirement 15: Perform Period-End Processing

**User Story:** As a Finance_User, I want to perform period-end processing, so that I can close each accounting month with accurate carry-forwards and a clean starting position for the next period

#### Acceptance Criteria

1. WHEN a Finance_User initiates cost carry-forward, THE Period_End_Processor SHALL generate a transfer voucher that moves the balance of cost accounts to the designated profit/loss account for the current Period
2. WHEN a Finance_User initiates profit/loss carry-forward and the Account_Set uses CAS, THE Period_End_Processor SHALL generate a transfer voucher that moves the net profit or loss to the CAS-designated retained earnings account for the current Period
3. WHEN a Finance_User initiates profit/loss carry-forward and the Account_Set uses IFRS, THE Period_End_Processor SHALL generate a transfer voucher that moves the net profit or loss to the retained earnings account in equity as specified by IAS 1 for the current Period
4. WHEN a Finance_User initiates month-end closing, THE Period_End_Processor SHALL validate that all vouchers in the current Period have been approved before allowing the close
5. IF unapproved vouchers exist in the current Period, THEN THE Period_End_Processor SHALL reject the month-end close and display the count of unapproved vouchers
6. WHEN a Period is closed, THE Period_End_Processor SHALL prevent creation or modification of vouchers in that Period
7. WHEN a Period is closed, THE Period_End_Processor SHALL carry forward the closing balances of all balance sheet accounts as the Opening_Balance of the next Period
8. WHEN a Finance_User initiates depreciation calculation, THE Period_End_Processor SHALL calculate depreciation for all active fixed assets and generate the corresponding depreciation voucher for the current Period

### Requirement 16: Manage Cashier Operations

**User Story:** As a Finance_User, I want to manage cash and bank accounts through a dedicated cashier module, so that I can track fund movements and maintain accurate cash positions

#### Acceptance Criteria

1. THE Cashier_Module SHALL allow Finance_Users to register cash accounts (account type 1010) and bank accounts (account type 1020) within the Account_Set
2. WHEN a Finance_User records a cash receipt, THE Cashier_Module SHALL create a corresponding receipt voucher in the Voucher_Engine
3. WHEN a Finance_User records a cash payment, THE Cashier_Module SHALL create a corresponding payment voucher in the Voucher_Engine
4. THE Cashier_Module SHALL allow Finance_Users to record fund transfers between two registered accounts with income and expenditure amounts
5. WHEN a fund transfer is recorded, THE Cashier_Module SHALL validate that the income amount equals the expenditure amount before saving
6. WHERE multi-currency is enabled for an Account_Set, THE Cashier_Module SHALL record the foreign currency amount, exchange rate, and functional currency equivalent for each transaction
7. WHERE multi-currency is enabled, THE Cashier_Module SHALL calculate and display the functional currency balance for each foreign currency account using the recorded exchange rates
8. WHEN a Finance_User performs a cash reconciliation check, THE Cashier_Module SHALL compare the system cash balance against the Finance_User-entered physical cash count and display any discrepancy

### Requirement 17: Manage Payroll

**User Story:** As a Finance_User, I want to manage employee payroll, so that I can calculate salaries, generate payslips, and create the corresponding accounting vouchers automatically

#### Acceptance Criteria

1. THE Payroll_Module SHALL allow Finance_Users to register employees with name, department, position, and base salary
2. THE Payroll_Module SHALL allow Finance_Users to organize employees into departments
3. WHEN a Finance_User initiates salary accrual for a Period, THE Payroll_Module SHALL calculate gross salary for each employee based on base salary and any recorded adjustments
4. WHEN a Finance_User initiates salary accrual, THE Payroll_Module SHALL calculate social insurance and housing fund deductions (五险一金) for each employee based on the configured contribution rates
5. WHEN salary accrual is confirmed, THE Payroll_Module SHALL generate a payroll voucher in the Voucher_Engine recording salary expense, social insurance expense, and payable liabilities
6. WHEN a Finance_User requests payslip generation, THE Payroll_Module SHALL generate individual payslips for all employees in the specified Period within 30 seconds
7. THE Payroll_Module SHALL allow Finance_Users to distribute payslips to employees via WeChat, email, or SMS
8. IF payslip distribution to an employee fails, THEN THE Payroll_Module SHALL record the failure with the employee identifier and the failure reason

### Requirement 18: Manage Fixed Assets

**User Story:** As a Finance_User, I want to register and track fixed assets, so that I can maintain an accurate asset register and automate depreciation calculations

#### Acceptance Criteria

1. THE Asset_Module SHALL allow Finance_Users to register a fixed asset with name, category, acquisition date, original cost, useful life in months, and depreciation method
2. THE Asset_Module SHALL support straight-line and declining-balance depreciation methods
3. WHEN a Finance_User requests depreciation calculation for a Period, THE Asset_Module SHALL calculate the depreciation amount for each active fixed asset using the asset's configured depreciation method
4. WHEN depreciation is calculated, THE Asset_Module SHALL update the accumulated depreciation and net book value for each asset
5. WHEN a Finance_User confirms depreciation for a Period, THE Asset_Module SHALL generate a depreciation voucher in the Voucher_Engine recording depreciation expense and accumulated depreciation
6. THE Asset_Module SHALL display the asset register showing original cost, accumulated depreciation, and net book value for each asset
7. WHEN a Finance_User disposes of a fixed asset, THE Asset_Module SHALL calculate the gain or loss on disposal and generate the corresponding disposal voucher in the Voucher_Engine

### Requirement 19: Smart Import of Bank and Payment Transactions

**User Story:** As a Finance_User, I want to import transaction data from bank statements, WeChat Pay, and Alipay, so that I can generate accounting vouchers automatically without manual data entry

#### Acceptance Criteria

1. THE Smart_Import SHALL accept transaction data files in formats exported by major Chinese banks, WeChat Pay, and Alipay
2. WHEN a transaction file is imported, THE Smart_Import SHALL parse each transaction record and extract date, amount, counterparty, and description
3. THE Smart_Import SHALL parse the imported file and produce a structured transaction list; FOR ALL valid transaction files, parsing then re-exporting then re-parsing SHALL produce an equivalent transaction list (round-trip property)
4. WHEN transactions are parsed, THE Smart_Import SHALL match each transaction to a suggested account code based on the transaction description and counterparty using keyword rules
5. WHEN a Finance_User confirms the account mapping for an imported transaction, THE Smart_Import SHALL generate a voucher in the Voucher_Engine with the mapped debit and credit entries
6. WHEN duplicate transactions are detected during import (same date, amount, and reference number already exist), THE Smart_Import SHALL skip the duplicate and report the count of skipped records to the Finance_User
7. WHEN an import batch is complete, THE Smart_Import SHALL display a summary showing total records processed, vouchers generated, and records skipped

### Requirement 20: Invoice Scanning and Voucher Auto-Generation

**User Story:** As a Finance_User, I want to scan invoices and automatically generate vouchers, so that I can reduce manual data entry and ensure invoice data is accurately recorded

#### Acceptance Criteria

1. THE Invoice_Scanner SHALL accept invoice images in JPEG and PDF formats
2. WHEN an invoice image is submitted, THE Invoice_Scanner SHALL extract invoice number, date, seller name, buyer name, item descriptions, amounts, and tax amounts
3. WHEN an invoice is extracted, THE Invoice_Scanner SHALL verify the invoice against the tax authority database and return a verification status within 10 seconds
4. IF invoice verification fails, THEN THE Invoice_Scanner SHALL display the verification failure reason and allow the Finance_User to proceed with manual correction
5. WHEN a Finance_User confirms a verified invoice, THE Invoice_Scanner SHALL generate a voucher in the Voucher_Engine with debit entries for expense and tax accounts and a credit entry for the payable account
6. THE Invoice_Scanner SHALL store the original invoice image as an attachment on the generated voucher
7. FOR ALL valid invoice images, scanning then generating a voucher then viewing the voucher attachment SHALL return the original invoice image (round-trip property)

### Requirement 21: Tax Filing Support

**User Story:** As a Finance_User, I want to prepare and submit tax filings from within the system, so that I can meet tax obligations efficiently using data already recorded in the accounting system

#### Acceptance Criteria

1. THE Tax_Module SHALL generate tax filing reports (value-added tax, corporate income tax) based on ledger data for the specified Period
2. WHEN a Finance_User requests a tax filing report, THE Tax_Module SHALL aggregate the relevant income, expense, and tax account balances from the Account_Set ledger
3. WHEN a tax filing report is generated, THE Tax_Module SHALL allow the Finance_User to review and adjust individual line items before submission
4. WHEN a Finance_User initiates tax submission, THE Tax_Module SHALL transmit the filing data to the connected tax authority system
5. WHEN tax submission is confirmed by the tax authority system, THE Tax_Module SHALL record the submission confirmation number and timestamp
6. IF tax submission fails, THEN THE Tax_Module SHALL display the failure reason and preserve the filing data for retry
7. THE Tax_Module SHALL maintain a history of all submitted tax filings with their confirmation numbers and submission timestamps

### Requirement 22: IFRS-Specific Accounting Requirements

**User Story:** As a Finance_User, I want the system to enforce IFRS-specific accounting rules and disclosures, so that financial statements produced under IFRS are compliant with the relevant IASB standards

#### Acceptance Criteria

1. WHILE an Account_Set uses IFRS, THE Accounting_System SHALL support fair value measurement for financial instruments in accordance with IFRS 9, allowing Finance_Users to record fair value adjustments as voucher entries
2. WHILE an Account_Set uses IFRS, THE Accounting_System SHALL support lease accounting in accordance with IFRS 16, allowing Finance_Users to register right-of-use assets and corresponding lease liabilities
3. WHEN a Finance_User records a right-of-use asset under IFRS 16, THE Voucher_Engine SHALL generate the initial recognition voucher debiting the right-of-use asset account and crediting the lease liability account
4. WHILE an Account_Set uses IFRS, THE Accounting_System SHALL support revenue recognition in accordance with IFRS 15, allowing Finance_Users to record revenue against identified performance obligations
5. WHEN a Finance_User initiates impairment testing for an asset under IFRS, THE Asset_Module SHALL compare the asset's carrying amount against its recoverable amount and generate an impairment loss voucher when the carrying amount exceeds the recoverable amount, in accordance with IAS 36
6. WHEN a Finance_User generates a financial statement and the Account_Set uses IFRS, THE Report_Engine SHALL include IFRS-required disclosure notes covering accounting policies, significant estimates, and standard-specific disclosures in the generated report
7. IF a Finance_User attempts to record a transaction that violates an IFRS recognition or measurement rule enforced by the system, THEN THE Accounting_System SHALL reject the transaction and display a descriptive error referencing the applicable IFRS standard

### Requirement 23: Machine Learning Cash Flow Forecasting

**User Story:** As a Finance_User, I want the system to forecast future cash flows using machine learning, so that I can anticipate liquidity needs and make informed financial decisions for the enterprise

#### Acceptance Criteria

1. THE ML_Forecast_Engine SHALL train a Forecast_Model for each Account_Set using at least 6 months of historical bank transaction and voucher data
2. WHEN a Finance_User requests a cash flow forecast, THE ML_Forecast_Engine SHALL generate predictions for a Forecast_Horizon of 1 to 12 months
3. WHEN a forecast is generated, THE ML_Forecast_Engine SHALL produce predicted inflow, predicted outflow, and predicted net cash flow for each future period in the Forecast_Horizon
4. WHEN a forecast is generated, THE ML_Forecast_Engine SHALL include a confidence interval (lower bound and upper bound) for each predicted period
5. THE ML_Forecast_Engine SHALL retrain the Forecast_Model for an Account_Set automatically when 30 or more new transactions have been recorded since the last training run
6. WHEN a Forecast_Model is retrained, THE ML_Forecast_Engine SHALL compare the new model's validation accuracy against the previous model and only replace the previous model if the new model achieves equal or better accuracy
7. THE ML_Forecast_Engine SHALL display the forecast accuracy metric (Mean Absolute Percentage Error) of the current Forecast_Model to the Finance_User
8. WHEN fewer than 6 months of historical data exist for an Account_Set, THE ML_Forecast_Engine SHALL notify the Finance_User that insufficient data is available and SHALL NOT generate a forecast
9. THE ML_Forecast_Engine SHALL allow Finance_Users to view a comparison chart of historical actual cash flows against previously forecasted values for the same periods
10. WHEN a Finance_User exports a cash flow forecast, THE ML_Forecast_Engine SHALL produce the export in PDF and CSV formats including predicted values, confidence intervals, and model accuracy metrics
11. THE ML_Forecast_Engine SHALL incorporate seasonal patterns (monthly, quarterly, annual) detected in the historical data when generating forecasts
12. THE ML_Forecast_Engine SHALL generate a forecast within 10 seconds of the Finance_User's request for a Forecast_Horizon of up to 12 months

### Requirement 24: NLP-Powered User Interaction

**User Story:** As a Finance_User, I want to interact with the accounting system using natural language, so that I can perform accounting tasks, query financial data, and get guidance without needing to navigate complex menus

#### Acceptance Criteria

1. THE NLP_Assistant SHALL accept natural language input from Finance_Users in both English and Chinese (Simplified)
2. WHEN a Finance_User submits a natural language query, THE NLP_Assistant SHALL classify the Intent within 3 seconds using the DeepSeek_Model
3. WHEN the Intent is classified as a data query (e.g., "what is my cash balance?", "show me last month's expenses"), THE NLP_Assistant SHALL translate the query into the appropriate system API call and return the result in natural language
4. WHEN the Intent is classified as an action request (e.g., "create a receipt voucher for 5000 yuan", "close this month"), THE NLP_Assistant SHALL present a structured confirmation form pre-filled with the extracted parameters before executing the action
5. WHEN the Intent is classified as a guidance request (e.g., "how do I reconcile my bank account?", "what is a debit entry?"), THE NLP_Assistant SHALL generate an explanatory response using the DeepSeek_Model without executing any system action
6. WHEN the NLP_Assistant cannot determine the Intent with sufficient confidence, THE NLP_Assistant SHALL ask the Finance_User a clarifying question rather than guessing
7. THE NLP_Assistant SHALL maintain Conversation_Context for up to 10 turns within a session, allowing Finance_Users to refer to previous results (e.g., "show me the details of that voucher")
8. THE NLP_Assistant SHALL use the DeepSeek_Model for common interactions (guidance, query translation, intent classification) without requiring external API calls
9. THE NLP_Assistant SHALL restrict all generated actions to the Finance_User's current Account_Set and RBAC permissions — it SHALL NOT execute actions the user is not authorized to perform
10. WHEN a Finance_User requests a financial calculation (e.g., "what is my net profit for Q3?"), THE NLP_Assistant SHALL compute the result from live ledger data and present it with the source accounts used
11. THE NLP_Assistant SHALL log all natural language interactions (user input, classified Intent, system response) in the Audit Log with the user identity and timestamp
12. WHEN the DeepSeek_Model is unavailable or returns an error, THE NLP_Assistant SHALL fall back to a rule-based intent classifier and notify the Finance_User that AI-assisted responses are temporarily limited
13. THE NLP_Assistant SHALL never expose raw SQL, internal API endpoints, or system credentials in its responses to Finance_Users
14. WHEN a Finance_User asks about accounting standards or tax rules, THE NLP_Assistant SHALL provide guidance based on the Account_Set's selected Accounting_Standard (CAS or IFRS) and clearly indicate that responses are informational and not legal advice

### Requirement 25: Bank Integration — Payment Routing Configuration

**User Story:** As a Finance_User, I want to configure Payment Routing methods for each connected Bank_Account, so that outgoing payments are transmitted through the correct channel for each bank and payment type

#### Acceptance Criteria

1. THE Bank_Integration SHALL support the following Payment_Routing_Methods per Bank_Account: Direct_Debit, Online_Banking_Transfer, SWIFT, CNAPS (大额支付), CIPS, Local_ACH, and Internal_Transfer (between accounts within the same bank)
2. WHEN a Finance_User connects a Bank_Account, THE Bank_Integration SHALL display only the Payment_Routing_Methods supported by that bank and account type
3. THE Bank_Integration SHALL allow Finance_Users to configure one or more active Payment_Routing_Methods per Bank_Account
4. WHEN a Finance_User sets a default Payment_Routing_Method for a Bank_Account, THE Payment_Hub SHALL pre-select that method when the account is chosen as the source account for a payment
5. THE Bank_Integration SHALL store the routing configuration (method, bank-specific routing codes, account identifiers) per Bank_Account in the encrypted secrets store
6. WHEN a Payment_Routing_Method requires additional parameters (e.g., SWIFT BIC code, CNAPS routing number, CIPS participant code), THE Bank_Integration SHALL prompt the Finance_User to supply those parameters during configuration
7. THE Bank_Integration SHALL validate routing configuration parameters against the bank's known format rules before saving (e.g., SWIFT BIC must be 8 or 11 characters)
8. WHEN a configured Payment_Routing_Method becomes unavailable (e.g., bank API reports the channel is down), THE Bank_Integration SHALL mark that routing method as temporarily unavailable and notify the Finance_User
9. THE Bank_Integration SHALL maintain a routing configuration history so that changes to routing methods are recorded in the Audit Log with user identity and timestamp

### Requirement 26: Payment Hub — Domestic Payment Initiation

**User Story:** As a Finance_User, I want a dedicated domestic payment initiation page, so that I can initiate local currency and foreign currency payments within the country using the appropriate routing and settlement methods

#### Acceptance Criteria

1. THE Payment_Hub SHALL provide a separate Domestic_Payment page for initiating payments between accounts within the same country
2. THE Domestic_Payment page SHALL support both local currency (CNY) and foreign currency payments; WHEN a Finance_User selects a foreign currency, THE Payment_Hub SHALL display the applicable foreign currency routing methods and settlement methods for that currency
3. THE Payment_Hub SHALL present available Settlement_Methods dynamically based on the combination of the selected source Bank_Account and the configured Payment_Routing_Method for that account
4. THE supported domestic Settlement_Methods per routing method are:
   - Direct_Debit: Same_Day_Settlement, Next_Day_Settlement
   - Online_Banking_Transfer: Real_Time_Gross_Settlement (RTGS), Batch_Settlement (T+1)
   - CNAPS (大额支付, CNY only): Real_Time_Settlement, Scheduled_Settlement
   - CIPS (cross-border RMB, CNY): Real_Time_Settlement, End_Of_Day_Settlement
   - Local_ACH: Next_Day_Settlement, Two_Day_Settlement
   - Internal_Transfer (same bank): Immediate_Settlement
5. WHEN a Finance_User selects a source Bank_Account, THE Payment_Hub SHALL display only the Payment_Routing_Methods configured and currently available for that account on the Domestic_Payment page
6. WHEN a Finance_User selects a Payment_Routing_Method, THE Payment_Hub SHALL immediately update the Settlement_Method options to show only those valid for the selected routing method
7. WHEN a Finance_User selects a recipient Bank_Account, THE Payment_Hub SHALL further filter the available routing and settlement options to those compatible with both the source and recipient accounts
8. THE Payment_Hub SHALL display the estimated settlement date for each Settlement_Method based on the current date and applicable cut-off times
9. IF the selected Settlement_Method cut-off time has already passed for the current business day, THE Payment_Hub SHALL warn the Finance_User and display the next available settlement date
10. WHEN a domestic payment is submitted, THE Payment_Hub SHALL record the Payment_Routing_Method, Settlement_Method, currency, and requested settlement date on the Payment record
11. WHEN a domestic payment is confirmed by the banking system, THE Payment_Hub SHALL record the actual settlement date for reconciliation purposes

### Requirement 27: Payment Hub — International Payment Initiation

**User Story:** As a Finance_User, I want a dedicated international payment initiation page, so that I can initiate cross-border payments using SWIFT with the appropriate settlement method and required correspondent banking details

#### Acceptance Criteria

1. THE Payment_Hub SHALL provide a separate International_Payment page for initiating cross-border payments
2. THE International_Payment page SHALL use SWIFT as the Payment_Routing_Method and SHALL support the following Settlement_Methods: Standard_Settlement (T+2), Express_Settlement (T+1), Same_Day_Value
3. WHEN a Finance_User selects a source Bank_Account on the International_Payment page, THE Payment_Hub SHALL display only SWIFT routing configurations available for that account
4. THE International_Payment page SHALL collect all fields required for a SWIFT payment: beneficiary name, beneficiary account (IBAN or account number), beneficiary bank BIC/SWIFT code, beneficiary bank name, beneficiary bank address, correspondent bank BIC (if applicable), payment currency, amount, value date, payment purpose code, and remittance information
5. WHEN a Finance_User selects a Settlement_Method on the International_Payment page, THE Payment_Hub SHALL display the estimated value date and any applicable cut-off time for same-day processing
6. THE Payment_Hub SHALL validate the beneficiary BIC/SWIFT code format (8 or 11 alphanumeric characters) before allowing submission
7. WHEN the payment currency differs from the source account currency, THE Payment_Hub SHALL display the indicative exchange rate and estimated debit amount in the source account currency
8. WHEN an international payment is submitted, THE Payment_Hub SHALL record all SWIFT-specific fields on the Payment record alongside the Settlement_Method and requested value date
9. WHEN an international payment is confirmed, THE Payment_Hub SHALL record the actual settlement date and bank reference (UETR — Unique End-to-end Transaction Reference) for reconciliation

### Requirement 29: Payment Hub — Settlement Process Workflow

**User Story:** As a Finance_User, I want payments to follow a structured settlement process with distinct stages — Prepare, Instruct, Check, Authorise, Confirm, and Settle — so that each payment is properly reviewed, authorised, and bank-confirmed before funds are considered settled, and I can schedule a queue of payments for batch processing or trigger immediate bank submission

#### Acceptance Criteria

1. THE Payment_Hub SHALL enforce the following sequential settlement workflow for every payment: Prepare → Instruct → Check → Authorise → Confirm → Settle
2. THE settlement workflow stages are defined as:
   - **Prepare**: Finance_User creates the payment record with all required fields; payment is saved as a draft; balance pre-check is performed and result displayed; payment enters the scheduling queue
   - **Instruct**: Finance_User (or an automated schedule trigger) promotes the payment to Instructed status, generating the ISO 20022 pain.001 payment instruction message; the instruction is validated against the field configuration for the selected routing/settlement combination
   - **Check**: A Reviewer role user reviews the payment instruction details and either approves it for authorisation or returns it to Prepare with a rejection reason; the system displays a diff of any changes since the last Check
   - **Authorise**: An Authoriser role user (Admin or designated Accountant with authorisation permission) provides final approval; dual-authorisation may be required for payments above a configurable threshold amount; the payment moves to Authorised status
   - **Confirm**: THE Payment_Hub sends the authorised payment instruction to the bank via the configured Payment_Routing_Method and awaits the bank's acknowledgement; on bank acknowledgement the payment moves to Confirmed status; on bank rejection the payment returns to Prepare with the bank rejection reason; this stage represents the bank's acceptance of the instruction before final settlement
   - **Settle**: THE Payment_Hub receives the final settlement notification from the bank (funds have moved); the payment status becomes Settled and the actual settlement date is recorded; if no settlement notification is received within the expected settlement window, the payment is flagged for manual review
3. WHEN a payment is in Prepare status, THE Payment_Hub SHALL allow the Finance_User to edit all payment fields and re-run the balance pre-check
4. THE Payment_Hub SHALL maintain a scheduling queue showing all payments in Prepare and Instructed status, ordered by requested settlement date; Finance_Users can view, reorder, and remove payments from the queue
5. WHEN a Finance_User clicks **Pay** on an Authorised payment, THE Payment_Hub SHALL immediately transmit the payment instruction to the bank (Confirm stage) without waiting for the scheduled date
6. WHEN a payment's scheduled date arrives and the payment is in Authorised status, THE Payment_Hub SHALL automatically trigger the Confirm stage via a Celery scheduled task
7. THE Payment_Hub SHALL enforce role-based access per stage: Prepare and Instruct require Accountant or above; Check requires Reviewer or above; Authorise requires Admin or Accountant with authorisation permission; Confirm and Settle are system-triggered (manual Pay button requires Authoriser role)
8. WHEN a payment exceeds the Account_Set's configured dual-authorisation threshold, THE Payment_Hub SHALL require a second Authoriser (different from the first) to approve before the payment can proceed to Confirm
9. THE Payment_Hub SHALL record a timestamped audit trail entry for every stage transition, including the user who triggered the transition, the stage moved from and to, and any rejection reason
10. WHEN a payment is rejected at Check or returns from Confirm with a bank rejection, THE Payment_Hub SHALL notify the originating Finance_User and display the rejection reason on the payment record
11. THE Payment_Hub SHALL display the current stage and full stage history on the payment detail view
12. THE Payment_Hub SHALL allow batch operations on the scheduling queue: select multiple Instructed payments and submit them all for Check in one action; select multiple Authorised payments and trigger Pay for all in one action

### Requirement 30: Payment Hub — Payment Transaction Type Configuration

**User Story:** As a Finance_Admin, I want to configure Payment Transaction Types that define which settlement process stages are required for manual completion and which auto-complete to the next stage, so that different payment types can have streamlined or fully controlled workflows

#### Acceptance Criteria

1. THE Payment_Hub SHALL provide a Payment_Transaction_Type configuration page accessible to Finance_Admin role users
2. A Payment_Transaction_Type defines, for each of the six settlement stages (Prepare, Instruct, Check, Authorise, Confirm, Settle), whether the stage is: **Manual** (a user must explicitly act to advance) or **Auto** (the system automatically advances to the next stage as soon as the prerequisites are met)
3. THE system SHALL ship with a default Payment_Transaction_Type named "Standard" where Instruct, Authorise, and Settle are Manual and Prepare, Check, and Confirm are Auto; this means by default only Instruct, Authorise, and Settle require explicit user action
4. Finance_Admins SHALL be able to create additional Payment_Transaction_Types with any combination of Manual and Auto stages, subject to the constraint that at least Instruct and Settle must always remain Manual (they cannot be set to Auto)
5. WHEN a Finance_User creates a new payment (Domestic or International), THE Payment_Hub SHALL allow them to select the Payment_Transaction_Type for that payment; the default type is pre-selected
6. WHEN a stage is configured as Auto for the selected Payment_Transaction_Type, THE Payment_Hub SHALL automatically advance the payment to the next stage without requiring user action, and SHALL record the auto-transition in the audit trail with `triggered_by = system`
7. WHEN a stage is configured as Manual for the selected Payment_Transaction_Type, THE Payment_Hub SHALL wait for the appropriate role user to explicitly act before advancing
8. THE Payment_Hub SHALL display the Payment_Transaction_Type and its stage configuration on the payment detail view so users can see which stages are manual and which are auto
9. WHEN a Finance_Admin saves a Payment_Transaction_Type, THE change SHALL be recorded in the Audit Log with user identity, timestamp, and before/after configuration
10. THE Payment_Transaction_Type configuration SHALL be scoped per Account_Set so that different enterprises can have different workflow configurations
11. WHEN a Finance_Admin deactivates a Payment_Transaction_Type, existing payments using that type SHALL continue to completion using the original configuration; new payments cannot select a deactivated type

### Requirement 28: Payment Hub — ISO 20022 Payment Initiation Field Configuration

**User Story:** As a Finance_Admin, I want a settings page where I can configure which ISO 20022 payment initiation fields are displayed for each combination of routing method and settlement method, so that the payment form shows only the fields relevant to each payment type

#### Acceptance Criteria

1. THE Payment_Hub SHALL provide a Payment_Field_Configuration settings page accessible to Finance_Admin role users
2. THE Payment_Field_Configuration page SHALL list all ISO 20022 pain.001 (CustomerCreditTransferInitiation) fields relevant to payment initiation, including: debtor name, debtor account (IBAN/account number), debtor agent BIC, creditor name, creditor account, creditor agent BIC, creditor agent name, creditor agent address, intermediary agent BIC, payment currency, instructed amount, exchange rate, value date, end-to-end ID, payment purpose code (Cd/Prtry), remittance information (structured/unstructured), charge bearer (SLEV/DEBT/CRED/SHAR), and regulatory reporting fields
3. FOR EACH combination of Payment_Routing_Method and Settlement_Method, THE Payment_Field_Configuration page SHALL allow a Finance_Admin to mark each ISO 20022 field as: Required, Optional, or Hidden
4. WHEN a Finance_User opens the Domestic_Payment or International_Payment page and selects a routing method and settlement method, THE Payment_Hub SHALL render only the fields configured as Required or Optional for that combination, in the order defined in the configuration
5. Required fields SHALL be visually distinguished from Optional fields on the payment initiation form
6. THE Payment_Hub SHALL ship with a default ISO 20022 field configuration for each routing/settlement combination that reflects standard banking practice; Finance_Admins may override the defaults
7. WHEN a Finance_Admin saves a field configuration, THE Payment_Hub SHALL validate that at minimum the following fields are always Required for any combination: debtor account, creditor name, creditor account, payment currency, instructed amount, and value date
8. WHEN a Finance_Admin saves a field configuration, THE change SHALL be recorded in the Audit Log with the user identity, timestamp, and the before/after configuration
9. THE Payment_Field_Configuration SHALL be scoped per Account_Set so that different enterprises can have different field visibility rules
10. WHEN a Finance_User submits a payment, THE Payment_Hub SHALL validate that all Required fields for the selected routing/settlement combination are populated before allowing submission

### Requirement 31: User Registration and Login

**User Story:** As a new user, I want to register an account using my email address or mobile number, so that I can access the accounting system and manage my enterprises

#### Acceptance Criteria

1. THE Accounting_System SHALL provide a registration page allowing new users to register with either an email address or a mobile phone number
2. WHEN a user registers with an email address, THE Accounting_System SHALL require the user to enter a display name, email address, and password; then send a 6-digit OTP to the provided email address
3. WHEN a user registers with a mobile number, THE Accounting_System SHALL require the user to enter a display name, mobile number (with country code), and password; then send a 6-digit OTP via SMS to the provided mobile number
4. WHEN a user submits the registration OTP, THE Accounting_System SHALL verify the OTP is correct and has not expired (OTP valid for 10 minutes); on success, activate the account immediately without requiring admin approval
5. IF the OTP is incorrect or expired, THEN THE Accounting_System SHALL display an error and allow the user to request a new OTP; a new OTP SHALL invalidate any previously issued OTP for the same registration session
6. THE Accounting_System SHALL validate that the email address or mobile number is not already registered before sending the OTP
7. THE Accounting_System SHALL enforce password strength requirements: minimum 8 characters, at least one uppercase letter, one lowercase letter, one digit, and one special character
8. WHEN registration is complete, THE Accounting_System SHALL automatically log the user in and redirect them to the Account Set creation page
9. THE Accounting_System SHALL support login via email address + password
10. THE Accounting_System SHALL support login via mobile number + OTP (sends a fresh 6-digit OTP to the registered mobile number on each login attempt)
11. WHEN a user requests a password reset via email, THE Accounting_System SHALL send a 6-digit OTP to the registered email address; on correct OTP entry, allow the user to set a new password
12. WHEN a user requests a password reset via mobile, THE Accounting_System SHALL send a 6-digit OTP to the registered mobile number; on correct OTP entry, allow the user to set a new password
13. THE Accounting_System SHALL rate-limit OTP requests to a maximum of 5 OTP sends per email/mobile per hour to prevent abuse
14. THE Accounting_System SHALL lock an account for 15 minutes after 10 consecutive failed login attempts

### Requirement 32: Define Currency

**User Story:** As a Finance_User, I want to define currencies used in the system, so that I can classify each currency correctly as Primary, Secondary, or Commodity and associate it with the appropriate market data

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to define a Currency with the following attributes: ISO 4217 code (e.g. CNY, USD, EUR), full name, currency type (Primary, Secondary, or Commodity), decimal places, and active/inactive status
2. THE Accounting_System SHALL support three currency types:
   - **Primary**: the functional/base currency of an Account_Set (e.g. CNY for a mainland China enterprise)
   - **Secondary**: a foreign currency used in transactions alongside the Primary currency (e.g. USD, EUR, HKD)
   - **Commodity**: a currency representing a physical commodity (e.g. XAU for gold, XAG for silver, XOI for oil); treated as a currency in FX pairs but carries a commodity subtype flag
3. WHEN a Finance_User creates a Currency, THE Accounting_System SHALL validate that the ISO 4217 code is unique within the platform
4. THE Accounting_System SHALL allow Finance_Users to associate a default Yield Curve with each currency; this curve is used as the default discount curve for interest calculations involving that currency
5. THE Accounting_System SHALL allow Finance_Users to define Currency Pairs (see Requirement 33) for any two defined currencies
6. THE Accounting_System SHALL allow Finance_Users to mark a currency as inactive; inactive currencies cannot be selected in new transactions but existing records are preserved
7. WHEN a Commodity currency is defined, THE Accounting_System SHALL require the user to specify the commodity subtype (e.g. Precious Metal, Energy, Agricultural) and the standard unit of measure (e.g. troy ounce, barrel, bushel)

### Requirement 33: Define Currency Pair

**User Story:** As a Finance_User, I want to define currency pairs with their associated spot curve and default yield curve, so that the system can correctly price FX transactions and calculate interest

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to define a Currency Pair consisting of a Base Currency and a Quote Currency, both selected from the defined Currency list (Requirement 32)
2. WHEN a Currency Pair is defined, THE Accounting_System SHALL require the user to specify:
   - Base Currency (the currency being priced)
   - Quote Currency (the currency in which the price is expressed)
   - Spot Curve: the historical time series of spot rates for this pair (see Requirement 35)
   - Default Yield Curve for Base Currency: the yield curve used to discount cash flows in the base currency (see Requirement 34)
   - Default Yield Curve for Quote Currency: the yield curve used to discount cash flows in the quote currency
3. THE Accounting_System SHALL validate that a Currency Pair with the same Base/Quote combination does not already exist; the inverse pair (Quote/Base) is treated as a separate pair
4. THE Accounting_System SHALL allow Finance_Users to update the Spot Curve and Default Yield Curve assignments for an existing Currency Pair
5. WHEN a Currency Pair involves a Commodity currency, THE Accounting_System SHALL allow the pair to be flagged as a Commodity FX Pair; the spot rate represents the price of the commodity in the quote currency
6. THE Accounting_System SHALL allow Finance_Users to set a Currency Pair as active or inactive; inactive pairs cannot be selected for new transactions

### Requirement 34: Define Yield Curve Type

**User Story:** As a Finance_User, I want to define yield curve types, so that I can categorise yield curves by their market convention and use the correct curve for each interest calculation context

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to define a Yield Curve Type with the following attributes: name, description, and currency association (optional — a type may be currency-specific or generic)
2. THE Accounting_System SHALL not restrict the set of curve types; Finance_Users may define any curve type they require (e.g. Government Bond, OIS, SOFR, LIBOR, SHIBOR, Swap, Credit Spread, Zero Coupon)
3. WHEN a Yield Curve Type is created, THE Accounting_System SHALL validate that the name is unique within the Account_Set
4. THE Accounting_System SHALL allow Finance_Users to mark a Yield Curve Type as active or inactive; inactive types cannot be assigned to new Yield Curves but existing assignments are preserved
5. THE Accounting_System SHALL allow Finance_Users to associate a Yield Curve Type with one or more currencies to indicate which currencies the curve type is applicable to; this association is advisory and does not prevent cross-currency assignment

### Requirement 35: Define Yield Curve

**User Story:** As a Finance_User, I want to define yield curves with dated rate points across tenors, so that the system can use them for interest calculations, discounting, and FX pricing

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to define a Yield Curve with the following header attributes: name, Yield Curve Type (from Requirement 34), currency, and description
2. EACH Yield Curve SHALL contain one or more rate points; each rate point SHALL have the following attributes:
   - Date: the curve date (the date on which this set of rates was observed or effective)
   - Time: the time of observation (to support intraday curve snapshots)
   - Tenor: the term to maturity for this rate point (e.g. ON, 1W, 1M, 3M, 6M, 9M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y)
   - Bid rate: the rate at which the market maker buys (borrows), expressed as a decimal (e.g. 0.0325 for 3.25%)
   - Offer rate: the rate at which the market maker sells (lends), expressed as a decimal
3. THE Accounting_System SHALL validate that Bid rate ≤ Offer rate for every rate point
4. THE Accounting_System SHALL allow multiple rate points per curve per date, one per tenor; duplicate (date, tenor) combinations within the same curve SHALL be rejected
5. THE Accounting_System SHALL allow Finance_Users to add, edit, and delete individual rate points on a Yield Curve manually via a data entry form
6. THE Accounting_System SHALL allow Finance_Users to import a batch of rate points for a given curve date via CSV upload; the CSV format SHALL include columns: date, time, tenor, bid, offer
7. THE Accounting_System SHALL allow Finance_Users to configure a market data feed connection for a Yield Curve; when a feed is configured, the system SHALL automatically pull and store rate points on a scheduled basis (configurable frequency: real-time, hourly, daily); feed-sourced records SHALL be tagged with source = "feed" and the feed provider name
8. THE Accounting_System SHALL allow Finance_Users to manually override any feed-sourced rate point; overridden records SHALL be tagged with source = "manual" and preserve the original feed value for audit purposes
9. WHEN a Yield Curve is used for interest calculation, THE Accounting_System SHALL interpolate between tenor points using linear interpolation when the required tenor does not exactly match a defined point
10. THE Accounting_System SHALL maintain a full history of rate points by date and time, allowing Finance_Users to query the curve as it stood on any past date

### Requirement 36: Define Spot Rate

**User Story:** As a Finance_User, I want to define and maintain spot rates for currency pairs, so that the system can convert between currencies accurately for transactions and reporting

#### Acceptance Criteria

1. THE Accounting_System SHALL allow Finance_Users to define a Spot Rate record for a Currency Pair (from Requirement 33) with the following attributes:
   - Currency Pair: the Base/Quote pair this rate applies to
   - Date: the date on which this spot rate was observed
   - Time: the time of observation (to support intraday rate snapshots)
   - Bid rate: the rate at which the market maker buys the base currency, expressed as units of quote currency per unit of base currency
   - Offer rate: the rate at which the market maker sells the base currency
2. THE Accounting_System SHALL validate that Bid rate ≤ Offer rate for every Spot Rate record
3. THE Accounting_System SHALL allow multiple Spot Rate records per Currency Pair per date (one per distinct time), forming the historical spot curve for that pair
4. THE Accounting_System SHALL allow Finance_Users to import a batch of spot rates via CSV upload; the CSV format SHALL include columns: base_currency, quote_currency, date, time, bid, offer
5. THE Accounting_System SHALL allow Finance_Users to configure a market data feed connection for a Currency Pair; when a feed is configured, the system SHALL automatically pull and store spot rates on a scheduled basis (configurable frequency: real-time, hourly, daily); feed-sourced records SHALL be tagged with source = "feed" and the feed provider name
6. THE Accounting_System SHALL allow Finance_Users to manually enter or override any spot rate; manually entered or overridden records SHALL be tagged with source = "manual" and preserve the original feed value for audit purposes
7. WHEN a transaction requires a spot rate for a Currency Pair on a given date and no exact match exists, THE Accounting_System SHALL use the most recent prior Spot Rate record for that pair as the applicable rate, and SHALL display a warning indicating the rate date used
8. THE Accounting_System SHALL allow Finance_Users to query the full historical spot rate series for any Currency Pair, filterable by date range
9. WHEN a Spot Rate is recorded for a Currency Pair involving a Commodity currency, THE Accounting_System SHALL display the rate with the commodity's standard unit of measure (e.g. USD per troy ounce for XAU/USD)

### Requirement 37: Partial MCP Support for External Agents

**User Story:** As a Finance_User (or developer integrating an External_Agent), I want the Accounting_System to expose a curated set of read-only MCP tools, so that agents can query Account Sets, vouchers, chart of accounts, and ledger summaries without bypassing authentication or inventing a second business layer

#### Acceptance Criteria

1. THE Accounting_System SHALL provide an MCP_Adapter that exposes tools over the Model Context Protocol without duplicating voucher, ledger, chart-of-accounts, or account-set business logic (tools SHALL call existing service functions)
2. THE MCP_Adapter SHALL support stdio transport for local External_Agent hosts (e.g., Cursor) via a dedicated module entry point
3. THE MCP_Adapter SHALL optionally expose Streamable HTTP transport mounted on svc-accounting at `/mcp` when enabled by configuration (`SMARTBOOK_MCP_ENABLED`)
4. WHEN an MCP_Tool is invoked, THE MCP_Adapter SHALL authenticate the caller using a JWT provided via `SMARTBOOK_MCP_TOKEN` (or equivalent) and SHALL enforce the same Account_Set RBAC permissions used by the REST API
5. WHEN an MCP_Tool receives an `account_set_id` argument, THE MCP_Adapter SHALL reject the call if that id does not match the active Account_Set claim in the JWT
6. THE initial MCP_Tool surface SHALL be read-only and SHALL include at least: list accessible Account Sets, get Chart of Accounts tree, list vouchers (optional period/status filters), get a single voucher with entries, and get account summary balances for a period
7. THE MCP_Adapter SHALL NOT expose write/mutate operations (create/approve voucher, payments, deletions, backup/restore, or similar) in the initial partial surface
8. THE Accounting_System SHALL document how to configure a local External_Agent (Cursor MCP config example) including token environment variables and working directory/`PYTHONPATH` requirements
9. THE platform package used by the backend SHALL remain compatible with third-party libraries that import the Python standard-library `platform` module (no breakage of MCP/attrs/jsonschema imports due to name shadowing)
