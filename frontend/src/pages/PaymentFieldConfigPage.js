import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPaymentApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId } from "../utils/ledger_page";

const MANDATORY_FIELDS = new Set([
  "debtor_account",
  "creditor_name",
  "creditor_account",
  "payment_currency",
  "instructed_amount",
  "value_date",
]);

const ALL_ISO_FIELDS = [
  "debtor_name",
  "debtor_account",
  "debtor_agent_bic",
  "creditor_name",
  "creditor_account",
  "creditor_agent_bic",
  "creditor_agent_name",
  "creditor_agent_address",
  "intermediary_agent_bic",
  "payment_currency",
  "instructed_amount",
  "exchange_rate",
  "value_date",
  "end_to_end_id",
  "payment_purpose_code",
  "remittance_information",
  "charge_bearer",
  "regulatory_reporting",
];

const FIELD_LABELS = {
  debtor_name: "Debtor Name",
  debtor_account: "Debtor Account",
  debtor_agent_bic: "Debtor Agent BIC",
  creditor_name: "Creditor Name",
  creditor_account: "Creditor Account",
  creditor_agent_bic: "Creditor Agent BIC",
  creditor_agent_name: "Creditor Bank Name",
  creditor_agent_address: "Creditor Bank Address",
  intermediary_agent_bic: "Intermediary BIC",
  payment_currency: "Payment Currency",
  instructed_amount: "Instructed Amount",
  exchange_rate: "Exchange Rate",
  value_date: "Value Date",
  end_to_end_id: "End-to-End ID",
  payment_purpose_code: "Payment Purpose Code",
  remittance_information: "Remittance Information",
  charge_bearer: "Charge Bearer",
  regulatory_reporting: "Regulatory Reporting",
};

const ROUTING_SETTLEMENTS = {
  Direct_Debit: ["Same_Day_Settlement", "Next_Day_Settlement"],
  Online_Banking_Transfer: ["Real_Time_Gross_Settlement", "Batch_Settlement_T+1"],
  CNAPS: ["Real_Time_Settlement", "Scheduled_Settlement"],
  CIPS: ["Real_Time_Settlement", "End_Of_Day_Settlement"],
  Local_ACH: ["Next_Day_Settlement", "Two_Day_Settlement"],
  Internal_Transfer: ["Immediate_Settlement"],
  SWIFT: ["Standard_Settlement_T+2", "Express_Settlement_T+1", "Same_Day_Value"],
};

const ROUTING_METHODS = Object.keys(ROUTING_SETTLEMENTS);

function orderStorageKey(asId, routing, settlement) {
  return `smartbook.fieldOrder.${asId}.${routing}.${settlement}`;
}

