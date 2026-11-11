import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { useService, useStore } from "../services/registry";

export class HomePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Dashboard'" loading="accountSetState.loading">
      <section class="sb-page">
        <h1>Welcome to SmartBook</h1>
        <p t-if="current">
          Current account set: <strong><t t-esc="current.name"/></strong>
          (<t t-esc="current.standard or 'CAS'"/>)
        </p>
        <p t-else="">Select or create an account set to begin. <a href="#/account-sets/create">Create one</a></p>
        <div class="sb-card-grid">
          <article class="sb-card">
            <h3>Vouchers</h3>
            <p>Create and approve accounting vouchers.</p>
            <a href="#/vouchers" class="sb-btn sb-btn--ghost">Open</a>
          </article>
          <article class="sb-card">
            <h3>Chart of Accounts</h3>
            <p>Manage your account hierarchy.</p>
            <a href="#/chart-of-accounts" class="sb-btn sb-btn--ghost">Open</a>
          </article>
          <article class="sb-card">
            <h3>Account Sets</h3>
            <p>Switch enterprises and manage permissions.</p>
            <a href="#/account-sets" class="sb-btn sb-btn--ghost">Open</a>
          </article>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.accountSetStore = useStore("accountSetStore");
    this.accountSetState = useState(this.accountSetStore.state);
    this.rpc = useService("rpc");
    this.orm = useService("orm");

    onWillStart(async () => {
      if (!this.env.stores.authStore.isAuthenticated()) return;
      await this.accountSetStore.loadAccountSets(this.rpc);
    });
  }

  get current() {
    return this.accountSetStore.currentAccountSet();
  }
}
