import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { LedgerFilterBar, LedgerNav } from "../components/LedgerNav";
import { createLedgerApi } from "../services/ledger_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, buildLedgerQuery, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class SubsidiaryLedgerPage extends Component {
  static components = { AppShell, LedgerNav, LedgerFilterBar };
  static template = xml`
    <AppShell title="'Subsidiary Ledger'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <LedgerNav/>
        <LedgerFilterBar
          periodCode="state.filters.periodCode"
          accountCode="state.filters.accountCode"
          dimension="state.filters.dimension"
          dimensionValue="state.filters.dimensionValue"
          dateFrom="state.filters.dateFrom"
          dateTo="state.filters.dateTo"
          showAccount="true"
          showDimension="true"
          showDimensionValue="true"
          onChange.bind="setFilter"
          onApply.bind="load"
        />
        <div t-foreach="state.groups" t-as="group" t-key="group.dimension_value" class="sb-panel">
          <h3><t t-esc="group.dimension_value or '(blank)'"/></h3>
          <table class="sb-table">
            <thead><tr><th>Date</th><th>Voucher</th><th>Description</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead>
            <tbody>
              <tr t-foreach="group.entries" t-as="e" t-key="e_index">
                <td><t t-esc="e.entry_date"/></td>
                <td><t t-esc="e.voucher_number"/></td>
                <td><t t-esc="e.description"/></td>
                <td><t t-esc="formatMoney(e.debit_amount)"/></td>
                <td><t t-esc="formatMoney(e.credit_amount)"/></td>
                <td><t t-esc="formatMoney(e.running_balance)"/></td>
              </tr>
            </tbody>
          </table>
        </div>
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
      groups: [],
      filters: {
        periodCode: "",
        accountCode: "1001",
        dimension: "department",
        dimensionValue: "",
        dateFrom: "",
        dateTo: "",
      },
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
      const data = await this.ledgerApi.subsidiary(id, buildLedgerQuery(this.state.filters));
      this.state.groups = data.groups || [];
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }
}
