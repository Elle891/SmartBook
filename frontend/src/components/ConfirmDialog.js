import { Component, xml } from "@odoo/owl";
import { useStore } from "../services/registry";

export class ConfirmDialog extends Component {
  static template = xml`
    <div t-if="notification.state.confirm" class="sb-modal-backdrop">
      <div class="sb-modal" role="dialog" aria-modal="true">
        <h3 class="sb-modal__title"><t t-esc="notification.state.confirm.title"/></h3>
        <p class="sb-modal__body"><t t-esc="notification.state.confirm.message"/></p>
        <div class="sb-modal__actions">
          <button type="button" class="sb-btn sb-btn--ghost" t-on-click="() => this.onAnswer(false)">
            <t t-esc="notification.state.confirm.cancelLabel"/>
          </button>
          <button type="button" class="sb-btn sb-btn--primary" t-on-click="() => this.onAnswer(true)">
            <t t-esc="notification.state.confirm.confirmLabel"/>
          </button>
        </div>
      </div>
    </div>
  `;

  setup() {
    this.notification = useStore("notificationStore");
  }

  onAnswer(value) {
    this.notification.resolveConfirm(value);
  }
}
