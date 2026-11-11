import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createAssetsApi, createIfrsApi } from "../services/module_apis";
import { createReportsApi } from "../services/reports_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod } from "../utils/ledger_page";

export class IFRSCompliancePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'IFRS Compliance'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <nav class="sb-subnav">
          <button type="button" t-att-class="tabClass('fair-value')" t-on-click="() => state.tab = 'fair-value'">Fair Value</button>
          <button type="button" t-att-class="tabClass('rou')" t-on-click="() => state.tab = 'rou'">ROU Asset</button>
          <button type="button" t-att-class="tabClass('revenue')" t-on-click="() => state.tab = 'revenue'">Revenue</button>
          <button type="button" t-att-class="tabClass('impairment')" t-on-click="() => state.tab = 'impairment'">Impairment</button>
          <button type="button" t-att-class="tabClass('disclosure')" t-on-click="() => state.tab = 'disclosure'">Disclosures</button>
        </nav>

        <t t-if="state.tab === 'fair-value'">
          <form class="sb-form sb-panel" t-on-submit.prevent="submitFairValue">
            <input class="sb-input" placeholder="Account code" t-att-value="state.fairValue.account_code" t-on-input="(ev) => state.fairValue.account_code = ev.target.value"/>
            <input class="sb-input" placeholder="Period" t-att-value="state.fairValue.period_code" t-on-input="(ev) => state.fairValue.period_code = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Carrying amount" t-att-value="state.fairValue.carrying_amount" t-on-input="(ev) => state.fairValue.carrying_amount = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Fair value" t-att-value="state.fairValue.fair_value" t-on-input="(ev) => state.fairValue.fair_value = ev.target.value"/>
            <input type="date" class="sb-input" t-att-value="state.fairValue.voucher_date" t-on-input="(ev) => state.fairValue.voucher_date = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Record Adjustment</button>
          </form>
        </t>

        <t t-elif="state.tab === 'rou'">
          <form class="sb-form sb-panel" t-on-submit.prevent="submitRou">
            <input class="sb-input" placeholder="Asset name" t-att-value="state.rou.name" t-on-input="(ev) => state.rou.name = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Lease term (months)" t-att-value="state.rou.lease_term_months" t-on-input="(ev) => state.rou.lease_term_months = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Lease liability" t-att-value="state.rou.lease_liability" t-on-input="(ev) => state.rou.lease_liability = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="ROU asset value" t-att-value="state.rou.rou_asset_value" t-on-input="(ev) => state.rou.rou_asset_value = ev.target.value"/>
            <input type="date" class="sb-input" placeholder="Commencement" t-att-value="state.rou.commencement_date" t-on-input="(ev) => state.rou.commencement_date = ev.target.value"/>
            <input class="sb-input" placeholder="Period" t-att-value="state.rou.period_code" t-on-input="(ev) => state.rou.period_code = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Register ROU Asset</button>
          </form>
        </t>

        <t t-elif="state.tab === 'revenue'">
          <form class="sb-form sb-panel" t-on-submit.prevent="submitRevenue">
            <input class="sb-input" placeholder="Performance obligation ID" t-att-value="state.revenue.obligation_id" t-on-input="(ev) => state.revenue.obligation_id = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Amount" t-att-value="state.revenue.amount" t-on-input="(ev) => state.revenue.amount = ev.target.value"/>
            <input class="sb-input" placeholder="Period" t-att-value="state.revenue.period_code" t-on-input="(ev) => state.revenue.period_code = ev.target.value"/>
            <input type="date" class="sb-input" t-att-value="state.revenue.voucher_date" t-on-input="(ev) => state.revenue.voucher_date = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Recognize Revenue</button>
          </form>
        </t>

        <t t-elif="state.tab === 'impairment'">
          <form class="sb-form sb-panel" t-on-submit.prevent="submitImpairment">
            <select class="sb-input" t-on-change="(ev) => state.impairment.asset_id = ev.target.value">
              <option value="">Select asset</option>
              <option t-foreach="state.assets" t-as="a" t-key="a.id" t-att-value="a.id"><t t-esc="a.name"/></option>
            </select>
            <input type="number" class="sb-input" placeholder="Recoverable amount" t-att-value="state.impairment.recoverable_amount" t-on-input="(ev) => state.impairment.recoverable_amount = ev.target.value"/>
            <input class="sb-input" placeholder="Period" t-att-value="state.impairment.period_code" t-on-input="(ev) => state.impairment.period_code = ev.target.value"/>
            <input type="date" class="sb-input" t-att-value="state.impairment.voucher_date" t-on-input="(ev) => state.impairment.voucher_date = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Run Impairment Test</button>
          </form>
        </t>

        <t t-else="">
          <div class="sb-filters">
            <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.disclosurePeriod" t-on-input="(ev) => state.disclosurePeriod = ev.target.value"/>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="loadDisclosure">Load Disclosure Notes</button>
          </div>
          <div t-if="state.disclosure" class="sb-panel">
            <h2><t t-esc="state.disclosure.title"/></h2>
            <div t-foreach="state.disclosure.sections || []" t-as="sec" t-key="sec.heading">
              <h3><t t-esc="sec.heading"/></h3>
              <p><t t-esc="sec.content"/></p>
            </div>
          </div>
        </t>

        <div t-if="state.lastResult" class="sb-panel sb-success-text">
          <pre><t t-esc="state.lastResult"/></pre>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.ifrsApi = createIfrsApi(this.rpc);
    this.assetsApi = createAssetsApi(this.rpc);
    this.reportsApi = createReportsApi(this.rpc);
    const period = defaultPeriod(this.accountSetStore);
    const today = new Date().toISOString().slice(0, 10);
    this.state = useState({
      loading: false,
      error: "",
      tab: "fair-value",
      assets: [],
      lastResult: "",
      disclosure: null,
      disclosurePeriod: period,
      fairValue: { account_code: "", period_code: period, carrying_amount: "", fair_value: "", voucher_date: today },
      rou: { name: "", lease_term_months: "36", lease_liability: "", rou_asset_value: "", commencement_date: today, period_code: period },
      revenue: { obligation_id: "", amount: "", period_code: period, voucher_date: today },
      impairment: { asset_id: "", recoverable_amount: "", period_code: period, voucher_date: today },
    });
    onWillStart(() => this.loadAssets());
  }

  tabClass(tab) {
    return this.state.tab === tab ? "is-active" : "";
  }

  async loadAssets() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    try {
      this.state.assets = (await this.assetsApi.registerTable(asId, false)) || [];
    } catch {
      this.state.assets = [];
    }
  }

  async submitFairValue() {
    await this.postForm("fairValue", (asId, f) =>
      this.ifrsApi.fairValueAdjustment(asId, {
        account_code: f.account_code,
        period_code: f.period_code,
        carrying_amount: Number(f.carrying_amount),
        fair_value: Number(f.fair_value),
        voucher_date: f.voucher_date,
      })
    );
  }

  async submitRou() {
    await this.postForm("rou", (asId, f) =>
      this.ifrsApi.registerRouAsset(asId, {
        name: f.name,
        lease_term_months: Number(f.lease_term_months),
        lease_liability: Number(f.lease_liability),
        rou_asset_value: Number(f.rou_asset_value),
        commencement_date: f.commencement_date,
        period_code: f.period_code,
      })
    );
  }

  async submitRevenue() {
    await this.postForm("revenue", (asId, f) =>
      this.ifrsApi.recognizeRevenue(asId, {
        obligation_id: f.obligation_id,
        amount: Number(f.amount),
        period_code: f.period_code,
        voucher_date: f.voucher_date,
      })
    );
  }

  async submitImpairment() {
    await this.postForm("impairment", (asId, f) =>
      this.ifrsApi.impairmentTest(asId, {
        asset_id: f.asset_id,
        recoverable_amount: Number(f.recoverable_amount),
        period_code: f.period_code,
        voucher_date: f.voucher_date,
      })
    );
  }

  async postForm(key, fn) {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const result = await fn(asId, this.state[key]);
      this.state.lastResult = JSON.stringify(result, null, 2);
      this.notificationStore.notify("IFRS transaction recorded.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async loadDisclosure() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      this.state.disclosure = await this.reportsApi.disclosureNotes(asId, {
        period_code: this.state.disclosurePeriod,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }
}
