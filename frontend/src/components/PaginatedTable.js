import { Component, useState, xml } from "@odoo/owl";

export class PaginatedTable extends Component {
  static template = xml`
    <div class="sb-table-wrap">
      <table class="sb-table">
        <thead>
          <tr>
            <th t-foreach="props.columns" t-as="col" t-key="col.key">
              <t t-esc="col.label"/>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr t-foreach="pageRows" t-as="row" t-key="row_index">
            <td t-foreach="props.columns" t-as="col" t-key="col.key">
              <t t-esc="formatCell(row, col)"/>
            </td>
          </tr>
          <tr t-if="!pageRows.length">
            <td t-att-colspan="props.columns.length" class="sb-table__empty">No records</td>
          </tr>
        </tbody>
      </table>
      <div class="sb-pagination">
        <button type="button" class="sb-btn sb-btn--ghost" t-att-disabled="page &lt;= 1" t-on-click="prevPage">Prev</button>
        <span>Page <t t-esc="page"/> / <t t-esc="totalPages"/></span>
        <button type="button" class="sb-btn sb-btn--ghost" t-att-disabled="page >= totalPages" t-on-click="nextPage">Next</button>
      </div>
    </div>
  `;

  static props = {
    columns: { type: Array },
    rows: { type: Array },
    pageSize: { type: Number, optional: true },
  };

  setup() {
    this.pageState = useState({ page: 1 });
  }

  get page() {
    return this.pageState.page;
  }

  get totalPages() {
    const size = this.props.pageSize || 10;
    return Math.max(1, Math.ceil((this.props.rows?.length || 0) / size));
  }

  get pageRows() {
    const size = this.props.pageSize || 10;
    const start = (this.page - 1) * size;
    return (this.props.rows || []).slice(start, start + size);
  }

  formatCell(row, col) {
    if (col.format) return col.format(row);
    return row[col.key] ?? "";
  }

  prevPage() {
    if (this.pageState.page > 1) this.pageState.page -= 1;
  }

  nextPage() {
    if (this.pageState.page < this.totalPages) this.pageState.page += 1;
  }
}
