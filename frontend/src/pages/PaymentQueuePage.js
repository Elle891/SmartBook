import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPaymentApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, formatMoney } from "../utils/ledger_page";

export class PaymentQueuePage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Payment Queue'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>Payment Scheduling Queue</h1>
          <p class="sb-muted">Prepare and Instructed payments ordered by requested settlement date.</p>
        </div>

        <div class="sb-filters">
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="batchInstruct" t-att-disabled="!selectedPrepareIds().length">
            Instruct Selected (<t t-esc="selectedPrepareIds().length"/>)
          </button>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="load">Refresh</button>
        </div>

        <table class="sb-table">
          <thead>
            <tr>
              <th></th>
              <th>Scope</th>
              <th>Recipient</th>
              <th>Amount</th>
              <th>Routing</th>
              <th>Settlement</th>
              <th>Stage</th>
              <th>Type</th>
              <th>Requested</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr t-foreach="state.queue" t-as="p" t-key="p.payment_id">
              <td>
                <input type="checkbox"
                       t-att-checked="isSelected(p.payment_id)"
                       t-on-change="(ev) => this.toggleSelect(p.payment_id, ev.target.checked)"/>
              </td>
              <td><t t-esc="p.payment_scope"/></td>
              <td><t t-esc="p.recipient_name"/></td>
              <td><t t-esc="formatMoney(p.amount)"/> <t t-esc="p.currency"/></td>
              <td><t t-esc="p.routing_method"/></td>
              <td>
                <t t-esc="p.settlement_method"/>
                <span t-if="p.cutoff_at_risk" class="sb-field__error" title="Cut-off at risk"> ⚠</span>
              </td>
              <td><span t-att-class="stageClass(p.stage)"><t t-esc="p.stage"/></span></td>
              <td><t t-esc="p.transaction_type_name or '—'"/></td>
              <td><t t-esc="p.scheduled_date or '—'"/></td>
              <td>
                <button t-if="p.stage === 'Prepare'" type="button" class="sb-link-btn" t-on-click="() => this.instructOne(p.payment_id)">Instruct</button>
                <a t-att-href="detailHref(p.payment_id)" class="sb-link-btn">View</a>
                <button type="button" class="sb-link-btn" t-on-click="() => this.removeOne(p.payment_id)">Remove</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p t-if="!state.queue.length" class="sb-muted">No payments in Prepare or Instructed queue.</p>

        <div class="sb-panel">
          <h2>Authorised — Batch Pay</h2>
          <div class="sb-filters">
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="batchPay" t-att-disabled="!state.selectedAuthorised.length">
              Pay Selected (<t t-esc="state.selectedAuthorised.length"/>)
            </button>
          </div>
          <table class="sb-table">
            <thead>
              <tr>
                <th></th>
                <th>Recipient</th>
                <th>Amount</th>
                <th>Settlement</th>
                <th>Requested</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr t-foreach="state.authorised" t-as="a" t-key="a.payment_id">
                <td>
                  <input type="checkbox"
                         t-att-checked="isAuthorisedSelected(a.payment_id)"
                         t-on-change="(ev) => this.toggleAuthorised(a.payment_id, ev.target.checked)"/>
                </td>
                <td><t t-esc="a.recipient_name"/></td>
                <td><t t-esc="formatMoney(a.amount)"/> <t t-esc="a.currency"/></td>
                <td>
                  <t t-esc="a.settlement_method"/>
                  <span t-if="a.cutoff_at_risk" class="sb-field__error"> ⚠</span>
                </td>
                <td><t t-esc="a.scheduled_date or '—'"/></td>
                <td><a t-att-href="detailHref(a.payment_id)" class="sb-link-btn">View</a></td>
              </tr>
            </tbody>
          </table>
          <p t-if="!state.authorised.length" class="sb-muted">No Authorised payments awaiting Pay Now.</p>
        </div>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createPaymentApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      queue: [],
      authorised: [],
      selected: {},
      selectedAuthorised: [],
    });
    onWillStart(() => this.load());
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  detailHref(id) {
    return `#/payments/${id}`;
  }

  stageClass(stage) {
    return `sb-status sb-status--${(stage || "").toLowerCase()}`;
  }

  isSelected(id) {
    return Boolean(this.state.selected[id]);
  }

  isAuthorisedSelected(id) {
    return this.state.selectedAuthorised.includes(id);
  }

  toggleSelect(id, checked) {
    this.state.selected = { ...this.state.selected, [id]: checked };
  }

  toggleAuthorised(id, checked) {
    if (checked) {
      if (!this.state.selectedAuthorised.includes(id)) {
        this.state.selectedAuthorised = [...this.state.selectedAuthorised, id];
      }
    } else {
      this.state.selectedAuthorised = this.state.selectedAuthorised.filter((x) => x !== id);
    }
  }

  selectedPrepareIds() {
    return Object.entries(this.state.selected)
      .filter(([id, on]) => on && this.state.queue.some((p) => p.payment_id === id && p.stage === "Prepare"))
      .map(([id]) => id);
  }

  async load() {
    const asId = accountSetId(this.accountSetStore);
    if (!asId) return;
    this.state.loading = true;
    this.state.error = "";
    try {
      const [queue, authorised] = await Promise.all([
        this.api.queue(asId),
        this.api.authorised(asId),
      ]);
      this.state.queue = queue || [];
      this.state.authorised = authorised || [];
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async instructOne(paymentId) {
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.instruct(asId, paymentId);
      this.notificationStore.notify("Payment instructed.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async removeOne(paymentId) {
    if (!window.confirm("Remove this payment from the queue?")) return;
    const asId = accountSetId(this.accountSetStore);
    try {
      await this.api.removeFromQueue(asId, paymentId);
      this.notificationStore.notify("Payment removed from queue.", { type: "success" });
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async batchInstruct() {
    const ids = this.selectedPrepareIds();
    if (!ids.length) return;
    const asId = accountSetId(this.accountSetStore);
    try {
      const res = await this.api.batchInstruct(asId, ids);
      const errors = (res.results || []).filter((r) => r.error);
      if (errors.length) {
        this.notificationStore.notify(`${errors.length} payment(s) failed to instruct.`, { type: "warning" });
      } else {
        this.notificationStore.notify("Batch instruct completed.", { type: "success" });
      }
      this.state.selected = {};
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }

  async batchPay() {
    if (!this.state.selectedAuthorised.length) return;
    const asId = accountSetId(this.accountSetStore);
    try {
      const res = await this.api.batchPay(asId, this.state.selectedAuthorised);
      const errors = (res.results || []).filter((r) => r.error);
      if (errors.length) {
        this.notificationStore.notify(`${errors.length} payment(s) failed to pay.`, { type: "warning" });
      } else {
        this.notificationStore.notify("Batch pay completed.", { type: "success" });
      }
      this.state.selectedAuthorised = [];
      await this.load();
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "warning" });
    }
  }
}
