import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createBankApi, createPaymentApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, formatMoney } from "../utils/ledger_page";

const ROUTING_SWIFT = "SWIFT";
const CURRENCIES = ["USD", "EUR", "GBP", "JPY", "HKD", "CNY", "AUD", "CAD", "SGD"];
const CHARGE_BEARERS = ["SLEV", "DEBT", "CRED", "SHAR"];
const PURPOSE_CODES = ["SALA", "TRAD", "INTC", "SUPP", "TAXS", "GDDS", "SCVE", "IVPT", "LOAN"];

const MAIN_FORM_FIELDS = new Set([
  "debtor_account",
  "creditor_name",
  "creditor_account",
  "creditor_agent_bic",
  "creditor_agent_name",
  "creditor_agent_address",
  "intermediary_agent_bic",
  "payment_currency",
  "instructed_amount",
  "value_date",
  "payment_purpose_code",
  "remittance_information",
  "charge_bearer",
]);

const FIELD_LABELS = {
  debtor_name: "Debtor Name",
  debtor_account: "Debtor Account",
  debtor_agent_bic: "Debtor Agent BIC",
  creditor_name: "Beneficiary Name",
  creditor_account: "Beneficiary Account (IBAN / Account No.)",
  creditor_agent_bic: "Beneficiary BIC",
  creditor_agent_name: "Beneficiary Bank Name",
  creditor_agent_address: "Beneficiary Bank Address",
  intermediary_agent_bic: "Correspondent BIC",
  payment_currency: "Payment Currency",
  instructed_amount: "Amount",
  exchange_rate: "Exchange Rate",
  value_date: "Value Date",
  end_to_end_id: "End-to-End ID",
  payment_purpose_code: "Payment Purpose Code",
  remittance_information: "Remittance Information",
  charge_bearer: "Charge Bearer",
  regulatory_reporting: "Regulatory Reporting",
};

