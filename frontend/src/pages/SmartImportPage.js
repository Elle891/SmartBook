import { Component, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createSmartImportApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class SmartImportPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Smart Import'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-panel">
          <h2>Upload Bank / Payment File</h2>
          <input type="file" accept=".csv,.xls,.xlsx" t-on-change="onFile"/>
          <p class="sb-muted">Supports bank CSV/XLS, WeChat Pay and Alipay exports.</p>
        </div>

        <t t-if="state.transactions.length">
          <table class="sb-table">
            <thead>
              <tr><th>Date</th><th>Amount</th><th>Direction</th><th>Counterparty</th><th>Suggested Dr</th><th>Suggested Cr</th><th>Debit</th><th>Credit</th><th>Skip</th></tr>
            </thead>
            <tbody>
              <tr t-foreach="state.transactions" t-as="txn" t-key="txn.id">
                <td><t t-esc="txn.txn_date"/></td>
                <td><t t-esc="formatMoney(txn.amount)"/></td>
                <td><t t-esc="txn.direction"/></td>
                <td><t t-esc="txn.counterparty or txn.description"/></td>
                <td><t t-esc="txn.suggested_debit_account or '—'"/></td>
                <td><t t-esc="txn.suggested_credit_account or '—'"/></td>
                <td><input class="sb-input sb-input--num" t-att-value="mappingFor(txn.id).debit" t-on-input="(ev) => this.setMapping(txn.id, 'debit', ev.target.value)"/></td>
                <td><input class="sb-input sb-input--num" t-att-value="mappingFor(txn.id).credit" t-on-input="(ev) => this.setMapping(txn.id, 'credit', ev.target.value)"/></td>
                <td><input type="checkbox" t-att-checked="mappingFor(txn.id).skip" t-on-change="(ev) => this.setMapping(txn.id, 'skip', ev.target.checked)"/></td>
              </tr>
            </tbody>
          </table>
          <div class="sb-auth__actions">
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="confirmImport">Confirm Import</button>
          </div>
        </t>

        <div t-if="state.summary" class="sb-panel">
          <h3>Import Summary</h3>
          <p>Vouchers generated: <strong><t t-esc="state.summary.vouchers_generated"/></strong></p>
          <p>Records skipped: <strong><t t-esc="state.summary.records_skipped"/></strong></p>
          <p>Status: <t t-esc="state.summary.status"/></p>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createSmartImportApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      sessionId: null,
      transactions: [],
      mappings: {},
      summary: null,
      periodCode: "",
    });
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  mappingFor(id) {
    if (!this.state.mappings[id]) {
      const txn = this.state.transactions.find((t) => t.id === id);
      this.state.mappings[id] = {
        debit: txn?.suggested_debit_account || "",
        credit: txn?.suggested_credit_account || "",
        skip: false,
      };
    }
    return this.state.mappings[id];
  }

  setMapping(id, field, value) {
    const m = this.mappingFor(id);
    m[field] = value;
  }

  async onFile(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    const id = accountSetId(this.accountSetStore);
    this.state.loading = true;
    this.state.error = "";
    try {
      const result = await this.api.upload(id, file);
      this.state.sessionId = result.session_id;
      this.state.transactions = result.transactions || [];
      this.state.mappings = {};
      this.state.summary = null;
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
      ev.target.value = "";
    }
  }

  async confirmImport() {
    const id = accountSetId(this.accountSetStore);
    const mappings = this.state.transactions.map((txn) => {
      const m = this.mappingFor(txn.id);
      return {
        transaction_id: txn.id,
        debit_account: m.skip ? undefined : m.debit || undefined,
        credit_account: m.skip ? undefined : m.credit || undefined,
        period_code: this.state.periodCode,
        skip: m.skip,
      };
    });
    this.state.loading = true;
    try {
      const result = await this.api.confirm(id, this.state.sessionId, mappings);
      this.state.summary = result.summary;
      this.notificationStore.notify("Import confirmed.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }
}
