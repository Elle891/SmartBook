/** Reports REST API (Task 33). */

export function createReportsApi(rpc) {
  const base = (accountSetId) => `/account-sets/${accountSetId}`;

  return {
    balanceSheet(accountSetId, filters) {
      return rpc.request(`${base(accountSetId)}/reports/balance-sheet`, {
        method: "POST",
        body: filters,
      });
    },
    incomeStatement(accountSetId, filters) {
      return rpc.request(`${base(accountSetId)}/reports/income-statement`, {
        method: "POST",
        body: filters,
      });
    },
    cashFlow(accountSetId, filters) {
      return rpc.request(`${base(accountSetId)}/reports/cash-flow`, {
        method: "POST",
        body: filters,
      });
    },
    accountSummary(accountSetId, filters) {
      return rpc.request(`${base(accountSetId)}/reports/account-summary`, {
        method: "POST",
        body: filters,
      });
    },
    exportReport(accountSetId, reportId, format = "pdf") {
      return rpc.download(
        `${base(accountSetId)}/reports/${reportId}/export?format=${format}`,
        `report.${format === "csv" ? "csv" : "pdf"}`
      );
    },
    listDataSources(accountSetId) {
      return rpc.request(`${base(accountSetId)}/report-data-sources`);
    },
    createDataSource(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/report-data-sources`, {
        method: "POST",
        body,
      });
    },
    testDataSource(accountSetId, sourceId) {
      return rpc.request(
        `${base(accountSetId)}/report-data-sources/${sourceId}/test`,
        { method: "POST" }
      );
    },
    listTemplates(accountSetId, roleId) {
      const q = roleId ? `?role_id=${encodeURIComponent(roleId)}` : "";
      return rpc.request(`${base(accountSetId)}/report-templates${q}`);
    },
    createTemplate(accountSetId, body) {
      return rpc.request(`${base(accountSetId)}/report-templates`, {
        method: "POST",
        body,
      });
    },
    publishTemplate(accountSetId, templateId, roleIds) {
      return rpc.request(`${base(accountSetId)}/report-templates/${templateId}/publish`, {
        method: "POST",
        body: { role_ids: roleIds },
      });
    },
    runTemplate(accountSetId, templateId, filters) {
      return rpc.request(`${base(accountSetId)}/report-templates/${templateId}/run`, {
        method: "POST",
        body: filters,
      });
    },
    disclosureNotes(accountSetId, filters) {
      return rpc.request(`${base(accountSetId)}/reports/disclosure-notes`, {
        method: "POST",
        body: filters,
      });
    },
  };
}
