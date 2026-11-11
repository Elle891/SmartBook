function qs(params) {
  const sp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

function base(accountSetId) {
  return `/account-sets/${accountSetId}`;
}

export function createCashierApi(rpc) {
  return {
    registerAccount(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/cashier/accounts`, { method: "POST", body });
    },
    receipt(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/cashier/receipts`, { method: "POST", body });
    },
    payment(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/cashier/payments`, { method: "POST", body });
    },
    transfer(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/cashier/transfers`, { method: "POST", body });
    },
    reconcile(accountSetId, accountCode, periodCode, physicalCount) {
      return rpc.request(
        `${base(accountSetId)}/cashier/accounts/${encodeURIComponent(accountCode)}/reconcile${qs({ period_code: periodCode })}`,
        { method: "POST", body: { physical_count: physicalCount } }
      );
    },
    fxBalance(accountSetId, accountCode, periodCode) {
      return rpc.request(
        `${base(accountSetId)}/cashier/accounts/${encodeURIComponent(accountCode)}/fx-balance${qs({ period_code: periodCode })}`
      );
    },
  };
}

export function createPayrollApi(rpc) {
  return {
    listEmployees(accountSetId, department) {
      return rpc.request(`${base(accountSetId)}/payroll/employees${qs({ department })}`);
    },
    createEmployee(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/payroll/employees`, { method: "POST", body });
    },
    accrue(accountSetId, periodCode) {
      return rpc.request(`${base(accountSetId)}/payroll/accrue`, {
        method: "POST",
        body: { period_code: periodCode },
      });
    },
    listPayslips(accountSetId, periodCode) {
      return rpc.request(`${base(accountSetId)}/payroll/payslips/${periodCode}`);
    },
    distribute(accountSetId, periodCode, channel) {
      return rpc.request(`${base(accountSetId)}/payroll/payslips/${periodCode}/distribute`, {
        method: "POST",
        body: { channel },
      });
    },
  };
}

export function createAssetsApi(rpc) {
  return {
    register(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/assets`, { method: "POST", body });
    },
    registerTable(accountSetId, includeDisposed = false) {
      return rpc.request(
        `${base(accountSetId)}/assets/register${qs({ include_disposed: includeDisposed })}`
      );
    },
    previewDepreciation(accountSetId, periodCode) {
      return rpc.request(`${base(accountSetId)}/assets/depreciation/calculate`, {
        method: "POST",
        body: { period_code: periodCode },
      });
    },
    confirmDepreciation(accountSetId, periodCode) {
      return rpc.request(`${base(accountSetId)}/assets/depreciation/confirm`, {
        method: "POST",
        body: { period_code: periodCode },
      });
    },
    dispose(accountSetId, assetId, body) {
      return rpc.request(`${base(accountSetId)}/assets/${assetId}/dispose`, {
        method: "POST",
        body,
      });
    },
  };
}

export function createSmartImportApi(rpc) {
  return {
    upload(accountSetId, file) {
      return rpc.upload(`${base(accountSetId)}/smart-import/upload`, file);
    },
    summary(accountSetId, sessionId) {
      return rpc.request(`${base(accountSetId)}/smart-import/${sessionId}/summary`);
    },
    confirm(accountSetId, sessionId, mappings) {
      return rpc.request(`${base(accountSetId)}/smart-import/${sessionId}/confirm`, {
        method: "POST",
        body: { mappings },
      });
    },
  };
}

export function createInvoiceApi(rpc) {
  return {
    upload(accountSetId, file) {
      return rpc.upload(`${base(accountSetId)}/invoices/upload`, file);
    },
    getJob(accountSetId, jobId) {
      return rpc.request(`${base(accountSetId)}/invoices/${jobId}`);
    },
    verify(accountSetId, jobId, confirmedData) {
      return rpc.request(`${base(accountSetId)}/invoices/${jobId}/verify`, {
        method: "POST",
        body: { confirmed_data: confirmedData },
      });
    },
    generateVoucher(accountSetId, jobId, body) {
      return rpc.request(`${base(accountSetId)}/invoices/${jobId}/generate-voucher`, {
        method: "POST",
        body,
      });
    },
  };
}

