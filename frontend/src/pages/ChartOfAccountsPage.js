import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AccountTree } from "../components/AccountTree";
import { AppShell } from "../components/AppShell";
import { createChartApi } from "../services/chart_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";

const ACCOUNT_TYPES = ["Asset", "Liability", "Equity", "Revenue", "Expense"];
const AUX_DIMS = ["department", "project", "customer", "supplier", "employee"];

export class ChartOfAccountsPage extends Component {
  static components = { AppShell, AccountTree };
  static template = xml`
    <AppShell title="'Chart of Accounts'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>Chart of Accounts</h1>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="openCreate">+ Add Account</button>
        </div>
        <AccountTree nodes="treeWithDepth" onEdit.bind="openEdit" onDelete.bind="onDelete"/>

        <div t-if="state.showForm" class="sb-modal-backdrop">
          <div class="sb-modal">
            <h3><t t-if="state.editing">Edit Account</t><t t-else="">Create Account</t></h3>
            <div class="sb-field"><label>Code</label><input class="sb-input" t-att-readonly="state.editing" t-att-value="state.form.code" t-on-input="(ev) => state.form.code = ev.target.value"/></div>
            <div class="sb-field"><label>Name</label><input class="sb-input" t-att-value="state.form.name" t-on-input="(ev) => state.form.name = ev.target.value"/></div>
            <div class="sb-field">
              <label>Type</label>
              <select class="sb-input" t-on-change="(ev) => state.form.account_type = ev.target.value">
                <option t-foreach="accountTypes" t-as="t" t-key="t" t-att-value="t"><t t-esc="t"/></option>
              </select>
            </div>
            <div class="sb-field"><label>Parent Code</label><input class="sb-input" placeholder="Optional" t-att-value="state.form.parent_code" t-on-input="(ev) => state.form.parent_code = ev.target.value"/></div>
            <div t-if="state.editing" class="sb-field">
              <label>Auxiliary Dimensions</label>
              <div class="sb-perm-grid">
                <label t-foreach="auxDims" t-as="dim" t-key="dim" class="sb-check">
                  <input type="checkbox" t-att-checked="state.form.aux_dimensions.includes(dim)" t-on-change="() => this.toggleDim(dim)"/>
                  <t t-esc="dim"/>
                </label>
              </div>
            </div>
            <div class="sb-auth__actions">
              <button type="button" class="sb-btn sb-btn--ghost" t-on-click="closeForm">Cancel</button>
              <button type="button" class="sb-btn sb-btn--primary" t-on-click="saveForm">Save</button>
            </div>
          </div>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.chartApi = createChartApi(this.rpc);
    this.accountTypes = ACCOUNT_TYPES;
    this.auxDims = AUX_DIMS;
    this.state = useState({
      loading: false,
      error: "",
      accounts: [],
      showForm: false,
      editing: false,
      form: { code: "", name: "", account_type: "Asset", parent_code: "", aux_dimensions: [] },
    });
  }

  get accountSetId() {
    return this.accountSetStore.state.currentId;
  }

  get treeWithDepth() {
    return (this.state.accounts || []).map((n) => ({ ...n, depth: 0 }));
  }

  async onWillStart() {
    await this.load();
  }

  async load() {
    if (!this.accountSetId) {
      this.state.error = "Select an account set first.";
      return;
    }
    this.state.loading = true;
    try {
      const data = await this.chartApi.getTree(this.accountSetId);
      this.state.accounts = data.accounts || [];
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  openCreate() {
    this.state.editing = false;
    this.state.form = { code: "", name: "", account_type: "Asset", parent_code: "", aux_dimensions: [] };
    this.state.showForm = true;
  }

  openEdit(node) {
    this.state.editing = true;
    this.state.form = {
      code: node.code,
      name: node.name,
      account_type: node.account_type,
      parent_code: node.parent_code || "",
      aux_dimensions: [...(node.aux_dimensions || [])],
    };
    this.state.showForm = true;
  }

  closeForm() {
    this.state.showForm = false;
  }

  toggleDim(dim) {
    const idx = this.state.form.aux_dimensions.indexOf(dim);
    if (idx >= 0) this.state.form.aux_dimensions.splice(idx, 1);
    else this.state.form.aux_dimensions.push(dim);
  }

  async saveForm() {
    try {
      if (this.state.editing) {
        await this.chartApi.updateAuxDimensions(
          this.accountSetId,
          this.state.form.code,
          this.state.form.aux_dimensions
        );
      } else {
        await this.chartApi.createAccount(this.accountSetId, {
          code: this.state.form.code.trim(),
          name: this.state.form.name.trim(),
          account_type: this.state.form.account_type,
          parent_code: this.state.form.parent_code.trim() || null,
        });
      }
      this.state.showForm = false;
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }

  async onDelete(node) {
    if (!window.confirm(`Delete account ${node.code}?`)) return;
    try {
      await this.chartApi.deleteAccount(this.accountSetId, node.code);
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }
}
