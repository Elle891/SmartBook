import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createAssetsApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class FixedAssetPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Fixed Assets'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <nav class="sb-subnav">
          <button type="button" t-att-class="{ 'is-active': state.tab === 'register' }" t-on-click="() => state.tab = 'register'">Register</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'depreciation' }" t-on-click="() => state.tab = 'depreciation'">Depreciation</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'dispose' }" t-on-click="() => state.tab = 'dispose'">Dispose</button>
        </nav>

        <t t-if="state.tab === 'register'">
          <form class="sb-form" t-on-submit.prevent="registerAsset">
            <div class="sb-field-row">
              <input class="sb-input" placeholder="Asset name" t-att-value="state.form.name" t-on-input="(ev) => state.form.name = ev.target.value"/>
              <input class="sb-input" placeholder="Category" t-att-value="state.form.category" t-on-input="(ev) => state.form.category = ev.target.value"/>
              <input type="date" class="sb-input" t-att-value="state.form.acquisition_date" t-on-input="(ev) => state.form.acquisition_date = ev.target.value"/>
              <input type="number" class="sb-input" placeholder="Cost" t-att-value="state.form.cost" t-on-input="(ev) => state.form.cost = ev.target.value"/>
              <input type="number" class="sb-input" placeholder="Useful life (months)" t-att-value="state.form.useful_life_months" t-on-input="(ev) => state.form.useful_life_months = ev.target.value"/>
            </div>
            <button type="submit" class="sb-btn sb-btn--primary">Register Asset</button>
          </form>
        </t>

        <t t-elif="state.tab === 'depreciation'">
          <div class="sb-filters">
            <input class="sb-input" placeholder="Period" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="previewDep">Preview</button>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="confirmDep">Confirm &amp; Post</button>
          </div>
          <table t-if="state.depPreview" class="sb-table">
            <thead><tr><th>Asset</th><th>Method</th><th>Amount</th><th>NBV</th></tr></thead>
            <tbody>
              <tr t-foreach="state.depPreview.lines" t-as="line" t-key="line.asset_id">
                <td><t t-esc="line.name"/></td>
                <td><t t-esc="line.depreciation_method"/></td>
                <td><t t-esc="formatMoney(line.depreciation_amount)"/></td>
                <td><t t-esc="formatMoney(line.projected_net_book_value)"/></td>
              </tr>
            </tbody>
          </table>
        </t>

        <t t-else="">
          <form class="sb-form" t-on-submit.prevent="disposeAsset">
            <select class="sb-input" t-on-change="(ev) => state.disposeAssetId = ev.target.value">
              <option value="">Select asset</option>
              <option t-foreach="state.assets" t-as="a" t-key="a.id" t-att-value="a.id"><t t-esc="a.name"/></option>
            </select>
            <input type="date" class="sb-input" t-att-value="state.disposeDate" t-on-input="(ev) => state.disposeDate = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Proceeds" t-att-value="state.proceeds" t-on-input="(ev) => state.proceeds = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Dispose</button>
          </form>
        </t>

        <h2>Asset Register</h2>
        <table class="sb-table">
          <thead><tr><th>Name</th><th>Category</th><th>Cost</th><th>Accum Dep</th><th>NBV</th><th>Status</th></tr></thead>
          <tbody>
            <tr t-foreach="state.assets" t-as="a" t-key="a.id">
              <td><t t-esc="a.name"/></td>
              <td><t t-esc="a.category or '—'"/></td>
              <td><t t-esc="formatMoney(a.cost)"/></td>
              <td><t t-esc="formatMoney(a.accumulated_depreciation)"/></td>
              <td><t t-esc="formatMoney(a.net_book_value)"/></td>
              <td><t t-esc="a.is_disposed ? 'Disposed' : 'Active'"/></td>
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
    this.api = createAssetsApi(this.rpc);
    this.state = useState({
      tab: "register",
      loading: false,
      error: "",
      assets: [],
      periodCode: "",
      depPreview: null,
      disposeAssetId: "",
      disposeDate: new Date().toISOString().slice(0, 10),
      proceeds: "",
      form: {
        name: "",
        category: "",
        acquisition_date: new Date().toISOString().slice(0, 10),
        cost: "",
        useful_life_months: "60",
      },
    });
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    await this.loadAssets();
  }

  async loadAssets() {
    const id = accountSetId(this.accountSetStore);
    if (!id) return;
    this.state.loading = true;
    try {
      this.state.assets = await this.api.registerTable(id, true);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async registerAsset() {
    const id = accountSetId(this.accountSetStore);
    try {
      await this.api.register(id, {
        name: this.state.form.name.trim(),
        category: this.state.form.category || null,
        acquisition_date: this.state.form.acquisition_date,
        cost: Number(this.state.form.cost),
        useful_life_months: Number(this.state.form.useful_life_months) || 60,
        depreciation_method: "StraightLine",
      });
      await this.loadAssets();
      this.notificationStore.notify("Asset registered.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async previewDep() {
    const id = accountSetId(this.accountSetStore);
    this.state.depPreview = await this.api.previewDepreciation(id, this.state.periodCode);
  }

  async confirmDep() {
    const id = accountSetId(this.accountSetStore);
    try {
      await this.api.confirmDepreciation(id, this.state.periodCode);
      await this.loadAssets();
      this.notificationStore.notify("Depreciation posted.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async disposeAsset() {
    const id = accountSetId(this.accountSetStore);
    try {
      await this.api.dispose(id, this.state.disposeAssetId, {
        disposal_date: this.state.disposeDate,
        proceeds_amount: Number(this.state.proceeds) || 0,
        period_code: this.state.periodCode,
      });
      await this.loadAssets();
      this.notificationStore.notify("Asset disposed.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