function formatSettlementLabel(method) {
  const labels = {
    Standard_Settlement_T2: "Standard T+2",
    Express_Settlement_T1: "Express T+1",
    Same_Day_Value: "Same Day Value",
  };
  if (labels[method]) return labels[method];
  if (method === "Standard_Settlement_T+2") return "Standard T+2";
  if (method === "Express_Settlement_T+1") return "Express T+1";
  return method.replace(/_/g, " ");
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function isValidBic(bic) {
  const normalized = (bic || "").trim().toUpperCase();
  return /^[A-Z0-9]{8}([A-Z0-9]{3})?$/.test(normalized);
}

export class InternationalPaymentPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'International Payment'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>International Payment (SWIFT)</h1>
          <p class="sb-muted">Create a SWIFT payment in Prepare stage and add it to the scheduling queue.</p>
          <nav class="sb-muted">
            <a href="#/payments/domestic">Domestic</a> · <strong>International</strong>
          </nav>
        </div>

        <form class="sb-form sb-panel" t-on-submit.prevent="submit">
          <h2>Source Account</h2>
          <label class="sb-field">
            <span class="sb-field__label">Source Account (SWIFT configured)</span>
            <select class="sb-input" t-att-value="state.sourceId" t-on-change="onSourceChange" required="required">
              <option value="">— Select source —</option>
              <option t-foreach="state.sourceAccounts" t-as="s" t-key="s.connection_id" t-att-value="s.connection_id">
                <t t-esc="s.bank_code"/> — <t t-esc="s.account_number"/>
              </option>
            </select>
          </label>

          <p t-if="state.balance" class="sb-muted">
            Balance: <t t-esc="formatMoney(state.balance.current_balance)"/>
            <t t-esc="state.balance.currency"/>
            <t t-if="state.balance.stale"> (stale)</t>
          </p>
          <p t-if="state.exchangeRate and showExchangeRate()" class="sb-muted">
            Indicative rate <t t-esc="state.currency"/> → <t t-esc="state.balance.currency"/>:
            <t t-esc="state.exchangeRate.rate"/>
            · Estimated debit:
            <t t-esc="formatMoney(estimatedDebit())"/>
            <t t-esc="state.balance.currency"/>
          </p>
          <p t-if="balanceInsufficient()" class="sb-field__error">Insufficient balance for estimated debit amount.</p>

          <h2>Settlement</h2>
          <label class="sb-field">
            <span class="sb-field__label">Settlement Method</span>
            <select class="sb-input" t-att-value="state.settlementMethod" t-on-change="onSettlementChange" t-att-disabled="!settlementMethods().length">
              <option value="">— Select settlement —</option>
              <option t-foreach="settlementMethods()" t-as="sm" t-key="sm.settlement_method" t-att-value="sm.settlement_method">
                <t t-esc="settlementLabel(sm.settlement_method)"/>
                <t t-if="sm.is_default"> (default)</t>
              </option>
            </select>
          </label>

          <t t-if="selectedSettlement()">
            <p class="sb-muted">
              Estimated value date: <t t-esc="selectedSettlement().estimated_value_date"/>
              · Cut-off: <t t-esc="selectedSettlement().cutoff_time"/>
            </p>
            <p t-if="selectedSettlement().cutoff_passed" class="sb-field__error">
              SWIFT cut-off has passed. Next available date:
              <t t-esc="selectedSettlement().next_available_date"/>
            </p>
          </t>

          <h2>Beneficiary (SWIFT)</h2>
          <label class="sb-field">
            <span class="sb-field__label">Beneficiary Name *</span>
            <input class="sb-input" t-att-value="state.recipientName" t-on-input="(ev) => state.recipientName = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Beneficiary Account (IBAN / Account No.) *</span>
            <input class="sb-input" t-att-value="state.recipientAccount" t-on-input="(ev) => state.recipientAccount = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Beneficiary BIC (8 or 11 chars) *</span>
            <input class="sb-input" t-att-value="state.beneficiaryBic" t-on-input="onBicInput" required="required"/>
            <span t-if="state.beneficiaryBic and !bicValid(state.beneficiaryBic)" class="sb-field__error">Invalid BIC format.</span>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Beneficiary Bank Name *</span>
            <input class="sb-input" t-att-value="state.beneficiaryBankName" t-on-input="(ev) => state.beneficiaryBankName = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Beneficiary Bank Address *</span>
            <input class="sb-input" t-att-value="state.beneficiaryBankAddress" t-on-input="(ev) => state.beneficiaryBankAddress = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Correspondent BIC (optional)</span>
            <input class="sb-input" t-att-value="state.intermediaryBic" t-on-input="(ev) => state.intermediaryBic = ev.target.value"/>
            <span t-if="state.intermediaryBic and !bicValid(state.intermediaryBic)" class="sb-field__error">Invalid BIC format.</span>
          </label>

          <h2>Payment Details</h2>
          <label class="sb-field">
            <span class="sb-field__label">Payment Currency *</span>
            <select class="sb-input" t-att-value="state.currency" t-on-change="onCurrencyChange">
              <option t-foreach="currencies" t-as="c" t-key="c" t-att-value="c"><t t-esc="c"/></option>
            </select>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Amount *</span>
            <input class="sb-input" type="number" min="0.01" step="0.01" t-att-value="state.amount" t-on-input="(ev) => state.amount = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Value Date *</span>
            <input class="sb-input" type="date" t-att-value="state.scheduledDate" t-on-input="(ev) => state.scheduledDate = ev.target.value" required="required"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Payment Purpose Code *</span>
            <select class="sb-input" t-att-value="state.purposeCode" t-on-change="(ev) => state.purposeCode = ev.target.value">
              <option t-foreach="purposeCodes" t-as="p" t-key="p" t-att-value="p"><t t-esc="p"/></option>
            </select>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Charge Bearer</span>
            <select class="sb-input" t-att-value="state.chargeBearer" t-on-change="(ev) => state.chargeBearer = ev.target.value">
              <option t-foreach="chargeBearers" t-as="cb" t-key="cb" t-att-value="cb"><t t-esc="cb"/></option>
            </select>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Remittance Information</span>
            <input class="sb-input" t-att-value="state.remittanceInfo" t-on-input="(ev) => state.remittanceInfo = ev.target.value"/>
          </label>
          <label class="sb-field">
            <span class="sb-field__label">Internal Reference</span>
            <input class="sb-input" t-att-value="state.reference" t-on-input="(ev) => state.reference = ev.target.value"/>
          </label>

          <t t-if="dynamicFields().length">
            <h2>ISO 20022 Fields</h2>
            <label t-foreach="dynamicFields()" t-as="f" t-key="f.name" class="sb-field">
              <span class="sb-field__label">
                <t t-esc="fieldLabel(f.name)"/>
                <t t-if="f.required"> *</t>
              </span>
              <input class="sb-input"
                     t-att-readonly="f.name === 'exchange_rate'"
                     t-att-value="isoValue(f.name)"
                     t-on-input="(ev) => this.setIsoField(f.name, ev.target.value)"/>
            </label>
          </t>

          <div class="sb-auth__actions">
            <button type="submit" class="sb-btn sb-btn--primary" t-att-disabled="state.submitting or !canSubmit()">
              Create SWIFT Payment (Prepare)
            </button>
          </div>
        </form>

        <t t-if="state.lastResult">
          <div class="sb-panel sb-success-text">
            Payment created: <t t-esc="state.lastResult.payment_id"/> · Stage: <t t-esc="state.lastResult.stage"/>
            · E2E: <t t-esc="state.lastResult.end_to_end_id"/>
          </div>
        </t>

        <div class="sb-panel">
          <h2>Scheduling Queue</h2>
          <table class="sb-table">
            <thead><tr><th>ID</th><th>Recipient</th><th>Amount</th><th>Date</th><th>Stage</th></tr></thead>
            <tbody>
              <tr t-foreach="state.queue" t-as="q" t-key="q.payment_id">
                <td><t t-esc="q.payment_id"/></td>
                <td><t t-esc="q.recipient_name"/></td>
                <td><t t-esc="formatMoney(q.amount)"/> <t t-esc="q.currency"/></td>
                <td><t t-esc="q.scheduled_date or '—'"/></td>
                <td><t t-esc="q.stage"/></td>
              </tr>
            </tbody>
          </table>
          <p t-if="!state.queue.length" class="sb-muted">No payments in Prepare / Instructed queue.</p>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.bankApi = createBankApi(this.rpc);
    this.paymentApi = createPaymentApi(this.rpc);
    this.currencies = CURRENCIES;
    this.chargeBearers = CHARGE_BEARERS;
    this.purposeCodes = PURPOSE_CODES;
    this.state = useState({
      loading: false,
      submitting: false,
      error: "",
      connections: [],
      sourceAccounts: [],
      sourceId: "",
      settlementMethod: "",
      routingOptions: [],
      fieldConfig: null,
      balance: null,
      exchangeRate: null,
      isoExtra: {},
      recipientName: "",
      recipientAccount: "",
      beneficiaryBic: "",
      beneficiaryBankName: "",
      beneficiaryBankAddress: "",
      intermediaryBic: "",
      currency: "USD",
      amount: "",
      scheduledDate: todayIso(),
      purposeCode: "TRAD",
      chargeBearer: "SLEV",
      remittanceInfo: "",
      reference: "",
      transactionTypeId: null,
      queue: [],
      lastResult: null,
    });
    onWillStart(() => this.loadInitial());
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  bicValid(bic) {
    return isValidBic(bic);
  }

  settlementLabel(method) {
    return formatSettlementLabel(method);
  }

  settlementMethods() {
    const opt = this.state.routingOptions.find((o) => o.routing_method === ROUTING_SWIFT);
    return opt ? opt.settlement_methods || [] : [];
  }

  selectedSettlement() {
    return this.settlementMethods().find((sm) => sm.settlement_method === this.state.settlementMethod) || null;
  }

  showExchangeRate() {
    return this.state.balance && this.state.currency !== this.state.balance.currency;
  }

  estimatedDebit() {
    if (!this.state.amount) return 0;
    const amount = Number(this.state.amount);
    if (!this.showExchangeRate() || !this.state.exchangeRate) return amount;
    return amount * Number(this.state.exchangeRate.rate);
  }

  balanceInsufficient() {
    if (!this.state.balance || !this.state.amount) return false;
    return this.estimatedDebit() > Number(this.state.balance.current_balance);
  }

  canSubmit() {
    if (this.balanceInsufficient()) return false;
    if (!this.state.sourceId || !this.state.settlementMethod) return false;
    if (!isValidBic(this.state.beneficiaryBic)) return false;
    if (this.state.intermediaryBic && !isValidBic(this.state.intermediaryBic)) return false;
    return true;
  }

  dynamicFields() {
    const cfg = this.state.fieldConfig;
    if (!cfg || !cfg.config_map) return [];
    return (cfg.form_fields || [])
      .filter((name) => !MAIN_FORM_FIELDS.has(name))
      .map((name) => ({
        name,
        required: cfg.config_map[name] === "Required",
      }));
  }

  fieldLabel(name) {
    return FIELD_LABELS[name] || name;
  }

  isoValue(name) {
    if (name === "exchange_rate" && this.state.exchangeRate) {
      return String(this.state.exchangeRate.rate);
    }
    return this.state.isoExtra[name] || "";
  }

  setIsoField(name, value) {
    this.state.isoExtra = { ...this.state.isoExtra, [name]: value };
  }

  onBicInput(ev) {
    this.state.beneficiaryBic = ev.target.value.toUpperCase();
  }

  async loadInitial() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const [connections, queue, defaultType] = await Promise.all([
        this.bankApi.listConnections(asId),
        this.paymentApi.queue(asId),
        this.paymentApi.defaultTransactionType(asId).catch(() => null),
      ]);
      this.state.connections = connections || [];
      this.state.queue = queue || [];
      if (defaultType && defaultType.id) {
        this.state.transactionTypeId = defaultType.id;
      }
      await this.refreshSourceAccounts();
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async refreshSourceAccounts() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    const withSwift = [];
    for (const conn of this.state.connections) {
      try {
        const info = await this.bankApi.availableRouting(asId, conn.connection_id);
        if ((info.available_methods || []).includes(ROUTING_SWIFT)) {
          withSwift.push(conn);
        }
      } catch {
        /* skip */
      }
    }
    this.state.sourceAccounts = withSwift;
  }

  async onSourceChange(ev) {
    this.state.sourceId = ev.target.value;
    this.state.settlementMethod = "";
    this.state.routingOptions = [];
    this.state.fieldConfig = null;
    this.state.balance = null;
    this.state.exchangeRate = null;
    if (!this.state.sourceId) return;
    await Promise.all([this.refreshBalance(), this.refreshRoutingOptions(), this.refreshExchangeRate()]);
  }

  async onCurrencyChange(ev) {
    this.state.currency = ev.target.value;
    await Promise.all([this.refreshRoutingOptions(), this.refreshExchangeRate()]);
  }

  async onSettlementChange(ev) {
    this.state.settlementMethod = ev.target.value;
    await this.refreshFieldConfig();
  }

  async refreshBalance() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.sourceId) return;
    try {
      this.state.balance = await this.bankApi.balance(asId, this.state.sourceId);
      await this.refreshExchangeRate();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async refreshExchangeRate() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.balance || this.state.currency === this.state.balance.currency) {
      this.state.exchangeRate = null;
      return;
    }
    try {
      this.state.exchangeRate = await this.paymentApi.exchangeRate(
        asId,
        this.state.currency,
        this.state.balance.currency
      );
    } catch {
      this.state.exchangeRate = null;
    }
  }

  async refreshRoutingOptions() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.sourceId) return;
    try {
      const data = await this.paymentApi.routingOptions(asId, {
        source_connection_id: this.state.sourceId,
        payment_scope: "International",
        currency: this.state.currency,
      });
      this.state.routingOptions = data.options || [];
      const settlements = this.settlementMethods();
      if (!this.state.settlementMethod && settlements.length) {
        const def = settlements.find((s) => s.is_default) || settlements[0];
        this.state.settlementMethod = def.settlement_method;
        await this.refreshFieldConfig();
      }
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
      this.state.routingOptions = [];
    }
  }

  async refreshFieldConfig() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId || !this.state.settlementMethod) return;
    try {
      this.state.fieldConfig = await this.paymentApi.fieldConfig(
        asId,
        ROUTING_SWIFT,
        this.state.settlementMethod
      );
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async refreshQueue() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.queue = (await this.paymentApi.queue(asId)) || [];
  }

  async submit() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) {
      this.state.error = "Select an account set first.";
      return;
    }
    if (!this.canSubmit()) {
      this.state.error = "Please complete all required fields and fix validation errors.";
      return;
    }
    this.state.submitting = true;
    this.state.error = "";
    try {
      const body = {
        source_connection_id: this.state.sourceId,
        recipient_name: this.state.recipientName,
        recipient_account: this.state.recipientAccount,
        beneficiary_bic: this.state.beneficiaryBic.trim().toUpperCase(),
        beneficiary_bank_name: this.state.beneficiaryBankName,
        beneficiary_bank_address: this.state.beneficiaryBankAddress,
        amount: Number(this.state.amount),
        currency: this.state.currency,
        settlement_method: this.state.settlementMethod,
        scheduled_date: this.state.scheduledDate,
        payment_purpose_code: this.state.purposeCode,
        charge_bearer: this.state.chargeBearer,
        remittance_information: this.state.remittanceInfo || null,
        reference: this.state.reference || null,
      };
      if (this.state.intermediaryBic) {
        body.intermediary_bic = this.state.intermediaryBic.trim().toUpperCase();
      }
      if (this.state.isoExtra.end_to_end_id) {
        body.end_to_end_id = this.state.isoExtra.end_to_end_id;
      }
      if (this.state.transactionTypeId) {
        body.transaction_type_id = this.state.transactionTypeId;
      }
      const result = await this.paymentApi.createInternational(asId, body);
      this.state.lastResult = result;
      this.notificationStore.notify(`SWIFT payment ${result.payment_id} created in ${result.stage}.`, {
        type: "success",
      });
      await this.refreshQueue();
      this.state.amount = "";
      this.state.remittanceInfo = "";
      this.state.reference = "";
      this.state.isoExtra = {};
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.submitting = false;
    }
  }
}
