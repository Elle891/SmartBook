/** Voucher REST API (Task 32). */

export function createVoucherApi(rpc) {
  return {
    list(accountSetId, { periodCode, statusFilter } = {}) {
      const params = new URLSearchParams();
      if (periodCode) params.set("period_code", periodCode);
      if (statusFilter) params.set("status_filter", statusFilter);
      const qs = params.toString();
      const path = `/account-sets/${accountSetId}/vouchers${qs ? `?${qs}` : ""}`;
      return rpc.request(path, { method: "GET" });
    },
    get(accountSetId, voucherId) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}`, { method: "GET" });
    },
    create(accountSetId, body) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers`, { method: "POST", body });
    },
    update(accountSetId, voucherId, body) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}`, {
        method: "PUT",
        body,
      });
    },
    submit(accountSetId, voucherId) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}/submit`, {
        method: "POST",
      });
    },
    approve(accountSetId, voucherId) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}/approve`, {
        method: "POST",
      });
    },
    reject(accountSetId, voucherId, reason) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}/reject`, {
        method: "POST",
        body: { reason },
      });
    },
    remove(accountSetId, voucherId) {
      return rpc.request(`/account-sets/${accountSetId}/vouchers/${voucherId}`, {
        method: "DELETE",
      });
    },
  };
}