export function createTaxApi(rpc) {
  return {
    generate(accountSetId, periodCode, taxType) {
      return rpc.request(`${base(accountSetId)}/tax/filings/generate`, {
        method: "POST",
        body: { period_code: periodCode, tax_type: taxType },
      });
    },
    getFiling(accountSetId, filingId) {
      return rpc.request(`${base(accountSetId)}/tax/filings/${filingId}`);
    },
    adjustLine(accountSetId, filingId, lineId, value) {
      return rpc.request(`${base(accountSetId)}/tax/filings/${filingId}/line-items`, {
        method: "PATCH",
        body: { line_id: lineId, value },
      });
    },
    submit(accountSetId, filingId) {
      return rpc.request(`${base(accountSetId)}/tax/filings/${filingId}/submit`, { method: "POST" });
    },
    history(accountSetId, taxType) {
      return rpc.request(`${base(accountSetId)}/tax/filings/history${qs({ tax_type: taxType })}`);
    },
  };
}

export function createBankApi(rpc) {
  return {
    listConnections(accountSetId) {
      return rpc.request(`${base(accountSetId)}/bank/connections`);
    },
    connect(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/bank/connections`, { method: "POST", body });
    },
    verify(accountSetId, connectionId) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/verify`, {
        method: "POST",
      });
    },
    sync(accountSetId, connectionId) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/sync`, {
        method: "POST",
      });
    },
    balance(accountSetId, connectionId) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/balance`);
    },
    listRouting(accountSetId, connectionId) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/routing`);
    },
    availableRouting(accountSetId, connectionId) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/routing/available`);
    },
    configureRouting(accountSetId, connectionId, body) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/routing`, {
        method: "POST",
        body,
      });
    },
    setDefaultRouting(accountSetId, connectionId, routingMethod) {
      return rpc.request(`${base(accountSetId)}/bank/connections/${connectionId}/routing/default`, {
        method: "POST",
        body: { routing_method: routingMethod },
      });
    },
  };
}

export function createPaymentApi(rpc) {
  return {
    createDomestic(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/payments/domestic`, { method: "POST", body });
    },
    createInternational(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/payments/international`, { method: "POST", body });
    },
    routingOptions(accountSetId, params) {
      return rpc.request(`${base(accountSetId)}/payments/routing-options${qs(params)}`);
    },
    settlementCutoff(accountSetId, routingMethod, settlementMethod) {
      return rpc.request(
        `${base(accountSetId)}/payments/settlement-cutoff${qs({
          routing_method: routingMethod,
          settlement_method: settlementMethod,
        })}`
      );
    },
    fieldConfig(accountSetId, routingMethod, settlementMethod) {
      return rpc.request(
        `${base(accountSetId)}/payment-field-config${qs({
          routing_method: routingMethod,
          settlement_method: settlementMethod,
        })}`
      );
    },
    saveFieldConfig(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/payment-field-config`, { method: "POST", body });
    },
    exchangeRate(accountSetId, sourceCurrency, targetCurrency) {
      return rpc.request(
        `${base(accountSetId)}/payments/exchange-rate${qs({
          source_currency: sourceCurrency,
          target_currency: targetCurrency,
        })}`
      );
    },
    defaultTransactionType(accountSetId) {
      return rpc.request(`${base(accountSetId)}/payment-transaction-types/default`);
    },
    queue(accountSetId) {
      return rpc.request(`${base(accountSetId)}/payments/queue`);
    },
    authorised(accountSetId) {
      return rpc.request(`${base(accountSetId)}/payments/authorised`);
    },
    status(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/status`);
    },
    history(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/history`);
    },
    instruct(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/instruct`, { method: "POST" });
    },
    check(accountSetId, paymentId, body) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/check`, { method: "POST", body });
    },
    authorise(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/authorise`, { method: "POST" });
    },
    payNow(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/pay-now`, { method: "POST" });
    },
    removeFromQueue(accountSetId, paymentId) {
      return rpc.request(`${base(accountSetId)}/payments/${paymentId}/remove-from-queue`, { method: "POST" });
    },
    batchInstruct(accountSetId, paymentIds) {
      return rpc.request(`${base(accountSetId)}/payments/batch-instruct`, {
        method: "POST",
        body: { payment_ids: paymentIds },
      });
    },
    batchPay(accountSetId, paymentIds) {
      return rpc.request(`${base(accountSetId)}/payments/batch-pay`, {
        method: "POST",
        body: { payment_ids: paymentIds },
      });
    },
  };
}

