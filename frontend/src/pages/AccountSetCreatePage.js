import { Component, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";

const CURRENCIES = ["CNY", "USD", "EUR", "GBP", "HKD", "SGD"];

export class AccountSetCreatePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Create Account Set'" loading="state.loading" error="state.error">
      <section class="sb-page sb-page--narrow">
        <h1>Create Account Set</h1>
        <form class="sb-form" t-on-submit.prevent="onSubmit">
          <div class="sb-field">
            <label for="as-name">Name</label>
            <input id="as-name" class="sb-input" t-att-value="state.name" t-on-input="(ev) => state.name = ev.target.value"/>
          </div>
          <div class="sb-field-row">
            <div class="sb-field">
              <label for="as-journal-set-no">Journal Set No.</label>
              <input id="as-journal-set-no" class="sb-input" placeholder="e.g. AS001"
                     t-att-value="state.journalSetNo"
                     t-on-input="(ev) => state.journalSetNo = ev.target.value"/>
            </div>
            <div class="sb-field">
              <label for="as-status">Status</label>
              <select id="as-status" class="sb-input" t-on-change="(ev) => state.status = ev.target.value">
                <option value="Active" t-att-selected="state.status === 'Active'">Active</option>
                <option value="Closed" t-att-selected="state.status === 'Closed'">Closed</option>
              </select>
            </div>
          </div>
          <div class="sb-field-row">
            <div class="sb-field">
              <label for="as-standard">Accounting Standard</label>
              <select id="as-standard" class="sb-input" t-on-change="(ev) => state.standard = ev.target.value">
                <option value="CAS" t-att-selected="state.standard === 'CAS'">CAS</option>
                <option value="IFRS" t-att-selected="state.standard === 'IFRS'">IFRS</option>
              </select>
            </div>
            <div class="sb-field">
              <label for="as-currency">Base Currency</label>
              <select id="as-currency" class="sb-input" t-on-change="(ev) => state.baseCurrency = ev.target.value">
                <t t-foreach="currencies" t-as="cur" t-key="cur">
                  <option t-att-value="cur" t-att-selected="cur === state.baseCurrency"><t t-esc="cur"/></option>
                </t>
              </select>
            </div>
          </div>
          <div class="sb-field">
            <label for="as-period">Start Period (YYYYMM)</label>
            <input id="as-period" class="sb-input" placeholder="202601" t-att-value="state.startPeriod" t-on-input="(ev) => state.startPeriod = ev.target.value"/>
          </div>
          <div class="sb-field">
            <label>Datasource</label>
            <div class="sb-radio-row">
              <label><input type="radio" name="ds" value="Shared" t-att-checked="state.datasourceType === 'Shared'" t-on-change="() => this.setDatasource('Shared')"/> Shared (platform managed)</label>
              <label><input type="radio" name="ds" value="Individual" t-att-checked="state.datasourceType === 'Individual'" t-on-change="() => this.setDatasource('Individual')"/> Individual (my own database)</label>
            </div>
          </div>
          <t t-if="state.datasourceType === 'Individual'">
            <div class="sb-field-row">
              <div class="sb-field"><label>Host</label><input class="sb-input" t-att-value="state.dbHost" t-on-input="(ev) => state.dbHost = ev.target.value"/></div>
              <div class="sb-field"><label>Port</label><input type="number" class="sb-input" t-att-value="state.dbPort" t-on-input="(ev) => state.dbPort = ev.target.value"/></div>
            </div>
            <div class="sb-field"><label>Database</label><input class="sb-input" t-att-value="state.dbName" t-on-input="(ev) => state.dbName = ev.target.value"/></div>
            <div class="sb-field-row">
              <div class="sb-field"><label>User</label><input class="sb-input" t-att-value="state.dbUser" t-on-input="(ev) => state.dbUser = ev.target.value"/></div>
              <div class="sb-field"><label>Password</label><input type="password" class="sb-input" t-att-value="state.dbPassword" t-on-input="(ev) => state.dbPassword = ev.target.value"/></div>
            </div>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="onTestConnection" t-att-disabled="state.testing">
              <t t-if="state.testing">Testing…</t>
              <t t-else="">Test Connection</t>
            </button>
            <p t-if="state.testMessage" t-att-class="state.testOk ? 'sb-success-text' : 'sb-field__error'">
              <t t-esc="state.testMessage"/>
            </p>
          </t>
          <div class="sb-auth__actions">
            <a href="#/account-sets" class="sb-btn sb-btn--ghost">Cancel</a>
            <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.loading">Create</button>
          </div>
        </form>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.currencies = CURRENCIES;
    this.state = useState({
      name: "",
      journalSetNo: "",
      status: "Active",
      standard: "CAS",
      baseCurrency: "CNY",
      startPeriod: "",
      datasourceType: "Shared",
      dbHost: "",
      dbPort: 5432,
      dbName: "",
      dbUser: "",
      dbPassword: "",
      loading: false,
      testing: false,
      testMessage: "",
      testOk: false,
      error: "",
    });
  }

  setDatasource(type) {
    this.state.datasourceType = type;
    this.state.testMessage = "";
  }

  datasourceConfig() {
    return {
      db_host: this.state.dbHost.trim(),
      db_port: Number(this.state.dbPort) || 5432,
      db_name: this.state.dbName.trim(),
      db_user: this.state.dbUser.trim(),
      db_password: this.state.dbPassword,
      db_type: "postgresql",
    };
  }

  validate() {
    if (!this.state.name.trim()) return "Name is required.";
    if (!this.state.journalSetNo.trim()) return "Journal Set No. is required.";
    if (!/^\d{6}$/.test(this.state.startPeriod.trim())) return "Start period must be YYYYMM.";
    if (this.state.datasourceType === "Individual") {
      const cfg = this.datasourceConfig();
      if (!cfg.db_host || !cfg.db_name || !cfg.db_user) {
        return "Complete all database connection fields.";
      }
    }
    return "";
  }

  async onTestConnection() {
    this.state.testing = true;
    this.state.testMessage = "";
    try {
      await this.accountSetStore.accountSetApi(this.rpc).testDatasource(this.datasourceConfig());
      this.state.testOk = true;
      this.state.testMessage = "Connection successful.";
    } catch (err) {
      this.state.testOk = false;
      this.state.testMessage = formatApiError(err);
    } finally {
      this.state.testing = false;
    }
  }

  async onSubmit() {
    const err = this.validate();
    if (err) {
      this.state.error = err;
      return;
    }
    this.state.loading = true;
    this.state.error = "";
    const body = {
      name: this.state.name.trim(),
      journal_set_no: this.state.journalSetNo.trim(),
      status: this.state.status || "Active",
      standard: this.state.standard,
      base_currency: this.state.baseCurrency,
      start_period: this.state.startPeriod.trim(),
      datasource_type: this.state.datasourceType,
    };
    if (this.state.datasourceType === "Individual") {
      body.datasource_config = this.datasourceConfig();
    }
    try {
      const created = await this.accountSetStore.accountSetApi(this.rpc).create(body);
      await this.accountSetStore.loadAccountSets(this.rpc);
      await this.accountSetStore.switchAccountSet(created.id, this.rpc);
      this.notificationStore.notify("Account set created.", { type: "success" });
      window.location.hash = "#/account-sets";
    } catch (e) {
      this.state.error = formatApiError(e);
    } finally {
      this.state.loading = false;
    }
  }
}
