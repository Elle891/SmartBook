import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";

export class AccountSetListPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Account Sets'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>Account Sets</h1>
          <a href="#/account-sets/create" class="sb-btn sb-btn--primary">Create Account Set</a>
        </div>
        <div class="sb-card-grid">
          <article t-foreach="accountSetStore.state.accountSets" t-as="as" t-key="as.id" class="sb-card">
            <h3><t t-esc="as.name"/></h3>
            <p>Journal Set No.: <t t-esc="as.journal_set_no"/> · Status: <t t-esc="as.status"/></p>
            <p><t t-esc="as.standard"/> · <t t-esc="as.base_currency"/> · Start <t t-esc="as.start_period"/></p>
            <p class="sb-muted">Datasource: <t t-esc="as.datasource_type"/></p>
            <div class="sb-card__actions">
              <button type="button" class="sb-btn sb-btn--ghost"
                t-att-disabled="as.id === accountSetStore.state.currentId"
                t-on-click="() => this.onSwitch(as.id)">
                <t t-if="as.id === accountSetStore.state.currentId">Active</t>
                <t t-else="">Switch</t>
              </button>
              <a t-att-href="'#/account-sets/' + as.id + '/permissions'" class="sb-btn sb-btn--ghost">Permissions</a>
              <a t-att-href="'#/account-sets/' + as.id + '/opening-balances'" class="sb-btn sb-btn--ghost">Opening Balances</a>
              <a t-att-href="'#/chart-of-accounts'" class="sb-btn sb-btn--ghost">Chart</a>
            </div>
          </article>
        </div>
        <p t-if="!accountSetStore.state.accountSets.length and !state.loading" class="sb-muted">
          No account sets yet. <a href="#/account-sets/create">Create your first account set</a>.
        </p>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.state = useState({ loading: false, error: "" });
  }

  async onWillStart() {
    this.state.loading = true;
    try {
      await this.accountSetStore.loadAccountSets(this.rpc);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async onSwitch(id) {
    try {
      await this.accountSetStore.switchAccountSet(id, this.rpc);
      this.notificationStore.notify("Switched account set.", { type: "success" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }
}
