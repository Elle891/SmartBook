import { Component, xml } from "@odoo/owl";
import { useStore } from "../services/registry";

export class TopBar extends Component {
  static template = xml`
    <header class="sb-topbar">
      <div class="sb-topbar__title"><t t-esc="props.title or 'SmartBook'"/></div>
      <div class="sb-topbar__actions">
        <span class="sb-topbar__user" t-if="authStore.state.user">
          <t t-esc="authStore.state.user.display_name or authStore.state.user.email or 'User'"/>
          · <t t-esc="authStore.state.role or 'Viewer'"/>
        </span>
        <button type="button" class="sb-btn sb-btn--ghost" t-on-click="logout">Logout</button>
      </div>
    </header>
  `;

  static props = {
    title: { type: String, optional: true },
  };

  setup() {
    this.authStore = useStore("authStore");
  }

  logout() {
    this.authStore.logout();
    window.location.hash = "#/login";
  }
}
