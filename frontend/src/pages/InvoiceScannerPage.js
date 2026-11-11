import { Component, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createInvoiceApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class InvoiceScannerPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Invoice Scanner'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <div class="sb-panel">
          <h2>Upload Invoice (JPEG / PDF)</h2>
          <input type="file" accept=".jpg,.jpeg,.pdf,image/jpeg,application/pdf" t-on-change="onFile"/>
        </div>

        <t t-if="state.job">
          <div class="sb-panel">
            <p>Status: <span t-att-class="'sb-status sb-status--' + state.job.status"><t t-esc="state.job.status"/></span></p>
            <p t-if="state.job.verification_result">
              Verification: <t t-esc="state.job.verification_result.verification_status"/>
            </p>
            <form class="sb-form" t-if="state.fields">
              <div t-foreach="fieldKeys" t-as="key" t-key="key" class="sb-field">
                <label><t t-esc="key"/></label>
                <input class="sb-input" t-att-value="state.fields[key]" t-on-input="(ev) => state.fields[key] = ev.target.value"/>
              </div>
              <div class="sb-auth__actions">
                <button type="button" class="sb-btn sb-btn--ghost" t-on-click="pollJob">Refresh</button>
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="verify">Verify</button>
                <button type="button" class="sb-btn sb-btn--primary" t-on-click="generateVoucher">Generate Voucher</button>
              </div>
            </form>
          </div>
        </t>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createInvoiceApi(this.rpc);
    this.state = useState({
      loading: false,
      error: "",
      job: null,
      jobId: null,
      fields: null,
      periodCode: "",
    });
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
  }

  get fieldKeys() {
    return this.state.fields ? Object.keys(this.state.fields) : [];
  }

  applyExtracted(job) {
    const d = job.extracted_data || {};
    this.state.fields = {
      invoice_number: d.invoice_number || "",
      invoice_date: d.invoice_date || "",
      seller_name: d.seller_name || "",
      buyer_name: d.buyer_name || "",
      amount_excl_tax: d.amount_excl_tax ?? "",
      tax_amount: d.tax_amount ?? "",
    };
  }

  async onFile(ev) {
    const file = ev.target.files?.[0];
    if (!file) return;
    const id = accountSetId(this.accountSetStore);
    this.state.loading = true;
    try {
      const job = await this.api.upload(id, file);
      this.state.job = job;
      this.state.jobId = job.id;
      this.applyExtracted(job);
      if (job.status === "Pending" || job.status === "Processing") {
        setTimeout(() => this.pollJob(), 2000);
      }
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
      ev.target.value = "";
    }
  }

  async pollJob() {
    const id = accountSetId(this.accountSetStore);
    if (!this.state.jobId) return;
    this.state.job = await this.api.getJob(id, this.state.jobId);
    if (this.state.job.extracted_data) this.applyExtracted(this.state.job);
    if (this.state.job.status === "Processing") setTimeout(() => this.pollJob(), 2000);
  }

  async verify() {
    const id = accountSetId(this.accountSetStore);
    try {
      const r = await this.api.verify(id, this.state.jobId, this.state.fields);
      this.notificationStore.notify(r.verification_status, { type: r.verified ? "success" : "warning" });
      await this.pollJob();
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async generateVoucher() {
    const id = accountSetId(this.accountSetStore);
    try {
      const r = await this.api.generateVoucher(id, this.state.jobId, {
        confirmed_data: this.state.fields,
        period_code: this.state.periodCode,
      });
      this.notificationStore.notify(`Voucher ${r.voucher_id} created.`, { type: "success" });
      await this.pollJob();
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
