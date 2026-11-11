import { Component, xml } from "@odoo/owl";

export class LoadingSpinner extends Component {
  static template = xml`
    <div class="sb-spinner" role="status" aria-live="polite">
      <div class="sb-spinner__ring"/>
      <span class="sb-spinner__label"><t t-esc="props.label or 'Loading...'"/></span>
    </div>
  `;
  static props = {
    label: { type: String, optional: true },
  };
}
