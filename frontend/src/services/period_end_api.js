/** Period-end REST API (Task 33). */

export function createPeriodEndApi(rpc) {
  return {
    carryCostForward(accountSetId, periodCode) {
      return rpc.request(
        `/account-sets/${accountSetId}/periods/${periodCode}/carry-cost-forward`,
        { method: "POST" }
      );
    },
    carryProfitLoss(accountSetId, periodCode) {
      return rpc.request(
        `/account-sets/${accountSetId}/periods/${periodCode}/carry-profit-loss`,
        { method: "POST" }
      );
    },
    calculateDepreciation(accountSetId, periodCode) {
      return rpc.request(
        `/account-sets/${accountSetId}/periods/${periodCode}/calculate-depreciation`,
        { method: "POST" }
      );
    },
    nextOpeningBalances(accountSetId, periodCode) {
      return rpc.request(
        `/account-sets/${accountSetId}/periods/${periodCode}/next-opening-balances`
      );
    },
    closePeriod(accountSetId, periodCode) {
      return rpc.request(
        `/account-sets/${accountSetId}/periods/${periodCode}/close`,
        { method: "POST" }
      );
    },
  };
}
