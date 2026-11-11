/** Shared helpers for ledger pages. */

export function defaultPeriod(accountSetStore) {
  return accountSetStore.currentAccountSet()?.start_period || "";
}

export function accountSetId(accountSetStore) {
  return accountSetStore.state.currentId;
}

export function formatMoney(v) {
  return Number(v || 0).toFixed(2);
}

export function buildLedgerQuery(filters, extra = {}) {
  const q = { period_code: filters.periodCode, ...extra };
  if (filters.accountCode) q.account_code = filters.accountCode;
  if (filters.dateFrom) q.date_from = filters.dateFrom;
  if (filters.dateTo) q.date_to = filters.dateTo;
  if (filters.dimensionValue) q.dimension_value = filters.dimensionValue;
  if (filters.dimension) q.dimension = filters.dimension;
  return q;
}
