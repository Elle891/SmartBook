import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createTaxApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class TaxFilingPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Tax Filing'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-filters">
          <select class="sb-input" t-on-change="(ev) => state.taxType = ev.target.value">
            <option value="VAT">VAT</option>
            <option value="CIT">CIT</option>
          </select>
          <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="generate">Generate Report</button>
          <button t-if="state.filing" type="button" class="sb-btn sb-btn--primary" t-on-click="submit" t-att-disabled="state.filing.status === 'Submitted'">Submit Filing</button>
        </div>

        <t t-if="state.filing">
          <div class="sb-panel">
            <h2><t t-esc="state.filing.report_data.title or state.filing.tax_type"/> — <t t-esc="state.filing.status"/></h2>
            <table class="sb-table">
              <thead><tr><th>Line</th><th>Amount</th><th></th></tr></thead>
              <tbody>
                <tr t-foreach="lineItems" t-as="line" t-key="line.line_id">
                  <td><t t-esc="line.label"/></td>
                  <td>
                    <t t-if="line.editable">
                      <input type="number" class="sb-input sb-input--num" t-att-value="line.amount" t-on-change="(ev) => this.adjustLine(line.line_id, ev.target.value)"/>
                    </t>
                    <t t-else=""><t t-esc="formatMoney(line.amount)"/></t>
                  </td>
                  <td><t t-if="line.adjusted" class="sb-tag">Adjusted</t></td>
                </tr>
              </tbody>
            </table>
          </div>
        </t>

        <h2>Filing History</h2>
        <table class="sb-table">
          <thead><tr><th>Period</th><th>Type</th><th>Status</th><th>Confirmation</th><th>Submitted</th></tr></thead>
          <tbody>
            <tr t-foreach="state.history" t-as="h" t-key="h.id">
              <td><t t-esc="h.period_code"/></td>
              <td><t t-esc="h.tax_type"/></td>
              <td><t t-esc="h.status"/></td>
              <td><t t-esc="h.confirmation_number or '—'"/></td>
              <td><t t-esc="h.submitted_at or '—'"/></td>
            </tr>
          </tbody>
        </table>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createTaxApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      taxType: "VAT",
      periodCode: "",
      filing: null,
      history: [],
    });
  }

  get lineItems() {
    return this.state.filing?.report_data?.line_items || [];
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    await this.loadHistory();
  }

  async loadHistory() {
    const id = accountSetId(this.accountSetStore);
    if (!id) return;
    try {
      this.state.history = await this.api.history(id, this.state.taxType);
    } catch {
      this.state.history = [];
    }
  }

  async generate() {
    const id = accountSetId(this.accountSetStore);
    this.state.loading = true;
    try {
      this.state.filing = await this.api.generate(id, this.state.periodCode, this.state.taxType);
      await this.loadHistory();
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async adjustLine(lineId, value) {
    const id = accountSetId(this.accountSetStore);
    try {
      this.state.filing = await this.api.adjustLine(id, this.state.filing.id, lineId, Number(value));
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async submit() {
    const id = accountSetId(this.accountSetStore);
    try {
      const r = await this.api.submit(id, this.state.filing.id);
      this.notificationStore.notify(r.message || "Submitted.", { type: "success" });
      this.state.filing = await this.api.getFiling(id, this.state.filing.id);
      await this.loadHistory();
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
