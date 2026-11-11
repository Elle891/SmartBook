/** Auth store — JWT, user, role, inactivity timer (Req 8.4). */

import { reactive } from "@odoo/owl";
import { decodeJwtPayload } from "../utils/jwt";

const STORAGE_KEY = "smartbook.auth";
const INACTIVITY_MS = 15 * 60 * 1000;

export function createAuthStore() {
  const saved = loadSaved();
  const state = reactive({
    accessToken: saved.accessToken || null,
    refreshToken: saved.refreshToken || null,
    user: saved.user || null,
    role: saved.role || null,
    accountSetId: saved.accountSetId || null,
    lastActivityAt: Date.now(),
    inactivityTimer: null,
  });

  function persist() {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        role: state.role,
        accountSetId: state.accountSetId,
      })
    );
  }

  function resetInactivityTimer(onTimeout) {
    state.lastActivityAt = Date.now();
    if (state.inactivityTimer) {
      clearTimeout(state.inactivityTimer);
    }
    if (!state.accessToken) return;
    state.inactivityTimer = setTimeout(() => {
      logout();
      if (onTimeout) onTimeout();
    }, INACTIVITY_MS);
  }

  function login({ accessToken, refreshToken, user, role, accountSetId }) {
    state.accessToken = accessToken;
    state.refreshToken = refreshToken || null;
    state.user = user;
    state.role = role || null;
    state.accountSetId = accountSetId || null;
    persist();
  }

  function loginFromToken(accessToken, userMeta = {}) {
    const payload = decodeJwtPayload(accessToken);
    // Identical token → no reactive churn (avoids remount/load loops).
    if (state.accessToken === accessToken) {
      return;
    }
    login({
      accessToken,
      user: {
        id: payload.sub,
        display_name:
          userMeta.display_name || userMeta.email || userMeta.mobile || "User",
        email: userMeta.email || null,
        mobile: userMeta.mobile || null,
      },
      role: payload.role || userMeta.role || null,
      accountSetId: payload.account_set_id || null,
    });
  }

  function logout() {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    state.role = null;
    state.accountSetId = null;
    localStorage.removeItem(STORAGE_KEY);
    if (state.inactivityTimer) {
      clearTimeout(state.inactivityTimer);
      state.inactivityTimer = null;
    }
  }

  function touchActivity(onTimeout) {
    resetInactivityTimer(onTimeout);
  }

  function isAuthenticated() {
    return Boolean(state.accessToken);
  }

  return {
    state,
    login,
    loginFromToken,
    logout,
    touchActivity,
    resetInactivityTimer,
    isAuthenticated,
    get accessToken() {
      return state.accessToken;
    },
  };
}

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}
