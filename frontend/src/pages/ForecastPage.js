import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createForecastApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class ForecastPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Cash Flow Forecast'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-filters">
          <label>Horizon (months)
            <select class="sb-input" t-att-value="state.horizon" t-on-change="(ev) => state.horizon = Number(ev.target.value)">
              <option t-foreach="horizons" t-as="h" t-key="h" t-att-value="h"><t t-esc="h"/></option>
            </select>
          </label>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="loadForecast">Generate Forecast</button>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => exportForecast('csv')">Export CSV</button>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => exportForecast('pdf')">Export PDF</button>
        </div>

        <p t-if="state.insufficientData" class="sb-field__error">
          Insufficient data: at least 6 months of history required to generate a forecast.
        </p>

        <t t-if="state.metrics">
          <div class="sb-panel">
            <h2>Model Metrics</h2>
            <p>MAPE: <strong><t t-esc="(state.metrics.mape * 100).toFixed(2)"/>%</strong> ·
               RMSE: <t t-esc="formatMoney(state.metrics.rmse)"/> ·
               Data points: <t t-esc="state.metrics.data_points"/> months ·
               Model: <t t-esc="state.metrics.model_type"/></p>
          </div>
        </t>

        <t t-if="state.forecast">
          <div class="sb-panel">
            <h2>Forecast (<t t-esc="state.forecast.horizon_months"/> months)</h2>
            <table class="sb-table">
              <thead>
                <tr><th>Period</th><th>Net Cash Flow</th><th>CI Lower</th><th>CI Upper</th><th>Chart</th></tr>
              </thead>
              <tbody>
                <tr t-foreach="state.forecast.periods" t-as="p" t-key="p.period_code">
                  <td><t t-esc="p.period_code"/></td>
                  <td><t t-esc="formatMoney(p.predicted_net_cash_flow)"/></td>
                  <td><t t-esc="formatMoney(p.confidence_lower)"/></td>
                  <td><t t-esc="formatMoney(p.confidence_upper)"/></td>
                  <td><div class="sb-bar" t-att-style="barStyle(p.predicted_net_cash_flow)"/></td>
                </tr>
              </tbody>
            </table>
          </div>
        </t>

        <div class="sb-panel">
          <h2>Forecast vs Actual</h2>
          <div class="sb-filters">
            <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.comparePeriod" t-on-input="(ev) => state.comparePeriod = ev.target.value"/>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="loadComparison">Compare</button>
          </div>
          <table t-if="state.comparison" class="sb-table">
            <thead><tr><th>Snapshot</th><th>Predicted</th><th>Actual</th><th>CI</th></tr></thead>
            <tbody>
              <tr t-foreach="state.comparison.comparisons" t-as="c" t-key="c.snapshot_period">
                <td><t t-esc="c.snapshot_period"/></td>
                <td><t t-esc="formatMoney(c.predicted_net_cash_flow)"/></td>
                <td><t t-esc="formatMoney(c.actual_net_cash_flow)"/></td>
                <td><t t-esc="formatMoney(c.confidence_lower)"/> – <t t-esc="formatMoney(c.confidence_upper)"/></td>
              </tr>
            </tbody>
          </table>
          <p t-if="state.comparison" class="sb-muted">Actual for period: <t t-esc="formatMoney(state.comparison.actual_net_cash_flow)"/></p>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createForecastApi(this.rpc);
    this.horizons = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
    this.state = useState({
      loading: false,
      error: "",
      horizon: 6,
      forecast: null,
      metrics: null,
      comparison: null,
      comparePeriod: defaultPeriod(this.accountSetStore),
      insufficientData: false,
      maxNet: 1,
    });
    onWillStart(() => this.loadMetrics());
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  barStyle(net) {
    const pct = Math.min(100, Math.abs(Number(net) / this.state.maxNet) * 100);
    const color = Number(net) >= 0 ? "#2e7d32" : "#c62828";
    return `width:${pct}%;max-width:120px;height:8px;background:${color}`;
  }

  async loadMetrics() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    try {
      this.state.metrics = await this.api.metrics(asId);
    } catch {
      this.state.metrics = null;
    }
  }

  async loadForecast() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    this.state.insufficientData = false;
    try {
      const [forecast, metrics] = await Promise.all([
        this.api.get(asId, this.state.horizon),
        this.api.metrics(asId).catch(() => null),
      ]);
      this.state.forecast = forecast;
      this.state.metrics = metrics;
      const nets = (forecast.periods || []).map((p) => Math.abs(p.predicted_net_cash_flow));
      this.state.maxNet = Math.max(...nets, 1);
    } catch (err) {
      const msg = formatApiError(err);
      if (msg.includes("insufficient_data") || msg.includes("Insufficient")) {
        this.state.insufficientData = true;
      } else {
        this.state.error = msg;
      }
    } finally {
      this.state.loading = false;
    }
  }

  async loadComparison() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.comparePeriod) return;
    try {
      this.state.comparison = await this.api.comparison(asId, this.state.comparePeriod);
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async exportForecast(format) {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    try {
      await this.api.export(asId, this.state.horizon, format);
      this.notificationStore.notify(`Forecast exported as ${format.toUpperCase()}.`, { type: "success" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }
}
