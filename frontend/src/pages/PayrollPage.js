import { Component, onWillStart, useState, xml } from "@odoo/owl";
import { AppShell } from "../components/AppShell";
import { createPayrollApi } from "../services/module_apis";
import { useService, useStore } from "../services/registry";
import { formatApiError } from "../utils/errors";
import { accountSetId, defaultPeriod, formatMoney } from "../utils/ledger_page";

export class PayrollPage extends Component {
  static components = { AppShell };
  static template = xml`
    <AppShell title="'Payroll'" loading="state.loading" error="state.error">
      <section class="sb-page">
        <nav class="sb-subnav">
          <button type="button" t-att-class="{ 'is-active': state.tab === 'employees' }" t-on-click="() => state.tab = 'employees'">Employees</button>
          <button type="button" t-att-class="{ 'is-active': state.tab === 'run' }" t-on-click="() => state.tab = 'run'">Accrue &amp; Payslips</button>
        </nav>

        <t t-if="state.tab === 'employees'">
          <form class="sb-form sb-form--inline" t-on-submit.prevent="addEmployee">
            <input class="sb-input" placeholder="Name" t-att-value="state.emp.name" t-on-input="(ev) => state.emp.name = ev.target.value"/>
            <input class="sb-input" placeholder="Department" t-att-value="state.emp.department" t-on-input="(ev) => state.emp.department = ev.target.value"/>
            <input class="sb-input" placeholder="Position" t-att-value="state.emp.position" t-on-input="(ev) => state.emp.position = ev.target.value"/>
            <input type="number" class="sb-input" placeholder="Base salary" t-att-value="state.emp.base_salary" t-on-input="(ev) => state.emp.base_salary = ev.target.value"/>
            <input class="sb-input" placeholder="Mobile" t-att-value="state.emp.mobile" t-on-input="(ev) => state.emp.mobile = ev.target.value"/>
            <button type="submit" class="sb-btn sb-btn--primary">Register</button>
          </form>
          <table class="sb-table">
            <thead><tr><th>Name</th><th>Dept</th><th>Position</th><th>Salary</th></tr></thead>
            <tbody>
              <tr t-foreach="state.employees" t-as="e" t-key="e.id">
                <td><t t-esc="e.name"/></td>
                <td><t t-esc="e.department or '—'"/></td>
                <td><t t-esc="e.position or '—'"/></td>
                <td><t t-esc="formatMoney(e.base_salary)"/></td>
              </tr>
            </tbody>
          </table>
        </t>

        <t t-else="">
          <div class="sb-filters">
            <input class="sb-input" placeholder="Period YYYYMM" t-att-value="state.periodCode" t-on-input="(ev) => state.periodCode = ev.target.value"/>
            <button type="button" class="sb-btn sb-btn--primary" t-on-click="accrue">Accrue Payroll</button>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="loadPayslips">Load Payslips</button>
            <select class="sb-input" t-on-change="(ev) => state.channel = ev.target.value">
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="wechat">WeChat</option>
            </select>
            <button type="button" class="sb-btn sb-btn--ghost" t-on-click="distribute">Distribute</button>
          </div>
          <p t-if="state.accrueResult" class="sb-muted"><t t-esc="state.accrueResult.message"/></p>
          <table class="sb-table">
            <thead><tr><th>Employee</th><th>Gross</th><th>Net</th><th>Dept</th></tr></thead>
            <tbody>
              <tr t-foreach="state.payslips" t-as="p" t-key="p.employee_id">
                <td><t t-esc="p.employee_name"/></td>
                <td><t t-esc="formatMoney(p.gross_salary)"/></td>
                <td><t t-esc="formatMoney(p.net_salary)"/></td>
                <td><t t-esc="p.department or '—'"/></td>
              </tr>
            </tbody>
          </table>
        </t>
      </section>
    </AppShell>
  `;

  setup() {
    this.rpc = useService("rpc");
    this.accountSetStore = useStore("accountSetStore");
    this.notificationStore = useStore("notificationStore");
    this.api = createPayrollApi(this.rpc);
    this.state = useState({
      tab: "employees",
      loading: false,
      error: "",
      employees: [],
      payslips: [],
      periodCode: "",
      channel: "email",
      accrueResult: null,
      emp: { name: "", department: "", position: "", base_salary: "", mobile: "" },
    });
  }

  formatMoney(v) {
    return formatMoney(v);
  }

  async onWillStart() {
    this.state.periodCode = defaultPeriod(this.accountSetStore);
    await this.loadEmployees();
  }

  async loadEmployees() {
    const id = accountSetId(this.accountSetStore);
    if (!id) return;
    this.state.loading = true;
    try {
      this.state.employees = await this.api.listEmployees(id);
    } catch (err) {
      this.state.error = formatApiError(err);
    } finally {
      this.state.loading = false;
    }
  }

  async addEmployee() {
    const id = accountSetId(this.accountSetStore);
    try {
      await this.api.createEmployee(id, {
        name: this.state.emp.name.trim(),
        department: this.state.emp.department || null,
        position: this.state.emp.position || null,
        base_salary: Number(this.state.emp.base_salary) || 0,
        mobile: this.state.emp.mobile || null,
      });
      this.state.emp = { name: "", department: "", position: "", base_salary: "", mobile: "" };
      await this.loadEmployees();
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async accrue() {
    const id = accountSetId(this.accountSetStore);
    try {
      this.state.accrueResult = await this.api.accrue(id, this.state.periodCode);
      this.notificationStore.notify("Payroll accrued.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async loadPayslips() {
    const id = accountSetId(this.accountSetStore);
    try {
      this.state.payslips = await this.api.listPayslips(id, this.state.periodCode);
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }

  async distribute() {
    const id = accountSetId(this.accountSetStore);
    try {
      const r = await this.api.distribute(id, this.state.periodCode, this.state.channel);
      this.notificationStore.notify(r.message || "Distribution complete.", { type: "success" });
    } catch (err) {
      this.state.error = formatApiError(err);
    }
  }
}
