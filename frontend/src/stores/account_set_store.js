/** Account Set store — current enterprise context (Req 7.3). */

import { reactive } from "@odoo/owl";
import { createAccountSetApi } from "../services/account_set_api";

export function createAccountSetStore(authStore) {
  const state = reactive({
    accountSets: [],
    currentId: authStore.state.accountSetId || null,
    loading: false,
  });

  function accountSetApi(rpc) {
    return createAccountSetApi(rpc);
  }

  async function loadAccountSets(rpc) {
    state.loading = true;
    try {
      const data = await accountSetApi(rpc).list();
      state.accountSets = Array.isArray(data) ? data : data.items || [];

      const jwtAccountSetId = authStore.state.accountSetId || null;
      const knownIds = new Set(state.accountSets.map((a) => a.id));

      // JWT already bound to a known account set — just sync local state, do not
      // call /switch again (that renews the token and remounts HomePage forever).
      if (jwtAccountSetId && knownIds.has(jwtAccountSetId)) {
        state.currentId = jwtAccountSetId;
        return;
      }

      const preferred =
        (state.currentId && knownIds.has(state.currentId) && state.currentId) ||
        (state.accountSets[0] && state.accountSets[0].id) ||
        null;

      if (preferred) {
        await switchAccountSet(preferred, rpc);
      } else {
        state.currentId = null;
      }
    } catch {
      state.accountSets = [];
    } finally {
      state.loading = false;
    }
  }

  async function switchAccountSet(id, rpc) {
    if (!id || !rpc) {
      state.currentId = id || null;
      authStore.state.accountSetId = id || null;
      return;
    }
    // Already active in both store and JWT — skip (prevents remount loops).
    if (state.currentId === id && authStore.state.accountSetId === id) {
      return;
    }
    try {
      const data = await accountSetApi(rpc).switch(id);
      state.currentId = id;
      if (data.access_token) {
        authStore.loginFromToken(data.access_token, {
          display_name: authStore.state.user?.display_name,
          email: authStore.state.user?.email,
          mobile: authStore.state.user?.mobile,
        });
      } else {
        authStore.state.accountSetId = id;
        authStore.state.role = data.role || authStore.state.role;
      }
    } catch {
      state.currentId = id;
      authStore.state.accountSetId = id;
    }
  }

  function currentAccountSet() {
    return state.accountSets.find((a) => a.id === state.currentId) || null;
  }

  function requireAccountSetId() {
    const id = state.currentId;
    if (!id) throw new Error("Select an account set first.");
    return id;
  }

  return {
    state,
    loadAccountSets,
    switchAccountSet,
    currentAccountSet,
    requireAccountSetId,
    accountSetApi,
  };
}
