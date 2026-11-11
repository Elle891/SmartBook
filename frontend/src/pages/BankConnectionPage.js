import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createBankApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, formatMoney } from "../utils/ledger_page";

const ROUTING_METHODS = [
  "SWIFT", "CNAPS", "CIPS", "Direct_Debit", "Online_Banking_Transfer", "Local_ACH", "Internal_Transfer",
];

export class BankConnectionPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Bank Connections'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>Bank Connections</h1>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="() => state.showConnect = true">Connect Bank</button>
        </div>

        <table class="sb-table">
          <thead><tr><th>Bank</th><th>Account</th><th>Status</th><th>Last Sync</th><th>Actions</th></tr></thead>
          <tbody>
            <tr t-foreach="state.connections" t-as="c" t-key="c.connection_id">
              <td><t t-esc="c.bank_code"/></td>
              <td><t t-esc="c.account_number"/></td>
              <td><t t-esc="c.status"/></td>
              <td><t t-esc="c.last_synced_at or '—'"/></td>
              <td>
                <button type="button" class="sb-link-btn" t-on-click="() => this.selectConnection(c.connection_id)">Configure</button>
                <button type="button" class="sb-link-btn" t-on-click="() => this.verify(c.connection_id)">Verify</button>
                <button type="button" class="sb-link-btn" t-on-click="() => this.sync(c.connection_id)">Sync</button>
              </td>
            </tr>
          </tbody>
        </table>

        <t t-if="state.selectedId">
          <div class="sb-panel">
            <h2>Routing — Connection <t t-esc="state.selectedId"/></h2>
            <form class="sb-form" t-on-submit.prevent="configureRouting">
              <select class="sb-input" t-on-change="(ev) => state.routing.method = ev.target.value">
                <option t-foreach="routingMethods" t-as="m" t-key="m" t-att-value="m"><t t-esc="m"/></option>
              </select>
              <input class="sb-input" placeholder="Param (BIC / CNAPS / account id)" t-att-value="state.routing.param" t-on-input="(ev) => state.routing.param = ev.target.value"/>
              <label class="sb-check"><input type="checkbox" t-att-checked="state.routing.is_default" t-on-change="(ev) => state.routing.is_default = ev.target.checked"/> Set as default</label>
              <button type="submit" class="sb-btn sb-btn--primary">Save Routing</button>
            </form>
            <h3>Configured Methods</h3>
            <table class="sb-table">
              <thead><tr><th>Method</th><th>Default</th><th>Available</th><th></th></tr></thead>
              <tbody>
                <tr t-foreach="state.routingConfigs" t-as="r" t-key="r.config_id">
                  <td><t t-esc="r.routing_method"/></td>
                  <td><t t-esc="r.is_default ? 'Yes' : 'No'"/></td>
                  <td><t t-esc="r.is_available ? 'Yes' : 'No'"/></td>
                  <td><button type="button" class="sb-link-btn" t-on-click="() => this.setDefault(r.routing_method)">Set Default</button></td>
                </tr>
              </tbody>
            </table>
            <p t-if="state.balance" class="sb-muted">
              Balance: <t t-esc="formatMoney(state.balance.current_balance)"/> <t t-esc="state.balance.currency"/>
            </p>
            <h3>Routing History</h3>
            <p class="sb-muted">Configuration changes are recorded in the audit log (no dedicated API yet).</p>
          </div>
        </t>

        <div t-if="state.showConnect" class="sb-modal-backdrop">
          <div class="sb-modal">
            <h3>Connect Bank Account</h3>
            <input class="sb-input" placeholder="Bank code (ICBC, BOC…)" t-att-value="state.connect.bank_code" t-on-input="(ev) => state.connect.bank_code = ev.target.value"/>
            <input class="sb-input" placeholder="Account number" t-att-value="state.connect.account_number" t-on-input="(ev) => state.connect.account_number = ev.target.value"/>
            <input class="sb-input" placeholder="API key / credential" t-att-value="state.connect.credential" t-on-input="(ev) => state.connect.credential = ev.target.value"/>
            <div class="sb-auth__actions">
              <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => state.showConnect = false">Cancel</button>
              <button type="button" class="sb-btn sb-btn--primary" t-on-click="connect">Connect</button>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createBankApi(this.rpc);
    this.routingMethods = ROUTING_METHODS;
    this.state = useState({
      loading: false,
      error: "",
      connections: [],
      selectedId: null,
      routingConfigs: [],
      balance: null,
      showConnect: false,
      connect: { bank_code: "", account_number: "", credential: "" },
      routing: { method: "CNAPS", param: "", is_default: false },
    });
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    await this.loadConnections();
  }

  async loadConnections() {
    const id = accountSetId(this.accountSetStore);
    if (!id) return;
    this.state.loading = true;
    try {
      this.state.connections = await this.api.listConnections(id);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async connect() {
    const id = accountSetId(this.accountSetStore);
    try {
      await this.api.connect(id, {
        bank_code: this.state.connect.bank_code.trim(),
        account_number: this.state.connect.account_number.trim(),
        credentials: { api_key: this.state.connect.credential },
      });
      this.state.showConnect = false;
      await this.loadConnections();
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async verify(connectionId) {
    const id = accountSetId(this.accountSetStore);
    const r = await this.api.verify(id, connectionId);
    this.notificationStore.notify(r.message, { type: r.connected ? "success" : "warning" });
  }

  async sync(connectionId) {
    const id = accountSetId(this.accountSetStore);
    const r = await this.api.sync(id, connectionId);
    this.notificationStore.notify(`Imported ${r.imported} transactions.`, { type: "success" });
    await this.loadConnections();
  }

  async selectConnection(connectionId) {
    this.state.selectedId = connectionId;
    const id = accountSetId(this.accountSetStore);
    this.state.routingConfigs = await this.api.listRouting(id, connectionId);
    this.state.balance = await this.api.balance(id, connectionId);
  }

  async configureRouting() {
    const id = accountSetId(this.accountSetStore);
    const method = this.state.routing.method;
    const params = method === "SWIFT"
      ? { bic: this.state.routing.param }
      : method === "CNAPS"
        ? { cnaps_routing_number: this.state.routing.param }
        : { account_identifier: this.state.routing.param };
    await this.api.configureRouting(id, this.state.selectedId, {
      routing_method: method,
      params,
      is_default: this.state.routing.is_default,
    });
    await this.selectConnection(this.state.selectedId);
    this.notificationStore.notify("Routing configured.", { type: "success" });
  }

  async setDefault(method) {
    const id = accountSetId(this.accountSetStore);
    await this.api.setDefaultRouting(id, this.state.selectedId, method);
    await this.selectConnection(this.state.selectedId);
  }
}