function loadStoredOrder(asId, routing, settlement) {
  try {
    const raw = localStorage.getItem(orderStorageKey(asId, routing, settlement));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveStoredOrder(asId, routing, settlement, order) {
  localStorage.setItem(orderStorageKey(asId, routing, settlement), JSON.stringify(order));
}

function applyOrder(fields, order) {
  if (!order || !order.length) return fields;
  const map = Object.fromEntries(fields.map((f) => [f.field_name, f]));
  const ordered = order.filter((name) => map[name]).map((name) => map[name]);
  const rest = fields.filter((f) => !order.includes(f.field_name));
  return [...ordered, ...rest];
}

function buildDiff(before, after) {
  const lines = [];
  const beforeMap = Object.fromEntries(before.map((f) => [f.field_name, f.visibility]));
  for (const f of after) {
    const prev = beforeMap[f.field_name];
    if (prev && prev !== f.visibility) {
      lines.push(`${fieldLabel(f.field_name)}: ${prev} → ${f.visibility}`);
    }
  }
  const beforeOrder = before.map((f) => f.field_name).join(", ");
  const afterOrder = after.map((f) => f.field_name).join(", ");
  if (beforeOrder !== afterOrder) {
    lines.push("Display order changed");
  }
  return lines;
}

function fieldLabel(name) {
  return FIELD_LABELS[name] || name;
}

export class PaymentFieldConfigPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Payment Field Config'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <t t-if="!isAdmin()">
          <p class="sb-field__error">Account Set Admin role required to configure payment fields.</p>
        </t>
        <t t-else="">
          <div class="sb-page__header">
            <h1>ISO 20022 Field Configuration</h1>
            <p class="sb-muted">Scoped to account set: <strong><t t-esc="accountSetName()"/></strong></p>
          </div>

          <div class="sb-filters">
            <select class="sb-input" t-att-value="state.routingMethod" t-on-change="onRoutingChange">
              <option value="">— Routing method —</option>
              <option t-foreach="routingMethods" t-as="r" t-key="r" t-att-value="r"><t t-esc="r"/></option>
            </select>
            <select class="sb-input" t-att-value="state.settlementMethod" t-on-change="onSettlementChange" t-att-disabled="!state.routingMethod">
              <option value="">— Settlement method —</option>
              <option t-foreach="settlementOptions()" t-as="sm" t-key="sm" t-att-value="sm"><t t-esc="sm"/></option>
            </select>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="loadConfig" t-att-disabled="!canLoad()">Load</button>
          </div>

          <t t-if="state.fields.length">
            <p class="sb-muted">Drag rows to reorder display. Six mandatory fields are locked to Required.</p>
            <table class="sb-table">
              <thead><tr><th></th><th>Order</th><th>Field</th><th>Required</th><th>Optional</th><th>Hidden</th></tr></thead>
              <tbody>
                <tr t-foreach="state.fields" t-as="f" t-key="f.field_name"
                    draggable="true"
                    t-on-dragstart="(ev) => this.onDragStart(f.field_name, ev)"
                    t-on-dragover.prevent=""
                    t-on-drop="(ev) => this.onDrop(f.field_name, ev)">
                  <td class="sb-muted">⋮⋮</td>
                  <td>
                    <button type="button" class="sb-link-btn" t-on-click="() => this.moveField(f.field_name, -1)">↑</button>
                    <button type="button" class="sb-link-btn" t-on-click="() => this.moveField(f.field_name, 1)">↓</button>
                  </td>
                  <td>
                    <t t-esc="fieldLabel(f.field_name)"/>
                    <span t-if="isMandatory(f.field_name)" class="sb-tag">Mandatory</span>
                  </td>
                  <td>
                    <input type="radio" t-att-name="visName(f.field_name)" t-att-checked="f.visibility === 'Required'"
                           t-att-disabled="isMandatory(f.field_name)"
                           t-on-change="() => this.setVisibility(f.field_name, 'Required')"/>
                  </td>
                  <td>
                    <input type="radio" t-att-name="visName(f.field_name)" t-att-checked="f.visibility === 'Optional'"
                           t-att-disabled="isMandatory(f.field_name)"
                           t-on-change="() => this.setVisibility(f.field_name, 'Optional')"/>
                  </td>
                  <td>
                    <input type="radio" t-att-name="visName(f.field_name)" t-att-checked="f.visibility === 'Hidden'"
                           t-att-disabled="isMandatory(f.field_name)"
                           t-on-change="() => this.setVisibility(f.field_name, 'Hidden')"/>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="sb-auth__actions">
              <button type="button" class="sb-btn sb-btn--primary" t-on-click="confirmSave" t-att-disabled="state.saving">Save</button>
            </div>
          </t>

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
    this.api = createPaymentApi(this.rpc);
    this.routingMethods = ROUTING_METHODS;
    this.state = useState({
      loading: false,
      saving: false,
      error: "",
      routingMethod: "",
      settlementMethod: "",
      fields: [],
      beforeSave: [],
      dragField: null,
      showAuditConfirm: false,
      auditDiff: [],
    });
    onWillStart(() => {});
  }

  isAdmin() {
    return this.authStore.state.role === "Account_Set_Admin";
  }

  accountSetName() {
    const id = accountSetId(this.accountSetStore);
    return this.accountSetStore.state.accountSets.find((a) => a.id === id)?.name || id || "—";
  }

  fieldLabel(name) {
    return fieldLabel(name);
  }

  visName(fieldName) {
    return `vis_${fieldName}`;
  }

  isMandatory(name) {
    return MANDATORY_FIELDS.has(name);
  }

  settlementOptions() {
    return ROUTING_SETTLEMENTS[this.state.routingMethod] || [];
  }

  canLoad() {
    return this.state.routingMethod && this.state.settlementMethod;
  }

  onRoutingChange(ev) {
    this.state.routingMethod = ev.target.value;
    this.state.settlementMethod = "";
    this.state.fields = [];
  }

  onSettlementChange(ev) {
    this.state.settlementMethod = ev.target.value;
    this.state.fields = [];
  }

  async loadConfig() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.canLoad()) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const data = await this.api.fieldConfig(
        asId,
        this.state.routingMethod,
        this.state.settlementMethod
      );
      const configMap = data.config_map || {};
      let fields = ALL_ISO_FIELDS.map((name) => ({
        field_name: name,
        visibility: configMap[name] || "Optional",
      }));
      for (const name of MANDATORY_FIELDS) {
        const row = fields.find((f) => f.field_name === name);
        if (row) row.visibility = "Required";
      }
      const storedOrder = loadStoredOrder(asId, this.state.routingMethod, this.state.settlementMethod);
      fields = applyOrder(fields, storedOrder);
      this.state.fields = fields;
      this.state.beforeSave = fields.map((f) => ({ ...f }));
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  setVisibility(fieldName, visibility) {
    if (MANDATORY_FIELDS.has(fieldName) && visibility !== "Required") return;
    this.state.fields = this.state.fields.map((f) =>
      f.field_name === fieldName ? { ...f, visibility } : f
    );
  }

  moveField(fieldName, delta) {
    const idx = this.state.fields.findIndex((f) => f.field_name === fieldName);
    if (idx < 0) return;
    const next = idx + delta;
    if (next < 0 || next >= this.state.fields.length) return;
    const copy = [...this.state.fields];
    const [item] = copy.splice(idx, 1);
    copy.splice(next, 0, item);
    this.state.fields = copy;
  }

  onDragStart(fieldName, ev) {
    this.state.dragField = fieldName;
    if (ev.dataTransfer) ev.dataTransfer.effectAllowed = "move";
  }

  onDrop(targetField, ev) {
    ev.preventDefault();
    const from = this.state.dragField;
    if (!from || from === targetField) return;
    const copy = [...this.state.fields];
    const fromIdx = copy.findIndex((f) => f.field_name === from);
    const toIdx = copy.findIndex((f) => f.field_name === targetField);
    if (fromIdx < 0 || toIdx < 0) return;
    const [item] = copy.splice(fromIdx, 1);
    copy.splice(toIdx, 0, item);
    this.state.fields = copy;
    this.state.dragField = null;
  }

  confirmSave() {
    this.state.auditDiff = buildDiff(this.state.beforeSave, this.state.fields);
    if (!this.state.auditDiff.length) {
      this.notificationStore.notify("No changes to save.", { type: "warning" });
      return;
    }
    this.state.showAuditConfirm = true;
  }

  async save() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.canLoad()) return;
    this.state.saving = true;
    this.state.showAuditConfirm = false;
    try {
      await this.api.saveFieldConfig(asId, {
        routing_method: this.state.routingMethod,
        settlement_method: this.state.settlementMethod,
        field_configs: this.state.fields.map((f) => ({
          field_name: f.field_name,
          visibility: f.visibility,
        })),
      });
      saveStoredOrder(
        asId,
        this.state.routingMethod,
        this.state.settlementMethod,
        this.state.fields.map((f) => f.field_name)
      );
      this.notificationStore.notify("Field configuration saved.", { type: "success" });
      this.state.beforeSave = this.state.fields.map((f) => ({ ...f }));
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.saving = false;
    }
  }
}
