import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createVoucherApi } from "../services/voucher_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";

export class VoucherDetailPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Voucher Detail'" loading="state.loading" error="state.error">
      <section class="sb-page" t-if="state.voucher">
        <div class="sb-page__header">
          <h1>Voucher #<t t-esc="state.voucher.voucher_number"/></h1>
          <span t-att-class="'sb-status sb-status--' + state.voucher.status"><t t-esc="state.voucher.status"/></span>
        </div>
        <div class="sb-meta-grid">
          <div><strong>Type:</strong> <t t-esc="state.voucher.type"/></div>
          <div><strong>Date:</strong> <t t-esc="state.voucher.date"/></div>
          <div><strong>Period:</strong> <t t-esc="state.voucher.period_code"/></div>
        </div>

        <h2>Entries</h2>
        <table class="sb-table">
          <thead><tr><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead>
          <tbody>
            <tr t-foreach="state.voucher.entries" t-as="e" t-key="e.id or e.sequence">
              <td><t t-esc="e.account_code"/></td>
              <td><t t-esc="e.description"/></td>
              <td><t t-esc="formatMoney(e.debit_amount)"/></td>
              <td><t t-esc="formatMoney(e.credit_amount)"/></td>
            </tr>
          </tbody>
        </table>

        <h2 t-if="state.voucher.attachments.length">Attachments</h2>
        <ul t-if="state.voucher.attachments.length">
          <li t-foreach="state.voucher.attachments" t-as="att" t-key="att.id">
            <t t-esc="att.filename"/>
          </li>
        </ul>

        <h2>Workflow / Audit</h2>
        <ul class="sb-audit-list">
          <li>Created at <t t-esc="state.voucher.created_at"/></li>
          <li t-if="state.voucher.reviewed_at">Reviewed at <t t-esc="state.voucher.reviewed_at"/> by <t t-esc="state.voucher.reviewed_by or '—'"/></li>
          <li t-if="state.voucher.rejection_reason">Rejection reason: <t t-esc="state.voucher.rejection_reason"/></li>
        </ul>

        <div class="sb-auth__actions" t-if="canReview or canSubmit">
          <button t-if="canSubmit" type="button" class="sb-btn sb-btn--primary" t-on-click="onSubmit">Submit for Review</button>
          <button t-if="canReview" type="button" class="sb-btn sb-btn--primary" t-on-click="onApprove">Approve</button>
          <button t-if="canReview" type="button" class="sb-btn sb-btn--ghost" t-on-click="onReject">Reject</button>
        </div>
        <a href="#/vouchers" class="sb-link">← Back to list</a>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.voucherApi = createVoucherApi(this.rpc);
    this.state = useState({ loading: false, error: "", voucher: null });
  }

  get voucherId() {
    const path = this.env.router.state.path;
    const match = path.match(/^\/vouchers\/([^/]+)$/);
    return match ? match[1] : null;
  }

  get canSubmit() {
    const s = this.state.voucher?.status;
    return s === "Draft" || s === "Rejected";
  }

  get canReview() {
    return this.state.voucher?.status === "PendingReview";
  }

  formatMoney(v) {
    return Number(v || 0).toFixed(2);
  }

  async onWillStart() {
    await this.load();
  }

  async load() {
    const accountSetId = this.accountSetStore.state.currentId;
    if (!accountSetId || !this.voucherId) {
      this.state.error = "Missing account set or voucher.";
      return;
    }
    this.state.loading = true;
    try {
      this.state.voucher = await this.voucherApi.get(accountSetId, this.voucherId);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async onSubmit() {
    try {
      await this.voucherApi.submit(this.accountSetStore.state.currentId, this.voucherId);
      await this.load();
      this.notificationStore.notify("Submitted for review.", { type: "success" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }

  async onApprove() {
    try {
      await this.voucherApi.approve(this.accountSetStore.state.currentId, this.voucherId);
      await this.load();
      this.notificationStore.notify("Voucher approved.", { type: "success" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }

  async onReject() {
    const reason = window.prompt("Rejection reason:");
    if (!reason) return;
    try {
      await this.voucherApi.reject(this.accountSetStore.state.currentId, this.voucherId, reason);
      await this.load();
      this.notificationStore.notify("Voucher rejected.", { type: "warning" });
    } catch (err) {
      this.notificationStore.notify(formatApiError(err), { type: "error" });
    }
  }
}
