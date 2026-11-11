import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createCashierApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

function cashierStorageKey(id) {
  return `smartbook.cashier.accounts.${id}`;
}

export class CashierPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Cashier'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <nav class="sb-subnav">
          <button type="button" t-att-class="{ 'is-active': state.tab === 'accounts' }" t-on-click="() => state.tab = 'accounts'">Accounts</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'txn' }" t-on-click="() => state.tab = 'txn'">Transactions</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'reconcile' }" t-on-click="() => state.tab = 'reconcile'">Reconcile</button>
        </nav>

        <t t-if="state.tab === 'accounts'">
          <div class="sb-panel">
            <h2>Register Cashier Account</h2>
            <form class="sb-form" t-on-submit.prevent="registerAccount">
              <div class="sb-field-row">
                <input class="sb-input" placeholder="Account code (1010/1020)" t-att-value="state.reg.code" t-on-input="(ev) => state.reg.code = ev.target.value"/>
                <select class="sb-input" t-on-change="(ev) => state.reg.cashier_type = ev.target.value">
                  <option value="Cash">Cash</option>
                  <option value="Bank">Bank</option>
                </select>
                <input class="sb-input" placeholder="Name" t-att-value="state.reg.name" t-on-input="(ev) => state.reg.name = ev.target.value"/>
                <input class="sb-input" placeholder="Currency" t-att-value="state.reg.currency" t-on-input="(ev) => state.reg.currency = ev.target.value"/>
              </div>
              <button type="submit" class="sb-btn sb-btn--primary">Register</button>
            </form>
          </div>
          <table class="sb-table">
            <thead><tr><th>Code</th><th>Type</th><th>Name</th><th>Currency</th><th>FX</th></tr></thead>
            <tbody>
              <tr t-foreach="state.accounts" t-as="a" t-key="a.account_code">
                <td><t t-esc="a.account_code"/></td>
                <td><t t-esc="a.cashier_type"/></td>
                <td><t t-esc="a.name"/></td>
                <td><t t-esc="a.currency"/></td>
                <td><button type="button" class="sb-link-btn" t-on-click="() => this.loadFx(a.account_code)">View</button></td>
              </tr>
            </tbody>
          </table>
          <p t-if="state.fx" class="sb-panel sb-muted">
            FX balance for <t t-esc="state.fx.account_code"/>:
            functional <t t-esc="formatMoney(state.fx.functional_balance)"/>
            <t t-if="state.fx.foreign_balance"> · foreign <t t-esc="formatMoney(state.fx.foreign_balance)"/></t>
          </p>
        </t>

        <t t-elif="state.tab === 'txn'">
          <div class="sb-filters">
            <select class="sb-input" t-on-change="(ev) => state.txnType = ev.target.value">
              <option value="receipt">Receipt</option>
              <option value="payment">Payment</option>
              <option value="transfer">Transfer</option>
            </select>
            <input class="sb-input" placeholder="Period" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
          </div>
          <form class="sb-form" t-on-submit.prevent="submitTxn">
            <t t-if="state.txnType !== 'transfer'">
              <input class="sb-input" placeholder="Account code" t-att-value="state.txn.account_code" t-on-input="(ev) => state.txn.account_code = ev.target.value"/>
              <input class="sb-input" placeholder="Counterparty account" t-att-value="state.txn.counterparty" t-on-input="(ev) => state.txn.counterparty = ev.target.value"/>
              <input type="number" class="sb-input" placeholder="Amount" t-att-value="state.txn.amount" t-on-input="(ev) => state.txn.amount = ev.target.value"/>
            </t>
            <t t-else="">
              <input class="sb-input" placeholder="From account" t-att-value="state.txn.from" t-on-input="(ev) => state.txn.from = ev.target.value"/>
              <input class="sb-input" placeholder="To account" t-att-value="state.txn.to" t-on-input="(ev) => state.txn.to = ev.target.value"/>
              <input type="number" class="sb-input" placeholder="Amount" t-att-value="state.txn.amount" t-on-input="(ev) => state.txn.amount = ev.target.value"/>
            </t>
            <input class="sb-input" placeholder="Description" t-att-value="state.txn.description" t-on-input="(ev) => state.txn.description = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Post</button>
          </form>
        </t>

        <t t-else="">
          <form class="sb-form" t-on-submit.prevent="reconcile">
            <input class="sb-input" placeholder="Cash account code" t-att-value="state.reconcileCode" t-on-input="(ev) => state.reconcileCode = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Physical count" t-att-value="state.physicalCount" t-on-input="(ev) => state.physicalCount = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Reconcile</button>
          </form>
          <p t-if="state.reconcileResult" t-att-class="state.reconcileResult.is_balanced ? 'sb-success-text' : 'sb-field__error'">
            System: <t t-esc="formatMoney(state.reconcileResult.system_balance)"/> ·
            Physical: <t t-esc="formatMoney(state.reconcileResult.physical_count)"/> ·
            Diff: <t t-esc="formatMoney(state.reconcileResult.discrepancy)"/>
          </p>
        </t>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createCashierApi(this.rpc);
    this.state = useState({
      tab: "accounts",
      loading: false,
      error: "",
      accounts: [],
      periodCode: "",
      fx: null,
      reg: { code: "", cashier_type: "Cash", name: "", currency: "CNY" },
      txnType: "receipt",
      txn: { account_code: "", counterparty: "", amount: "", from: "", to: "", description: "" },
      reconcileCode: "",
      physicalCount: "",
      reconcileResult: null,
    });
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    this.loadAccounts();
  }

  loadAccounts() {
    const id = accountSetId(this.accountSetStore);
    if (!id) return;
    try {
      this.state.accounts = JSON.parse(localStorage.getItem(cashierStorageKey(id)) || "[]");
    } catch {
      this.state.accounts = [];
    }
  }

  saveAccounts() {
    const id = accountSetId(this.accountSetStore);
    localStorage.setItem(cashierStorageKey(id), JSON.stringify(this.state.accounts));
  }

  async registerAccount() {
    const id = accountSetId(this.accountSetStore);
    try {
      const acc = await this.api.registerAccount(id, {
        account_code: this.state.reg.code.trim(),
        cashier_type: this.state.reg.cashier_type,
        name: this.state.reg.name.trim(),
        currency: this.state.reg.currency.trim() || "CNY",
      });
      this.state.accounts.push(acc);
      this.saveAccounts();
      this.notificationStore.notify("Cashier account registered.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async loadFx(code) {
    const id = accountSetId(this.accountSetStore);
    this.state.fx = await this.api.fxBalance(id, code, this.state.periodCode);
  }

  async submitTxn() {
    const id = accountSetId(this.accountSetStore);
    const period = this.state.periodCode;
    try {
      if (this.state.txnType === "receipt") {
        await this.api.receipt(id, {
          account_code: this.state.txn.account_code,
          counterparty_account_code: this.state.txn.counterparty,
          amount: Number(this.state.txn.amount),
          period_code: period,
          description: this.state.txn.description,
        });
      } else if (this.state.txnType === "payment") {
        await this.api.payment(id, {
          account_code: this.state.txn.account_code,
          counterparty_account_code: this.state.txn.counterparty,
          amount: Number(this.state.txn.amount),
          period_code: period,
          description: this.state.txn.description,
        });
      } else {
        const amt = Number(this.state.txn.amount);
        await this.api.transfer(id, {
          from_account_code: this.state.txn.from,
          to_account_code: this.state.txn.to,
          income_amount: amt,
          expenditure_amount: amt,
          period_code: period,
          description: this.state.txn.description,
        });
      }
      this.notificationStore.notify("Transaction posted.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async reconcile() {
    const id = accountSetId(this.accountSetStore);
    try {
      this.state.reconcileResult = await this.api.reconcile(
        id,
        this.state.reconcileCode.trim(),
        this.state.periodCode,
        Number(this.state.physicalCount)
      );
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
