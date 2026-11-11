import { Component, xml } from "@odoo/owl";
import { ConfirmDialog } from "./ConfirmDialog";
import { ErrorBanner } from "./ErrorBanner";
import { LoadingSpinner } from "./LoadingSpinner";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { useStore } from "../services/registry";

export class AppShell extends Component {
  static components = { Sidebar, TopBar, LoadingSpinner, ErrorBanner, ConfirmDialog };
  static template = xml`
    <div class="sb-shell">
      <Sidebar/>
      <div class="sb-shell__main">
        <TopBar title="props.title"/>
        <ErrorBanner t-if="props.error" message="props.error" onDismiss.bind="clearError"/>
        <main class="sb-shell__content">
          <LoadingSpinner t-if="props.loading" label="'Loading workspace...'"/>
          <t t-else="" t-slot="default"/>
        </main>
      </div>
      <div class="sb-toasts">
        <div t-foreach="notificationStore.state.items" t-as="toast" t-key="toast.id"
             t-att-class="'sb-toast sb-toast--' + toast.type">
          <t t-esc="toast.message"/>
          <button type="button" class="sb-toast__close" t-on-click="() => this.dismissToast(toast.id)">×</button>
        </div>
      </div>
      <ConfirmDialog/>
    </div>
  `;

  static props = {
    title: { type: String, optional: true },
    loading: { type: Boolean, optional: true },
    error: { type: String, optional: true },
  };

  setup() {
    this.notificationStore = useStore("notificationStore");
  }

  clearError() {
    // Parent may re-render without error prop
  }

  dismissToast(id) {
    this.notificationStore.dismiss(id);
  }
}
