import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createChartApi } from "../services/chart_api";
import { createVoucherApi } from "../services/voucher_api";
import { useService, useStore } from "../services/registry";
import { flattenAccounts } from "../utils/account_tree";
import { formatApiError } from "../utils/errors";

export class VoucherCreatePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Create Voucher'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <h1>Create Voucher</h1>
        <form class="sb-form" t-on-submit.prevent="onSubmit">
          <div class="sb-field-row">
            <div class="sb-field">
              <label>Type</label>
              <select class="sb-input" t-on-change="(ev) => state.type = ev.target.value">
                <option value="Receipt">Receipt</option>
                <option value="Payment">Payment</option>
                <option value="Transfer">Transfer</option>
              </select>
            </div>
            <div class="sb-field">
              <label>Date</label>
              <input type="date" class="sb-input" t-att-value="state.date" t-on-input="(ev) => state.date = ev.target.value"/>
            </div>
            <div class="sb-field">
              <label>Period (YYYYMM)</label>
              <input class="sb-input" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
            </div>
          </div>

          <h2>Entries</h2>
          <table class="sb-table">
            <thead><tr><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th><th></th></tr></thead>
            <tbody>
              <tr t-foreach="state.entries" t-as="entry" t-key="entry_index">
                <td>
                  <select class="sb-input" t-on-change="(ev) => this.setEntryField(entry_index, 'account_code', ev.target.value)">
                    <option value="">—</option>
                    <option t-foreach="leafAccounts" t-as="acc" t-key="acc.code" t-att-value="acc.code">
                      <t t-esc="acc.code + ' ' + acc.name"/>
                    </option>
                  </select>
                </td>
                <td><input class="sb-input" t-att-value="entry.description" t-on-input="(ev) => this.setEntryField(entry_index, 'description', ev.target.value)"/></td>
                <td><input type="number" min="0" step="0.01" class="sb-input sb-input--num" t-att-value="entry.debit_amount" t-on-input="(ev) => this.setEntryField(entry_index, 'debit_amount', ev.target.value)"/></td>
                <td><input type="number" min="0" step="0.01" class="sb-input sb-input--num" t-att-value="entry.credit_amount" t-on-input="(ev) => this.setEntryField(entry_index, 'credit_amount', ev.target.value)"/></td>
                <td><button type="button" class="sb-link-btn" t-on-click="() => this.removeEntry(entry_index)">Remove</button></td>
              </tr>
            </tbody>
          </table>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="addEntry">+ Add line</button>
          <p t-if="!isBalanced" class="sb-field__error">Entries must balance (debits = credits).</p>

          <h2>Attachments</h2>
          <div class="sb-field">
            <input type="file" t-on-change="onFileSelected"/>
            <ul>
              <li t-foreach="state.attachments" t-as="att" t-key="att_index">
                <t t-esc="att.filename"/> <button type="button" class="sb-link-btn" t-on-click="() => this.removeAttachment(att_index)">Remove</button>
              </li>
            </ul>
          </div>

          <div class="sb-auth__actions">
            <a href="#/vouchers" class="sb-btn sb-btn--ghost">Cancel</a>
            <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.saving">Save Draft</button>
            <button type="button" class="sb-btn sb-btn--primary" t-att-disabled="state.saving or !isBalanced" t-on-click="onSubmitForReview">Save &amp; Submit</button>
          </div>
        </form>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.voucherApi = createVoucherApi(this.rpc);
    this.chartApi = createChartApi(this.rpc);
    this.state = useState({
      loading: false,
      saving: false,
      error: "",
      type: "Receipt",
      date: new Date().toISOString().slice(0, 10),
      periodCode: "",
      accounts: [],
      entries: [
        { account_code: "", description: "", debit_amount: 0, credit_amount: 0, aux_dimension_values: {}, sequence: 0 },
        { account_code: "", description: "", debit_amount: 0, credit_amount: 0, aux_dimension_values: {}, sequence: 1 },
      ],
      attachments: [],
    });
  }

  get leafAccounts() {
    return flattenAccounts(this.state.accounts).filter((a) => a.is_leaf);
  }

  get totalDebits() {
    return this.state.entries.reduce((s, e) => s + Number(e.debit_amount || 0), 0);
  }

  get totalCredits() {
    return this.state.entries.reduce((s, e) => s + Number(e.credit_amount || 0), 0);
  }

  get isBalanced() {
    return Math.abs(this.totalDebits - this.totalCredits) < 0.005 && this.totalDebits > 0;
  }

  async onWillStart() {
    const as = this.accountSetStore.currentAccountSet();
    if (as?.start_period) this.state.periodCode = as.start_period;
    const id = this.accountSetStore.state.currentId;
    if (!id) return;
    try {
      const tree = await this.chartApi.getTree(id);
      this.state.accounts = tree.accounts || [];
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  setEntryField(index, field, value) {
    const entry = this.state.entries[index];
    if (!entry) return;
    if (field === "debit_amount" || field === "credit_amount") {
      entry[field] = Math.max(0, Number(value) || 0);
    } else {
      entry[field] = value;
    }
  }

  addEntry() {
    this.state.entries.push({
      account_code: "",
      description: "",
      debit_amount: 0,
      credit_amount: 0,
      aux_dimension_values: {},
      sequence: this.state.entries.length,
    });
  }

  removeEntry(index) {
    if (this.state.entries.length <= 2) return;
    this.state.entries.splice(index, 1);
  }

  onFileSelected(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    this.state.attachments.push({
      file_key: `uploads/${Date.now()}-${file.name}`,
      filename: file.name,
    });
    ev.target.value = "";
  }

  removeAttachment(index) {
    this.state.attachments.splice(index, 1);
  }

  buildPayload() {
    return {
      period_code: this.state.periodCode.trim(),
      type: this.state.type,
      date: this.state.date,
      entries: this.state.entries.map((e, i) => ({
        account_code: e.account_code,
        debit_amount: Number(e.debit_amount) || 0,
        credit_amount: Number(e.credit_amount) || 0,
        description: e.description || "",
        aux_dimension_values: e.aux_dimension_values || {},
        sequence: i,
      })),
      attachments: this.state.attachments,
    };
  }

  async onSubmit() {
    await this.save(false);
  }

  async onSubmitForReview() {
    await this.save(true);
  }

  async save(submit) {
    if (!this.isBalanced) {
      this.state.error = "Voucher entries must balance.";
      return;
    }
    const id = this.accountSetStore.state.currentId;
    this.state.saving = true;
    this.state.error = "";
    try {
      const voucher = await this.voucherApi.create(id, this.buildPayload());
      if (submit) {
        await this.voucherApi.submit(id, voucher.id);
      }
      this.notificationStore.notify(submit ? "Voucher submitted for review." : "Voucher saved.", {
        type: "success",
      });
      window.location.hash = `#/vouchers/${voucher.id}`;
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.saving = false;
    }
  }
}
