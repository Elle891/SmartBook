import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPeriodEndApi } from "../services/period_end_api";
import { createVoucherApi } from "../services/voucher_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { defaultPeriod } from "../utils/ledger_page";

export class PeriodEndPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Period End'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <h1>Month-End Close</h1>
        <div class="sb-field sb-field--inline">
          <label>Period (YYYYMM)</label>
          <input class="sb-input" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="refreshPreflight">Refresh Status</button>
        </div>

        <div class="sb-panel">
          <h2>Pre-flight Status</h2>
          <ul class="sb-preflight">
            <li t-att-class="state.unapprovedCount === 0 ? 'sb-preflight__ok' : 'sb-preflight__warn'">
              Unapproved vouchers: <strong><t t-esc="state.unapprovedCount"/></strong>
            </li>
            <li t-att-class="state.openingPreview.length ? 'sb-preflight__ok' : ''">
              Next-period opening preview: <strong><t t-esc="state.openingPreview.length"/> accounts</strong>
            </li>
          </ul>
        </div>

        <div class="sb-card-grid">
          <article class="sb-card">
            <h3>Cost Carry-Forward</h3>
            <p>Transfer cost accounts to inventory / COGS.</p>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="carryCost" t-att-disabled="state.busy">Run</button>
            <p t-if="state.lastCost" class="sb-muted"><t t-esc="state.lastCost.message"/></p>
          </article>
          <article class="sb-card">
            <h3>Profit / Loss Carry-Forward</h3>
            <p>Close P&amp;L to retained earnings.</p>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="carryPl" t-att-disabled="state.busy">Run</button>
            <p t-if="state.lastPl" class="sb-muted"><t t-esc="state.lastPl.message"/></p>
          </article>
          <article class="sb-card">
            <h3>Depreciation</h3>
            <p>Calculate fixed asset depreciation for the period.</p>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="depreciation" t-att-disabled="state.busy">Run</button>
            <p t-if="state.lastDep" class="sb-muted"><t t-esc="state.lastDep.message"/></p>
          </article>
          <article class="sb-card">
            <h3>Close Period</h3>
            <p>Lock period and carry balance sheet opening balances forward.</p>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="closePeriod" t-att-disabled="state.busy or state.unapprovedCount > 0">Close Period</button>
            <p t-if="state.lastClose" class="sb-muted"><t t-esc="state.lastClose.message"/></p>
          </article>
        </div>

        <div t-if="state.openingPreview.length" class="sb-panel">
          <h2>Next Period Opening Balances (Preview)</h2>
          <table class="sb-table">
            <thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Opening</th></tr></thead>
            <tbody>
              <tr t-foreach="state.openingPreview" t-as="row" t-key="row.account_code">
                <td><t t-esc="row.account_code"/></td>
                <td><t t-esc="row.account_name"/></td>
                <td><t t-esc="row.account_type"/></td>
                <td><t t-esc="row.opening_balance"/></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.periodApi = createPeriodEndApi(this.rpc);
    this.voucherApi = createVoucherApi(this.rpc);
    this.state = useState({
      loading: false,
      busy: false,
      error: "",
      periodCode: "",
      unapprovedCount: 0,
      openingPreview: [],
      lastCost: null,
      lastPl: null,
      lastDep: null,
      lastClose: null,
    });
  }

  get accountSetId() {
    return this.accountSetStore.state.currentId;
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    await this.refreshPreflight();
  }

  async refreshPreflight() {
    if (!this.accountSetId || !this.state.periodCode) return;
    this.state.loading = true;
    try {
      const pending = await this.voucherApi.list(this.accountSetId, {
        periodCode: this.state.periodCode,
        statusFilter: "PendingReview",
      });
      this.state.unapprovedCount = (pending || []).length;
      this.state.openingPreview = await this.periodApi.nextOpeningBalances(
        this.accountSetId,
        this.state.periodCode
      );
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async runAction(fn, resultKey, successMsg) {
    this.state.busy = true;
    this.state.error = "";
    try {
      this.state[resultKey] = await fn();
      this.notificationStore.notify(successMsg, { type: "success" });
      await this.refreshPreflight();
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.busy = false;
    }
  }

  carryCost() {
    return this.runAction(
      () => this.periodApi.carryCostForward(this.accountSetId, this.state.periodCode),
      "lastCost",
      "Cost carry-forward completed."
    );
  }

  carryPl() {
    return this.runAction(
      () => this.periodApi.carryProfitLoss(this.accountSetId, this.state.periodCode),
      "lastPl",
      "P/L carry-forward completed."
    );
  }

  depreciation() {
    return this.runAction(
      () => this.periodApi.calculateDepreciation(this.accountSetId, this.state.periodCode),
      "lastDep",
      "Depreciation calculated."
    );
  }

  closePeriod() {
    return this.runAction(
      () => this.periodApi.closePeriod(this.accountSetId, this.state.periodCode),
      "lastClose",
      "Period closed."
    );
  }
}
