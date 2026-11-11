import { Component, useState, xml } from "@odoo/owl";
import { AccountSetCreatePage } from "./pages/AccountSetCreatePage";
import { AccountSetListPage } from "./pages/AccountSetListPage";
import { AccountSetPermissionsPage } from "./pages/AccountSetPermissionsPage";
import { AccountSummaryPage } from "./pages/AccountSummaryPage";
import { BankConnectionPage } from "./pages/BankConnectionPage";
import { CashierPage } from "./pages/CashierPage";
import { ChartOfAccountsPage } from "./pages/ChartOfAccountsPage";
import { ForecastPage } from "./pages/ForecastPage";
import { IFRSCompliancePage } from "./pages/IFRSCompliancePage";
import { NLPAssistantPage } from "./pages/NLPAssistantPage";
import { FixedAssetPage } from "./pages/FixedAssetPage";
import { GeneralLedgerPage } from "./pages/GeneralLedgerPage";
import { HomePage } from "./pages/HomePage";
import { InvoiceScannerPage } from "./pages/InvoiceScannerPage";
import { BankJournalPage, CashJournalPage } from "./pages/JournalPages";
import { LoginPage } from "./pages/LoginPage";
import { OpeningBalancePage } from "./pages/OpeningBalancePage";
import { PasswordResetPage } from "./pages/PasswordResetPage";
import { PayrollPage } from "./pages/PayrollPage";
import { PeriodEndPage } from "./pages/PeriodEndPage";
import { PaymentFieldConfigPage } from "./pages/PaymentFieldConfigPage";
import { PaymentTransactionTypePage } from "./pages/PaymentTransactionTypePage";
import { PaymentDetailPage } from "./pages/PaymentDetailPage";
import { PaymentQueuePage } from "./pages/PaymentQueuePage";
import { DomesticPaymentPage } from "./pages/DomesticPaymentPage";
import { InternationalPaymentPage } from "./pages/InternationalPaymentPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { RegistrationPage } from "./pages/RegistrationPage";
import { ReportPage } from "./pages/ReportPage";
import { SmartImportPage } from "./pages/SmartImportPage";
import { SubsidiaryLedgerPage } from "./pages/SubsidiaryLedgerPage";
import { TaxFilingPage } from "./pages/TaxFilingPage";
import { VoucherCreatePage } from "./pages/VoucherCreatePage";
import { VoucherDetailPage } from "./pages/VoucherDetailPage";
import { VoucherListPage } from "./pages/VoucherListPage";

