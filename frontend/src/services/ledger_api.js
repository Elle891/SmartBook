/** Ledger REST API (Task 33). */

function qs(params) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function createLedgerApi(rpc) {
  return {
    general(accountSetId, params) {
      return rpc.request(`/account-sets/${accountSetId}/ledger/general${qs(params)}`);
    },
    subsidiary(accountSetId, params) {
      return rpc.request(`/account-sets/${accountSetId}/ledger/subsidiary${qs(params)}`);
    },
    cashJournal(accountSetId, params) {
      return rpc.request(`/account-sets/${accountSetId}/ledger/cash-journal${qs(params)}`);
    },
    bankJournal(accountSetId, params) {
      return rpc.request(`/account-sets/${accountSetId}/ledger/bank-journal${qs(params)}`);
    },
    accountSummary(accountSetId, params) {
      return rpc.request(`/account-sets/${accountSetId}/ledger/account-summary${qs(params)}`);
    },
    exportLedger(accountSetId, params, filename) {
      return rpc.download(
        `/account-sets/${accountSetId}/ledger/export${qs(params)}`,
        filename
      );
    },
  };
}
