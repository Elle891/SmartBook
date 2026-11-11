import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPaymentTransactionTypeApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId } from "../utils/ledger_page";

const STAGES = [
  { key: "prepare_mode", label: "Prepare", editable: true },
  { key: "instruct_mode", label: "Instruct", editable: false, locked: "Manual" },
  { key: "check_mode", label: "Check", editable: true },
  { key: "authorise_mode", label: "Authorise", editable: false, locked: "Manual" },
  { key: "confirm_mode", label: "Confirm", editable: true },
  { key: "settle_mode", label: "Settle", editable: false, locked: "Manual" },
];

const LOCKED_TOOLTIP =
  "Instruct, Authorise, and Settle must always be Manual (regulatory constraint).";

function emptyForm() {
  return {
    id: null,
    name: "",
    prepare_mode: "Auto",
    instruct_mode: "Manual",
    check_mode: "Auto",
    authorise_mode: "Manual",
    confirm_mode: "Auto",
    settle_mode: "Manual",
  };
}

function snapshot(form) {
  return {
    name: form.name,
    prepare_mode: form.prepare_mode,
    check_mode: form.check_mode,
    confirm_mode: form.confirm_mode,
  };
}

function buildDiff(before, after) {
  const lines = [];
  if (before.name !== after.name) lines.push(`Name: ${before.name} → ${after.name}`);
  for (const { key, label } of STAGES.filter((s) => s.editable)) {
    if (before[key] !== after[key]) {
      lines.push(`${label}: ${before[key]} → ${after[key]}`);
    }
  }
  return lines;
}

