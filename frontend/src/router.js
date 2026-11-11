/** Hash-based client-side router. */

import { reactive } from "@odoo/owl";

const routes = [
  { path: "/", name: "home" },
  { path: "/login", name: "login" },
  { path: "/register", name: "register" },
  { path: "/password-reset", name: "password-reset" },
  { path: "/account-sets/create", name: "account-set-create" },
  { path: "/account-sets", name: "account-sets" },
  { path: "/chart-of-accounts", name: "chart-of-accounts" },
  { path: "/vouchers/create", name: "voucher-create" },
  { path: "/vouchers", name: "vouchers" },
  { path: "/ledger/general", name: "ledger-general" },
  { path: "/ledger/subsidiary", name: "ledger-subsidiary" },
  { path: "/ledger/cash-journal", name: "ledger-cash" },
  { path: "/ledger/bank-journal", name: "ledger-bank" },
  { path: "/ledger/account-summary", name: "ledger-summary" },
  { path: "/period-end", name: "period-end" },
  { path: "/reports", name: "reports" },
  { path: "/cashier", name: "cashier" },
  { path: "/payroll", name: "payroll" },
  { path: "/fixed-assets", name: "fixed-assets" },
  { path: "/smart-import", name: "smart-import" },
  { path: "/invoice-scanner", name: "invoice-scanner" },
  { path: "/tax-filing", name: "tax-filing" },
  { path: "/bank", name: "bank" },
  { path: "/reconciliation", name: "reconciliation" },
  { path: "/payments/domestic", name: "payments-domestic" },
  { path: "/payments/international", name: "payments-international" },
  { path: "/payments/queue", name: "payments-queue" },
  { path: "/payments/transaction-types", name: "payment-transaction-types" },
  { path: "/payments/field-config", name: "payment-field-config" },
  { path: "/ifrs", name: "ifrs" },
  { path: "/forecast", name: "forecast" },
  { path: "/assistant", name: "assistant" },
];

export function createRouter() {
  const state = reactive({
    path: getHashPath(),
    name: matchRoute(getHashPath()).name,
  });

  function navigate(path) {
    if (!path.startsWith("#")) {
      window.location.hash = path.startsWith("/") ? path : `/${path}`;
    } else {
      window.location.hash = path.slice(1);
    }
  }

  function sync() {
    state.path = getHashPath();
    state.name = matchRoute(state.path).name;
  }

  window.addEventListener("hashchange", sync);

  return { state, navigate, sync, routes };
}

function getHashPath() {
  const hash = window.location.hash.replace(/^#/, "");
  return hash || "/";
}

function matchRoute(path) {
  const found = routes.find((r) => r.path === path);
  if (found) return found;

  if (/^\/account-sets\/[^/]+\/permissions$/.test(path)) {
    return { path, name: "account-set-permissions" };
  }
  if (/^\/account-sets\/[^/]+\/opening-balances$/.test(path)) {
    return { path, name: "opening-balances" };
  }
  if (/^\/vouchers\/[^/]+$/.test(path)) {
    return { path, name: "voucher-detail" };
  }

  if (/^\/payments\/[^/]+$/.test(path)) {
    const segment = path.split("/")[2];
    if (!["domestic", "international", "queue", "authorised", "transaction-types", "field-config"].includes(segment)) {
      return { path, name: "payment-detail" };
    }
  }

  return { path, name: "home" };
}

export { routes };
