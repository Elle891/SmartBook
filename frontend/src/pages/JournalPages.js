import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { LedgerFilterBar, LedgerNav } from "../components/LedgerNav";
import { createLedgerApi } from "../services/ledger_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, buildLedgerQuery, defaultPeriod, formatMoney } from "../utils/ledger_page";

function makeJournalPage(title, journalFn, exportType) {
  class Page extends Component {
    static components = { AppShell, LedgerNav, LedgerFilterBar };
    static template = xml`
      <AppShell title="pageTitle" loading="state.loading" error="state.error">
        <section class="sb-page">
          <LedgerNav/>
          <LedgerFilterBar
            periodCode="state.filters.periodCode"
            accountCode="state.filters.accountCode"
            dateFrom="state.filters.dateFrom"
            dateTo="state.filters.dateTo"
            showAccount="true"
            onChange.bind="setFilter"
            onApply.bind="load"
            onExportPdf.bind="exportPdf"
            onExportExcel.bind="exportExcel"
          />
          <table class="sb-table">
            <thead><tr><th>Date</th><th>Voucher</th><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
            <tbody>
              <tr t-foreach="state.entries" t-as="e" t-key="e_index">
                <td><t t-esc="e.entry_date"/></td>
                <td><t t-esc="e.voucher_number"/></td>
                <td><t t-esc="e.account_code"/> <t t-esc="e.account_name"/></td>
                <td><t t-esc="e.description"/></td>
                <td><t t-esc="fmt(e.debit_amount)"/></td>
                <td><t t-esc="fmt(e.credit_amount)"/></td>
                <td><t t-esc="fmt(e.running_balance)"/></td>
              </tr>
            </tbody>
          </table>
        </section>
      </AppShell>
    `;

    setup() {
      this.pageTitle = title;
      this.journalFn = journalFn;
      this.exportType = exportType;
      this.rpc = useService("rpc");
      this.accountSetStore = useStore("accountSetStore");
      this.ledgerApi = createLedgerApi(this.rpc);
      this.state = useState({
        loading: false,
        error: "",
        entries: [],
        filters: { periodCode: "", accountCode: "", dateFrom: "", dateTo: "" },
      });
    }

    fmt(v) {
      return formatMoney(v);
    }

    async onWillStart() {
      this.state.filters.periodCode = defaultPeriod(this.accountSetStore);
    }

    setFilter(key, value) {
      this.state.filters[key] = value;
    }

    async load() {
      const id = accountSetId(this.accountSetStore);
      if (!id) return;
      this.state.loading = true;
      try {
        const data = await this.journalFn(this.ledgerApi, id, buildLedgerQuery(this.state.filters));
        this.state.entries = data.entries || [];
      } catch (err) {
        this.state.error = formatApiError(err);
      } finally {
        this.state.loading = false;
      }
    }

    async exportPdf() {
      await this.export("pdf");
    }

    async exportExcel() {
      await this.export("excel");
    }

    async export(format) {
      const id = accountSetId(this.accountSetStore);
      await this.ledgerApi.exportLedger(
        id,
        { ...buildLedgerQuery(this.state.filters), format, ledger_type: this.exportType },
        `${this.exportType}-journal.${format === "excel" ? "xlsx" : "pdf"}`
      );
    }
  }
  return Page;
}

export const CashJournalPage = makeJournalPage(
  "Cash Journal",
  (api, id, q) => api.cashJournal(id, q),
  "cash"
);

export const BankJournalPage = makeJournalPage(
  "Bank Journal",
  (api, id, q) => api.bankJournal(id, q),
  "bank"
);
