import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createChartApi } from "../services/chart_api";
import { useService, useStore } from "../services/registry";
import { leafAccounts } from "../utils/account_tree";
import { formatApiError } from "../utils/errors";

export class OpeningBalancePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Opening Balances'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <h1>Opening Balances</h1>
        <p class="sb-muted">Enter debit and credit amounts for leaf accounts. Totals must balance.</p>
        <table class="sb-table">
          <thead><tr><th>Code</th><th>Name</th><th>Debit</th><th>Credit</th></tr></thead>
          <tbody>
            <tr t-foreach="state.rows" t-as="row" t-key="row.account_code">
              <td><t t-esc="row.account_code"/></td>
              <td><t t-esc="row.account_name"/></td>
              <td><input type="number" min="0" step="0.01" class="sb-input sb-input--num" t-att-value="row.debit_amount" t-on-input="(ev) => this.onAmount(row.account_code, 'debit', ev.target.value)"/></td>
              <td><input type="number" min="0" step="0.01" class="sb-input sb-input--num" t-att-value="row.credit_amount" t-on-input="(ev) => this.onAmount(row.account_code, 'credit', ev.target.value)"/></td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th colspan="2">Totals</th>
              <th><t t-esc="formatMoney(totalDebits)"/></th>
              <th><t t-esc="formatMoney(totalCredits)"/></th>
            </tr>
          </tfoot>
        </table>
        <p t-if="!isBalanced" class="sb-field__error">Debits and credits must be equal.</p>
        <div class="sb-auth__actions">
          <button type="button" class="sb-btn sb-btn--primary" t-att-disabled="state.saving or !isBalanced" t-on-click="onSave">
            <t t-if="state.saving">Saving…</t>
            <t t-else="">Save Opening Balances</t>
          </button>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.chartApi = createChartApi(this.rpc);
    this.state = useState({ loading: false, saving: false, error: "", rows: [] });
  }

  get accountSetId() {
    const path = this.env.router.state.path;
    const match = path.match(/^\/account-sets\/([^/]+)\/opening-balances$/);
    return match ? match[1] : this.accountSetStore.state.currentId;
  }

  get totalDebits() {
    return this.state.rows.reduce((s, r) => s + Number(r.debit_amount || 0), 0);
  }

  get totalCredits() {
    return this.state.rows.reduce((s, r) => s + Number(r.credit_amount || 0), 0);
  }

  get isBalanced() {
    return Math.abs(this.totalDebits - this.totalCredits) < 0.005;
  }

  formatMoney(v) {
    return Number(v || 0).toFixed(2);
  }

  async onWillStart() {
    this.state.loading = true;
    try {
      const tree = await this.chartApi.getTree(this.accountSetId);
      this.state.rows = leafAccounts(tree.accounts || []).map((a) => ({
        account_code: a.code,
        account_name: a.name,
        debit_amount: 0,
        credit_amount: 0,
      }));
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  onAmount(code, side, value) {
    const row = this.state.rows.find((r) => r.account_code === code);
    if (!row) return;
    const num = Math.max(0, Number(value) || 0);
    if (side === "debit") {
      row.debit_amount = num;
      if (num > 0) row.credit_amount = 0;
    } else {
      row.credit_amount = num;
      if (num > 0) row.debit_amount = 0;
    }
  }

  async onSave() {
    if (!this.isBalanced) return;
    this.state.saving = true;
    try {
      const entries = this.state.rows
        .filter((r) => r.debit_amount > 0 || r.credit_amount > 0)
        .map((r) => ({
          account_code: r.account_code,
          debit_amount: Number(r.debit_amount) || 0,
          credit_amount: Number(r.credit_amount) || 0,
        }));
      await this.accountSetStore.accountSetApi(this.rpc).setOpeningBalances(this.accountSetId, entries);
      this.notificationStore.notify("Opening balances saved.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.saving = false;
    }
  }
}
