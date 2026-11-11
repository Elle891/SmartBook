import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createVoucherApi } from "../services/voucher_api";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";

export class VoucherListPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Vouchers'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-page__header">
          <h1>Vouchers</h1>
          <a href="#/vouchers/create" class="sb-btn sb-btn--primary">Create Voucher</a>
        </div>
        <div class="sb-filters">
          <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
          <select class="sb-input" t-on-change="(ev) => state.statusFilter = ev.target.value">
            <option value="">All statuses</option>
            <option value="Draft">Draft</option>
            <option value="PendingReview">Pending Review</option>
            <option value="Approved">Approved</option>
            <option value="Rejected">Rejected</option>
          </select>
          <select class="sb-input" t-on-change="(ev) => state.typeFilter = ev.target.value">
            <option value="">All types</option>
            <option value="Receipt">Receipt</option>
            <option value="Payment">Payment</option>
            <option value="Transfer">Transfer</option>
          </select>
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="load">Apply</button>
        </div>
        <table class="sb-table">
          <thead>
            <tr><th>#</th><th>Date</th><th>Type</th><th>Period</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            <tr t-foreach="filteredVouchers" t-as="v" t-key="v.id">
              <td><t t-esc="v.voucher_number"/></td>
              <td><t t-esc="v.date"/></td>
              <td><t t-esc="v.type"/></td>
              <td><t t-esc="v.period_code"/></td>
              <td><span t-att-class="'sb-status sb-status--' + v.status"><t t-esc="v.status"/></span></td>
              <td><a t-att-href="'#/vouchers/' + v.id" class="sb-link">Open</a></td>
            </tr>
            <tr t-if="!filteredVouchers.length"><td colspan="6" class="sb-table__empty">No vouchers</td></tr>
          </tbody>
        </table>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.voucherApi = createVoucherApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      vouchers: [],
      periodCode: "",
      statusFilter: "",
      typeFilter: "",
    });
  }

  get filteredVouchers() {
    let list = this.state.vouchers;
    if (this.state.typeFilter) {
      list = list.filter((v) => v.type === this.state.typeFilter);
    }
    return list;
  }

  async onWillStart() {
    await this.load();
  }

  async load() {
    const id = this.accountSetStore.state.currentId;
    if (!id) {
      this.state.error = "Select an account set first.";
      return;
    }
    this.state.loading = true;
    try {
      this.state.vouchers = await this.voucherApi.list(id, {
        periodCode: this.state.periodCode || undefined,
        statusFilter: this.state.statusFilter || undefined,
      });
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }
}
