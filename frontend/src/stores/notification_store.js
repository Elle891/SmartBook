/** Toast / notification store. */

import { reactive } from "@odoo/owl";

let nextId = 1;

export function createNotificationStore() {
  const state = reactive({
    items: [],
    confirm: null,
  });

  function notify(message, { type = "info", duration = 5000 } = {}) {
    const id = nextId++;
    state.items.push({ id, message, type });
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }

  function dismiss(id) {
    const idx = state.items.findIndex((n) => n.id === id);
    if (idx >= 0) state.items.splice(idx, 1);
  }

  function askConfirm({ title, message, confirmLabel = "Confirm", cancelLabel = "Cancel" }) {
    return new Promise((resolve) => {
      state.confirm = {
        title,
        message,
        confirmLabel,
        cancelLabel,
        resolve,
      };
    });
  }

  function resolveConfirm(confirmed) {
    if (state.confirm) {
      state.confirm.resolve(confirmed);
      state.confirm = null;
    }
  }

  return { state, notify, dismiss, askConfirm, resolveConfirm };
}
