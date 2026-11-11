import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createBankApi, createReconciliationApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class ReconciliationPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Reconciliation'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-filters">
          <select class="sb-input" t-on-change="(ev) => state.connectionId = ev.target.value">
            <option value="">Select bank connection</option>
            <option t-foreach="state.connections" t-as="c" t-key="c.connection_id" t-att-value="c.connection_id">
              <t t-esc="c.bank_code"/> — <t t-esc="c.account_number"/>
            </option>
          </select>
          <input class="sb-input" placeholder="Period" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="initiate">Start Session</button>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="autoMatch" t-att-disabled="!state.sessionId">Auto Match</button>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="complete" t-att-disabled="!state.sessionId">Complete</button>
        </div>

        <p t-if="state.sessionId" class="sb-muted">Session: <t t-esc="state.sessionId"/></p>
        <p t-if="state.diff" t-att-class="state.diff.difference === 0 ? 'sb-success-text' : 'sb-field__error'">
          Difference: <t t-esc="formatMoney(state.diff.difference)"/> ·
          Unmatched bank: <t t-esc="state.diff.unmatched_bank_count"/> ·
          Unmatched internal: <t t-esc="state.diff.unmatched_internal_count"/>
        </p>

        <t t-if="state.report">
          <div class="sb-panel">
            <h2>Matched (<t t-esc="state.report.matched.length"/>)</h2>
            <table class="sb-table">
              <thead><tr><th>Bank Txn</th><th>Entry</th><th>Type</th></tr></thead>
              <tbody>
                <tr t-foreach="state.report.matched" t-as="m" t-key="m.match_id">
                  <td><t t-esc="m.bank_transaction_id"/></td>
                  <td><t t-esc="m.voucher_entry_id or '—'"/></td>
                  <td><t t-esc="m.match_type"/></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="sb-panel">
            <h2>Unmatched Bank</h2>
            <table class="sb-table">
              <thead><tr><th>ID</th><th>Date</th><th>Amount</th><th>Description</th><th>Match Entry ID</th><th></th></tr></thead>
              <tbody>
                <tr t-foreach="state.report.unmatched.bank" t-as="b" t-key="b.bank_transaction_id">
                  <td><t t-esc="b.bank_transaction_id"/></td>
                  <td><t t-esc="b.date"/></td>
                  <td><t t-esc="formatMoney(b.signed_amount)"/></td>
                  <td><t t-esc="b.description"/></td>
                  <td><input class="sb-input" t-att-value="manualEntry(b.bank_transaction_id)" t-on-input="(ev) => this.setManual(b.bank_transaction_id, ev.target.value)"/></td>
                  <td><button type="button" class="sb-link-btn" t-on-click="() => this.manualMatch(b.bank_transaction_id)">Match</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="sb-panel">
            <h2>Unmatched Internal</h2>
            <ul>
              <li t-foreach="state.report.unmatched.internal" t-as="i" t-key="i.entry_id">
                <t t-esc="i.entry_id"/> · <t t-esc="i.date"/> · <t t-esc="formatMoney(i.signed_amount)"/> · <t t-esc="i.description"/>
              </li>
            </ul>
          </div>
        </t>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.bankApi = createBankApi(this.rpc);
    this.api = createReconciliationApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      connections: [],
      connectionId: "",
      periodCode: "",
      sessionId: null,
      report: null,
      diff: null,
      manual: {},
    });
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  manualEntry(bankId) {
    return this.state.manual[bankId] || "";
  }

  setManual(bankId, value) {
    this.state.manual[bankId] = value;
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    const id = accountSetId(this.accountSetStore);
    if (id) this.state.connections = await this.bankApi.listConnections(id);
  }

  async initiate() {
    const id = accountSetId(this.accountSetStore);
    this.state.loading = true;
    try {
      const r = await this.api.initiate(id, this.state.connectionId, this.state.periodCode);
      this.state.sessionId = r.session_id;
      await this.refreshReport();
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async autoMatch() {
    const id = accountSetId(this.accountSetStore);
    const r = await this.api.autoMatch(id, this.state.sessionId);
    this.notificationStore.notify(`Matched ${r.matched_count} pairs.`, { type: "success" });
    await this.refreshReport();
  }

  async manualMatch(bankTransactionId) {
    const id = accountSetId(this.accountSetStore);
    const entryId = this.state.manual[bankTransactionId];
    if (!entryId) return;
    await this.api.manualMatch(id, this.state.sessionId, bankTransactionId, entryId);
    await this.refreshReport();
  }

  async refreshReport() {
    const id = accountSetId(this.accountSetStore);
    this.state.report = await this.api.report(id, this.state.sessionId);
    this.state.diff = await this.api.difference(id, this.state.sessionId);
  }

  async complete() {
    const id = accountSetId(this.accountSetStore);
    const r = await this.api.complete(id, this.state.sessionId);
    this.notificationStore.notify(`Session completed. Difference: ${r.difference}`, {
      type: r.difference === 0 ? "success" : "warning",
    });
    await this.refreshReport();
  }
}
