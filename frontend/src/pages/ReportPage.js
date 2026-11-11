import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createReportsApi } from "../services/reports_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { defaultPeriod, formatMoney } from "../utils/ledger_page";

const REPORT_TYPES = [
  { id: "balance-sheet", label: "Balance Sheet" },
  { id: "income-statement", label: "Income Statement" },
  { id: "cash-flow", label: "Cash Flow" },
  { id: "account-summary", label: "Account Summary" },
];

export class ReportPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Reports'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <nav class="sb-subnav">
          <button type="button" t-att-class="{ 'is-active': state.tab === 'reports' }" t-on-click="() => state.tab = 'reports'">Financial Reports</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'templates' }" t-on-click="() => state.tab = 'templates'">Templates</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'datasources' }" t-on-click="() => state.tab = 'datasources'">Data Sources</button>
        </nav>

        <t t-if="state.tab === 'reports'">
          <div class="sb-filters">
            <select class="sb-input" t-on-change="(ev) => state.reportType = ev.target.value">
              <option t-foreach="reportTypes" t-as="rt" t-key="rt.id" t-att-value="rt.id"><t t-esc="rt.label"/></option>
            </select>
            <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.filters.period_code" t-on-input="(ev) => state.filters.period_code = ev.target.value"/>
            <input class="sb-input" type="date" t-att-value="state.filters.date_from" t-on-input="(ev) => state.filters.date_from = ev.target.value"/>
            <input class="sb-input" type="date" t-att-value="state.filters.date_to" t-on-input="(ev) => state.filters.date_to = ev.target.value"/>
            <input class="sb-input" placeholder="Currency" t-att-value="state.filters.report_currency" t-on-input="(ev) => state.filters.report_currency = ev.target.value"/>
            <input class="sb-input" placeholder="Entity ID" t-att-value="state.filters.entity_id" t-on-input="(ev) => state.filters.entity_id = ev.target.value"/>
            <select t-if="state.reportType === 'cash-flow'" class="sb-input" t-on-change="(ev) => state.filters.cash_flow_method = ev.target.value">
              <option value="Indirect">Indirect</option>
              <option value="Direct">Direct (IFRS)</option>
            </select>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="generateReport">Generate</button>
            <button t-if="state.report and state.report.report_id" type="button" class="sb-btn sb-btn--ghost" t-on-click="() => exportReport('pdf')">PDF</button>
            <button t-if="state.report and state.report.report_id" type="button" class="sb-btn sb-btn--ghost" t-on-click="() => exportReport('csv')">CSV</button>
          </div>
          <div t-if="state.report" class="sb-panel">
            <h2><t t-esc="state.report.title or 'Report'"/></h2>
            <p class="sb-muted">Generated in <t t-esc="state.report.generation_ms"/> ms · <t t-esc="state.report.transaction_count"/> transactions</p>
            <table t-if="state.report.line_items" class="sb-table">
              <tbody>
                <tr t-foreach="state.report.line_items" t-as="line" t-key="line_index">
                  <td><t t-esc="line.label or line.section"/></td>
                  <td><t t-esc="line.amount_formatted or formatMoney(line.amount)"/></td>
                </tr>
              </tbody>
            </table>
            <table t-if="state.report.rows" class="sb-table">
              <thead><tr><th>Code</th><th>Name</th><th>Debits</th><th>Credits</th><th>Closing</th></tr></thead>
              <tbody>
                <tr t-foreach="state.report.rows" t-as="row" t-key="row.account_code">
                  <td><t t-esc="row.account_code"/></td>
                  <td><t t-esc="row.account_name"/></td>
                  <td><t t-esc="row.total_debits_formatted or formatMoney(row.total_debits)"/></td>
                  <td><t t-esc="row.total_credits_formatted or formatMoney(row.total_credits)"/></td>
                  <td><t t-esc="formatMoney(row.closing_balance)"/></td>
                </tr>
              </tbody>
            </table>
            <p t-if="state.report.is_balanced !== undefined">
              Balanced: <strong><t t-esc="state.report.is_balanced ? 'Yes' : 'No'"/></strong>
            </p>
            <p t-if="state.report.net_profit !== undefined">Net profit: <t t-esc="formatMoney(state.report.net_profit)"/></p>
          </div>
        </t>

        <t t-elif="state.tab === 'templates'">
          <div class="sb-page__header">
            <h2>Report Templates</h2>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="openTemplateForm">+ New Template</button>
          </div>
          <table class="sb-table">
            <thead><tr><th>Name</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              <tr t-foreach="state.templates" t-as="tpl" t-key="tpl.id">
                <td><t t-esc="tpl.name"/></td>
                <td><t t-esc="tpl.status"/></td>
                <td>
                  <button type="button" class="sb-link-btn" t-on-click="() => this.runTemplate(tpl.id)">Run</button>
                  <button t-if="tpl.status === 'Draft'" type="button" class="sb-link-btn" t-on-click="() => this.publishTemplate(tpl.id)">Publish</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div t-if="state.showTemplateForm" class="sb-modal-backdrop">
            <div class="sb-modal">
              <h3>New Report Template</h3>
              <div class="sb-field"><label>Name</label><input class="sb-input" t-att-value="state.templateForm.name" t-on-input="(ev) => state.templateForm.name = ev.target.value"/></div>
              <div class="sb-field">
                <label>Report type</label>
                <select class="sb-input" t-on-change="(ev) => state.templateForm.report_type = ev.target.value">
                  <option value="BalanceSheet">Balance Sheet</option>
                  <option value="IncomeStatement">Income Statement</option>
                  <option value="CashFlow">Cash Flow</option>
                  <option value="AccountSummary">Account Summary</option>
                </select>
              </div>
              <div class="sb-field">
                <label>Data source</label>
                <select class="sb-input" t-on-change="(ev) => state.templateForm.data_source_id = ev.target.value">
                  <option value="">Ledger (default)</option>
                  <option t-foreach="state.dataSources" t-as="ds" t-key="ds.id" t-att-value="ds.id"><t t-esc="ds.name"/></option>
                </select>
              </div>
              <div class="sb-auth__actions">
                <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => state.showTemplateForm = false">Cancel</button>
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="saveTemplate">Save</button>
              </div>
            </div>
          </div>
        </t>

        <t t-else="">
          <div class="sb-page__header">
            <h2>Data Sources</h2>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="() => state.showDsForm = true">+ Add Data Source</button>
          </div>
          <table class="sb-table">
            <thead><tr><th>Name</th><th>Mode</th><th>Status</th><th></th></tr></thead>
            <tbody>
              <tr t-foreach="state.dataSources" t-as="ds" t-key="ds.id">
                <td><t t-esc="ds.name"/></td>
                <td><t t-esc="ds.connection_mode"/></td>
                <td><t t-esc="ds.status"/></td>
                <td><button type="button" class="sb-link-btn" t-on-click="() => this.testDataSource(ds.id)">Test</button></td>
              </tr>
            </tbody>
          </table>
          <div t-if="state.showDsForm" class="sb-modal-backdrop">
            <div class="sb-modal">
              <h3>Register Data Source</h3>
              <div class="sb-field"><label>Name</label><input class="sb-input" t-att-value="state.dsForm.name" t-on-input="(ev) => state.dsForm.name = ev.target.value"/></div>
              <div class="sb-field">
                <label>Connection mode</label>
                <select class="sb-input" t-on-change="(ev) => state.dsForm.connection_mode = ev.target.value">
                  <option value="Ledger">Ledger</option>
                  <option value="API">API</option>
                  <option value="DataServer">Data Server</option>
                </select>
              </div>
              <div class="sb-field"><label>Endpoint URL</label><input class="sb-input" t-att-value="state.dsForm.endpoint_url" t-on-input="(ev) => state.dsForm.endpoint_url = ev.target.value"/></div>
              <div class="sb-auth__actions">
                <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => state.showDsForm = false">Cancel</button>
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="saveDataSource">Save</button>
              </div>
            </div>
          </div>
        </t>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.reportsApi = createReportsApi(this.rpc);
    this.reportTypes = REPORT_TYPES;
    this.state = useState({
      tab: "reports",
      loading: false,
      error: "",
      reportType: "balance-sheet",
      filters: {
        period_code: "",
        date_from: "",
        date_to: "",
        report_currency: "",
        entity_id: "",
        entity_group_id: "",
        cash_flow_method: "Indirect",
      },
      report: null,
      templates: [],
      dataSources: [],
      showTemplateForm: false,
      showDsForm: false,
      templateForm: { name: "", report_type: "BalanceSheet", data_source_id: "" },
      dsForm: { name: "", connection_mode: "Ledger", endpoint_url: "" },
    });
  }

  get accountSetId() {
    return this.accountSetStore.state.currentId;
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    this.state.filters.period_code = defaultPeriod(this.accountSetStore);
    await this.loadMeta();
  }

  async loadMeta() {
    if (!this.accountSetId) return;
    try {
      [this.state.templates, this.state.dataSources] = await Promise.all([
        this.reportsApi.listTemplates(this.accountSetId),
        this.reportsApi.listDataSources(this.accountSetId),
      ]);
    } catch {
      // optional metadata
    }
  }

  buildFilters() {
    const f = { ...this.state.filters };
    Object.keys(f).forEach((k) => {
      if (!f[k]) delete f[k];
    });
    return f;
  }

  async generateReport() {
    if (!this.accountSetId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const filters = this.buildFilters();
      const api = this.reportsApi;
      const type = this.state.reportType;
      if (type === "balance-sheet") this.state.report = await api.balanceSheet(this.accountSetId, filters);
      else if (type === "income-statement") this.state.report = await api.incomeStatement(this.accountSetId, filters);
      else if (type === "cash-flow") this.state.report = await api.cashFlow(this.accountSetId, filters);
      else this.state.report = await api.accountSummary(this.accountSetId, filters);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async exportReport(format) {
    if (!this.state.report?.report_id) return;
    await this.reportsApi.exportReport(this.accountSetId, this.state.report.report_id, format);
  }

  openTemplateForm() {
    this.state.showTemplateForm = true;
  }

  async saveTemplate() {
    const dsId = this.state.templateForm.data_source_id;
    const body = {
      name: this.state.templateForm.name.trim(),
      layout: { report_type: this.state.templateForm.report_type },
      data_source_id: dsId || this.state.dataSources[0]?.id,
    };
    if (!body.data_source_id) {
      this.notificationStore.notify("Create a data source first.", { type: "warning" });
      return;
    }
    await this.reportsApi.createTemplate(this.accountSetId, body);
    this.state.showTemplateForm = false;
    await this.loadMeta();
  }

  async publishTemplate(templateId) {
    await this.reportsApi.publishTemplate(this.accountSetId, templateId, []);
    await this.loadMeta();
  }

  async runTemplate(templateId) {
    this.state.report = await this.reportsApi.runTemplate(
      this.accountSetId,
      templateId,
      this.buildFilters()
    );
    this.state.tab = "reports";
  }

  async saveDataSource() {
    await this.reportsApi.createDataSource(this.accountSetId, {
      name: this.state.dsForm.name.trim(),
      connection_mode: this.state.dsForm.connection_mode,
      endpoint_url: this.state.dsForm.endpoint_url || null,
      vendor: "",
      credentials: {},
      config: {},
    });
    this.state.showDsForm = false;
    await this.loadMeta();
  }

  async testDataSource(sourceId) {
    const result = await this.reportsApi.testDataSource(this.accountSetId, sourceId);
    this.notificationStore.notify(result.message, { type: result.success ? "success" : "error" });
  }
}
