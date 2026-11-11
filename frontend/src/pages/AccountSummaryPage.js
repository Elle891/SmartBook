import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { LedgerFilterBar, LedgerNav } from "../components/LedgerNav";
import { createLedgerApi } from "../services/ledger_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, buildLedgerQuery, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class AccountSummaryPage extends Component {
  static components = { AppShell, LedgerNav, LedgerFilterBar };
  static template = xml`
    <AppShell title="'Account Summary'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <LedgerNav/>
        <LedgerFilterBar
          periodCode="state.filters.periodCode"
          accountCode="state.filters.accountCode"
          showAccount="true"
          onChange.bind="setFilter"
          onApply.bind="load"
          onExportPdf.bind="exportPdf"
          onExportExcel.bind="exportExcel"
        />
        <table class="sb-table">
          <thead><tr><th>Code</th><th>Name</th><th>Opening</th><th>Debits</th><th>Credits</th><th>Closing</th></tr></thead>
          <tbody>
            <tr t-foreach="state.rows" t-as="r" t-key="r.account_code">
              <td><t t-esc="r.account_code"/></td>
              <td><t t-esc="r.account_name"/></td>
              <td><t t-esc="formatMoney(r.opening_balance)"/></td>
              <td><t t-esc="formatMoney(r.total_debits)"/></td>
              <td><t t-esc="formatMoney(r.total_credits)"/></td>
              <td><t t-esc="formatMoney(r.closing_balance)"/></td>
            </tr>
          </tbody>
        </table>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.ledgerApi = createLedgerApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      rows: [],
      filters: { periodCode: "", accountCode: "" },
    });
  }

  formatMoney(v) {
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
      this.state.rows = await this.ledgerApi.accountSummary(id, buildLedgerQuery(this.state.filters));
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
      { ...buildLedgerQuery(this.state.filters), format, ledger_type: "account-summary" },
      `account-summary.${format === "excel" ? "xlsx" : "pdf"}`
    );
  }
}
