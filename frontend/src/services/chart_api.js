/** Chart of accounts REST API (Task 32). */

export function createChartApi(rpc) {
  return {
    getTree(accountSetId) {
      return rpc.request(`/account-sets/${accountSetId}/accounts`, { method: "GET" });
    },
    createAccount(accountSetId, body) {
      return rpc.request(`/account-sets/${accountSetId}/accounts`, { method: "POST", body });
    },
    deleteAccount(accountSetId, code) {
      return rpc.request(`/account-sets/${accountSetId}/accounts/${encodeURIComponent(code)}`, {
        method: "DELETE",
      });
    },
    updateAuxDimensions(accountSetId, code, dimensions) {
      return rpc.request(
        `/account-sets/${accountSetId}/accounts/${encodeURIComponent(code)}/aux-dimensions`,
        { method: "PATCH", body: { dimensions } }
      );
    },
  };
}
