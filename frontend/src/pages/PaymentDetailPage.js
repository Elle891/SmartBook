import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPaymentApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, formatMoney } from "../utils/ledger_page";

const ROLE_INSTRUCT = new Set(["Account_Set_Admin", "Supervisor", "Voucher_Clerk", "Cashier"]);
const ROLE_REVIEWER = new Set(["Account_Set_Admin", "Supervisor"]);
const ROLE_AUTHORISER = new Set(["Account_Set_Admin", "Supervisor"]);

export class PaymentDetailPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Payment Detail'" loading="state.loading" error="state.error">
      <section class="sb-page" t-if="state.payment">
        <div class="sb-page__header">
          <h1>Payment <t t-esc="state.payment.payment_id"/></h1>
          <span t-att-class="stageClass(state.payment.stage)"><t t-esc="state.payment.stage"/></span>
        </div>
        <a href="#/payments/queue" class="sb-link">← Back to queue</a>

        <p t-if="state.payment.rejection_reason" class="sb-field__error">
          Rejection: <t t-esc="state.payment.rejection_reason"/>
        </p>

        <div class="sb-panel">
          <h2>Transaction Type</h2>
          <p><t t-esc="state.payment.transaction_type?.name or '—'"/></p>
          <div class="sb-meta-grid">
            <div t-foreach="state.payment.stage_pipeline" t-as="s" t-key="s.stage">
              <strong><t t-esc="s.stage"/></strong>
              <span t-att-class="s.mode === 'Auto' ? 'sb-muted' : ''">
                <t t-esc="s.mode"/>
              </span>
              <t t-if="s.stage === state.payment.stage"> ◀ current</t>
            </div>
          </div>
          <p t-if="state.payment.next_auto_stages?.length" class="sb-muted">
            Next stage(s) will auto-advance: <t t-esc="state.payment.next_auto_stages.join(', ')"/>
          </p>
        </div>

        <div t-if="state.payment.requires_dual_auth" class="sb-panel">
          <h2>Dual Authorisation</h2>
          <p>Threshold: <t t-esc="formatMoney(state.payment.dual_auth_threshold)"/></p>
          <p t-if="state.payment.first_authoriser_id">
            First authoriser: <t t-esc="state.payment.first_authoriser_id"/>
          </p>
          <p t-if="state.payment.awaiting_second_authoriser" class="sb-field__error">
            Awaiting second authoriser (must differ from first).
          </p>
        </div>

        <div class="sb-panel">
          <h2>Payment Fields</h2>
          <div class="sb-meta-grid">
            <div><strong>Scope:</strong> <t t-esc="state.payment.payment_scope"/></div>
            <div><strong>Amount:</strong> <t t-esc="formatMoney(state.payment.amount)"/> <t t-esc="state.payment.currency"/></div>
            <div><strong>Routing:</strong> <t t-esc="state.payment.routing_method"/></div>
            <div><strong>Settlement:</strong> <t t-esc="state.payment.settlement_method"/></div>
            <div><strong>Requested date:</strong> <t t-esc="state.payment.scheduled_date or '—'"/></div>
            <div><strong>Recipient:</strong> <t t-esc="state.payment.recipient_name"/></div>
            <div><strong>Account:</strong> <t t-esc="state.payment.recipient_account"/></div>
            <div t-if="state.payment.beneficiary_bic"><strong>BIC:</strong> <t t-esc="state.payment.beneficiary_bic"/></div>
            <div t-if="state.payment.beneficiary_bank_name"><strong>Bank:</strong> <t t-esc="state.payment.beneficiary_bank_name"/></div>
            <div t-if="state.payment.end_to_end_id"><strong>E2E ID:</strong> <t t-esc="state.payment.end_to_end_id"/></div>
            <div t-if="state.payment.uetr"><strong>UETR:</strong> <t t-esc="state.payment.uetr"/></div>
            <div t-if="state.payment.bank_reference"><strong>Bank ref:</strong> <t t-esc="state.payment.bank_reference"/></div>
          </div>
        </div>

        <div class="sb-panel">
          <h2>Stage History</h2>
          <ul class="sb-audit-list">
            <li t-foreach="state.payment.history" t-as="h" t-key="h.transitioned_at + h.to_stage">
              <t t-esc="h.transitioned_at"/> ·
              <t t-esc="h.from_stage"/> → <t t-esc="h.to_stage"/> ·
              <t t-esc="h.triggered_by"/>
              <t t-if="h.reason"> · <t t-esc="h.reason"/></t>
            </li>
          </ul>
        </div>

        <div class="sb-auth__actions">
          <button t-if="canInstruct()" type="button" class="sb-btn sb-btn--primary" t-on-click="instruct">Instruct</button>
          <t t-if="canCheck()">
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="() => this.check(true)">Approve Check</button>
            <input class="sb-input" placeholder="Rejection reason" t-att-value="state.rejectReason" t-on-input="(ev) => state.rejectReason = ev.target.value"/>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => this.check(false)">Reject Check</button>
          </t>
          <button t-if="canAuthorise()" type="button" class="sb-btn sb-btn--primary" t-on-click="authorise">Authorise</button>
          <button t-if="canPayNow()" type="button" class="sb-btn sb-btn--primary" t-on-click="payNow">Pay Now</button>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.authStore = useStore("authStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createPaymentApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      payment: null,
      rejectReason: "",
    });
    onWillStart(() => this.load());
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  stageClass(stage) {
    return `sb-status sb-status--${(stage || "").toLowerCase()}`;
  }

  paymentId() {
    const hash = window.location.hash.replace(/^#/, "");
    const m = hash.match(/^\/payments\/([^/]+)$/);
    return m ? m[1] : null;
  }

  role() {
    return this.authStore.state.role || "";
  }

  canInstruct() {
    const p = this.state.payment;
    return p && p.stage === "Prepare" && ROLE_INSTRUCT.has(this.role());
  }

  canCheck() {
    const p = this.state.payment;
    return (
      p &&
      p.stage === "Instructed" &&
      p.transaction_type?.check_mode === "Manual" &&
      ROLE_REVIEWER.has(this.role())
    );
  }

  canAuthorise() {
    const p = this.state.payment;
    return (
      p &&
      (p.stage === "Checked" || p.stage === "PendingSecondAuth") &&
      ROLE_AUTHORISER.has(this.role())
    );
  }

  canPayNow() {
    const p = this.state.payment;
    return p && p.stage === "Authorised" && ROLE_AUTHORISER.has(this.role());
  }

  async load() {
    const asId = accountSetId(this.accountSetStore);
    const pid = this.paymentId();
    if (!asId || !pid) {
      this.state.error = "Invalid payment.";
      return;
    }
    this.state.loading = true;
    this.state.error = "";
    try {
      this.state.payment = await this.api.status(asId, pid);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async instruct() {
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.instruct(asId, this.state.payment.payment_id);
      this.notificationStore.notify("Payment instructed.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async check(approved) {
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.check(asId, this.state.payment.payment_id, {
        approved,
        rejection_reason: approved ? null : this.state.rejectReason || "Rejected",
      });
      this.notificationStore.notify(approved ? "Check approved." : "Check rejected.", {
        type: approved ? "success" : "warning",
      });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async authorise() {
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.authorise(asId, this.state.payment.payment_id);
      this.notificationStore.notify("Payment authorised.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async payNow() {
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.payNow(asId, this.state.payment.payment_id);
      this.notificationStore.notify("Pay Now submitted.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }
}
