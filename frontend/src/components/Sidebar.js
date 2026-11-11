import { Component, useState, xml } from "@odoo/owl";
import { useService, useStore } from "../services/registry";

const NAV_ITEMS = [
  { label: "Dashboard", hash: "#/" },
  { label: "Account Sets", hash: "#/account-sets" },
  { label: "Chart of Accounts", hash: "#/chart-of-accounts" },
  { label: "Vouchers", hash: "#/vouchers" },
  { label: "Ledger", hash: "#/ledger/account-summary" },
  { label: "Period End", hash: "#/period-end" },
  { label: "Reports", hash: "#/reports" },
  { label: "Cashier", hash: "#/cashier" },
  { label: "Payroll", hash: "#/payroll" },
  { label: "Fixed Assets", hash: "#/fixed-assets" },
  { label: "Smart Import", hash: "#/smart-import" },
  { label: "Invoices", hash: "#/invoice-scanner" },
  { label: "Tax Filing", hash: "#/tax-filing" },
  { label: "Bank", hash: "#/bank" },
  { label: "Reconciliation", hash: "#/reconciliation" },
  { label: "Domestic Pay", hash: "#/payments/domestic" },
  { label: "Intl Pay", hash: "#/payments/international" },
  { label: "Pay Queue", hash: "#/payments/queue" },
  { label: "Pay Types", hash: "#/payments/transaction-types" },
  { label: "Pay Fields", hash: "#/payments/field-config" },
  { label: "IFRS", hash: "#/ifrs" },
  { label: "Forecast", hash: "#/forecast" },
  { label: "Assistant", hash: "#/assistant" },
];

export class Sidebar extends Component {
  static template = xml`
    <aside class="sb-sidebar">
      <div class="sb-sidebar__brand">SmartBook</div>
      <nav class="sb-sidebar__nav">
        <a t-foreach="items" t-as="item" t-key="item.hash"
           t-att-href="item.hash"
           t-att-class="{ 'is-active': isActive(item.hash) }">
          <t t-esc="item.label"/>
        </a>
      </nav>
      <div class="sb-sidebar__footer">
        <label class="sb-sidebar__label">Account Set</label>
        <select class="sb-select" t-on-change="onAccountSetChange">
          <option value="">— Select —</option>
          <option t-foreach="accountSetState.accountSets" t-as="as" t-key="as.id"
                  t-att-value="as.id"
                  t-att-selected="as.id === accountSetState.currentId">
            <t t-esc="accountSetLabel(as)"/>
          </option>
        </select>
      </div>
    </aside>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.accountSetState = useState(this.accountSetStore.state);
    this.routerState = useState(this.env.router.state);
    this.items = NAV_ITEMS;
  }

  isActive(hash) {
    const normalized =
      this.routerState.path === "/" ? "#/" : `#${this.routerState.path}`;
    if (hash.startsWith("#/payments/") && normalized.startsWith("#/payments/")) {
      return normalized === hash;
    }
    return normalized === hash;
  }

  accountSetLabel(as) {
    if (as.journal_set_no) return `${as.name} (${as.journal_set_no})`;
    return as.name;
  }

  onAccountSetChange(ev) {
    const id = ev.target.value;
    if (id) this.accountSetStore.switchAccountSet(id, this.rpc);
  }
}
