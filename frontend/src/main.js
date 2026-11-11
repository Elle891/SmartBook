/**
 * SmartBook OWL application entry point (Task 31).
 */

import { mount } from "@odoo/owl";
import { Root } from "./app";
import { createRouter } from "./router";
import { makeEnv } from "./services/registry";
import { createAccountSetStore } from "./stores/account_set_store";
import { createAuthStore } from "./stores/auth_store";
import { createNotificationStore } from "./stores/notification_store";

async function start() {
  const authStore = createAuthStore();
  const notificationStore = createNotificationStore();
  const accountSetStore = createAccountSetStore(authStore);
  const router = createRouter();

  const env = makeEnv({
    authStore,
    notificationStore,
    accountSetStore,
  });
  env.router = router;

  // OWL 2: mount(ComponentClass, target, config) OR new App(...).mount(target)
  await mount(Root, document.getElementById("app"), { env });
}

start().catch((err) => {
  console.error("Failed to start SmartBook app:", err);
  const root = document.getElementById("app");
  if (root) {
    root.innerHTML = `<pre style="color:red;padding:1rem;">${err.message}</pre>`;
  }
});
