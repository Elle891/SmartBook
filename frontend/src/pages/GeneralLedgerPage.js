import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { LedgerFilterBar, LedgerNav } from "../components/LedgerNav";
import { createLedgerApi } from "../services/ledger_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, buildLedgerQuery, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class GeneralLedgerPage extends Component {
  static components = { AppShell, LedgerNav, LedgerFilterBar };
  static template = xml`
    <AppShell title="'General Ledger'" loading="state.loading" error="state.error">
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
          <thead><tr><th>Date</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
          <tbody>
            <tr t-foreach="state.entries" t-as="e" t-key="e.id">
              <td><t t-esc="e.entry_date"/></td>
              <td><t t-esc="formatMoney(e.debit_amount)"/></td>
              <td><t t-esc="formatMoney(e.credit_amount)"/></td>
              <td><t t-esc="formatMoney(e.running_balance)"/></td>
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
      entries: [],
      filters: { periodCode: "", accountCode: "1001", dateFrom: "", dateTo: "" },
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
    if (!id || !this.state.filters.accountCode) {
      this.state.error = "Account code and period are required.";
      return;
    }
    this.state.loading = true;
    try {
      const data = await this.ledgerApi.general(id, buildLedgerQuery(this.state.filters));
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
      { ...buildLedgerQuery(this.state.filters), format, ledger_type: "general" },
      `general-ledger.${format === "excel" ? "xlsx" : "pdf"}`
    );
  }
}
