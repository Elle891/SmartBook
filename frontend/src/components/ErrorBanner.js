import { Component, xml } from "@odoo/owl";

export class ErrorBanner extends Component {
  static template = xml`
    <div t-if="props.message" class="sb-banner sb-banner--error" role="alert">
      <strong>Error</strong>
      <span><t t-esc="props.message"/></span>
      <button type="button" class="sb-banner__close" t-on-click="onDismiss">×</button>
    </div>
  `;
  static props = {
    message: { type: String, optional: true },
    onDismiss: { type: Function, optional: true },
  };

  onDismiss() {
    if (this.props.onDismiss) this.props.onDismiss();
  }
}
