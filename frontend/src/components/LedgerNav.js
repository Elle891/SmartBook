import { Component, xml } from "@odoo/owl";

export const LEDGER_NAV = [
  { label: "Account Summary", hash: "#/ledger/account-summary" },
  { label: "General Ledger", hash: "#/ledger/general" },
  { label: "Subsidiary Ledger", hash: "#/ledger/subsidiary" },
  { label: "Cash Journal", hash: "#/ledger/cash-journal" },
  { label: "Bank Journal", hash: "#/ledger/bank-journal" },
];

export class LedgerNav extends Component {
  static template = xml`
    <nav class="sb-subnav">
      <a t-foreach="items" t-as="item" t-key="item.hash"
         t-att-href="item.hash"
         t-att-class="{ 'is-active': isActive(item.hash) }">
        <t t-esc="item.label"/>
      </a>
    </nav>
  `;
  static props = {
    items: { type: Array, optional: true },
  };

  setup() {
    this.items = this.props.items || LEDGER_NAV;
  }

  isActive(hash) {
    return (window.location.hash || "#/").replace(/^#/, "") === hash.replace(/^#/, "");
  }
}

export class LedgerFilterBar extends Component {
  static template = xml`
    <div class="sb-filters">
      <input class="sb-input" placeholder="Period YYYYMM" t-att-value="props.periodCode" t-on-input="(ev) => props.onChange('periodCode', ev.target.value)"/>
      <input t-if="props.showAccount" class="sb-input" placeholder="Account code" t-att-value="props.accountCode" t-on-input="(ev) => props.onChange('accountCode', ev.target.value)"/>
      <select t-if="props.showDimension" class="sb-input" t-on-change="(ev) => props.onChange('dimension', ev.target.value)">
        <option value="department">Department</option>
        <option value="project">Project</option>
        <option value="customer">Customer</option>
        <option value="supplier">Supplier</option>
        <option value="employee">Employee</option>
      </select>
      <input t-if="props.showDimensionValue" class="sb-input" placeholder="Dimension value" t-att-value="props.dimensionValue" t-on-input="(ev) => props.onChange('dimensionValue', ev.target.value)"/>
      <input class="sb-input" type="date" t-att-value="props.dateFrom" t-on-input="(ev) => props.onChange('dateFrom', ev.target.value)"/>
      <input class="sb-input" type="date" t-att-value="props.dateTo" t-on-input="(ev) => props.onChange('dateTo', ev.target.value)"/>
      <button type="button" class="sb-btn sb-btn--primary" t-on-click="props.onApply">Apply</button>
      <button t-if="props.onExportPdf" type="button" class="sb-btn sb-btn--ghost" t-on-click="() => props.onExportPdf()">PDF</button>
      <button t-if="props.onExportExcel" type="button" class="sb-btn sb-btn--ghost" t-on-click="() => props.onExportExcel()">Excel</button>
    </div>
  `;
  static props = {
    periodCode: { type: String, optional: true },
    accountCode: { type: String, optional: true },
    dimension: { type: String, optional: true },
    dimensionValue: { type: String, optional: true },
    dateFrom: { type: String, optional: true },
    dateTo: { type: String, optional: true },
    showAccount: { type: Boolean, optional: true },
    showDimension: { type: Boolean, optional: true },
    showDimensionValue: { type: Boolean, optional: true },
    onChange: Function,
    onApply: Function,
    onExportPdf: { type: Function, optional: true },
    onExportExcel: { type: Function, optional: true },
  };
}