export function createPaymentTransactionTypeApi(rpc) {
  return {
    list(accountSetId, includeInactive = true) {
      return rpc.request(
        `${base(accountSetId)}/payment-transaction-types${qs({ include_inactive: includeInactive })}`
      );
    },
    defaultType(accountSetId) {
      return rpc.request(`${base(accountSetId)}/payment-transaction-types/default`);
    },
    create(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/payment-transaction-types`, { method: "POST", body });
    },
    update(accountSetId, typeId, body) {
      return rpc.request(`${base(accountSetId)}/payment-transaction-types/${typeId}`, {
        method: "PATCH",
        body,
      });
    },
    deactivate(accountSetId, typeId) {
      return rpc.request(`${base(accountSetId)}/payment-transaction-types/${typeId}`, {
        method: "PATCH",
        body: { is_active: false },
      });
    },
  };
}

export function createIfrsApi(rpc) {
  return {
    fairValueAdjustment(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/ifrs/fair-value-adjustments`, { method: "POST", body });
    },
    registerRouAsset(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/ifrs/right-of-use-assets`, { method: "POST", body });
    },
    recognizeRevenue(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/ifrs/revenue-recognition`, { method: "POST", body });
    },
    impairmentTest(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/ifrs/impairment-tests`, { method: "POST", body });
    },
  };
}

export function createForecastApi(rpc) {
  return {
    get(accountSetId, horizonMonths) {
      return rpc.request(`${base(accountSetId)}/forecast${qs({ horizon_months: horizonMonths })}`);
    },
    metrics(accountSetId) {
      return rpc.request(`${base(accountSetId)}/forecast/metrics`);
    },
    comparison(accountSetId, periodCode) {
      return rpc.request(`${base(accountSetId)}/forecast/comparison${qs({ period: periodCode })}`);
    },
    export(accountSetId, horizonMonths, format) {
      return rpc.downloadPost(`${base(accountSetId)}/forecast/export`, {
        horizon_months: horizonMonths,
        export_format: format,
      });
    },
  };
}

export function createNlpApi(rpc) {
  return {
    chat(body) {
      return rpc.request("/nlp/chat", { method: "POST", body });
    },
    clearSession(sessionId) {
      return rpc.request(`/nlp/sessions/${sessionId}/context`, { method: "DELETE" });
    },
  };
}

export function createReconciliationApi(rpc) {
  return {
    initiate(accountSetId, connectionId, periodCode) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions`, {
        method: "POST",
        body: { connection_id: connectionId, period_code: periodCode },
      });
    },
    autoMatch(accountSetId, sessionId, fuzzyThreshold) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions/${sessionId}/auto-match`, {
        method: "POST",
        body: fuzzyThreshold != null ? { fuzzy_threshold: fuzzyThreshold } : {},
      });
    },
    manualMatch(accountSetId, sessionId, bankTransactionId, voucherEntryId) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions/${sessionId}/manual-match`, {
        method: "POST",
        body: { bank_transaction_id: bankTransactionId, voucher_entry_id: voucherEntryId },
      });
    },
    report(accountSetId, sessionId) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions/${sessionId}/report`);
    },
    difference(accountSetId, sessionId) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions/${sessionId}/difference`);
    },
    complete(accountSetId, sessionId) {
      return rpc.request(`${base(accountSetId)}/reconciliation/sessions/${sessionId}/complete`, {
        method: "POST",
      });
    },
  };
}