export class Root extends Component {
  static components = {
    HomePage,
    LoginPage,
    RegistrationPage,
    PasswordResetPage,
    AccountSetCreatePage,
    AccountSetListPage,
    AccountSetPermissionsPage,
    OpeningBalancePage,
    ChartOfAccountsPage,
    VoucherListPage,
    VoucherCreatePage,
    VoucherDetailPage,
    GeneralLedgerPage,
    SubsidiaryLedgerPage,
    CashJournalPage,
    BankJournalPage,
    AccountSummaryPage,
    PeriodEndPage,
    ReportPage,
    CashierPage,
    PayrollPage,
    FixedAssetPage,
    SmartImportPage,
    InvoiceScannerPage,
    TaxFilingPage,
    BankConnectionPage,
    ReconciliationPage,
    DomesticPaymentPage,
    InternationalPaymentPage,
    PaymentQueuePage,
    PaymentDetailPage,
    PaymentTransactionTypePage,
    PaymentFieldConfigPage,
    IFRSCompliancePage,
    ForecastPage,
    NLPAssistantPage,
  };
  static template = xml`
    <t t-if="!isAuthed and routeName === 'register'"><RegistrationPage/></t>
    <t t-elif="!isAuthed and routeName === 'password-reset'"><PasswordResetPage/></t>
    <t t-elif="!isAuthed"><LoginPage/></t>
    <t t-elif="routeName === 'account-set-create'"><AccountSetCreatePage/></t>
    <t t-elif="routeName === 'account-sets'"><AccountSetListPage/></t>
    <t t-elif="routeName === 'account-set-permissions'"><AccountSetPermissionsPage/></t>
    <t t-elif="routeName === 'opening-balances'"><OpeningBalancePage/></t>
    <t t-elif="routeName === 'chart-of-accounts'"><ChartOfAccountsPage/></t>
    <t t-elif="routeName === 'vouchers'"><VoucherListPage/></t>
    <t t-elif="routeName === 'voucher-create'"><VoucherCreatePage/></t>
    <t t-elif="routeName === 'voucher-detail'"><VoucherDetailPage/></t>
    <t t-elif="routeName === 'ledger-general'"><GeneralLedgerPage/></t>
    <t t-elif="routeName === 'ledger-subsidiary'"><SubsidiaryLedgerPage/></t>
    <t t-elif="routeName === 'ledger-cash'"><CashJournalPage/></t>
    <t t-elif="routeName === 'ledger-bank'"><BankJournalPage/></t>
    <t t-elif="routeName === 'ledger-summary'"><AccountSummaryPage/></t>
    <t t-elif="routeName === 'period-end'"><PeriodEndPage/></t>
    <t t-elif="routeName === 'reports'"><ReportPage/></t>
    <t t-elif="routeName === 'cashier'"><CashierPage/></t>
    <t t-elif="routeName === 'payroll'"><PayrollPage/></t>
    <t t-elif="routeName === 'fixed-assets'"><FixedAssetPage/></t>
    <t t-elif="routeName === 'smart-import'"><SmartImportPage/></t>
    <t t-elif="routeName === 'invoice-scanner'"><InvoiceScannerPage/></t>
    <t t-elif="routeName === 'tax-filing'"><TaxFilingPage/></t>
    <t t-elif="routeName === 'bank'"><BankConnectionPage/></t>
    <t t-elif="routeName === 'reconciliation'"><ReconciliationPage/></t>
    <t t-elif="routeName === 'payments-domestic'"><DomesticPaymentPage/></t>
    <t t-elif="routeName === 'payments-international'"><InternationalPaymentPage/></t>
    <t t-elif="routeName === 'payments-queue'"><PaymentQueuePage/></t>
    <t t-elif="routeName === 'payment-detail'"><PaymentDetailPage/></t>
    <t t-elif="routeName === 'payment-transaction-types'"><PaymentTransactionTypePage/></t>
    <t t-elif="routeName === 'payment-field-config'"><PaymentFieldConfigPage/></t>
    <t t-elif="routeName === 'ifrs'"><IFRSCompliancePage/></t>
    <t t-elif="routeName === 'forecast'"><ForecastPage/></t>
    <t t-elif="routeName === 'assistant'"><NLPAssistantPage/></t>
    <t t-else=""><HomePage/></t>
  `;

  setup() {
    this.router = this.env.router;
    // Subscribe so hashchange → router.state updates re-render Root
    this.routerState = useState(this.env.router.state);
    this.authStore = this.env.stores.authStore;
    this.authState = useState(this.env.stores.authStore.state);
    const onActivity = () => {
      if (this.authStore.isAuthenticated()) {
        this.authStore.touchActivity(() => {
          this.env.stores.notificationStore.notify("Session expired due to inactivity.", {
            type: "warning",
          });
          window.location.hash = "#/login";
        });
      }
    };
    ["click", "keydown", "mousemove"].forEach((evt) =>
      window.addEventListener(evt, onActivity, { passive: true })
    );
    if (this.authStore.isAuthenticated()) {
      this.authStore.resetInactivityTimer(() => {
        window.location.hash = "#/login";
      });
    }
  }

  get routeName() {
    return this.routerState.name;
  }

  get isAuthed() {
    return Boolean(this.authState.accessToken);
  }
}