export class PaymentTransactionTypePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Payment Transaction Types'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <t t-if="!isAdmin()">
          <p class="sb-field__error">Account Set Admin role required to configure payment transaction types.</p>
        </t>
        <t t-else="">
          <div class="sb-page__header">
            <h1>Payment Transaction Types</h1>
            <p class="sb-muted">Scoped to account set: <strong><t t-esc="accountSetName()"/></strong></p>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="newType">+ New Type</button>
          </div>

          <table class="sb-table">
            <thead>
              <tr><th>Name</th><th>Status</th><th>Default</th><th>Pipeline</th><th></th></tr>
            </thead>
            <tbody>
              <tr t-foreach="state.types" t-as="row" t-key="row.id">
                <td><t t-esc="row.name"/></td>
                <td><t t-esc="row.is_active ? 'Active' : 'Inactive'"/></td>
                <td><t t-if="isDefault(row.id)">★ Default</t><t t-else="">—</t></td>
                <td><t t-esc="pipelineSummary(row)"/></td>
                <td>
                  <button type="button" class="sb-link-btn" t-on-click="() => this.editType(row)" t-att-disabled="!row.is_active">Edit</button>
                  <button t-if="row.is_active and !isDefault(row.id)" type="button" class="sb-link-btn" t-on-click="() => this.deactivate(row.id)">Deactivate</button>
                </td>
              </tr>
            </tbody>
          </table>

          <div class="sb-panel">
            <h2><t t-if="state.form.id">Edit</t><t t-else="">Create</t> Transaction Type</h2>
            <form class="sb-form" t-on-submit.prevent="confirmSave">
              <label class="sb-field">
                <span class="sb-field__label">Name</span>
                <input class="sb-input" t-att-value="state.form.name" t-on-input="(ev) => state.form.name = ev.target.value" required="required"/>
              </label>

              <h3>Stage Configuration</h3>
              <p class="sb-muted" t-att-title="lockedTooltip"><t t-esc="lockedTooltip"/></p>

              <div class="sb-meta-grid">
                <div t-foreach="stages" t-as="s" t-key="s.key" class="sb-panel">
                  <strong><t t-esc="s.label"/></strong>
                  <t t-if="s.editable">
                    <select class="sb-input" t-att-value="formMode(s.key)" t-on-change="(ev) => this.setMode(s.key, ev.target.value)">
                      <option value="Auto">Auto</option>
                      <option value="Manual">Manual</option>
                    </select>
                  </t>
                  <t t-else="">
                    <span class="sb-tag" t-att-title="lockedTooltip">Manual (locked)</span>
                  </t>
                </div>
              </div>

              <h3>Pipeline Preview</h3>
              <p class="sb-muted"><t t-esc="pipelinePreviewText()"/></p>

              <label class="sb-field">
                <span class="sb-field__label">Default for new payments</span>
                <select class="sb-input" t-att-value="state.defaultTypeId" disabled="disabled">
                  <option t-foreach="activeTypes()" t-as="dt" t-key="dt.id" t-att-value="dt.id">
                    <t t-esc="dt.name"/>
                  </option>
                </select>
                <span class="sb-muted">System default is the active "Standard" type (read-only).</span>
              </label>

              <div class="sb-auth__actions">
                <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.saving">Save</button>
                <button t-if="state.form.id" type="button" class="sb-btn sb-btn--ghost" t-on-click="cancelEdit">Cancel</button>
              </div>
            </form>
          </div>

          <div t-if="state.showAuditConfirm" class="sb-modal-backdrop">
            <div class="sb-modal">
              <h3>Confirm Save — Audit Log</h3>
              <p>The following changes will be recorded in the audit log:</p>
              <ul>
                <li t-foreach="state.auditDiff" t-as="line" t-key="line"><t t-esc="line"/></li>
              </ul>
              <div class="sb-auth__actions">
                <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => state.showAuditConfirm = false">Cancel</button>
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="save">Confirm Save</button>
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
    this.authStore = useStore("authStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createPaymentTransactionTypeApi(this.rpc);
    this.stages = STAGES;
    this.lockedTooltip = LOCKED_TOOLTIP;
    this.state = useState({
      loading: false,
      saving: false,
      error: "",
      types: [],
      defaultTypeId: "",
      form: emptyForm(),
      beforeEdit: null,
      showAuditConfirm: false,
      auditDiff: [],
    });
    onWillStart(() => this.load());
  }

  isAdmin() {
    return this.authStore.state.role === "Account_Set_Admin";
  }

  accountSetName() {
    const id = accountSetId(this.accountSetStore);
    return this.accountSetStore.state.accountSets.find((a) => a.id === id)?.name || id || "—";
  }

  isDefault(typeId) {
    return typeId === this.state.defaultTypeId;
  }

  pipelineSummary(t) {
    return `P:${t.prepare_mode} I:M C:${t.check_mode} A:M Cf:${t.confirm_mode} S:M`;
  }

  pipelineStages() {
    return STAGES.map((s) => ({
      label: s.label,
      mode: s.editable ? this.state.form[s.key] : s.locked,
    }));
  }

  pipelinePreviewText() {
    return this.pipelineStages()
      .map((p) => `${p.label} (${p.mode})`)
      .join(" → ");
  }

  activeTypes() {
    return this.state.types.filter((t) => t.is_active);
  }

  formMode(key) {
    return this.state.form[key];
  }

  setMode(key, value) {
    this.state.form = { ...this.state.form, [key]: value };
  }

  newType() {
    this.state.form = emptyForm();
    this.state.beforeEdit = null;
  }

  editType(t) {
    this.state.form = {
      id: t.id,
      name: t.name,
      prepare_mode: t.prepare_mode,
      instruct_mode: "Manual",
      check_mode: t.check_mode,
      authorise_mode: "Manual",
      confirm_mode: t.confirm_mode,
      settle_mode: "Manual",
    };
    this.state.beforeEdit = snapshot(this.state.form);
  }

  cancelEdit() {
    this.state.form = emptyForm();
    this.state.beforeEdit = null;
  }

  async load() {
    if (!this.isAdmin()) return;
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const [types, defaultType] = await Promise.all([
        this.api.list(asId, true),
        this.api.defaultType(asId).catch(() => null),
      ]);
      this.state.types = types || [];
      this.state.defaultTypeId = defaultType?.id || "";
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  confirmSave() {
    const after = snapshot(this.state.form);
    if (this.state.beforeEdit) {
      this.state.auditDiff = buildDiff(this.state.beforeEdit, after);
      if (!this.state.auditDiff.length) {
        this.notificationStore.notify("No changes to save.", { type: "warning" });
        return;
      }
    } else {
      this.state.auditDiff = [
        `Create type "${this.state.form.name}" with Prepare=${after.prepare_mode}, Check=${after.check_mode}, Confirm=${after.confirm_mode}`,
      ];
    }
    this.state.showAuditConfirm = true;
  }

  async save() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.form.name.trim()) return;
    this.state.saving = true;
    this.state.showAuditConfirm = false;
    try {
      const body = {
        name: this.state.form.name.trim(),
        prepare_mode: this.state.form.prepare_mode,
        instruct_mode: "Manual",
        check_mode: this.state.form.check_mode,
        authorise_mode: "Manual",
        confirm_mode: this.state.form.confirm_mode,
        settle_mode: "Manual",
      };
      if (this.state.form.id) {
        await this.api.update(asId, this.state.form.id, {
          name: body.name,
          prepare_mode: body.prepare_mode,
          check_mode: body.check_mode,
          confirm_mode: body.confirm_mode,
        });
      } else {
        await this.api.create(asId, body);
      }
      this.notificationStore.notify("Transaction type saved.", { type: "success" });
      this.state.form = emptyForm();
      this.state.beforeEdit = null;
      await this.load();
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.saving = false;
    }
  }

  async deactivate(typeId) {
    if (!window.confirm("Deactivate this transaction type? Existing payments are unaffected.")) return;
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.deactivate(asId, typeId);
      this.notificationStore.notify("Transaction type deactivated.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }
}
